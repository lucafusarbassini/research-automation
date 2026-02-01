"""Token estimation and budget tracking."""

from dataclasses import dataclass


@dataclass
class TokenBudget:
    session_limit: int = 100_000  # Tokens per session
    daily_limit: int = 500_000  # Tokens per day
    current_session: int = 0
    current_daily: int = 0


def estimate_tokens(text: str) -> int:
    """Estimate token count (~4 chars per token)."""
    return len(text) // 4


def check_budget(budget: TokenBudget, estimated_cost: int) -> dict:
    """Check if operation is within budget."""
    session_remaining = budget.session_limit - budget.current_session
    daily_remaining = budget.daily_limit - budget.current_daily

    return {
        "can_proceed": estimated_cost < min(session_remaining, daily_remaining),
        "session_used_pct": (budget.current_session / budget.session_limit) * 100,
        "daily_used_pct": (budget.current_daily / budget.daily_limit) * 100,
        "warning": budget.current_session > budget.session_limit * 0.75,
    }


def select_thinking_mode(task_description: str) -> str:
    """Auto-select thinking mode based on task complexity."""
    task_lower = task_description.lower()

    # CRITICAL tasks
    critical_keywords = ["validate", "prove", "paper", "publish", "final", "submit"]
    if any(kw in task_lower for kw in critical_keywords):
        return "ultrathink"  # Max budget

    # COMPLEX tasks
    complex_keywords = ["debug", "design", "architecture", "research", "why", "investigate"]
    if any(kw in task_lower for kw in complex_keywords):
        return "extended"  # 3% budget

    # SIMPLE tasks
    simple_keywords = ["format", "list", "show", "what is", "lookup", "find"]
    if any(kw in task_lower for kw in simple_keywords):
        return "none"  # No extended thinking

    # Default to MEDIUM
    return "standard"
