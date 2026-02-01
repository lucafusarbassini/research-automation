"""Tests for browser integration module (TDD — written before implementation)."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch, call

import pytest

from core.browser import BrowserSession


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def session():
    """Return a BrowserSession with Puppeteer disabled so it uses fallback."""
    with patch("core.browser.BrowserSession._detect_puppeteer", return_value=False):
        return BrowserSession()


@pytest.fixture
def puppeteer_session():
    """Return a BrowserSession that believes Puppeteer MCP is available."""
    with patch("core.browser.BrowserSession._detect_puppeteer", return_value=True):
        return BrowserSession()


# ---------------------------------------------------------------------------
# 1. is_available — fallback path (curl/wget present)
# ---------------------------------------------------------------------------

def test_is_available_true_when_curl_exists(session):
    with patch("shutil.which", return_value="/usr/bin/curl"):
        assert session.is_available() is True


def test_is_available_false_when_nothing_found(session):
    with patch("shutil.which", return_value=None):
        assert session.is_available() is False


# ---------------------------------------------------------------------------
# 2. is_available — Puppeteer path
# ---------------------------------------------------------------------------

def test_is_available_true_when_puppeteer_detected(puppeteer_session):
    assert puppeteer_session.is_available() is True


# ---------------------------------------------------------------------------
# 3. screenshot — fallback uses subprocess
# ---------------------------------------------------------------------------

def test_screenshot_fallback_runs_subprocess(session, tmp_path):
    out = tmp_path / "shot.png"
    completed = subprocess.CompletedProcess(args=[], returncode=0)
    with patch("shutil.which", return_value="/usr/bin/chromium-browser"), \
         patch("subprocess.run", return_value=completed) as mock_run:
        result = session.screenshot("https://example.com", out)
        assert result == out
        mock_run.assert_called_once()
        args = mock_run.call_args
        # The command should reference the URL
        cmd_str = " ".join(str(a) for a in args[0][0]) if isinstance(args[0][0], list) else str(args[0][0])
        assert "example.com" in cmd_str


# ---------------------------------------------------------------------------
# 4. screenshot — Puppeteer path
# ---------------------------------------------------------------------------

def test_screenshot_puppeteer_delegates(puppeteer_session, tmp_path):
    out = tmp_path / "shot.png"
    with patch.object(puppeteer_session, "_puppeteer_call", return_value={"success": True}) as mock_pup:
        result = puppeteer_session.screenshot("https://example.com", out)
        assert result == out
        mock_pup.assert_called_once()
        call_args = mock_pup.call_args
        assert call_args[0][0] == "screenshot"


# ---------------------------------------------------------------------------
# 5. extract_text — fallback fetches via HTTP
# ---------------------------------------------------------------------------

def test_extract_text_fallback(session):
    html = "<html><body><p>Hello world</p></body></html>"
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=html)
    with patch("shutil.which", return_value="/usr/bin/curl"), \
         patch("subprocess.run", return_value=completed):
        text = session.extract_text("https://example.com")
        assert "Hello world" in text


# ---------------------------------------------------------------------------
# 6. extract_text — Puppeteer path
# ---------------------------------------------------------------------------

def test_extract_text_puppeteer(puppeteer_session):
    with patch.object(
        puppeteer_session,
        "_puppeteer_call",
        return_value={"text": "Extracted via Puppeteer"},
    ) as mock_pup:
        text = puppeteer_session.extract_text("https://example.com")
        assert "Extracted via Puppeteer" in text
        mock_pup.assert_called_once()


# ---------------------------------------------------------------------------
# 7. fill_form
# ---------------------------------------------------------------------------

def test_fill_form_puppeteer(puppeteer_session):
    fields = {"username": "alice", "password": "secret"}
    with patch.object(
        puppeteer_session,
        "_puppeteer_call",
        return_value={"submitted": True},
    ) as mock_pup:
        ok = puppeteer_session.fill_form("https://example.com/login", fields)
        assert ok is True
        mock_pup.assert_called_once()
        assert mock_pup.call_args[0][0] == "fill_form"


def test_fill_form_fallback_returns_false(session):
    """Fallback HTTP cannot fill forms — should return False."""
    result = session.fill_form("https://example.com/login", {"user": "x"})
    assert result is False


# ---------------------------------------------------------------------------
# 8. wait_for_element
# ---------------------------------------------------------------------------

def test_wait_for_element_puppeteer(puppeteer_session):
    with patch.object(
        puppeteer_session,
        "_puppeteer_call",
        return_value={"found": True},
    ):
        assert puppeteer_session.wait_for_element("https://example.com", "#main") is True


def test_wait_for_element_fallback_returns_false(session):
    """Fallback cannot inspect the DOM — should return False."""
    assert session.wait_for_element("https://example.com", "#main") is False


# ---------------------------------------------------------------------------
# 9. generate_pdf
# ---------------------------------------------------------------------------

def test_generate_pdf_fallback(session, tmp_path):
    out = tmp_path / "page.pdf"
    completed = subprocess.CompletedProcess(args=[], returncode=0)
    with patch("shutil.which", return_value="/usr/bin/chromium-browser"), \
         patch("subprocess.run", return_value=completed):
        result = session.generate_pdf("https://example.com", out)
        assert result == out


def test_generate_pdf_puppeteer(puppeteer_session, tmp_path):
    out = tmp_path / "page.pdf"
    with patch.object(
        puppeteer_session,
        "_puppeteer_call",
        return_value={"success": True},
    ):
        result = puppeteer_session.generate_pdf("https://example.com", out)
        assert result == out


# ---------------------------------------------------------------------------
# 10. _puppeteer_call plumbing
# ---------------------------------------------------------------------------

def test_puppeteer_call_invokes_subprocess(puppeteer_session):
    payload = json.dumps({"result": "ok"})
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=payload)
    with patch("subprocess.run", return_value=completed) as mock_run:
        result = puppeteer_session._puppeteer_call("navigate", url="https://x.com")
        assert result == {"result": "ok"}
        mock_run.assert_called_once()


def test_puppeteer_call_handles_failure(puppeteer_session):
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd")):
        result = puppeteer_session._puppeteer_call("navigate", url="https://x.com")
        assert result == {}
