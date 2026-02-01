"""Tests for token estimation and budget tracking."""

from core.tokens import TokenBudget, check_budget, estimate_tokens, select_thinking_mode


def test_estimate_tokens_empty():
    assert estimate_tokens("") == 0


def test_estimate_tokens_short():
    # 12 chars -> ~3 tokens
    assert estimate_tokens("hello world!") == 3


def test_estimate_tokens_longer():
    text = "a" * 400
    assert estimate_tokens(text) == 100


def test_check_budget_within_limits():
    budget = TokenBudget(session_limit=1000, daily_limit=5000)
    result = check_budget(budget, estimated_cost=100)
    assert result["can_proceed"] is True
    assert result["warning"] is False


def test_check_budget_exceeds_session():
    budget = TokenBudget(session_limit=1000, daily_limit=5000, current_session=950)
    result = check_budget(budget, estimated_cost=100)
    assert result["can_proceed"] is False
    assert result["warning"] is True


def test_check_budget_exceeds_daily():
    budget = TokenBudget(session_limit=10000, daily_limit=500, current_daily=450)
    result = check_budget(budget, estimated_cost=100)
    assert result["can_proceed"] is False


def test_check_budget_warning_at_75_pct():
    budget = TokenBudget(session_limit=1000, current_session=760)
    result = check_budget(budget, estimated_cost=10)
    assert result["warning"] is True


def test_select_thinking_mode_critical():
    assert select_thinking_mode("validate the final results") == "ultrathink"
    assert select_thinking_mode("submit the paper") == "ultrathink"


def test_select_thinking_mode_complex():
    assert select_thinking_mode("debug this segfault") == "extended"
    assert select_thinking_mode("investigate why loss is NaN") == "extended"


def test_select_thinking_mode_simple():
    assert select_thinking_mode("format this table") == "none"
    assert select_thinking_mode("show the config") == "none"


def test_select_thinking_mode_default():
    assert select_thinking_mode("process the dataset") == "standard"


# --- Bridge-integrated tests ---

from unittest.mock import MagicMock, patch

from core.tokens import _select_thinking_mode_keywords


def test_estimate_tokens_via_bridge():
    mock_bridge = MagicMock()
    mock_bridge.get_metrics.return_value = {"tokens_used": 42}
    with patch("core.tokens._get_bridge", return_value=mock_bridge):
        assert estimate_tokens("ignored text") == 42


def test_estimate_tokens_bridge_fallback():
    from core.claude_flow import ClaudeFlowUnavailable
    with patch("core.tokens._get_bridge", side_effect=ClaudeFlowUnavailable("no")):
        assert estimate_tokens("abcd" * 25) == 25


def test_check_budget_via_bridge():
    mock_bridge = MagicMock()
    mock_bridge.get_metrics.return_value = {"session_tokens": 800, "daily_tokens": 400}
    with patch("core.tokens._get_bridge", return_value=mock_bridge):
        budget = TokenBudget(session_limit=1000, daily_limit=5000)
        result = check_budget(budget, estimated_cost=100)
        assert result["can_proceed"] is True
        assert budget.current_session == 800


def test_select_thinking_mode_via_bridge():
    mock_bridge = MagicMock()
    mock_bridge.route_model.return_value = {"tier": "booster", "complexity": "simple"}
    with patch("core.tokens._get_bridge", return_value=mock_bridge):
        assert select_thinking_mode("anything") == "none"


def test_select_thinking_mode_bridge_oracle_critical():
    mock_bridge = MagicMock()
    mock_bridge.route_model.return_value = {"tier": "oracle", "complexity": "critical"}
    with patch("core.tokens._get_bridge", return_value=mock_bridge):
        assert select_thinking_mode("validate the paper") == "ultrathink"


def test_select_thinking_mode_bridge_oracle_complex():
    mock_bridge = MagicMock()
    mock_bridge.route_model.return_value = {"tier": "oracle", "complexity": "complex"}
    with patch("core.tokens._get_bridge", return_value=mock_bridge):
        assert select_thinking_mode("debug memory leak") == "extended"


def test_select_thinking_mode_keywords_fallback():
    assert _select_thinking_mode_keywords("format table") == "none"
    assert _select_thinking_mode_keywords("validate results") == "ultrathink"
