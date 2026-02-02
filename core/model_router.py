"""Multi-model routing: task complexity classification, model selection, cross-provider fallback.

When claude-flow is available, classification and routing delegate to the bridge's
3-tier model router. Otherwise, falls back to keyword-based classification.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

logger = logging.getLogger(__name__)


class TaskComplexity(str, Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    CRITICAL = "critical"


@dataclass
class ModelConfig:
    name: str
    provider: str  # "anthropic", "openai", "local"
    max_tokens: int = 4096
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    supports_thinking: bool = False
    strengths: list[str] = field(default_factory=list)


# Keyword sets for complexity classification
_SIMPLE_KEYWORDS = {
    "format",
    "list",
    "lookup",
    "rename",
    "move",
    "copy",
    "count",
    "sort",
    "print",
    "echo",
    "display",
    "show",
}
_COMPLEX_KEYWORDS = {
    "debug",
    "design",
    "architect",
    "research",
    "analyze",
    "investigate",
    "compare",
    "benchmark",
    "profile",
    "optimize",
}
_CRITICAL_KEYWORDS = {
    "validate",
    "prove",
    "paper",
    "publish",
    "submit",
    "security",
    "audit",
    "falsify",
    "verify",
    "production",
}

# Default model configs
DEFAULT_MODELS = {
    "claude-opus": ModelConfig(
        name="claude-opus-4-5-20251101",
        provider="anthropic",
        max_tokens=8192,
        cost_per_1k_input=0.015,
        cost_per_1k_output=0.075,
        supports_thinking=True,
        strengths=["reasoning", "code", "writing", "analysis"],
    ),
    "claude-sonnet": ModelConfig(
        name="claude-sonnet-4-20250514",
        provider="anthropic",
        max_tokens=8192,
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
        supports_thinking=True,
        strengths=["code", "speed", "general"],
    ),
    "claude-haiku": ModelConfig(
        name="claude-haiku-3-5-20241022",
        provider="anthropic",
        max_tokens=4096,
        cost_per_1k_input=0.001,
        cost_per_1k_output=0.005,
        supports_thinking=False,
        strengths=["speed", "simple-tasks", "classification"],
    ),
}

# Fallback chain per provider
FALLBACK_CHAINS: dict[str, list[str]] = {
    "anthropic": ["claude-opus", "claude-sonnet", "claude-haiku"],
}


def _classify_task_complexity_claude(description: str) -> TaskComplexity | None:
    """Try classifying via Claude CLI."""
    from core.claude_helper import call_claude

    prompt = (
        "Is this task simple, medium, complex, or critical? "
        "Reply with exactly one word.\n\n"
        f"Task: {description[:500]}"
    )
    result = call_claude(prompt)
    if result:
        word = result.strip().lower().split()[0] if result.strip() else ""
        if word in {c.value for c in TaskComplexity}:
            return TaskComplexity(word)
    return None


def classify_task_complexity(description: str) -> TaskComplexity:
    """Classify a task's complexity.

    Tries claude-flow's 3-tier router first, then Claude CLI, falls back to keyword matching.

    Args:
        description: Natural language task description.

    Returns:
        TaskComplexity level.
    """
    try:
        bridge = _get_bridge()
        result = bridge.route_model(description)
        tier = result.get("tier", "")
        tier_to_complexity = {
            "booster": TaskComplexity.SIMPLE,
            "workhorse": TaskComplexity.MEDIUM,
            "oracle": TaskComplexity.COMPLEX,
        }
        complexity_str = result.get("complexity", "")
        if complexity_str in {c.value for c in TaskComplexity}:
            return TaskComplexity(complexity_str)
        if tier in tier_to_complexity:
            return tier_to_complexity[tier]
    except (ClaudeFlowUnavailable, KeyError, ValueError):
        pass

    # Try Claude CLI
    claude_result = _classify_task_complexity_claude(description)
    if claude_result is not None:
        return claude_result

    return _classify_task_complexity_keywords(description)


def _classify_task_complexity_keywords(description: str) -> TaskComplexity:
    """Keyword-based complexity classification (legacy fallback)."""
    words = set(description.lower().split())

    if words & _CRITICAL_KEYWORDS:
        return TaskComplexity.CRITICAL
    if words & _COMPLEX_KEYWORDS:
        return TaskComplexity.COMPLEX
    if words & _SIMPLE_KEYWORDS:
        return TaskComplexity.SIMPLE
    return TaskComplexity.MEDIUM


def route_to_model(
    description: str,
    *,
    complexity: Optional[TaskComplexity] = None,
    prefer_provider: str = "anthropic",
    budget_remaining_pct: float = 100.0,
) -> ModelConfig:
    """Select the best model for a task.

    Tries claude-flow routing first, falls back to keyword-based selection.

    Args:
        description: Task description.
        complexity: Pre-classified complexity (auto-classifies if None).
        prefer_provider: Preferred provider.
        budget_remaining_pct: Remaining budget percentage (0-100).

    Returns:
        Selected ModelConfig.
    """
    # Try bridge routing
    try:
        bridge = _get_bridge()
        result = bridge.route_model(description)
        model_name = result.get("model", "")
        for key, cfg in DEFAULT_MODELS.items():
            if cfg.name == model_name:
                # Still respect budget override
                if budget_remaining_pct < 20:
                    return DEFAULT_MODELS["claude-haiku"]
                return cfg
    except (ClaudeFlowUnavailable, KeyError):
        pass

    return _route_to_model_keywords(
        description,
        complexity=complexity,
        budget_remaining_pct=budget_remaining_pct,
    )


def _route_to_model_keywords(
    description: str,
    *,
    complexity: Optional[TaskComplexity] = None,
    budget_remaining_pct: float = 100.0,
) -> ModelConfig:
    """Keyword-based model selection (legacy fallback)."""
    if complexity is None:
        complexity = _classify_task_complexity_keywords(description)

    if budget_remaining_pct < 20:
        return DEFAULT_MODELS["claude-haiku"]

    complexity_to_model = {
        TaskComplexity.SIMPLE: "claude-haiku",
        TaskComplexity.MEDIUM: "claude-sonnet",
        TaskComplexity.COMPLEX: "claude-opus",
        TaskComplexity.CRITICAL: "claude-opus",
    }

    model_key = complexity_to_model[complexity]
    return DEFAULT_MODELS[model_key]


def get_fallback_model(
    current_model: str,
    provider: str = "anthropic",
) -> Optional[ModelConfig]:
    """Get the next fallback model in the chain.

    Args:
        current_model: Key of the current model that failed.
        provider: Provider to use for fallback.

    Returns:
        Next ModelConfig in fallback chain, or None if exhausted.
    """
    chain = FALLBACK_CHAINS.get(provider, [])
    if current_model not in chain:
        return None
    idx = chain.index(current_model)
    if idx + 1 < len(chain):
        return DEFAULT_MODELS[chain[idx + 1]]
    return None
