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
