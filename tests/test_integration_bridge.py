"""Integration tests for the claude-flow bridge (require real claude-flow installation).

These tests are skipped when claude-flow/npx is not available.
Run with: python3 -m pytest tests/test_integration_bridge.py -v
"""

import subprocess

import pytest

from core.claude_flow import ClaudeFlowBridge, ClaudeFlowUnavailable

# Skip entire module if npx is not available
pytestmark = pytest.mark.skipif(
    (
        subprocess.run(["npx", "--version"], capture_output=True, timeout=10).returncode
        != 0
        if subprocess.run(["which", "npx"], capture_output=True).returncode == 0
        else True
    ),
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


class TestConfTestFixture:
    """Verify the conftest mock_bridge fixture works end-to-end."""

    def test_mock_bridge_fixture_agents(self, mock_bridge):
        from unittest.mock import patch

        from core.agents import AgentType, execute_agent_task

        mock_bridge.spawn_agent.return_value = {
            "status": "success",
            "output": "fixture test",
            "tokens_used": 50,
        }
        with patch("core.agents._get_bridge", return_value=mock_bridge):
            result = execute_agent_task(AgentType.RESEARCHER, "find papers")
            assert result.status == "success"
            assert result.output == "fixture test"

    def test_mock_bridge_fixture_knowledge(self, mock_bridge, tmp_path):
        from unittest.mock import patch

        from core.knowledge import search_knowledge

        mock_bridge.query_memory.return_value = {
            "results": [{"text": "fixture semantic result", "score": 0.9}]
        }
        enc = tmp_path / "ENC.md"
        enc.write_text("# Test\n")
        with patch("core.knowledge._get_bridge", return_value=mock_bridge):
            results = search_knowledge("anything", encyclopedia_path=enc)
            assert "fixture semantic result" in results

    def test_mock_bridge_fixture_tokens(self, mock_bridge):
        from unittest.mock import patch

        from core.tokens import estimate_tokens

        mock_bridge.get_metrics.return_value = {"tokens_used": 999}
        with patch("core.tokens._get_bridge", return_value=mock_bridge):
            assert estimate_tokens("text") == 999

    def test_mock_bridge_fixture_model_router(self, mock_bridge):
        from unittest.mock import patch

        from core.model_router import DEFAULT_MODELS, route_to_model

        mock_bridge.route_model.return_value = {"model": "claude-sonnet-4-20250514"}
        with patch("core.model_router._get_bridge", return_value=mock_bridge):
            model = route_to_model("write some code")
            assert model.name == DEFAULT_MODELS["claude-sonnet"].name

    def test_mock_bridge_fixture_security(self, mock_bridge, tmp_path):
        from unittest.mock import patch

        from core.security import scan_for_secrets

        mock_bridge.scan_security.return_value = {"findings": []}
        f = tmp_path / "clean.py"
        f.write_text("x = 1\n")
        with patch("core.security._get_bridge", return_value=mock_bridge):
            findings = scan_for_secrets(f)
            assert findings == []

    def test_mock_bridge_fixture_session(self, mock_bridge, tmp_path, monkeypatch):
        from unittest.mock import patch

        from core.session import close_session, create_session

        monkeypatch.setattr("core.session.SESSIONS_DIR", tmp_path / "sessions")
        with patch("core.session._get_bridge", return_value=mock_bridge):
            session = create_session("fixture-session")
            mock_bridge.start_session.assert_called_once_with("fixture-session")
            close_session(session)
            mock_bridge.end_session.assert_called_once_with("fixture-session")


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
                    agent=AgentType.CODER,
                    task="test",
                    status="success",
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

        with patch(
            "core.knowledge._get_bridge", side_effect=ClaudeFlowUnavailable("no")
        ):
            results = search_knowledge("keyword", encyclopedia_path=enc)
            assert any("keyword" in r for r in results)

    def test_fallback_pattern_model_router(self):
        """Verify model router falls back gracefully."""
        from unittest.mock import patch

        from core.model_router import TaskComplexity, classify_task_complexity

        with patch(
            "core.model_router._get_bridge", side_effect=ClaudeFlowUnavailable("no")
        ):
            result = classify_task_complexity("debug the issue")
            assert result == TaskComplexity.COMPLEX
