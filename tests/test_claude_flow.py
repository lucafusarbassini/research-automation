"""Tests for the claude-flow bridge (mocked subprocess)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from core.claude_flow import (
    AGENT_TYPE_MAP,
    ClaudeFlowBridge,
    ClaudeFlowUnavailable,
    _get_bridge,
)


@pytest.fixture
def bridge():
    """Create a fresh bridge instance."""
    return ClaudeFlowBridge()


def _mock_run(stdout="", returncode=0, stderr=""):
    """Build a mock subprocess.run result."""
    m = MagicMock()
    m.stdout = stdout
    m.returncode = returncode
    m.stderr = stderr
    return m


class TestBridgeAvailability:
    def test_is_available_true(self, bridge):
        with patch("core.claude_flow.subprocess.run") as mock:
            mock.return_value = _mock_run(stdout='{"version": "3.0.0"}')
            assert bridge.is_available() is True
            assert bridge.get_version() == "3.0.0"

    def test_is_available_false_not_found(self, bridge):
        with patch("core.claude_flow.subprocess.run", side_effect=FileNotFoundError):
            assert bridge.is_available() is False

    def test_is_available_false_nonzero_exit(self, bridge):
        with patch("core.claude_flow.subprocess.run") as mock:
            mock.return_value = _mock_run(returncode=1, stderr="not found")
            assert bridge.is_available() is False

    def test_is_available_cached(self, bridge):
        bridge._available = True
        assert bridge.is_available() is True

    def test_get_version_unavailable(self, bridge):
        with patch("core.claude_flow.subprocess.run", side_effect=FileNotFoundError):
            bridge.is_available()
            assert bridge.get_version() == "unavailable"


class TestBridgeRun:
    def test_run_json_output(self, bridge):
        with patch("core.claude_flow.subprocess.run") as mock:
            mock.return_value = _mock_run(stdout='{"status": "ok"}')
            result = bridge._run("test", "cmd")
            assert result == {"status": "ok"}

    def test_run_plain_text_output(self, bridge):
        with patch("core.claude_flow.subprocess.run") as mock:
            mock.return_value = _mock_run(stdout="plain text output")
            result = bridge._run("test")
            assert result["output"] == "plain text output"
            assert result["ok"] is True

    def test_run_nonzero_exit_raises(self, bridge):
        with patch("core.claude_flow.subprocess.run") as mock:
            mock.return_value = _mock_run(returncode=1, stderr="fail")
            with pytest.raises(ClaudeFlowUnavailable, match="exited 1"):
                bridge._run("bad", "cmd")

    def test_run_timeout_raises(self, bridge):
        import subprocess as sp

        with patch(
            "core.claude_flow.subprocess.run", side_effect=sp.TimeoutExpired("cmd", 10)
        ):
            with pytest.raises(ClaudeFlowUnavailable, match="timed out"):
                bridge._run("slow")

    def test_run_file_not_found_raises(self, bridge):
        with patch("core.claude_flow.subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(ClaudeFlowUnavailable, match="npx not found"):
                bridge._run("missing")


class TestSpawnAgent:
    def test_spawn_agent_maps_type(self, bridge):
        with patch("core.claude_flow.subprocess.run") as mock:
            mock.return_value = _mock_run(
                stdout='{"status": "success", "output": "done"}'
            )
            result = bridge.spawn_agent("coder", "fix the bug")
            assert result["status"] == "success"
            call_args = mock.call_args[0][0]
            assert "coder" in call_args  # claude-flow type "coder"

    def test_spawn_agent_unknown_type_passes_through(self, bridge):
        with patch("core.claude_flow.subprocess.run") as mock:
            mock.return_value = _mock_run(stdout='{"status": "success"}')
            bridge.spawn_agent("custom-agent", "do stuff")
            call_args = mock.call_args[0][0]
            assert "custom-agent" in call_args


class TestRunSwarm:
    def test_run_swarm(self, bridge):
        with patch("core.claude_flow.subprocess.run") as mock:
            mock.return_value = _mock_run(stdout='{"results": []}')
            tasks = [
                {"type": "coder", "task": "implement feature"},
                {"type": "reviewer", "task": "review code"},
            ]
            result = bridge.run_swarm(tasks)
            assert "results" in result
            call_args = mock.call_args[0][0]
            assert "--topology" in call_args
            assert "hierarchical" in call_args


class TestRouteModel:
    def test_route_model(self, bridge):
        with patch("core.claude_flow.subprocess.run") as mock:
            mock.return_value = _mock_run(
                stdout='{"tier": "workhorse", "model": "claude-sonnet-4-20250514", "complexity": "medium"}'
            )
            result = bridge.route_model("implement a data loader")
            assert result["tier"] == "workhorse"
            assert result["complexity"] == "medium"


class TestMemory:
    def test_query_memory(self, bridge):
        with patch("core.claude_flow.subprocess.run") as mock:
            mock.return_value = _mock_run(
                stdout='{"results": [{"text": "use batch size 32", "score": 0.95}]}'
            )
            result = bridge.query_memory("batch size")
            assert len(result["results"]) == 1

    def test_store_memory(self, bridge):
        with patch("core.claude_flow.subprocess.run") as mock:
            mock.return_value = _mock_run(stdout='{"id": "mem-123"}')
            result = bridge.store_memory("vectorized ops are fast", namespace="tricks")
            assert result["id"] == "mem-123"

    def test_store_memory_with_metadata(self, bridge):
        with patch("core.claude_flow.subprocess.run") as mock:
            mock.return_value = _mock_run(stdout='{"id": "mem-456"}')
            result = bridge.store_memory(
                "learning rate warmup helps",
                metadata={"section": "What Works"},
            )
            assert result["id"] == "mem-456"
            call_args = mock.call_args[0][0]
            assert "--metadata" in call_args


class TestSecurity:
    def test_scan_security(self, bridge):
        with patch("core.claude_flow.subprocess.run") as mock:
            mock.return_value = _mock_run(stdout='{"findings": []}')
            result = bridge.scan_security("/project")
            assert result["findings"] == []


class TestMetrics:
    def test_get_metrics(self, bridge):
        with patch("core.claude_flow.subprocess.run") as mock:
            mock.return_value = _mock_run(
                stdout='{"tokens_used": 5000, "cost_usd": 0.12}'
            )
            result = bridge.get_metrics()
            assert result["tokens_used"] == 5000


class TestSession:
    def test_start_session(self, bridge):
        with patch("core.claude_flow.subprocess.run") as mock:
            mock.return_value = _mock_run(stdout='{"session_id": "sess-abc"}')
            result = bridge.start_session("my-session")
            assert result["session_id"] == "sess-abc"

    def test_end_session(self, bridge):
        with patch("core.claude_flow.subprocess.run") as mock:
            mock.return_value = _mock_run(
                stdout='{"summary": {"tokens": 12000, "tasks": 5}}'
            )
            result = bridge.end_session("my-session")
            assert "summary" in result


class TestMultiRepoSync:
    def test_multi_repo_sync(self, bridge):
        with patch("core.claude_flow.subprocess.run") as mock:
            mock.return_value = _mock_run(stdout='{"repo-a": true, "repo-b": true}')
            result = bridge.multi_repo_sync("sync commit", ["repo-a", "repo-b"])
            assert result["repo-a"] is True


class TestAgentTypeMap:
    def test_all_our_types_mapped(self):
        expected = {
            "master",
            "researcher",
            "coder",
            "reviewer",
            "falsifier",
            "writer",
            "cleaner",
        }
        assert expected == set(AGENT_TYPE_MAP.keys())


class TestGetBridge:
    def test_get_bridge_raises_when_unavailable(self):
        import core.claude_flow as cf_mod

        old = cf_mod._bridge_instance
        cf_mod._bridge_instance = None
        try:
            with patch.object(ClaudeFlowBridge, "is_available", return_value=False):
                with pytest.raises(ClaudeFlowUnavailable):
                    _get_bridge()
        finally:
            cf_mod._bridge_instance = old

    def test_get_bridge_returns_singleton(self):
        import core.claude_flow as cf_mod

        old = cf_mod._bridge_instance
        cf_mod._bridge_instance = None
        try:
            with patch.object(ClaudeFlowBridge, "is_available", return_value=True):
                b1 = _get_bridge()
                b2 = _get_bridge()
                assert b1 is b2
        finally:
            cf_mod._bridge_instance = old
