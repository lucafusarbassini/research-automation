"""Phase 3 tests: voice pipeline (language detection, prompt structuring) and mobile API."""

import json
import threading
import time
import urllib.request
import urllib.error
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Voice: language detection
# ---------------------------------------------------------------------------


class TestDetectLanguage:
    """Test core.voice.detect_language for multiple languages."""

    def test_detect_language_english(self):
        from core.voice import detect_language

        assert detect_language("This is a normal English sentence") == "en"

    def test_detect_language_chinese(self):
        from core.voice import detect_language

        assert detect_language("这是一个中文句子用于测试语言检测") == "zh"

    def test_detect_language_russian(self):
        from core.voice import detect_language

        assert detect_language("Это предложение на русском языке") == "ru"

    def test_detect_language_arabic(self):
        from core.voice import detect_language

        assert detect_language("هذه جملة باللغة العربية للاختبار") == "ar"

    def test_detect_language_spanish(self):
        from core.voice import detect_language

        assert detect_language("El gato de la casa que los niños las quieren") == "es"

    def test_detect_language_empty_string(self):
        from core.voice import detect_language

        assert detect_language("") == "en"
        assert detect_language("   ") == "en"


# ---------------------------------------------------------------------------
# Voice: prompt structuring
# ---------------------------------------------------------------------------


class TestStructurePrompt:
    """Test core.voice.structure_prompt with template matching."""

    def test_structure_prompt_no_templates(self):
        from core.voice import structure_prompt

        # No templates -> returns input unchanged
        result = structure_prompt("debug the failing test", templates={})
        assert result == "debug the failing test"

    def test_structure_prompt_with_matching_template(self):
        from core.voice import structure_prompt

        templates = {
            "debug_help": {
                "tags": ["debug", "fix", "error"],
                "template": "Please investigate and fix: [DESCRIPTION]",
            },
            "write_docs": {
                "tags": ["write", "document", "docs"],
                "template": "Write documentation for: [TOPIC]",
            },
        }

        result = structure_prompt("debug the authentication error", templates=templates)
        assert "Please investigate and fix:" in result
        assert "debug the authentication error" in result

    def test_structure_prompt_write_template(self):
        from core.voice import structure_prompt

        templates = {
            "write_docs": {
                "tags": ["write", "document"],
                "template": "Write documentation for: [TOPIC]",
            },
        }

        result = structure_prompt("write documentation for the API", templates=templates)
        assert "Write documentation for:" in result

    def test_structure_prompt_no_match_returns_original(self):
        from core.voice import structure_prompt

        templates = {
            "only_deploy": {
                "tags": ["deploy", "release"],
                "template": "Deploy: [DESCRIPTION]",
            },
        }

        result = structure_prompt("train a neural network", templates=templates)
        assert result == "train a neural network"


# ---------------------------------------------------------------------------
# Mobile: authentication lifecycle
# ---------------------------------------------------------------------------


class TestMobileAuth:
    """Test core.mobile.MobileAuth generate/validate/revoke lifecycle."""

    def test_mobile_auth_generate_validate_revoke(self):
        from core.mobile import MobileAuth

        auth = MobileAuth()

        # Generate
        token = auth.generate_token()
        assert isinstance(token, str)
        assert len(token) >= 40

        # Validate
        assert auth.validate(token) is True
        assert auth.validate("invalid-token-xyz") is False

        # Revoke
        auth.revoke(token)
        assert auth.validate(token) is False

    def test_mobile_auth_multiple_tokens(self):
        from core.mobile import MobileAuth

        auth = MobileAuth()
        t1 = auth.generate_token()
        t2 = auth.generate_token()

        assert auth.validate(t1) is True
        assert auth.validate(t2) is True
        assert t1 != t2

        auth.revoke(t1)
        assert auth.validate(t1) is False
        assert auth.validate(t2) is True


# ---------------------------------------------------------------------------
# Mobile: server dispatch (no actual HTTP)
# ---------------------------------------------------------------------------


class TestMobileServerAllRoutes:
    """Test MobileServer.dispatch for all 5 endpoints."""

    def test_mobile_server_all_routes(self):
        from core.mobile import MobileAuth, MobileServer

        auth = MobileAuth()
        token = auth.generate_token()
        server = MobileServer(auth=auth)
        headers = {"Authorization": f"Bearer {token}"}

        # POST /task
        resp = server.dispatch("POST", "/task", {"prompt": "Run experiment 1"}, headers=headers)
        assert resp["ok"] is True
        assert "task_id" in resp
        assert resp["status"] == "queued"
        assert "_ts" in resp

        # GET /status
        resp = server.dispatch("GET", "/status", headers=headers)
        assert resp["ok"] is True
        assert "tasks_queued" in resp
        assert resp["tasks_queued"] >= 1

        # GET /sessions
        resp = server.dispatch("GET", "/sessions", headers=headers)
        assert resp["ok"] is True
        assert "sessions" in resp

        # POST /voice
        resp = server.dispatch("POST", "/voice", {"text": "check status"}, headers=headers)
        assert resp["ok"] is True
        assert resp["source"] == "voice"
        assert "task_id" in resp

        # GET /progress
        resp = server.dispatch("GET", "/progress", headers=headers)
        assert resp["ok"] is True
        assert "entries" in resp
        assert len(resp["entries"]) >= 2  # At least the /task and /voice submissions


class TestMobileAuthRejection:
    """Test that requests with a bad token are rejected."""

    def test_mobile_auth_rejection(self):
        from core.mobile import MobileAuth, MobileServer

        auth = MobileAuth()
        server = MobileServer(auth=auth)
        bad_headers = {"Authorization": "Bearer totally-invalid-token-000"}

        resp = server.dispatch("POST", "/task", {"prompt": "should fail"}, headers=bad_headers)
        assert resp["ok"] is False
        assert resp["error"] == "unauthorized"

    def test_mobile_auth_rejection_missing_header(self):
        from core.mobile import MobileAuth, MobileServer

        auth = MobileAuth()
        server = MobileServer(auth=auth)

        resp = server.dispatch("GET", "/status", headers={})
        assert resp["ok"] is False
        assert resp["error"] == "unauthorized"

    def test_mobile_no_auth_allows_all(self):
        from core.mobile import MobileServer

        # No auth configured -> all requests allowed
        server = MobileServer(auth=None)
        resp = server.dispatch("GET", "/status")
        assert resp["ok"] is True


# ---------------------------------------------------------------------------
# Mobile: format_for_mobile
# ---------------------------------------------------------------------------


class TestFormatForMobile:
    """Test core.mobile.format_for_mobile."""

    def test_format_for_mobile_short_values(self):
        from core.mobile import format_for_mobile

        data = {"status": "running", "task_id": "abc123"}
        result = format_for_mobile(data)

        assert result["status"] == "running"
        assert result["task_id"] == "abc123"
        assert "_ts" in result  # Timestamp injected

    def test_format_for_mobile_truncates_long_strings(self):
        from core.mobile import format_for_mobile

        long_text = "x" * 500
        data = {"output": long_text}
        result = format_for_mobile(data)

        assert len(result["output"]) <= 280
        assert result["output"].endswith("...")

    def test_format_for_mobile_preserves_non_strings(self):
        from core.mobile import format_for_mobile

        data = {"count": 42, "active": True, "items": [1, 2, 3]}
        result = format_for_mobile(data)
        assert result["count"] == 42
        assert result["active"] is True
        assert result["items"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Mobile: generate_mobile_url
# ---------------------------------------------------------------------------


class TestGenerateMobileUrl:
    """Test core.mobile.generate_mobile_url."""

    def test_generate_mobile_url_default(self):
        from core.mobile import generate_mobile_url

        url = generate_mobile_url()
        assert url.startswith("http://0.0.0.0:8777?token=")
        # Token portion should be non-empty
        token_part = url.split("token=")[1]
        assert len(token_part) >= 40

    def test_generate_mobile_url_custom(self):
        from core.mobile import MobileAuth, generate_mobile_url

        auth = MobileAuth()
        url = generate_mobile_url(host="192.168.1.10", port=9999, auth=auth)
        assert "192.168.1.10:9999" in url
        token_part = url.split("token=")[1]
        assert auth.validate(token_part) is True


# ---------------------------------------------------------------------------
# Mobile: real HTTP start/stop
# ---------------------------------------------------------------------------


class TestMobileServerStartStop:
    """Test start_server/stop_server with a real HTTP request."""

    def test_mobile_server_start_stop(self):
        from core.mobile import start_server, stop_server

        # Use a high port to avoid conflicts
        port = 18777
        thread = start_server(host="127.0.0.1", port=port)

        try:
            assert thread.is_alive()

            # Give server time to bind
            time.sleep(0.3)

            # Make a real HTTP GET to /status
            url = f"http://127.0.0.1:{port}/status"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as response:
                body = json.loads(response.read().decode())

            assert body["ok"] is True
            assert "status" in body
            assert "_ts" in body
        finally:
            stop_server()

        # After stop, thread should no longer be serving
        time.sleep(0.3)
        with pytest.raises((urllib.error.URLError, ConnectionRefusedError, OSError)):
            urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=2)

    def test_mobile_server_post_task_http(self):
        from core.mobile import start_server, stop_server

        port = 18778
        thread = start_server(host="127.0.0.1", port=port)

        try:
            time.sleep(0.3)

            # POST a task via real HTTP
            url = f"http://127.0.0.1:{port}/task"
            payload = json.dumps({"prompt": "Run experiment"}).encode()
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                body = json.loads(response.read().decode())

            assert body["ok"] is True
            assert "task_id" in body
        finally:
            stop_server()

    def test_mobile_server_not_found_route(self):
        from core.mobile import start_server, stop_server

        port = 18779
        thread = start_server(host="127.0.0.1", port=port)

        try:
            time.sleep(0.3)

            url = f"http://127.0.0.1:{port}/nonexistent"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as response:
                body = json.loads(response.read().decode())

            assert body["ok"] is False
            assert body["error"] == "not_found"
        finally:
            stop_server()
