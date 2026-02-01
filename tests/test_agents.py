"""Tests for agent routing and orchestration."""

from unittest.mock import MagicMock, patch

from core.agents import (
    AgentType,
    TaskResult,
    _route_task_keywords,
    execute_agent_task,
    route_task,
)


def test_route_to_researcher():
    assert route_task("search for papers on transformers") == AgentType.RESEARCHER
    assert route_task("literature review on GANs") == AgentType.RESEARCHER


def test_route_to_coder():
    assert route_task("implement the training loop") == AgentType.CODER
    assert route_task("fix the bug in data loading") == AgentType.CODER


def test_route_to_reviewer():
    assert route_task("review the code quality") == AgentType.REVIEWER


def test_route_to_falsifier():
    assert route_task("validate the experimental results") == AgentType.FALSIFIER
    assert route_task("falsify and verify the data leakage") == AgentType.FALSIFIER


def test_route_to_writer():
    assert route_task("draft the introduction section") == AgentType.WRITER
    assert route_task("write the abstract") == AgentType.WRITER


def test_route_to_cleaner():
    assert route_task("refactor the preprocessing module") == AgentType.CLEANER
    assert route_task("optimize the data pipeline") == AgentType.CLEANER


def test_route_default():
    # Unrecognized tasks default to coder
    assert route_task("do something vague") == AgentType.CODER


# --- Bridge-integrated tests ---


def test_route_task_keywords_fallback():
    """_route_task_keywords always uses keyword matching."""
    assert _route_task_keywords("search for papers") == AgentType.RESEARCHER
    assert _route_task_keywords("unknown thing") == AgentType.CODER


def test_route_task_via_bridge():
    """When bridge returns a valid agent_type, route_task uses it."""
    mock_bridge = MagicMock()
    mock_bridge.route_model.return_value = {"agent_type": "researcher"}
    with patch("core.agents._get_bridge", return_value=mock_bridge):
        assert route_task("anything") == AgentType.RESEARCHER


def test_route_task_bridge_unavailable_falls_back():
    """When bridge raises, route_task falls back to keyword matching."""
    from core.claude_flow import ClaudeFlowUnavailable

    with patch("core.agents._get_bridge", side_effect=ClaudeFlowUnavailable("nope")):
        assert route_task("implement the feature") == AgentType.CODER


def test_execute_agent_task_via_bridge():
    """When bridge is available, execute_agent_task uses spawn_agent."""
    mock_bridge = MagicMock()
    mock_bridge.spawn_agent.return_value = {
        "status": "success",
        "output": "done via claude-flow",
        "tokens_used": 500,
    }
    with patch("core.agents._get_bridge", return_value=mock_bridge):
        result = execute_agent_task(AgentType.CODER, "fix the bug")
        assert result.status == "success"
        assert result.output == "done via claude-flow"
        assert result.tokens_used == 500
        mock_bridge.spawn_agent.assert_called_once_with("coder", "fix the bug")


def test_execute_agent_task_bridge_fallback():
    """When bridge is unavailable, execute_agent_task falls back to legacy."""
    from core.claude_flow import ClaudeFlowUnavailable

    with patch("core.agents._get_bridge", side_effect=ClaudeFlowUnavailable("nope")):
        with patch("core.agents._execute_agent_task_legacy") as mock_legacy:
            mock_legacy.return_value = TaskResult(
                agent=AgentType.CODER,
                task="test",
                status="success",
            )
            result = execute_agent_task(AgentType.CODER, "test")
            assert result.status == "success"
            mock_legacy.assert_called_once()
