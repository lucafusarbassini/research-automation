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
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
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
        """Generate a new self-signed certificate and private key.

        Includes Subject Alternative Names for localhost, 127.0.0.1, and the
        machine's LAN IP so browsers accept the certificate without hostname
        mismatch errors.
        """
        self.certs_dir.mkdir(parents=True, exist_ok=True)
        # Build SAN list so the cert is valid for localhost + LAN IP
        san_entries = ["DNS:localhost", "IP:127.0.0.1"]
        try:
            lan_ip = _get_local_ip()
            if lan_ip and lan_ip not in ("127.0.0.1", "0.0.0.0"):
                san_entries.append(f"IP:{lan_ip}")
        except Exception:
            pass
        san_value = ",".join(san_entries)
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
                "/CN=localhost",
                "-addext",
                f"subjectAltName={san_value}",
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
_NO_TRUNCATE_KEYS = frozenset({"content", "_html", "todo", "goal"})


def format_for_mobile(data: dict) -> dict:
    """Format a response dict for compact mobile display.

    * Long string values are truncated to 280 characters (except content/html/todo/goal).
    * A ``_ts`` key with the current ISO-8601 timestamp is injected.
    """
    out: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str) and len(value) > _MOBILE_MAX_STR and key not in _NO_TRUNCATE_KEYS:
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
        screen_session: Optional[str] = None,
    ) -> None:
        self._auth = auth
        self._registry = registry or ProjectRegistry()
        self._tls = tls_manager
        # Screen session for live injection. Read from env var if not passed.
        self._screen_session: str = screen_session or os.environ.get("RICET_SCREEN_SESSION", "")
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
        self._routes[("POST", "/project/create")] = self._handle_create_project
        self._routes[("GET", "/dashboard")] = self._handle_get_dashboard
        self._routes[("GET", "/dashboard/html")] = self._handle_get_dashboard_html
        self._routes[("GET", "/screen/capture")] = self._handle_get_screen_capture
        self._routes[("POST", "/todo")] = self._handle_post_todo

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
        # Auth check (skip for PWA asset routes and localhost/tunnel access)
        is_local = client_ip in ("127.0.0.1", "::1", "localhost", "")
        if self._auth is not None and not is_local and path not in (
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
        injected = _inject_to_screen(prompt, self._screen_session) if self._screen_session else False
        status = "injected" if injected else "queued"
        task = {"task_id": task_id, "prompt": prompt, "status": status}
        self._tasks.append(task)
        if not injected:
            self._persist_task_to_todo(prompt)
        logger.info("Task %s: %s — %s", status, task_id, prompt[:80])
        return {"ok": True, "task_id": task_id, "status": status}

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
        # Use client-provided language if available, fall back to detection
        original_lang = (body or {}).get("source_lang", "")
        from core.voice import detect_language, translate_to_english
        if not original_lang:
            original_lang = detect_language(text)
        if original_lang and original_lang != "en":
            translated = translate_to_english(text, source_lang=original_lang)
            if translated and translated != text:
                logger.info("Voice translated %s→en: %s → %s", original_lang, text[:40], translated[:40])
                text = translated
        task_id = uuid.uuid4().hex[:12]
        injected = _inject_to_screen(text, self._screen_session) if self._screen_session else False
        status = "injected" if injected else "queued"
        task = {"task_id": task_id, "prompt": text, "status": status, "source": "voice"}
        self._tasks.append(task)
        if not injected:
            self._persist_task_to_todo(text, source="voice")
        logger.info("Voice %s: %s — %s", status, task_id, text[:80])
        return {"ok": True, "task_id": task_id, "source": "voice", "injected": injected,
                "original_lang": original_lang}

    def _persist_task_to_todo(self, prompt: str, source: str = "mobile") -> None:
        """Append a task to state/TODO.md so ricet overnight can pick it up.

        Uses the active project path from the registry so it works regardless
        of the server process's current working directory.
        """
        base = Path.cwd()
        try:
            active = self._registry.get_active_project()
            if active and active.get("path"):
                base = Path(active["path"])
        except Exception:
            pass
        todo_path = base / "state" / "TODO.md"
        try:
            todo_path.parent.mkdir(parents=True, exist_ok=True)
            if not todo_path.exists():
                todo_path.write_text("# TODO\n\n")
            with open(todo_path, "a") as f:
                f.write(f"- [ ] [{source}] {prompt}\n")
            logger.info("Task persisted to %s", todo_path.resolve())
        except Exception as exc:
            logger.warning(
                "Could not persist task to %s: %s", todo_path.resolve(), exc
            )

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
        # Inject to screen if available, fall back to TODO
        injected = _inject_to_screen(prompt, self._screen_session) if self._screen_session else False
        status = "injected" if injected else "queued"
        task = {
            "task_id": task_id,
            "prompt": prompt,
            "project": name,
            "status": status,
        }
        self._tasks.append(task)
        if not injected:
            self._persist_task_to_todo(prompt, source=f"mobile:{name}")
        logger.info("Project task %s: %s [%s] — %s", status, task_id, name, prompt[:80])
        return {"ok": True, "task_id": task_id, "project": name, "status": status}

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

    def _handle_create_project(self, body: Optional[dict]) -> dict:
        """Create a new ricet project from mobile/web."""
        name = (body or {}).get("name", "").strip()
        goal = (body or {}).get("goal", "").strip()
        if not name:
            return {"ok": False, "error": "missing_project_name"}
        if not goal:
            return {"ok": False, "error": "missing_goal"}

        # Sanitize name
        import re as _re

        name = _re.sub(r"[^a-zA-Z0-9_-]", "-", name).strip("-")[:60]
        if not name:
            return {"ok": False, "error": "invalid_project_name"}

        # Launch init in background thread
        import threading as _thr

        def _run_init():
            try:
                _run_project_init(name, goal, self._registry)
            except Exception as exc:
                logger.error("Mobile project init failed: %s", exc)

        _thr.Thread(target=_run_init, daemon=True, name=f"init-{name}").start()
        return {"ok": True, "project": name, "status": "creating"}

    def _handle_get_dashboard(self, body: Optional[dict]) -> dict:
        """Return comprehensive dashboard data as JSON."""
        data: dict = {"ok": True}

        # Goal
        goal_path = Path("knowledge/GOAL.md")
        data["goal"] = goal_path.read_text()[:500] if goal_path.exists() else ""

        # Progress
        progress_path = Path("state/PROGRESS.md")
        if progress_path.exists():
            lines = progress_path.read_text().strip().splitlines()
            data["progress"] = lines[-20:]
        else:
            data["progress"] = []

        # TODO
        todo_path = Path("state/TODO.md")
        data["todo"] = todo_path.read_text()[:1000] if todo_path.exists() else ""

        # Resources
        try:
            from core.resources import monitor_resources

            snap = monitor_resources()
            data["resources"] = {
                "cpu_percent": snap.cpu_percent,
                "ram_used_gb": snap.ram_used_gb,
                "ram_total_gb": snap.ram_total_gb,
                "disk_free_gb": snap.disk_free_gb,
            }
        except Exception:
            data["resources"] = {}

        # Sessions
        sessions_dir = Path("state/sessions")
        sessions = []
        if sessions_dir.is_dir():
            for f in sorted(sessions_dir.glob("*.json"))[-10:]:
                try:
                    sessions.append(json.loads(f.read_text()))
                except Exception:
                    pass
        data["sessions"] = sessions

        # Projects
        data["projects"] = self._registry.list_projects()

        return data

    def _handle_get_screen_capture(self, body: Optional[dict]) -> dict:
        """Capture current screen session content via `screen -X hardcopy`."""
        if not self._screen_session:
            return {"ok": True, "content": ""}
        import shutil
        import tempfile
        if not shutil.which("screen"):
            return {"ok": True, "content": "screen not available"}
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            result = subprocess.run(
                ["screen", "-S", self._screen_session, "-X", "hardcopy", "-h", tmp_path],
                capture_output=True, timeout=3,
            )
            if result.returncode != 0:
                return {"ok": True, "content": "Screen session not reachable."}
            content = Path(tmp_path).read_text(errors="replace")
            # Strip trailing blank lines
            lines = content.rstrip("\n").split("\n")
            # Remove leading blank lines too
            while lines and not lines[0].strip():
                lines.pop(0)
            return {"ok": True, "content": "\n".join(lines)}
        except Exception as exc:
            return {"ok": True, "content": f"Error: {exc}"}
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _handle_post_todo(self, body: Optional[dict]) -> dict:
        """Save a task directly to TODO.md (skip screen injection)."""
        prompt = (body or {}).get("prompt", "") or (body or {}).get("text", "")
        if not prompt:
            return {"ok": False, "error": "empty_prompt"}
        self._persist_task_to_todo(prompt, source="mobile-todo")
        task_id = uuid.uuid4().hex[:12]
        return {"ok": True, "task_id": task_id, "status": "saved_to_todo"}

    def _handle_get_dashboard_html(self, body: Optional[dict]) -> dict:
        """Serve standalone dashboard HTML page."""
        from core.mobile_pwa import DASHBOARD_HTML

        return {"ok": True, "_html": DASHBOARD_HTML}


def _run_project_init(
    name: str, goal: str, registry: "ProjectRegistry"
) -> None:
    """Run project init in a background thread (called from mobile)."""
    import shutil
    import subprocess

    from core.credential_store import load_global_credentials
    from core.onboarding import (
        OnboardingAnswers,
        setup_workspace,
        write_env_file,
        write_goal_file,
        write_settings,
    )

    base_dir = Path.home() / "research"
    base_dir.mkdir(parents=True, exist_ok=True)
    project_path = base_dir / name

    if project_path.exists():
        logger.warning("Project %s already exists at %s", name, project_path)
        return

    # Copy templates
    template_dir = Path(__file__).resolve().parent.parent / "templates"
    if template_dir.exists():
        shutil.copytree(template_dir, project_path, dirs_exist_ok=True)
    else:
        project_path.mkdir(parents=True, exist_ok=True)

    # Fill answers with defaults
    answers = OnboardingAnswers(
        project_name=name,
        goal=goal,
        needs_website=True,
        needs_mobile=True,
    )

    # Setup workspace
    setup_workspace(project_path)
    write_settings(project_path, answers)
    write_goal_file(project_path, answers)

    # Write goal to GOAL.md
    goal_file = project_path / "knowledge" / "GOAL.md"
    if goal_file.exists():
        content = goal_file.read_text()
        for ph in ("<!-- User provides during init -->", "<!-- WRITE YOUR PROJECT DESCRIPTION HERE -->"):
            content = content.replace(ph, goal)
        goal_file.write_text(content)

    # Use global credentials
    global_creds = load_global_credentials()
    if global_creds:
        write_env_file(project_path, global_creds)

    # Git init + commit
    try:
        subprocess.run(
            "git init && git add -A && git commit -m 'Initial ricet project (created from mobile)'",
            shell=True,
            cwd=project_path,
            capture_output=True,
            timeout=30,
        )
    except Exception:
        pass

    # Register in project registry
    try:
        registry.register(
            name=name,
            path=str(project_path),
            project_type="general",
            description=goal[:100],
        )
    except Exception as exc:
        logger.warning("Could not register project: %s", exc)

    logger.info("Mobile project init complete: %s at %s", name, project_path)


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
    """Generate a QR code for the terminal.

    Tries the Python ``qrcode`` library first (pip install qrcode),
    then falls back to the ``qrencode`` CLI tool.
    """
    # Try Python qrcode library first (no system dependency needed)
    try:
        import io

        import qrcode  # type: ignore[import-untyped]

        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        buf = io.StringIO()
        qr.print_ascii(out=buf, invert=True)
        return buf.getvalue()
    except ImportError:
        pass

    # Fallback to qrencode CLI
    try:
        result = subprocess.run(
            ["qrencode", "-t", "UTF8", url],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return f"QR code unavailable (pip install qrcode). URL:\n{url}"


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
                self._send_content(SERVICE_WORKER_JS, "application/javascript", no_cache=True)
                return
            if path == "/icon.svg":
                self._send_content(ICON_SVG, "image/svg+xml")
                return

            headers = {k: v for k, v in self.headers.items()}
            client_ip = self.client_address[0]
            resp = mobile.dispatch(
                "GET", self.path, headers=headers, client_ip=client_ip
            )
            # If response contains _html, serve as raw HTML page
            if "_html" in resp:
                self._send_html(resp["_html"])
            else:
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
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(payload)

        def _send_content(self, content: str, content_type: str, no_cache: bool = False) -> None:
            payload = content.encode()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            if no_cache:
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
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
    screen_session: Optional[str] = None,
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

    _mobile_server = MobileServer(auth=auth, tls_manager=tlsm if tls else None, screen_session=screen_session)
    handler_class = _make_handler(_mobile_server)
    _server_instance = ThreadingHTTPServer((host, port), handler_class)

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


def _inject_to_screen(text: str, session: str) -> bool:
    """Inject text into a running GNU screen session as if typed at the prompt.

    Uses ``screen -S <session> -X stuff "<text>\\r"``.
    Returns True if the screen command succeeded (session exists and is reachable).
    Safe to call even when no screen session is running — just returns False.
    """
    if not session:
        return False
    import shutil
    import subprocess
    if not shutil.which("screen"):
        return False
    result = subprocess.run(
        ["screen", "-S", session, "-X", "stuff", f"{text}\r"],
        capture_output=True,
        timeout=3,
    )
    if result.returncode == 0:
        logger.info("Injected %d chars into screen session '%s'", len(text), session)
    return result.returncode == 0


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
        screen_session: Optional[str] = None,
    ) -> str:
        """Start the HTTPS server. Returns fingerprint info."""
        self._auth = MobileAuth()
        self._tls = TLSManager() if tls else None
        start_server(
            host=host, port=port, auth=self._auth, tls=tls, tls_manager=self._tls,
            screen_session=screen_session or os.environ.get("RICET_SCREEN_SESSION", ""),
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


# ---------------------------------------------------------------------------
# Cloudflare tunnel for phone access through firewalls
# ---------------------------------------------------------------------------

_CLOUDFLARED_BIN = Path.home() / ".local" / "bin" / "cloudflared"


def _ensure_cloudflared() -> Path:
    """Download cloudflared binary if not present. No sudo needed."""
    # Check system-wide first
    import shutil

    system_cf = shutil.which("cloudflared")
    if system_cf:
        return Path(system_cf)

    if _CLOUDFLARED_BIN.exists():
        return _CLOUDFLARED_BIN

    import platform as _plat
    import urllib.request

    arch = _plat.machine()
    arch_map = {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64"}
    arch_slug = arch_map.get(arch, "amd64")
    url = (
        f"https://github.com/cloudflare/cloudflared/releases/latest/download/"
        f"cloudflared-linux-{arch_slug}"
    )
    _CLOUDFLARED_BIN.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading cloudflared from %s", url)
    urllib.request.urlretrieve(url, str(_CLOUDFLARED_BIN))
    os.chmod(_CLOUDFLARED_BIN, 0o755)
    logger.info("cloudflared installed at %s", _CLOUDFLARED_BIN)
    return _CLOUDFLARED_BIN


def get_tailscale_address() -> str:
    """Return the machine's Tailscale IP/hostname, or '' if not running."""
    import shutil
    if not shutil.which("tailscale"):
        return ""
    result = subprocess.run(
        ["tailscale", "ip", "--4"],
        capture_output=True, text=True, timeout=5,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return ""


def start_tunnel(port: int = 8777) -> subprocess.Popen:
    """Start a cloudflared quick-tunnel exposing localhost:port.

    Returns the Popen object. The public URL is printed to stderr by
    cloudflared and can be parsed from its output.
    """
    cf_bin = _ensure_cloudflared()
    scheme = "http"  # tunnel terminates TLS, so connect to local HTTP
    proc = subprocess.Popen(
        [
            str(cf_bin),
            "tunnel",
            "--url",
            f"{scheme}://localhost:{port}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc


def parse_tunnel_url(proc: subprocess.Popen, timeout: float = 30.0) -> str:
    """Read cloudflared stderr until the public URL appears."""
    import re
    import select

    deadline = time.monotonic() + timeout
    url_re = re.compile(r"(https://[a-z0-9-]+\.trycloudflare\.com)")
    collected = []
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        ready, _, _ = select.select([proc.stderr], [], [], min(remaining, 1.0))
        if ready:
            line = proc.stderr.readline()  # type: ignore[union-attr]
            if not line:
                break
            collected.append(line)
            m = url_re.search(line)
            if m:
                return m.group(1)
    logger.warning("Could not parse tunnel URL. Output:\n%s", "".join(collected))
    return ""
