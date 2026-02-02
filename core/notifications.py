"""Notification system: email, Slack, and desktop notifications with throttling."""

import json
import logging
import mimetypes
import smtplib
import subprocess
import time
from dataclasses import dataclass, field
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

CONFIG_FILE = Path("state/notification_config.json")
THROTTLE_FILE = Path("state/.notification_throttle.json")

# Minimum seconds between notifications of the same type
DEFAULT_THROTTLE_SECONDS = 300  # 5 minutes


@dataclass
class NotificationConfig:
    slack_webhook: str = ""
    email_to: str = ""
    email_from: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    desktop_enabled: bool = True
    throttle_seconds: int = DEFAULT_THROTTLE_SECONDS

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> "NotificationConfig":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save(self, path: Path = CONFIG_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: getattr(self, k) for k in self.__dataclass_fields__}
        path.write_text(json.dumps(data, indent=2))


def _check_throttle(notification_type: str, config: NotificationConfig) -> bool:
    """Check if a notification type is throttled.

    Returns True if we should send, False if throttled.
    """
    if not THROTTLE_FILE.exists():
        return True

    throttle_data = json.loads(THROTTLE_FILE.read_text())
    last_sent = throttle_data.get(notification_type, 0)
    return (time.time() - last_sent) >= config.throttle_seconds


def _update_throttle(notification_type: str) -> None:
    """Record that a notification was sent."""
    THROTTLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    throttle_data = {}
    if THROTTLE_FILE.exists():
        throttle_data = json.loads(THROTTLE_FILE.read_text())
    throttle_data[notification_type] = time.time()
    THROTTLE_FILE.write_text(json.dumps(throttle_data))


def send_slack(message: str, config: Optional[NotificationConfig] = None) -> bool:
    """Send a Slack notification via webhook.

    Args:
        message: Message text.
        config: Notification config (loaded from disk if None).

    Returns:
        True if sent successfully.
    """
    if config is None:
        config = NotificationConfig.load()

    if not config.slack_webhook:
        logger.debug("Slack webhook not configured")
        return False

    if not _check_throttle("slack", config):
        logger.debug("Slack notification throttled")
        return False

    try:
        payload = json.dumps({"text": message}).encode()
        req = Request(
            config.slack_webhook,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urlopen(req, timeout=10)
        _update_throttle("slack")
        logger.info("Slack notification sent")
        return True
    except Exception as e:
        logger.error("Failed to send Slack notification: %s", e)
        return False


def send_email(
    subject: str,
    body: str,
    config: Optional[NotificationConfig] = None,
) -> bool:
    """Send an email notification.

    Args:
        subject: Email subject.
        body: Email body text.
        config: Notification config.

    Returns:
        True if sent successfully.
    """
    if config is None:
        config = NotificationConfig.load()

    if not config.email_to or not config.smtp_user:
        logger.debug("Email not configured")
        return False

    if not _check_throttle("email", config):
        logger.debug("Email notification throttled")
        return False

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = config.email_from or config.smtp_user
        msg["To"] = config.email_to

        with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
            server.starttls()
            server.login(config.smtp_user, config.smtp_password)
            server.send_message(msg)

        _update_throttle("email")
        logger.info("Email notification sent to %s", config.email_to)
        return True
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        return False


def send_email_with_attachment(
    subject: str,
    body: str,
    attachment_path: Path,
    config: Optional[NotificationConfig] = None,
) -> bool:
    """Send an email with a file attachment.

    Args:
        subject: Email subject.
        body: Email body text.
        attachment_path: Path to the file to attach.
        config: Notification config.

    Returns:
        True if sent successfully.
    """
    if config is None:
        config = NotificationConfig.load()

    if not config.email_to or not config.smtp_user:
        logger.debug("Email not configured")
        return False

    attachment_path = Path(attachment_path)
    if not attachment_path.exists():
        logger.error("Attachment not found: %s", attachment_path)
        return False

    try:
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = config.email_from or config.smtp_user
        msg["To"] = config.email_to

        msg.attach(MIMEText(body, "plain"))

        ctype, _ = mimetypes.guess_type(str(attachment_path))
        if ctype is None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)

        with open(attachment_path, "rb") as f:
            part = MIMEBase(maintype, subtype)
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=attachment_path.name,
        )
        msg.attach(part)

        with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
            server.starttls()
            server.login(config.smtp_user, config.smtp_password)
            server.send_message(msg)

        logger.info(
            "Email with attachment sent to %s (%s)",
            config.email_to,
            attachment_path.name,
        )
        return True
    except Exception as e:
        logger.error("Failed to send email with attachment: %s", e)
        return False


def send_desktop(title: str, message: str) -> bool:
    """Send a desktop notification (Linux notify-send).

    Args:
        title: Notification title.
        message: Notification body.

    Returns:
        True if sent successfully.
    """
    config = NotificationConfig.load()
    if not config.desktop_enabled:
        return False

    if not _check_throttle("desktop", config):
        return False

    try:
        subprocess.run(
            ["notify-send", title, message],
            check=True,
            capture_output=True,
        )
        _update_throttle("desktop")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.debug("Desktop notifications not available")
        return False


def notify(
    message: str,
    *,
    title: str = "ricet",
    level: str = "info",
) -> None:
    """Send notification through all configured channels.

    Args:
        message: Notification message.
        title: Notification title.
        level: One of 'info', 'warning', 'error', 'success'.
    """
    config = NotificationConfig.load()
    prefix = {
        "info": "",
        "warning": "[WARNING] ",
        "error": "[ERROR] ",
        "success": "[OK] ",
    }.get(level, "")
    full_message = f"{prefix}{title}: {message}"

    send_desktop(title, message)
    send_slack(full_message, config)

    if level in ("error", "success"):
        send_email(f"{prefix}{title}", message, config)
