"""Integration tests for the claude-flow bridge (require real claude-flow installation).

These tests are skipped when claude-flow/npx is not available.
Run with: python3 -m pytest tests/test_integration_bridge.py -v
"""

import subprocess

import pytest

from core.claude_flow import ClaudeFlowBridge, ClaudeFlowUnavailable

# Skip entire module if npx is not available
pytestmark = pytest.mark.skipif(
    subprocess.run(
        ["npx", "--version"], capture_output=True, timeout=10
    ).returncode != 0
    if subprocess.run(["which", "npx"], capture_output=True).returncode == 0
    else True,
    reason="npx not available",
)


def _bridge_available():
    """Check if claude-flow responds."""
    try:
        b = ClaudeFlowBridge()
        return b.is_available()
    except Exception:
        return False


skip_if_no_claude_flow = pytest.mark.skipif(
    not _bridge_available(),
    reason="claude-flow not installed or not responding",
)


@skip_if_no_claude_flow
class TestBridgeVersionCheck:
    def test_bridge_version_check(self):
        bridge = ClaudeFlowBridge()
        assert bridge.is_available()
        version = bridge.get_version()
        assert version != "unavailable"


@skip_if_no_claude_flow
class TestBridgeSpawnAndComplete:
    def test_bridge_spawn_and_complete(self):
        bridge = ClaudeFlowBridge()
        result = bridge.spawn_agent("coder", "echo hello world", timeout=30)
        assert "status" in result or "output" in result


@skip_if_no_claude_flow
class TestBridgeMemoryRoundtrip:
    def test_bridge_memory_roundtrip(self):
        bridge = ClaudeFlowBridge()
        try:
            # Store
            store_result = bridge.store_memory(
                "integration test entry",
                namespace="test",
                metadata={"test": True},
            )
            assert "id" in store_result

            # Query
            query_result = bridge.query_memory("integration test", top_k=1)
            assert "results" in query_result
        except ClaudeFlowUnavailable as e:
            pytest.skip(f"Memory operations not configured: {e}")


@skip_if_no_claude_flow
class TestBridgeSessionLifecycle:
    def test_bridge_session_lifecycle(self):
        bridge = ClaudeFlowBridge()
        # Start
        start_result = bridge.start_session("integration-test-session")
        assert "session_id" in start_result or "output" in start_result

        # End
        end_result = bridge.end_session("integration-test-session")
        assert end_result is not None


class TestBridgeUnavailableGracefully:
    """These tests run without claude-flow and verify graceful degradation."""

    def test_bridge_unavailable_spawn(self):
        """spawn_agent raises ClaudeFlowUnavailable when not installed."""
        bridge = ClaudeFlowBridge()
        bridge._available = False
        # Direct _run should raise
        with pytest.raises(ClaudeFlowUnavailable):
            bridge._run("nonexistent", "command")

    def test_fallback_pattern_agents(self):
        """Verify agents module falls back gracefully."""
        from unittest.mock import patch

        from core.agents import AgentType, execute_agent_task

        with patch("core.agents._get_bridge", side_effect=ClaudeFlowUnavailable("no")):
            with patch("core.agents._execute_agent_task_legacy") as mock_legacy:
                from core.agents import TaskResult
                mock_legacy.return_value = TaskResult(
                    agent=AgentType.CODER, task="test", status="success",
                )
                result = execute_agent_task(AgentType.CODER, "test fallback")
                assert result.status == "success"
                mock_legacy.assert_called_once()

    def test_fallback_pattern_knowledge(self, tmp_path):
        """Verify knowledge module falls back gracefully."""
        from unittest.mock import patch

        from core.knowledge import search_knowledge

        enc = tmp_path / "ENCYCLOPEDIA.md"
        enc.write_text("# Test\n- [2024] keyword match\n")

        with patch("core.knowledge._get_bridge", side_effect=ClaudeFlowUnavailable("no")):
            results = search_knowledge("keyword", encyclopedia_path=enc)
            assert any("keyword" in r for r in results)

    def test_fallback_pattern_model_router(self):
        """Verify model router falls back gracefully."""
        from unittest.mock import patch

        from core.model_router import TaskComplexity, classify_task_complexity

        with patch("core.model_router._get_bridge", side_effect=ClaudeFlowUnavailable("no")):
            result = classify_task_complexity("debug the issue")
            assert result == TaskComplexity.COMPLEX
