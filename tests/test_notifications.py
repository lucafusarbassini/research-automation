"""Tests for the notification system (email, Slack, desktop, throttling)."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.notifications import (
    NotificationConfig,
    _check_throttle,
    _update_throttle,
    notify,
    send_desktop,
    send_email,
    send_email_with_attachment,
    send_slack,
)

# ---------------------------------------------------------------------------
# NotificationConfig
# ---------------------------------------------------------------------------


def test_config_defaults():
    cfg = NotificationConfig()
    assert cfg.smtp_host == "smtp.gmail.com"
    assert cfg.smtp_port == 587
    assert cfg.email_to == ""
    assert cfg.smtp_user == ""
    assert cfg.desktop_enabled is True
    assert cfg.throttle_seconds == 300


def test_config_load_missing_file(tmp_path):
    cfg = NotificationConfig.load(tmp_path / "nonexistent.json")
    assert cfg.email_to == ""


def test_config_save_and_load(tmp_path):
    path = tmp_path / "notif.json"
    cfg = NotificationConfig(email_to="test@example.com", smtp_user="user@mail.com")
    cfg.save(path)

    loaded = NotificationConfig.load(path)
    assert loaded.email_to == "test@example.com"
    assert loaded.smtp_user == "user@mail.com"


def test_config_load_ignores_extra_keys(tmp_path):
    path = tmp_path / "notif.json"
    path.write_text(json.dumps({"email_to": "a@b.com", "bogus_key": 42}))
    cfg = NotificationConfig.load(path)
    assert cfg.email_to == "a@b.com"


# ---------------------------------------------------------------------------
# Throttle
# ---------------------------------------------------------------------------


def test_throttle_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr("core.notifications.THROTTLE_FILE", tmp_path / "t.json")
    cfg = NotificationConfig(throttle_seconds=60)
    assert _check_throttle("email", cfg) is True


def test_throttle_recent_send(tmp_path, monkeypatch):
    tfile = tmp_path / "t.json"
    tfile.write_text(json.dumps({"email": time.time()}))
    monkeypatch.setattr("core.notifications.THROTTLE_FILE", tfile)
    cfg = NotificationConfig(throttle_seconds=60)
    assert _check_throttle("email", cfg) is False


def test_throttle_expired(tmp_path, monkeypatch):
    tfile = tmp_path / "t.json"
    tfile.write_text(json.dumps({"email": time.time() - 120}))
    monkeypatch.setattr("core.notifications.THROTTLE_FILE", tfile)
    cfg = NotificationConfig(throttle_seconds=60)
    assert _check_throttle("email", cfg) is True


def test_update_throttle(tmp_path, monkeypatch):
    tfile = tmp_path / "t.json"
    monkeypatch.setattr("core.notifications.THROTTLE_FILE", tfile)
    _update_throttle("slack")
    data = json.loads(tfile.read_text())
    assert "slack" in data
    assert abs(data["slack"] - time.time()) < 5


# ---------------------------------------------------------------------------
# send_email
# ---------------------------------------------------------------------------


def test_send_email_not_configured():
    cfg = NotificationConfig()
    assert send_email("subj", "body", cfg) is False


@patch("core.notifications.smtplib.SMTP")
@patch("core.notifications._check_throttle", return_value=True)
def test_send_email_success(mock_throttle, mock_smtp):
    server = MagicMock()
    mock_smtp.return_value.__enter__ = MagicMock(return_value=server)
    mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

    cfg = NotificationConfig(
        email_to="dest@example.com",
        smtp_user="user@example.com",
        smtp_password="pass",
    )
    result = send_email("Test Subject", "Test body", cfg)
    assert result is True
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("user@example.com", "pass")
    server.send_message.assert_called_once()


@patch(
    "core.notifications.smtplib.SMTP", side_effect=ConnectionRefusedError("no server")
)
@patch("core.notifications._check_throttle", return_value=True)
def test_send_email_connection_error(mock_throttle, mock_smtp):
    cfg = NotificationConfig(
        email_to="dest@example.com",
        smtp_user="user@example.com",
        smtp_password="pass",
    )
    assert send_email("subj", "body", cfg) is False


# ---------------------------------------------------------------------------
# send_email_with_attachment
# ---------------------------------------------------------------------------


def test_send_email_attachment_not_configured():
    cfg = NotificationConfig()
    assert send_email_with_attachment("subj", "body", Path("/fake"), cfg) is False


def test_send_email_attachment_missing_file():
    cfg = NotificationConfig(
        email_to="dest@example.com", smtp_user="u@e.com", smtp_password="p"
    )
    assert (
        send_email_with_attachment("subj", "body", Path("/nonexistent.pdf"), cfg)
        is False
    )


@patch("core.notifications.smtplib.SMTP")
def test_send_email_attachment_success(mock_smtp, tmp_path):
    server = MagicMock()
    mock_smtp.return_value.__enter__ = MagicMock(return_value=server)
    mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake pdf content")

    cfg = NotificationConfig(
        email_to="dest@example.com",
        smtp_user="user@example.com",
        smtp_password="pass",
    )
    result = send_email_with_attachment("Report", "See attached.", pdf, cfg)
    assert result is True
    server.starttls.assert_called_once()
    server.send_message.assert_called_once()

    sent_msg = server.send_message.call_args[0][0]
    payloads = sent_msg.get_payload()
    assert len(payloads) == 2  # body + attachment
    assert payloads[1].get_filename() == "report.pdf"


# ---------------------------------------------------------------------------
# send_slack
# ---------------------------------------------------------------------------


def test_send_slack_not_configured():
    cfg = NotificationConfig()
    assert send_slack("msg", cfg) is False


@patch("core.notifications.urlopen")
@patch("core.notifications._check_throttle", return_value=True)
def test_send_slack_success(mock_throttle, mock_urlopen):
    mock_urlopen.return_value = MagicMock()
    cfg = NotificationConfig(slack_webhook="https://hooks.slack.com/test")
    assert send_slack("hello", cfg) is True
    mock_urlopen.assert_called_once()


# ---------------------------------------------------------------------------
# send_desktop
# ---------------------------------------------------------------------------


@patch("core.notifications.subprocess.run", side_effect=FileNotFoundError)
def test_send_desktop_no_notifysend(mock_run):
    with patch(
        "core.notifications.NotificationConfig.load", return_value=NotificationConfig()
    ):
        with patch("core.notifications._check_throttle", return_value=True):
            assert send_desktop("title", "msg") is False


# ---------------------------------------------------------------------------
# notify (multi-channel)
# ---------------------------------------------------------------------------


@patch("core.notifications.send_email")
@patch("core.notifications.send_slack")
@patch("core.notifications.send_desktop")
def test_notify_error_sends_email(mock_desktop, mock_slack, mock_email):
    with patch(
        "core.notifications.NotificationConfig.load",
        return_value=NotificationConfig(email_to="x@y.com", smtp_user="u"),
    ):
        notify("boom", level="error")
    mock_email.assert_called_once()
    mock_slack.assert_called_once()


@patch("core.notifications.send_email")
@patch("core.notifications.send_slack")
@patch("core.notifications.send_desktop")
def test_notify_info_skips_email(mock_desktop, mock_slack, mock_email):
    with patch(
        "core.notifications.NotificationConfig.load",
        return_value=NotificationConfig(),
    ):
        notify("just info", level="info")
    mock_email.assert_not_called()
