"""Mobile phone control module for research project management.

Provides a lightweight HTTPS API so users can control research projects
from their phone — submit tasks, check status, review progress, or issue
voice commands via a simple text transcription endpoint.

Security model:
- Self-signed TLS via ``openssl`` CLI (no pip deps)
- SHA-256 fingerprint verification (SSH trust model)
- Bearer tokens — only SHA-256 hashes stored on disk
- Rate limiting per client IP

Only standard-library dependencies are used (http.server, ssl, hashlib, etc.).
"""

import hashlib
import json
import logging
import os
import secrets
import ssl
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_RICET_DIR = Path.home() / ".ricet"
_CERTS_DIR = _RICET_DIR / "certs"
_TOKENS_FILE = _RICET_DIR / "mobile_tokens.json"
_PROJECTS_FILE = _RICET_DIR / "projects.json"

# ---------------------------------------------------------------------------
# TLS Manager
# ---------------------------------------------------------------------------


class TLSManager:
    """Manage self-signed TLS certificates via the ``openssl`` CLI."""

    def __init__(self, certs_dir: Optional[Path] = None) -> None:
        self.certs_dir = certs_dir or _CERTS_DIR
        self.cert_path = self.certs_dir / "server.crt"
        self.key_path = self.certs_dir / "server.key"

    def ensure_certs(self) -> None:
        """Generate a self-signed cert+key if not already present."""
        if self.cert_path.exists() and self.key_path.exists():
            return
        self.generate_certs()

    def generate_certs(self) -> None:
        """Generate a new self-signed certificate and private key."""
        self.certs_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-keyout",
                str(self.key_path),
                "-out",
                str(self.cert_path),
                "-days",
                "365",
                "-nodes",
                "-subj",
                "/CN=ricet-mobile",
            ],
            check=True,
            capture_output=True,
        )
        # Restrict key file permissions
        os.chmod(self.key_path, 0o600)
        logger.info("TLS certs generated in %s", self.certs_dir)

    def fingerprint(self) -> str:
        """Return the SHA-256 fingerprint of the certificate."""
        if not self.cert_path.exists():
            return ""
        result = subprocess.run(
            [
                "openssl",
                "x509",
                "-fingerprint",
                "-sha256",
                "-noout",
                "-in",
                str(self.cert_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        # Output: "sha256 Fingerprint=AA:BB:CC:..." or "SHA256 Fingerprint=..."
        line = result.stdout.strip()
        if "=" in line:
            return line.split("=", 1)[1]
        return line

    def create_ssl_context(self) -> ssl.SSLContext:
        """Return an ``ssl.SSLContext`` wrapping the cert and key."""
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(str(self.cert_path), str(self.key_path))
        return ctx


# ---------------------------------------------------------------------------
# Authentication — persistent, hash-based
# ---------------------------------------------------------------------------

# Rate-limit constants
_MAX_FAILURES = 10
_LOCKOUT_SECONDS = 900  # 15 minutes


class MobileAuth:
    """Token-based authentication with persistent hash storage and rate limiting."""

    def __init__(self, tokens_file: Optional[Path] = None) -> None:
        self._tokens_file = tokens_file or _TOKENS_FILE
        self._tokens: dict[str, dict] = {}  # hash -> {label, created}
        self._failures: dict[str, list[float]] = {}  # ip -> [timestamps]
        self._load()

    def _load(self) -> None:
        if self._tokens_file.exists():
            try:
                data = json.loads(self._tokens_file.read_text())
                self._tokens = data.get("tokens", {})
            except (json.JSONDecodeError, OSError):
                self._tokens = {}

    def _save(self) -> None:
        self._tokens_file.parent.mkdir(parents=True, exist_ok=True)
        self._tokens_file.write_text(
            json.dumps({"tokens": self._tokens}, indent=2) + "\n"
        )

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def generate_token(self, label: str = "") -> str:
        """Create a new random bearer token. Returns plaintext (shown once)."""
        token = secrets.token_urlsafe(36)
        h = self._hash(token)
        self._tokens[h] = {
            "label": label,
            "created": datetime.now(timezone.utc).isoformat(),
            "hash_prefix": h[:12],
        }
        self._save()
        return token

    def validate(self, token: str, client_ip: str = "") -> bool:
        """Return *True* if *token* is valid and IP is not locked out."""
        if client_ip and self._is_locked_out(client_ip):
            return False
        h = self._hash(token)
        if h in self._tokens:
            # Clear failures on success
            if client_ip:
                self._failures.pop(client_ip, None)
            return True
        # Record failure
        if client_ip:
            self._record_failure(client_ip)
        return False

    def revoke(self, hash_prefix: str) -> bool:
        """Revoke a token by its hash prefix. Returns True if found."""
        to_remove = [h for h in self._tokens if h.startswith(hash_prefix)]
        if not to_remove:
            return False
        for h in to_remove:
            del self._tokens[h]
        self._save()
        return True

    def list_tokens(self) -> list[dict]:
        """Return a list of token metadata (no secrets)."""
        return [
            {
                "hash_prefix": info.get("hash_prefix", h[:12]),
                "label": info.get("label", ""),
                "created": info.get("created", ""),
            }
            for h, info in self._tokens.items()
        ]

    def _record_failure(self, ip: str) -> None:
        now = time.monotonic()
        if ip not in self._failures:
            self._failures[ip] = []
        self._failures[ip].append(now)
        # Keep only recent failures
        cutoff = now - _LOCKOUT_SECONDS
        self._failures[ip] = [t for t in self._failures[ip] if t > cutoff]

    def _is_locked_out(self, ip: str) -> bool:
        if ip not in self._failures:
            return False
        now = time.monotonic()
        cutoff = now - _LOCKOUT_SECONDS
        recent = [t for t in self._failures[ip] if t > cutoff]
        self._failures[ip] = recent
        return len(recent) >= _MAX_FAILURES


# ---------------------------------------------------------------------------
# Project Registry
# ---------------------------------------------------------------------------


class ProjectRegistry:
    """Read project list from ``~/.ricet/projects.json``."""

    def __init__(self, projects_file: Optional[Path] = None) -> None:
        self._file = projects_file or _PROJECTS_FILE

    def list_projects(self) -> list[dict]:
        if not self._file.exists():
            return []
        try:
            data = json.loads(self._file.read_text())
            return data.get("projects", [])
        except (json.JSONDecodeError, OSError):
            return []

    def get_project(self, name: str) -> Optional[dict]:
        for p in self.list_projects():
            if p.get("name") == name:
                return p
        return None

    def get_project_status(self, name: str) -> dict:
        """Read a project's PROGRESS.md and session info."""
        project = self.get_project(name)
        if not project:
            return {"ok": False, "error": "project_not_found"}
        project_path = Path(project.get("path", "."))
        progress = ""
        progress_file = project_path / "state" / "PROGRESS.md"
        if progress_file.exists():
            try:
                progress = progress_file.read_text()[:2000]
            except OSError:
                pass
        sessions: list[dict] = []
        sessions_dir = project_path / "state" / "sessions"
        if sessions_dir.is_dir():
            for f in sorted(sessions_dir.glob("*.json"))[-5:]:
                try:
                    sdata = json.loads(f.read_text())
                    sessions.append(
                        {
                            "name": sdata.get("name", f.stem),
                            "status": sdata.get("status", "unknown"),
                        }
                    )
                except Exception:
                    sessions.append({"name": f.stem, "status": "unknown"})
        return {
            "ok": True,
            "name": name,
            "progress": progress,
            "sessions": sessions,
        }


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

    def __init__(
        self,
        auth: Optional[MobileAuth] = None,
        registry: Optional[ProjectRegistry] = None,
        tls_manager: Optional[TLSManager] = None,
    ) -> None:
        self._auth = auth
        self._registry = registry or ProjectRegistry()
        self._tls = tls_manager
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
        self._routes[("GET", "/projects")] = self._handle_get_projects
        self._routes[("GET", "/project/status")] = self._handle_get_project_status
        self._routes[("POST", "/project/task")] = self._handle_post_project_task
        self._routes[("GET", "/connect-info")] = self._handle_get_connect_info

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
        query_params: Optional[dict] = None,
        client_ip: str = "",
    ) -> dict:
        """Resolve *method* + *path* to a handler and return the response dict.

        If authentication is configured, the ``Authorization`` header must
        contain a valid ``Bearer <token>``.
        """
        # Auth check (skip for PWA asset routes)
        if self._auth is not None and path not in (
            "/",
            "/manifest.json",
            "/sw.js",
            "/icon.svg",
        ):
            token = _extract_bearer(headers)
            if not self._auth.validate(token or "", client_ip=client_ip):
                return format_for_mobile({"ok": False, "error": "unauthorized"})

        # Parse query params from path if not provided
        parsed = urlparse(path)
        clean_path = parsed.path
        if query_params is None:
            query_params = {
                k: v[0] if len(v) == 1 else v for k, v in parse_qs(parsed.query).items()
            }

        handler = self._routes.get((method.upper(), clean_path))
        if handler is None:
            return format_for_mobile({"ok": False, "error": "not_found"})

        # Inject query_params into body for handlers that need them
        if body is None:
            body = {}
        body["_query"] = query_params

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

    def _handle_get_projects(self, body: Optional[dict]) -> dict:
        projects = self._registry.list_projects()
        return {"ok": True, "projects": projects}

    def _handle_get_project_status(self, body: Optional[dict]) -> dict:
        name = (body or {}).get("_query", {}).get("name", "")
        if not name:
            return {"ok": False, "error": "missing_project_name"}
        return self._registry.get_project_status(name)

    def _handle_post_project_task(self, body: Optional[dict]) -> dict:
        name = (body or {}).get("_query", {}).get("name", "")
        prompt = (body or {}).get("prompt", "")
        if not name:
            return {"ok": False, "error": "missing_project_name"}
        task_id = uuid.uuid4().hex[:12]
        task = {
            "task_id": task_id,
            "prompt": prompt,
            "project": name,
            "status": "queued",
        }
        self._tasks.append(task)
        logger.info("Project task queued: %s [%s] — %s", task_id, name, prompt[:80])
        return {"ok": True, "task_id": task_id, "project": name, "status": "queued"}

    def _handle_get_connect_info(self, body: Optional[dict]) -> dict:
        fp = ""
        tls_enabled = self._tls is not None
        if tls_enabled and self._tls is not None:
            try:
                fp = self._tls.fingerprint()
            except Exception:
                fp = "unavailable"
        return {
            "ok": True,
            "tls": tls_enabled,
            "fingerprint": fp,
            "server": f"{_get_local_ip()}:{_server_port}",
            "methods": [
                "Direct HTTPS (if server has public IP)",
                "SSH tunnel: ssh -L 8777:localhost:8777 user@server",
                "WireGuard VPN (peer-to-peer)",
            ],
        }


# ---------------------------------------------------------------------------
# URL generation
# ---------------------------------------------------------------------------


def generate_mobile_url(
    host: str = "0.0.0.0",
    port: int = 8777,
    auth: Optional[MobileAuth] = None,
    tls: bool = True,
) -> str:
    """Generate a URL for mobile access, embedding a fresh auth token.

    If no *auth* instance is provided, a temporary ``MobileAuth`` is created
    and a single-use token is generated.
    """
    if auth is None:
        auth = MobileAuth()
    token = auth.generate_token()
    scheme = "https" if tls else "http"
    display_host = host if host != "0.0.0.0" else _get_local_ip()
    return f"{scheme}://{display_host}:{port}?token={token}"


# ---------------------------------------------------------------------------
# QR code generation
# ---------------------------------------------------------------------------


def generate_qr_terminal(url: str) -> str:
    """Generate a QR code for the terminal using ``qrencode`` if available.

    Falls back to returning just the URL if ``qrencode`` is not installed.
    """
    try:
        result = subprocess.run(
            ["qrencode", "-t", "UTF8", url],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return f"QR code unavailable (install qrencode). URL:\n{url}"


# ---------------------------------------------------------------------------
# HTTP glue — actual server (uses http.server from stdlib)
# ---------------------------------------------------------------------------

_server_instance: Optional[HTTPServer] = None
_server_thread: Optional[threading.Thread] = None
_mobile_server: Optional[MobileServer] = None
_server_port: int = 8777


def _make_handler(mobile: MobileServer) -> type:
    """Factory that returns a request-handler class bound to *mobile*."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            from core.mobile_pwa import (
                ICON_SVG,
                MANIFEST_JSON,
                PWA_HTML,
                SERVICE_WORKER_JS,
            )

            parsed = urlparse(self.path)
            path = parsed.path

            # PWA asset routes (no auth)
            if path == "/" or path == "":
                self._send_html(PWA_HTML)
                return
            if path == "/manifest.json":
                self._send_content(MANIFEST_JSON, "application/json")
                return
            if path == "/sw.js":
                self._send_content(SERVICE_WORKER_JS, "application/javascript")
                return
            if path == "/icon.svg":
                self._send_content(ICON_SVG, "image/svg+xml")
                return

            headers = {k: v for k, v in self.headers.items()}
            client_ip = self.client_address[0]
            resp = mobile.dispatch(
                "GET", self.path, headers=headers, client_ip=client_ip
            )
            self._send_json(resp)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw)
            headers = {k: v for k, v in self.headers.items()}
            client_ip = self.client_address[0]
            resp = mobile.dispatch(
                "POST", self.path, body, headers=headers, client_ip=client_ip
            )
            self._send_json(resp)

        def _send_json(self, data: dict) -> None:
            payload = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_html(self, html: str) -> None:
            payload = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_content(self, content: str, content_type: str) -> None:
            payload = content.encode()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt: str, *args: Any) -> None:
            logger.debug(fmt, *args)

    return _Handler


def start_server(
    host: str = "0.0.0.0",
    port: int = 8777,
    auth: Optional[MobileAuth] = None,
    tls: bool = True,
    tls_manager: Optional[TLSManager] = None,
) -> threading.Thread:
    """Start the mobile API server in a daemon thread.

    Returns the ``threading.Thread`` so callers can join or check liveness.
    """
    global _server_instance, _server_thread, _mobile_server, _server_port

    _server_port = port
    tlsm = tls_manager
    if tls:
        if tlsm is None:
            tlsm = TLSManager()
        tlsm.ensure_certs()

    _mobile_server = MobileServer(auth=auth, tls_manager=tlsm if tls else None)
    handler_class = _make_handler(_mobile_server)
    _server_instance = HTTPServer((host, port), handler_class)

    if tls and tlsm is not None:
        ssl_ctx = tlsm.create_ssl_context()
        _server_instance.socket = ssl_ctx.wrap_socket(
            _server_instance.socket, server_side=True
        )

    _server_thread = threading.Thread(
        target=_server_instance.serve_forever,
        daemon=True,
        name="mobile-api",
    )
    _server_thread.start()
    scheme = "https" if tls else "http"
    logger.info("Mobile API server started on %s://%s:%s", scheme, host, port)
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


def is_server_running() -> bool:
    """Return True if the mobile server thread is alive."""
    return _server_thread is not None and _server_thread.is_alive()


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


def _get_local_ip() -> str:
    """Best-effort detection of the machine's LAN IP."""
    import socket

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ---------------------------------------------------------------------------
# CLI adapter — ``from core.mobile import mobile_server``
# ---------------------------------------------------------------------------


class _MobileManager:
    """Thin CLI-facing adapter wrapping the module-level start/stop functions."""

    def __init__(self) -> None:
        self._auth: Optional[MobileAuth] = None
        self._tls: Optional[TLSManager] = None

    def serve(
        self,
        host: str = "0.0.0.0",
        port: int = 8777,
        tls: bool = True,
    ) -> str:
        """Start the HTTPS server. Returns fingerprint info."""
        self._auth = MobileAuth()
        self._tls = TLSManager() if tls else None
        start_server(
            host=host, port=port, auth=self._auth, tls=tls, tls_manager=self._tls
        )
        fp = ""
        if self._tls:
            try:
                fp = self._tls.fingerprint()
            except Exception:
                fp = "unavailable"
        scheme = "https" if tls else "http"
        return f"Server started on {scheme}://{host}:{port}\nFingerprint: {fp}"

    # Backward compat alias
    def start(self, host: str = "0.0.0.0", port: int = 8777) -> None:
        self.serve(host=host, port=port, tls=False)

    def stop(self) -> None:
        stop_server()

    def pair(
        self, label: str = "", host: str = "0.0.0.0", port: int = 8777, tls: bool = True
    ) -> str:
        """Generate a new token and return the URL + QR output."""
        if self._auth is None:
            self._auth = MobileAuth()
        token = self._auth.generate_token(label=label)
        url = generate_mobile_url(host=host, port=port, auth=None, tls=tls)
        # Build URL with the actual token (generate_mobile_url creates its own)
        scheme = "https" if tls else "http"
        display_host = host if host != "0.0.0.0" else _get_local_ip()
        url = f"{scheme}://{display_host}:{port}?token={token}"
        qr = generate_qr_terminal(url)
        return f"Token: {token}\nURL: {url}\n\n{qr}"

    def connect_info(self, host: str = "0.0.0.0", port: int = 8777) -> str:
        """Print connection methods."""
        ip = _get_local_ip()
        lines = [
            f"1. Direct HTTPS: https://{ip}:{port}",
            f"2. SSH tunnel:   ssh -L {port}:localhost:{port} user@{ip}",
            f"   then open:    https://localhost:{port}",
            f"3. WireGuard:    Connect via WG IP, then https://<wg-ip>:{port}",
        ]
        if self._tls:
            try:
                fp = self._tls.fingerprint()
                lines.insert(0, f"Fingerprint: {fp}")
            except Exception:
                pass
        return "\n".join(lines)

    def tokens(self) -> list[dict]:
        """List active tokens."""
        if self._auth is None:
            self._auth = MobileAuth()
        return self._auth.list_tokens()

    def cert_regen(self) -> str:
        """Regenerate TLS certificates."""
        self._tls = TLSManager()
        self._tls.generate_certs()
        fp = self._tls.fingerprint()
        return f"Certificates regenerated.\nNew fingerprint: {fp}"

    def status(self) -> dict:
        """Return server status info."""
        running = is_server_running()
        return {
            "running": running,
            "port": _server_port,
            "tls": self._tls is not None,
        }

    # Backward compat alias
    def get_url(self, host: str = "0.0.0.0", port: int = 8777) -> str:
        return generate_mobile_url(host=host, port=port)


mobile_server = _MobileManager()
