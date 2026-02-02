"""Mobile phone control module for research project management.

Provides a lightweight HTTP API so users can control research projects
from their phone — submit tasks, check status, review progress, or issue
voice commands via a simple text transcription endpoint.

Only standard-library dependencies are used (http.server, threading, etc.).
"""

import json
import logging
import secrets
import threading
import uuid
from datetime import datetime, timezone
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


class MobileAuth:
    """Simple token-based authentication for mobile API access."""

    def __init__(self) -> None:
        self._tokens: set[str] = set()

    def generate_token(self) -> str:
        """Create a new random bearer token (URL-safe, 48 chars)."""
        token = secrets.token_urlsafe(36)  # >=48 chars
        self._tokens.add(token)
        return token

    def validate(self, token: str) -> bool:
        """Return *True* if *token* is currently valid."""
        return token in self._tokens

    def revoke(self, token: str) -> None:
        """Revoke *token* so it can no longer authenticate."""
        self._tokens.discard(token)


# ---------------------------------------------------------------------------
# Response formatting
# ---------------------------------------------------------------------------

_MOBILE_MAX_STR = 280  # comfortable for phone screens


def format_for_mobile(data: dict) -> dict:
    """Format a response dict for compact mobile display.

    * Long string values are truncated to 280 characters.
    * A ``_ts`` key with the current ISO-8601 timestamp is injected.
    """
    out: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str) and len(value) > _MOBILE_MAX_STR:
            out[key] = value[: _MOBILE_MAX_STR - 3] + "..."
        else:
            out[key] = value
    out["_ts"] = datetime.now(timezone.utc).isoformat()
    return out


# ---------------------------------------------------------------------------
# Mobile server — route-based dispatch (no framework dependency)
# ---------------------------------------------------------------------------

# Type alias for route handlers
RouteHandler = Callable[[Optional[dict]], dict]


class MobileServer:
    """Lightweight HTTP API server for mobile control of research projects.

    Routes are stored as ``(method, path) -> handler`` mappings.  The
    ``dispatch`` method resolves a request to its handler without requiring
    a running socket — handy for testing.
    """

    def __init__(self, auth: Optional[MobileAuth] = None) -> None:
        self._auth = auth
        self._routes: dict[tuple[str, str], RouteHandler] = {}
        self._tasks: list[dict] = []
        self._register_default_routes()

    # -- route helpers ------------------------------------------------------

    def _register_default_routes(self) -> None:
        self._routes[("POST", "/task")] = self._handle_post_task
        self._routes[("GET", "/status")] = self._handle_get_status
        self._routes[("GET", "/sessions")] = self._handle_get_sessions
        self._routes[("POST", "/voice")] = self._handle_post_voice
        self._routes[("GET", "/progress")] = self._handle_get_progress

    @property
    def routes(self) -> dict[tuple[str, str], RouteHandler]:
        return dict(self._routes)

    # -- dispatch -----------------------------------------------------------

    def dispatch(
        self,
        method: str,
        path: str,
        body: Optional[dict] = None,
        *,
        headers: Optional[dict] = None,
    ) -> dict:
        """Resolve *method* + *path* to a handler and return the response dict.

        If authentication is configured, the ``Authorization`` header must
        contain a valid ``Bearer <token>``.
        """
        # Auth check
        if self._auth is not None:
            token = _extract_bearer(headers)
            if not self._auth.validate(token or ""):
                return format_for_mobile({"ok": False, "error": "unauthorized"})

        handler = self._routes.get((method.upper(), path))
        if handler is None:
            return format_for_mobile({"ok": False, "error": "not_found"})

        return format_for_mobile(handler(body))

    # -- built-in handlers --------------------------------------------------

    def _handle_post_task(self, body: Optional[dict]) -> dict:
        prompt = (body or {}).get("prompt", "")
        task_id = uuid.uuid4().hex[:12]
        task = {"task_id": task_id, "prompt": prompt, "status": "queued"}
        self._tasks.append(task)
        logger.info("Task queued: %s — %s", task_id, prompt[:80])
        return {"ok": True, "task_id": task_id, "status": "queued"}

    def _handle_get_status(self, body: Optional[dict]) -> dict:
        return {
            "ok": True,
            "status": "running",
            "tasks_queued": sum(1 for t in self._tasks if t["status"] == "queued"),
            "tasks_total": len(self._tasks),
        }

    def _handle_get_sessions(self, body: Optional[dict]) -> dict:
        """Return known sessions from the sessions directory."""
        from pathlib import Path

        sessions_dir = Path("state") / "sessions"
        sessions: list[dict] = []
        if sessions_dir.is_dir():
            for f in sorted(sessions_dir.glob("*.json")):
                try:
                    data = json.loads(f.read_text())
                    sessions.append(
                        {
                            "name": data.get("name", f.stem),
                            "status": data.get("status", "unknown"),
                            "created": data.get("created", ""),
                        }
                    )
                except Exception:
                    sessions.append({"name": f.stem, "status": "unknown"})
        return {"ok": True, "sessions": sessions}

    def _handle_post_voice(self, body: Optional[dict]) -> dict:
        text = (body or {}).get("text", "")
        # Voice input is treated as a task submission
        task_id = uuid.uuid4().hex[:12]
        task = {
            "task_id": task_id,
            "prompt": text,
            "status": "queued",
            "source": "voice",
        }
        self._tasks.append(task)
        logger.info("Voice task queued: %s — %s", task_id, text[:80])
        return {"ok": True, "task_id": task_id, "source": "voice"}

    def _handle_get_progress(self, body: Optional[dict]) -> dict:
        recent = self._tasks[-10:] if self._tasks else []
        return {"ok": True, "entries": recent}


# ---------------------------------------------------------------------------
# URL generation
# ---------------------------------------------------------------------------


def generate_mobile_url(
    host: str = "0.0.0.0",
    port: int = 8777,
    auth: Optional[MobileAuth] = None,
) -> str:
    """Generate a URL for mobile access, embedding a fresh auth token.

    If no *auth* instance is provided, a temporary ``MobileAuth`` is created
    and a single-use token is generated.
    """
    if auth is None:
        auth = MobileAuth()
    token = auth.generate_token()
    return f"http://{host}:{port}?token={token}"


# ---------------------------------------------------------------------------
# HTTP glue — actual server (uses http.server from stdlib)
# ---------------------------------------------------------------------------

_server_instance: Optional[HTTPServer] = None
_server_thread: Optional[threading.Thread] = None
_mobile_server: Optional[MobileServer] = None


def _make_handler(mobile: MobileServer):
    """Factory that returns a request-handler class bound to *mobile*."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            headers = {k: v for k, v in self.headers.items()}
            resp = mobile.dispatch("GET", self.path, headers=headers)
            self._send_json(resp)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw)
            headers = {k: v for k, v in self.headers.items()}
            resp = mobile.dispatch("POST", self.path, body, headers=headers)
            self._send_json(resp)

        def _send_json(self, data: dict) -> None:
            payload = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt, *args):  # silence default stderr logging
            logger.debug(fmt, *args)

    return _Handler


def start_server(
    host: str = "0.0.0.0",
    port: int = 8777,
    auth: Optional[MobileAuth] = None,
) -> threading.Thread:
    """Start the mobile API server in a daemon thread.

    Returns the ``threading.Thread`` so callers can join or check liveness.
    """
    global _server_instance, _server_thread, _mobile_server

    _mobile_server = MobileServer(auth=auth)
    handler_class = _make_handler(_mobile_server)
    _server_instance = HTTPServer((host, port), handler_class)

    _server_thread = threading.Thread(
        target=_server_instance.serve_forever,
        daemon=True,
        name="mobile-api",
    )
    _server_thread.start()
    logger.info("Mobile API server started on %s:%s", host, port)
    return _server_thread


def stop_server() -> None:
    """Shut down the running mobile API server, if any."""
    global _server_instance, _server_thread, _mobile_server

    if _server_instance is not None:
        _server_instance.shutdown()
        logger.info("Mobile API server stopped.")
    _server_instance = None
    _server_thread = None
    _mobile_server = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_bearer(headers: Optional[dict]) -> Optional[str]:
    """Pull the token out of an ``Authorization: Bearer <tok>`` header."""
    if not headers:
        return None
    auth_value = headers.get("Authorization", "")
    if auth_value.startswith("Bearer "):
        return auth_value[7:]
    return None


# ---------------------------------------------------------------------------
# CLI adapter — ``from core.mobile import mobile_server``
# ---------------------------------------------------------------------------


class _MobileManager:
    """Thin CLI-facing adapter wrapping the module-level start/stop functions."""

    def start(self, host: str = "0.0.0.0", port: int = 8777) -> None:
        start_server(host=host, port=port)

    def stop(self) -> None:
        stop_server()

    def get_url(self, host: str = "0.0.0.0", port: int = 8777) -> str:
        return generate_mobile_url(host=host, port=port)


mobile_server = _MobileManager()
