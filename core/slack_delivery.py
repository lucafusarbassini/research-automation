"""Slack figure delivery: upload plots to a dedicated channel.

Requires a Bot Token (xoxb-) with scopes: files:write, chat:write.
Set in .env:
    SLACK_BOT_TOKEN=xoxb-...
    SLACK_PLOTS_CHANNEL=claude_plots   # channel name or ID

Usage:
    from core.slack_delivery import send_plot
    send_plot("/path/to/figure.png", title="Loss curve epoch 10")

Falls back to text-only notification if file upload fails.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_SLACK_API = "https://slack.com/api"


def _get_credentials() -> tuple[str | None, str]:
    """Return (bot_token, channel). Bot token may be None if not configured."""
    # Load .env from project root if not already loaded
    try:
        from dotenv import load_dotenv

        for candidate in [Path.cwd() / ".env", Path(__file__).parent.parent / ".env"]:
            if candidate.exists():
                load_dotenv(candidate, override=False)
                break
    except ImportError:
        pass

    token = os.getenv("SLACK_BOT_TOKEN", "").strip()
    channel = os.getenv("SLACK_PLOTS_CHANNEL", "claude_plots").strip()
    channel = channel.lstrip("#")
    return token or None, channel


def send_plot(
    image_path: str | Path,
    *,
    title: str = "",
    caption: str = "",
    channel: str | None = None,
    token: str | None = None,
) -> bool:
    """Upload an image file to the Slack plots channel.

    Args:
        image_path: Path to a PNG/SVG/PDF figure.
        title: Short title shown as filename in Slack.
        caption: Text message posted alongside the file.
        channel: Override channel (defaults to SLACK_PLOTS_CHANNEL env var).
        token: Override bot token (defaults to SLACK_BOT_TOKEN env var).

    Returns:
        True if upload succeeded, False otherwise.
    """
    import urllib.request

    _token, _channel = _get_credentials()
    token = token or _token
    channel = channel or _channel

    if not token:
        logger.warning(
            "SLACK_BOT_TOKEN not set. Cannot upload file. "
            "Set xoxb- Bot Token in .env to enable figure delivery."
        )
        return False

    if token.startswith("xapp-"):
        logger.warning(
            "SLACK_BOT_TOKEN is an App-level token (xapp-), not a Bot Token (xoxb-). "
            "File uploads require xoxb- with files:write scope."
        )
        return False

    image_path = Path(image_path)
    if not image_path.exists():
        logger.error("Image not found: %s", image_path)
        return False

    file_bytes = image_path.read_bytes()
    filename = title or image_path.name
    content_type = _content_type(image_path.suffix)

    # Use files.getUploadURLExternal → files.completeUploadExternal (Slack v2 API)
    try:
        # Step 1: get upload URL
        import json
        import urllib.parse

        params = urllib.parse.urlencode({
            "filename": filename,
            "length": len(file_bytes),
        })
        req = urllib.request.Request(
            f"{_SLACK_API}/files.getUploadURLExternal?{params}",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        if not resp.get("ok"):
            logger.error("files.getUploadURLExternal failed: %s", resp.get("error"))
            return _fallback_upload(token, channel, image_path, filename, caption, file_bytes)

        upload_url = resp["upload_url"]
        file_id = resp["file_id"]

        # Step 2: POST bytes to upload URL.
        # CRITICAL: NO Authorization header — the URL is pre-authenticated.
        # Adding auth causes Slack to redirect to slack.com homepage (upload fails silently).
        import requests as _req
        r_upload = _req.post(
            upload_url,
            data=file_bytes,
            headers={"Content-Type": "application/octet-stream"},
            allow_redirects=False,
            timeout=60,
        )
        if r_upload.status_code != 200:
            raise RuntimeError(f"Upload to upload_url failed: HTTP {r_upload.status_code} {r_upload.text[:200]}")

        # Step 3: complete upload and share to channel
        # Resolve channel name → ID if needed
        channel_id = channel if channel.startswith("C") else _resolve_channel_id(token, channel)
        body = json.dumps({
            "files": [{"id": file_id, "title": title or image_path.stem}],
            "channel_id": channel_id,
            "initial_comment": caption or "",
        }).encode()
        complete_req = urllib.request.Request(
            f"{_SLACK_API}/files.completeUploadExternal",
            data=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        result = json.loads(urllib.request.urlopen(complete_req, timeout=15).read())
        if result.get("ok"):
            logger.info("Uploaded %s to #%s", filename, channel)
            return True
        logger.error("files.completeUploadExternal failed: %s", result.get("error"))
        return False

    except Exception as exc:
        logger.error("Slack upload error: %s", exc)
        return False


_channel_id_cache: dict[str, str] = {}


def _resolve_channel_id(token: str, channel_name: str) -> str:
    """Resolve a channel name to its Slack ID.

    Uses chat.postMessage (which accepts names) to discover the ID —
    avoids needing the channels:read scope. Result is cached for the
    process lifetime so the discovery only happens once.
    Returns the name unchanged if all lookups fail.
    """
    import json
    import urllib.parse
    import urllib.request

    channel_name = channel_name.lstrip("#")

    if channel_name in _channel_id_cache:
        return _channel_id_cache[channel_name]

    # Try conversations.list (requires channels:read scope — may not be granted)
    try:
        req = urllib.request.Request(
            f"{_SLACK_API}/conversations.list?limit=999&types=public_channel,private_channel",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        if resp.get("ok"):
            for ch in resp.get("channels", []):
                if ch.get("name") == channel_name:
                    _channel_id_cache[channel_name] = ch["id"]
                    return ch["id"]
    except Exception:
        pass

    # Fallback: post a message (accepts names) and read the channel ID from response
    try:
        data = urllib.parse.urlencode({"channel": channel_name, "text": "\u200b"}).encode()
        req = urllib.request.Request(
            f"{_SLACK_API}/chat.postMessage",
            data=data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        if resp.get("ok"):
            ch_id = resp.get("channel", "")
            ts = resp.get("ts", "")
            # Best-effort delete of the probe message
            if ch_id and ts:
                try:
                    del_data = urllib.parse.urlencode({"channel": ch_id, "ts": ts}).encode()
                    del_req = urllib.request.Request(
                        f"{_SLACK_API}/chat.delete",
                        data=del_data,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/x-www-form-urlencoded",
                        },
                    )
                    urllib.request.urlopen(del_req, timeout=5)
                except Exception:
                    pass  # delete failure is non-fatal
            if ch_id:
                _channel_id_cache[channel_name] = ch_id
                return ch_id
    except Exception:
        pass

    return channel_name


def _fallback_upload(token, channel, image_path, filename, caption, file_bytes) -> bool:
    """Fall back to deprecated files.upload API."""
    import json
    import urllib.request

    boundary = "ricet_boundary_xyz"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="channels"\r\n\r\n{channel}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="filename"\r\n\r\n{filename}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="initial_comment"\r\n\r\n{caption}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {_content_type(image_path.suffix)}\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{_SLACK_API}/files.upload",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        result = json.loads(urllib.request.urlopen(req, timeout=60).read())
        return result.get("ok", False)
    except Exception as exc:
        logger.error("Fallback upload error: %s", exc)
        return False


def send_text(message: str, *, channel: str | None = None, token: str | None = None) -> bool:
    """Send a plain text message to the plots channel via bot token."""
    import json
    import urllib.parse
    import urllib.request

    _token, _channel = _get_credentials()
    token = token or _token
    channel = channel or _channel

    if not token or token.startswith("xapp-"):
        return False

    data = urllib.parse.urlencode({"channel": channel, "text": message}).encode()
    req = urllib.request.Request(
        f"{_SLACK_API}/chat.postMessage",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        result = json.loads(urllib.request.urlopen(req, timeout=10).read())
        return result.get("ok", False)
    except Exception:
        return False


def _content_type(suffix: str) -> str:
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".pdf": "application/pdf",
    }.get(suffix.lower(), "application/octet-stream")
