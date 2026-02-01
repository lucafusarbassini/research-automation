"""Tests for mobile phone control module."""

import json
import time
from unittest.mock import patch

from core.mobile import (
    MobileAuth,
    MobileServer,
    format_for_mobile,
    generate_mobile_url,
    start_server,
    stop_server,
)

# ---------------------------------------------------------------------------
# MobileAuth
# ---------------------------------------------------------------------------


def test_auth_generate_token():
    auth = MobileAuth()
    token = auth.generate_token()
    assert isinstance(token, str)
    assert len(token) >= 32


def test_auth_validate_good_token():
    auth = MobileAuth()
    token = auth.generate_token()
    assert auth.validate(token) is True


def test_auth_validate_bad_token():
    auth = MobileAuth()
    auth.generate_token()
    assert auth.validate("bogus-token-value") is False


def test_auth_revoke_token():
    auth = MobileAuth()
    token = auth.generate_token()
    auth.revoke(token)
    assert auth.validate(token) is False


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


def test_server_dispatch_auth_required():
    """Requests with a bad token are rejected when auth is enabled."""
    auth = MobileAuth()
    auth.generate_token()
    server = MobileServer(auth=auth)
    response = server.dispatch(
        "GET", "/status", headers={"Authorization": "Bearer wrong"}
    )
    assert response["ok"] is False
    assert response["error"] == "unauthorized"


def test_server_dispatch_auth_accepted():
    auth = MobileAuth()
    token = auth.generate_token()
    server = MobileServer(auth=auth)
    response = server.dispatch(
        "GET", "/status", headers={"Authorization": f"Bearer {token}"}
    )
    assert response["ok"] is True


# ---------------------------------------------------------------------------
# generate_mobile_url
# ---------------------------------------------------------------------------


def test_generate_mobile_url_contains_token():
    url = generate_mobile_url(host="192.168.1.10", port=8777)
    assert url.startswith("http://192.168.1.10:8777")
    assert "token=" in url


def test_generate_mobile_url_default():
    url = generate_mobile_url()
    assert "0.0.0.0:8777" in url


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
# start_server / stop_server (lifecycle, no real socket)
# ---------------------------------------------------------------------------


def test_start_and_stop_server():
    """start_server launches a thread; stop_server shuts it down."""
    thread = start_server(host="127.0.0.1", port=18777)
    assert thread.is_alive()
    stop_server()
    thread.join(timeout=3)
    assert not thread.is_alive()
