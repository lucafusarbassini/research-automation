"""Tests for mobile phone control module."""

import hashlib
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.mobile import (
    MobileAuth,
    MobileServer,
    ProjectRegistry,
    TLSManager,
    format_for_mobile,
    generate_mobile_url,
    generate_qr_terminal,
    start_server,
    stop_server,
)

# ---------------------------------------------------------------------------
# TLSManager
# ---------------------------------------------------------------------------


def test_tls_generate_certs(tmp_path):
    """generate_certs() creates cert and key files."""
    tls = TLSManager(certs_dir=tmp_path / "certs")
    tls.generate_certs()
    assert tls.cert_path.exists()
    assert tls.key_path.exists()
    # Key should have restricted permissions
    assert oct(tls.key_path.stat().st_mode & 0o777) == "0o600"


def test_tls_ensure_certs_idempotent(tmp_path):
    """ensure_certs() generates on first call, skips on second."""
    tls = TLSManager(certs_dir=tmp_path / "certs")
    tls.ensure_certs()
    mtime1 = tls.cert_path.stat().st_mtime
    tls.ensure_certs()  # should not regenerate
    mtime2 = tls.cert_path.stat().st_mtime
    assert mtime1 == mtime2


def test_tls_fingerprint(tmp_path):
    """fingerprint() returns a colon-separated hex string."""
    tls = TLSManager(certs_dir=tmp_path / "certs")
    tls.generate_certs()
    fp = tls.fingerprint()
    assert ":" in fp
    # SHA-256 fingerprint has 32 bytes = 64 hex chars + 31 colons
    parts = fp.split(":")
    assert len(parts) == 32


def test_tls_fingerprint_missing_cert(tmp_path):
    """fingerprint() returns empty string if cert doesn't exist."""
    tls = TLSManager(certs_dir=tmp_path / "certs")
    assert tls.fingerprint() == ""


def test_tls_create_ssl_context(tmp_path):
    """create_ssl_context() returns an SSLContext."""
    import ssl

    tls = TLSManager(certs_dir=tmp_path / "certs")
    tls.generate_certs()
    ctx = tls.create_ssl_context()
    assert isinstance(ctx, ssl.SSLContext)


# ---------------------------------------------------------------------------
# MobileAuth — persistent, hash-based
# ---------------------------------------------------------------------------


def test_auth_generate_token(tmp_path):
    auth = MobileAuth(tokens_file=tmp_path / "tokens.json")
    token = auth.generate_token()
    assert isinstance(token, str)
    assert len(token) >= 32


def test_auth_validate_good_token(tmp_path):
    auth = MobileAuth(tokens_file=tmp_path / "tokens.json")
    token = auth.generate_token()
    assert auth.validate(token) is True


def test_auth_validate_bad_token(tmp_path):
    auth = MobileAuth(tokens_file=tmp_path / "tokens.json")
    auth.generate_token()
    assert auth.validate("bogus-token-value") is False


def test_auth_persistence(tmp_path):
    """Tokens survive reload from disk."""
    tf = tmp_path / "tokens.json"
    auth1 = MobileAuth(tokens_file=tf)
    token = auth1.generate_token(label="test-device")
    # Create a new instance reading from the same file
    auth2 = MobileAuth(tokens_file=tf)
    assert auth2.validate(token) is True


def test_auth_revoke_by_prefix(tmp_path):
    auth = MobileAuth(tokens_file=tmp_path / "tokens.json")
    token = auth.generate_token()
    h = hashlib.sha256(token.encode()).hexdigest()
    prefix = h[:12]
    assert auth.revoke(prefix) is True
    assert auth.validate(token) is False


def test_auth_revoke_unknown_prefix(tmp_path):
    auth = MobileAuth(tokens_file=tmp_path / "tokens.json")
    assert auth.revoke("nonexistent00") is False


def test_auth_list_tokens(tmp_path):
    auth = MobileAuth(tokens_file=tmp_path / "tokens.json")
    auth.generate_token(label="phone")
    auth.generate_token(label="tablet")
    listing = auth.list_tokens()
    assert len(listing) == 2
    labels = {t["label"] for t in listing}
    assert labels == {"phone", "tablet"}
    for t in listing:
        assert "hash_prefix" in t
        assert "created" in t


def test_auth_rate_limiting(tmp_path):
    """10 failures from same IP triggers lockout."""
    auth = MobileAuth(tokens_file=tmp_path / "tokens.json")
    auth.generate_token()
    ip = "192.168.1.100"
    for _ in range(10):
        auth.validate("wrong", client_ip=ip)
    # 11th attempt — locked out even with correct token
    token = auth.generate_token()
    assert auth.validate(token, client_ip=ip) is False


def test_auth_rate_limiting_different_ip(tmp_path):
    """Different IP is not affected by another IP's failures."""
    auth = MobileAuth(tokens_file=tmp_path / "tokens.json")
    token = auth.generate_token()
    # Lock out one IP
    for _ in range(10):
        auth.validate("wrong", client_ip="10.0.0.1")
    # Different IP still works
    assert auth.validate(token, client_ip="10.0.0.2") is True


def test_auth_generate_token_with_label(tmp_path):
    auth = MobileAuth(tokens_file=tmp_path / "tokens.json")
    auth.generate_token(label="my-phone")
    listing = auth.list_tokens()
    assert listing[0]["label"] == "my-phone"


# ---------------------------------------------------------------------------
# ProjectRegistry
# ---------------------------------------------------------------------------


def test_project_registry_empty(tmp_path):
    reg = ProjectRegistry(projects_file=tmp_path / "projects.json")
    assert reg.list_projects() == []


def test_project_registry_list(tmp_path):
    pf = tmp_path / "projects.json"
    pf.write_text(
        json.dumps(
            {
                "projects": [
                    {"name": "proj-a", "path": str(tmp_path / "a")},
                    {"name": "proj-b", "path": str(tmp_path / "b")},
                ]
            }
        )
    )
    reg = ProjectRegistry(projects_file=pf)
    projects = reg.list_projects()
    assert len(projects) == 2
    assert projects[0]["name"] == "proj-a"


def test_project_registry_get_project(tmp_path):
    pf = tmp_path / "projects.json"
    pf.write_text(json.dumps({"projects": [{"name": "alpha", "path": "/tmp/alpha"}]}))
    reg = ProjectRegistry(projects_file=pf)
    assert reg.get_project("alpha")["name"] == "alpha"
    assert reg.get_project("missing") is None


def test_project_registry_get_project_status(tmp_path):
    proj_dir = tmp_path / "myproj"
    state_dir = proj_dir / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "PROGRESS.md").write_text("# Progress\n50% done")

    pf = tmp_path / "projects.json"
    pf.write_text(json.dumps({"projects": [{"name": "myproj", "path": str(proj_dir)}]}))
    reg = ProjectRegistry(projects_file=pf)
    status = reg.get_project_status("myproj")
    assert status["ok"] is True
    assert "50% done" in status["progress"]


def test_project_registry_get_project_status_not_found(tmp_path):
    pf = tmp_path / "projects.json"
    pf.write_text(json.dumps({"projects": []}))
    reg = ProjectRegistry(projects_file=pf)
    status = reg.get_project_status("nope")
    assert status["ok"] is False
    assert status["error"] == "project_not_found"


# ---------------------------------------------------------------------------
# MobileServer — route registration and dispatch
# ---------------------------------------------------------------------------


def test_server_has_all_routes():
    server = MobileServer()
    routes = server.routes
    assert ("POST", "/task") in routes
    assert ("GET", "/status") in routes
    assert ("GET", "/sessions") in routes
    assert ("POST", "/voice") in routes
    assert ("GET", "/progress") in routes
    assert ("GET", "/projects") in routes
    assert ("GET", "/project/status") in routes
    assert ("POST", "/project/task") in routes
    assert ("GET", "/connect-info") in routes


def test_server_dispatch_post_task():
    server = MobileServer()
    response = server.dispatch("POST", "/task", {"prompt": "update the website"})
    assert response["ok"] is True
    assert "task_id" in response


def test_server_dispatch_get_status():
    server = MobileServer()
    response = server.dispatch("GET", "/status")
    assert response["ok"] is True
    assert "status" in response


def test_server_dispatch_get_sessions():
    server = MobileServer()
    response = server.dispatch("GET", "/sessions")
    assert response["ok"] is True
    assert isinstance(response["sessions"], list)


def test_server_dispatch_post_voice():
    server = MobileServer()
    response = server.dispatch("POST", "/voice", {"text": "check progress"})
    assert response["ok"] is True
    assert "task_id" in response


def test_server_dispatch_get_progress():
    server = MobileServer()
    response = server.dispatch("GET", "/progress")
    assert response["ok"] is True
    assert "entries" in response


def test_server_dispatch_unknown_route():
    server = MobileServer()
    response = server.dispatch("GET", "/nonexistent")
    assert response["ok"] is False
    assert response["error"] == "not_found"


def test_server_dispatch_auth_required(tmp_path):
    """Requests with a bad token are rejected when auth is enabled."""
    auth = MobileAuth(tokens_file=tmp_path / "tokens.json")
    auth.generate_token()
    server = MobileServer(auth=auth)
    response = server.dispatch(
        "GET", "/status", headers={"Authorization": "Bearer wrong"}
    )
    assert response["ok"] is False
    assert response["error"] == "unauthorized"


def test_server_dispatch_auth_accepted(tmp_path):
    auth = MobileAuth(tokens_file=tmp_path / "tokens.json")
    token = auth.generate_token()
    server = MobileServer(auth=auth)
    response = server.dispatch(
        "GET", "/status", headers={"Authorization": f"Bearer {token}"}
    )
    assert response["ok"] is True


# -- Multi-project routes --------------------------------------------------


def test_server_dispatch_get_projects(tmp_path):
    pf = tmp_path / "projects.json"
    pf.write_text(json.dumps({"projects": [{"name": "demo"}]}))
    reg = ProjectRegistry(projects_file=pf)
    server = MobileServer(registry=reg)
    resp = server.dispatch("GET", "/projects")
    assert resp["ok"] is True
    assert len(resp["projects"]) == 1


def test_server_dispatch_get_project_status(tmp_path):
    proj_dir = tmp_path / "proj"
    (proj_dir / "state").mkdir(parents=True)
    (proj_dir / "state" / "PROGRESS.md").write_text("# All good")
    pf = tmp_path / "projects.json"
    pf.write_text(json.dumps({"projects": [{"name": "proj", "path": str(proj_dir)}]}))
    reg = ProjectRegistry(projects_file=pf)
    server = MobileServer(registry=reg)
    resp = server.dispatch("GET", "/project/status?name=proj")
    assert resp["ok"] is True
    assert "All good" in resp["progress"]


def test_server_dispatch_post_project_task(tmp_path):
    pf = tmp_path / "projects.json"
    pf.write_text(json.dumps({"projects": [{"name": "proj"}]}))
    reg = ProjectRegistry(projects_file=pf)
    server = MobileServer(registry=reg)
    resp = server.dispatch(
        "POST",
        "/project/task?name=proj",
        {"prompt": "run experiments"},
    )
    assert resp["ok"] is True
    assert resp["project"] == "proj"
    assert "task_id" in resp


def test_server_dispatch_project_task_missing_name():
    server = MobileServer()
    resp = server.dispatch("POST", "/project/task", {"prompt": "hello"})
    assert resp["ok"] is False
    assert resp["error"] == "missing_project_name"


def test_server_dispatch_connect_info():
    server = MobileServer()
    resp = server.dispatch("GET", "/connect-info")
    assert resp["ok"] is True
    assert "methods" in resp
    assert isinstance(resp["methods"], list)


# -- PWA routes (via handler) -----------------------------------------------


def test_pwa_html_content():
    """The PWA HTML constant starts with <!DOCTYPE html>."""
    from core.mobile_pwa import PWA_HTML

    assert PWA_HTML.strip().startswith("<!DOCTYPE html>")


def test_pwa_manifest_is_valid_json():
    from core.mobile_pwa import MANIFEST_JSON

    data = json.loads(MANIFEST_JSON)
    assert data["name"] == "ricet Mobile"


def test_pwa_service_worker_has_cache_name():
    from core.mobile_pwa import SERVICE_WORKER_JS

    assert "CACHE_NAME" in SERVICE_WORKER_JS


# ---------------------------------------------------------------------------
# generate_mobile_url
# ---------------------------------------------------------------------------


def test_generate_mobile_url_https(tmp_path):
    auth = MobileAuth(tokens_file=tmp_path / "tokens.json")
    url = generate_mobile_url(host="192.168.1.10", port=8777, auth=auth, tls=True)
    assert url.startswith("https://192.168.1.10:8777")
    assert "token=" in url


def test_generate_mobile_url_http(tmp_path):
    auth = MobileAuth(tokens_file=tmp_path / "tokens.json")
    url = generate_mobile_url(host="192.168.1.10", port=8777, auth=auth, tls=False)
    assert url.startswith("http://192.168.1.10:8777")
    assert "token=" in url


def test_generate_mobile_url_default():
    url = generate_mobile_url()
    assert "token=" in url
    # Default is HTTPS
    assert url.startswith("https://")


# ---------------------------------------------------------------------------
# generate_qr_terminal
# ---------------------------------------------------------------------------


def test_generate_qr_terminal_fallback():
    """When qrencode is unavailable, returns the URL in a fallback message."""
    with patch("core.mobile.subprocess.run", side_effect=FileNotFoundError):
        result = generate_qr_terminal("https://example.com")
    assert "https://example.com" in result
    assert "QR code unavailable" in result


def test_generate_qr_terminal_with_qrencode():
    """When qrencode works, returns its stdout."""
    mock_result = MagicMock()
    mock_result.stdout = "FAKE_QR_OUTPUT"
    with patch("core.mobile.subprocess.run", return_value=mock_result):
        result = generate_qr_terminal("https://example.com")
    assert result == "FAKE_QR_OUTPUT"


# ---------------------------------------------------------------------------
# format_for_mobile
# ---------------------------------------------------------------------------


def test_format_for_mobile_truncates_long_values():
    data = {"message": "x" * 500, "count": 3}
    result = format_for_mobile(data)
    assert len(result["message"]) <= 280
    assert result["count"] == 3


def test_format_for_mobile_adds_timestamp():
    result = format_for_mobile({"a": 1})
    assert "_ts" in result


# ---------------------------------------------------------------------------
# start_server / stop_server (lifecycle, no real socket, no TLS)
# ---------------------------------------------------------------------------


def test_start_and_stop_server():
    """start_server launches a thread; stop_server shuts it down."""
    thread = start_server(host="127.0.0.1", port=18777, tls=False)
    assert thread.is_alive()
    stop_server()
    thread.join(timeout=3)
    assert not thread.is_alive()
