"""Token estimation and budget tracking.

When claude-flow is available, uses bridge metrics for accurate token counts
and complexity-based thinking mode selection.
"""

import logging
from dataclasses import dataclass

from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

logger = logging.getLogger(__name__)


@dataclass
class TokenBudget:
    session_limit: int = 100_000  # Tokens per session
    daily_limit: int = 500_000  # Tokens per day
    current_session: int = 0
    current_daily: int = 0


def estimate_tokens(text: str) -> int:
    """Estimate token count.

    Tries claude-flow metrics for actual counts, falls back to ~4 chars/token.
    """
    try:
        bridge = _get_bridge()
        metrics = bridge.get_metrics()
        actual = metrics.get("tokens_used")
        if actual is not None and isinstance(actual, int):
            return actual
    except ClaudeFlowUnavailable:
        pass

    return len(text) // 4


def check_budget(budget: TokenBudget, estimated_cost: int) -> dict:
    """Check if operation is within budget.

    Uses bridge session metrics when available for more accurate tracking.
    """
    try:
        bridge = _get_bridge()
        metrics = bridge.get_metrics()
        session_used = metrics.get("session_tokens", None)
        daily_used = metrics.get("daily_tokens", None)
        if session_used is not None:
            budget.current_session = session_used
        if daily_used is not None:
            budget.current_daily = daily_used
    except ClaudeFlowUnavailable:
        pass

    session_remaining = budget.session_limit - budget.current_session
    daily_remaining = budget.daily_limit - budget.current_daily

    return {
        "can_proceed": estimated_cost < min(session_remaining, daily_remaining),
        "session_used_pct": (budget.current_session / budget.session_limit) * 100,
        "daily_used_pct": (budget.current_daily / budget.daily_limit) * 100,
        "warning": budget.current_session > budget.session_limit * 0.75,
    }


def select_thinking_mode(task_description: str) -> str:
    """Auto-select thinking mode based on task complexity.

    When claude-flow is available, uses the bridge's complexity tier:
    booster -> none, workhorse -> standard, oracle -> extended/ultrathink.
    """
    try:
        bridge = _get_bridge()
        result = bridge.route_model(task_description)
        tier = result.get("tier", "")
        complexity = result.get("complexity", "")
        if complexity == "critical" or tier == "oracle":
            # Distinguish critical from complex by keyword check
            task_lower = task_description.lower()
            critical_kw = ["validate", "prove", "paper", "publish", "final", "submit"]
            if any(kw in task_lower for kw in critical_kw):
                return "ultrathink"
            return "extended"
        if tier == "booster":
            return "none"
        if tier == "workhorse":
            return "standard"
    except ClaudeFlowUnavailable:
        pass

    return _select_thinking_mode_keywords(task_description)


def _select_thinking_mode_keywords(task_description: str) -> str:
    """Keyword-based thinking mode selection (legacy fallback)."""
    task_lower = task_description.lower()

    critical_keywords = ["validate", "prove", "paper", "publish", "final", "submit"]
    if any(kw in task_lower for kw in critical_keywords):
        return "ultrathink"

    complex_keywords = ["debug", "design", "architecture", "research", "why", "investigate"]
    if any(kw in task_lower for kw in complex_keywords):
        return "extended"

    simple_keywords = ["format", "list", "show", "what is", "lookup", "find"]
    if any(kw in task_lower for kw in simple_keywords):
        return "none"

    return "standard"
