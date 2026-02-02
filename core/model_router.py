"""Multi-model routing: task complexity classification, model selection, cross-provider fallback.

Quality-First Model Routing
----------------------------
The router selects the best model for each task based on complexity classification.
When budget runs low, the router follows a **quality-first** policy:

- CRITICAL tasks (validation, paper writing, falsification) ALWAYS use Opus,
  regardless of budget.  The router will never downgrade these.
- For non-critical tasks, if budget drops below the configured threshold the
  router does **not** silently switch to a cheaper model.  Instead it:
    * In **interactive mode** -- warns the user and asks for explicit
      confirmation before downgrading.
    * In **autonomous / overnight mode** -- pauses execution and sends a
      notification so a human can decide.
- A ``min_quality_tier`` floor can be configured so the router never selects a
  model below that tier, no matter how low the budget gets.

Every model-selection decision is logged at INFO level so the user can audit
which model was used for which task.

When claude-flow is available, classification and routing delegate to the
bridge's 3-tier model router.  Otherwise, falls back to keyword-based
classification.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data classes
# ---------------------------------------------------------------------------


class TaskComplexity(str, Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    CRITICAL = "critical"


class ModelTier(str, Enum):
    """Quality tiers ordered from lowest to highest.

    Used by ``min_quality_tier`` to set a floor on model selection.
    """

    HAIKU = "haiku"
    SONNET = "sonnet"
    OPUS = "opus"


# Ordered list so we can compare tiers numerically.
_TIER_RANK: dict[ModelTier, int] = {
    ModelTier.HAIKU: 0,
    ModelTier.SONNET: 1,
    ModelTier.OPUS: 2,
}

# Map model keys to their tier.
_MODEL_KEY_TO_TIER: dict[str, ModelTier] = {
    "claude-haiku": ModelTier.HAIKU,
    "claude-sonnet": ModelTier.SONNET,
    "claude-opus": ModelTier.OPUS,
}


class DowngradeAction(str, Enum):
    """Result of a downgrade confirmation request."""

    APPROVED = "approved"
    REJECTED = "rejected"
    PAUSED = "paused"


@dataclass
class ModelConfig:
    """Configuration for a single model.

    Attributes:
        name: Full model identifier (e.g. ``claude-opus-4-5-20251101``).
        provider: Provider key -- ``"anthropic"``, ``"openai"``, or ``"local"``.
        max_tokens: Maximum output tokens supported.
        cost_per_1k_input: Cost in USD per 1 000 input tokens.
        cost_per_1k_output: Cost in USD per 1 000 output tokens.
        supports_thinking: Whether the model supports extended thinking.
        strengths: List of task-type tags the model excels at.
    """

    name: str
    provider: str  # "anthropic", "openai", "local"
    max_tokens: int = 4096
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    supports_thinking: bool = False
    strengths: list[str] = field(default_factory=list)


@dataclass
class RouterConfig:
    """Configuration knobs for the quality-first model router.

    Attributes:
        quality_first: When ``True`` (the default), the router will never
            silently downgrade to a cheaper model.  It will warn / pause
            instead.
        min_quality_tier: The lowest :class:`ModelTier` the router is allowed
            to select.  For example, setting this to ``ModelTier.SONNET``
            means Haiku will never be chosen.
        low_budget_threshold_pct: Budget percentage (0-100) below which the
            router considers the budget "low" and the quality-first policy
            kicks in.
        interactive: ``True`` when a human is at the terminal and can answer
            confirmation prompts.  ``False`` during overnight / autonomous
            runs.
        confirmation_callback: Optional callable invoked to ask the user for
            confirmation.  Signature: ``(message: str) -> bool``.  Return
            ``True`` to approve the downgrade, ``False`` to reject.
            If ``None`` and ``interactive`` is ``True``, a default
            stdin-based prompt is used.
        pause_callback: Optional callable invoked in autonomous mode when the
            router would need to downgrade a non-critical task.
            Signature: ``(message: str) -> None``.  It should notify the
            operator and block or raise so execution does not continue with
            a degraded model.
    """

    quality_first: bool = True
    min_quality_tier: ModelTier = ModelTier.HAIKU
    low_budget_threshold_pct: float = 20.0
    interactive: bool = True
    confirmation_callback: Optional[object] = None  # Callable[[str], bool]
    pause_callback: Optional[object] = None  # Callable[[str], None]


# Module-level default config.  Callers can replace this or pass overrides to
# ``route_to_model``.
_router_config = RouterConfig()


def configure_router(config: RouterConfig) -> None:
    """Replace the module-level router configuration.

    Args:
        config: New :class:`RouterConfig` to use for all subsequent calls
            to :func:`route_to_model`.
    """
    global _router_config
    _router_config = config
    logger.info(
        "Router reconfigured: quality_first=%s, min_quality_tier=%s, "
        "low_budget_threshold=%.1f%%, interactive=%s",
        config.quality_first,
        config.min_quality_tier.value,
        config.low_budget_threshold_pct,
        config.interactive,
    )


# ---------------------------------------------------------------------------
# Keyword sets for complexity classification
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Default model configs
# ---------------------------------------------------------------------------

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
        name="claude-3-5-haiku-20241022",
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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _tier_of(model_key: str) -> ModelTier:
    """Return the :class:`ModelTier` for a model key, defaulting to OPUS."""
    return _MODEL_KEY_TO_TIER.get(model_key, ModelTier.OPUS)


def _is_below_floor(model_key: str, floor: ModelTier) -> bool:
    """Return ``True`` if *model_key* is below the *floor* tier."""
    return _TIER_RANK[_tier_of(model_key)] < _TIER_RANK[floor]


def _enforce_floor(model_key: str, floor: ModelTier) -> str:
    """Return *model_key* raised to at least *floor* tier if necessary."""
    if _is_below_floor(model_key, floor):
        # Find the cheapest model that meets the floor.
        for key, tier in _MODEL_KEY_TO_TIER.items():
            if _TIER_RANK[tier] >= _TIER_RANK[floor]:
                logger.info(
                    "Model '%s' is below min_quality_tier '%s'; " "raising to '%s'.",
                    model_key,
                    floor.value,
                    key,
                )
                return key
    return model_key


def _default_confirm(message: str) -> bool:
    """Default interactive confirmation via stdin."""
    try:
        answer = input(f"\n{message} [y/N]: ").strip().lower()
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def _default_pause(message: str) -> None:
    """Default autonomous-mode pause: log a critical message and raise."""
    logger.critical("PAUSED -- %s", message)
    from core.notifications import notify

    try:
        notify(
            title="Model Router: Budget Low -- Action Required",
            body=message,
            level="critical",
        )
    except Exception:
        # Notification delivery is best-effort; never crash the router.
        logger.warning("Failed to send pause notification.")

    raise BudgetPauseError(message)


class BudgetPauseError(Exception):
    """Raised in autonomous mode when the budget is too low and the router
    refuses to silently downgrade.

    Callers (e.g. the overnight loop) should catch this, save a checkpoint,
    and wait for human intervention.
    """


def _handle_low_budget_downgrade(
    ideal_model_key: str,
    cheap_model_key: str,
    complexity: TaskComplexity,
    description: str,
    budget_remaining_pct: float,
    config: RouterConfig,
) -> str:
    """Decide what to do when budget is low and a downgrade is proposed.

    For CRITICAL tasks, the downgrade is always refused and the ideal model
    is returned.

    For non-critical tasks under the quality-first policy:
    - Interactive mode: ask the user for confirmation.
    - Autonomous mode: pause and notify.

    If quality_first is disabled, the cheap model is returned silently
    (legacy behaviour).

    Returns:
        The model key to use.
    """
    if complexity == TaskComplexity.CRITICAL:
        logger.warning(
            "Budget is low (%.1f%%), but task is CRITICAL -- "
            "refusing to downgrade from '%s'. "
            "Task: %.120s",
            budget_remaining_pct,
            ideal_model_key,
            description,
        )
        return ideal_model_key

    if not config.quality_first:
        # Legacy behaviour: silent downgrade.
        logger.info(
            "Budget low (%.1f%%), quality_first OFF -- downgrading "
            "from '%s' to '%s'. Task: %.120s",
            budget_remaining_pct,
            ideal_model_key,
            cheap_model_key,
            description,
        )
        return cheap_model_key

    # --- Quality-first path ---
    warning_msg = (
        f"Budget is low ({budget_remaining_pct:.1f}% remaining). "
        f"The router wants to downgrade from '{ideal_model_key}' to "
        f"'{cheap_model_key}' for task: {description[:120]}"
    )
    logger.warning(warning_msg)

    if config.interactive:
        confirm_fn = config.confirmation_callback or _default_confirm
        prompt_msg = (
            f"WARNING: Budget is low ({budget_remaining_pct:.1f}% remaining).\n"
            f"The system wants to switch from {ideal_model_key} to "
            f"{cheap_model_key} for this task.\n"
            f"Task: {description[:200]}\n\n"
            f"Approve downgrade?"
        )
        approved = confirm_fn(prompt_msg)
        if approved:
            logger.info(
                "User approved downgrade from '%s' to '%s'.",
                ideal_model_key,
                cheap_model_key,
            )
            return cheap_model_key
        else:
            logger.info(
                "User rejected downgrade -- keeping '%s'.",
                ideal_model_key,
            )
            return ideal_model_key
    else:
        # Autonomous mode: pause and notify.
        pause_fn = config.pause_callback or _default_pause
        pause_msg = (
            f"Budget is low ({budget_remaining_pct:.1f}% remaining). "
            f"Cannot silently downgrade from '{ideal_model_key}' to "
            f"'{cheap_model_key}' in quality-first mode. "
            f"Task: {description[:200]}. "
            f"Human intervention required."
        )
        pause_fn(pause_msg)
        # If pause_fn returns instead of raising, keep the ideal model.
        return ideal_model_key


# ---------------------------------------------------------------------------
# Complexity classification
# ---------------------------------------------------------------------------


def _classify_task_complexity_claude(description: str) -> TaskComplexity | None:
    """Try classifying task complexity via the Claude CLI.

    Sends a short prompt asking Claude to reply with exactly one word:
    ``simple``, ``medium``, ``complex``, or ``critical``.

    Returns:
        The parsed :class:`TaskComplexity`, or ``None`` if the call fails or
        returns an unexpected value.
    """
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

    Tries claude-flow's 3-tier router first, then the Claude CLI, and falls
    back to keyword matching.

    Args:
        description: Natural-language task description.

    Returns:
        The determined :class:`TaskComplexity` level.
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
    """Keyword-based complexity classification (legacy fallback).

    Scans *description* for known keyword sets and returns the highest
    matching complexity.  Defaults to ``MEDIUM`` when no keywords match.
    """
    words = set(description.lower().split())

    if words & _CRITICAL_KEYWORDS:
        return TaskComplexity.CRITICAL
    if words & _COMPLEX_KEYWORDS:
        return TaskComplexity.COMPLEX
    if words & _SIMPLE_KEYWORDS:
        return TaskComplexity.SIMPLE
    return TaskComplexity.MEDIUM


# ---------------------------------------------------------------------------
# Model routing (public API)
# ---------------------------------------------------------------------------


def route_to_model(
    description: str,
    *,
    complexity: Optional[TaskComplexity] = None,
    prefer_provider: str = "anthropic",
    budget_remaining_pct: float = 100.0,
    config: Optional[RouterConfig] = None,
) -> ModelConfig:
    """Select the best model for a task using the quality-first policy.

    The selection process:

    1. If claude-flow is available, ask the bridge for a routing decision.
    2. Otherwise, fall back to keyword-based classification.
    3. If the budget is low (below ``config.low_budget_threshold_pct``):
       - CRITICAL tasks are **never** downgraded -- they always use Opus.
       - Non-critical tasks: in interactive mode the user is warned and asked
         for confirmation; in autonomous mode the router pauses and notifies.
    4. The final model is clamped to ``config.min_quality_tier`` so the router
       never selects a model below the configured floor.
    5. Every decision is logged at INFO level for auditing.

    Args:
        description: Natural-language task description.
        complexity: Pre-classified complexity.  Auto-classified if ``None``.
        prefer_provider: Preferred provider key (currently only
            ``"anthropic"`` is supported).
        budget_remaining_pct: Remaining budget as a percentage (0--100).
        config: Optional :class:`RouterConfig` override.  Uses the
            module-level config if ``None``.

    Returns:
        The selected :class:`ModelConfig`.

    Raises:
        BudgetPauseError: In autonomous mode when the budget is low and
            quality-first mode prevents a silent downgrade.
    """
    cfg = config or _router_config

    # Classify if needed.
    if complexity is None:
        complexity = classify_task_complexity(description)

    # --- Try bridge routing first ---
    try:
        bridge = _get_bridge()
        result = bridge.route_model(description)
        model_name = result.get("model", "")
        bridge_model_key: Optional[str] = None
        for key, mcfg in DEFAULT_MODELS.items():
            if mcfg.name == model_name:
                bridge_model_key = key
                break

        if bridge_model_key is not None:
            if budget_remaining_pct < cfg.low_budget_threshold_pct:
                chosen_key = _handle_low_budget_downgrade(
                    ideal_model_key=bridge_model_key,
                    cheap_model_key="claude-haiku",
                    complexity=complexity,
                    description=description,
                    budget_remaining_pct=budget_remaining_pct,
                    config=cfg,
                )
            else:
                chosen_key = bridge_model_key

            chosen_key = _enforce_floor(chosen_key, cfg.min_quality_tier)
            selected = DEFAULT_MODELS[chosen_key]
            logger.info(
                "MODEL SELECTED (bridge): model='%s', tier='%s', "
                "complexity='%s', budget=%.1f%%, task='%.120s'",
                selected.name,
                _tier_of(chosen_key).value,
                complexity.value,
                budget_remaining_pct,
                description,
            )
            return selected
    except (ClaudeFlowUnavailable, KeyError):
        pass

    # --- Keyword-based fallback ---
    return _route_to_model_keywords(
        description,
        complexity=complexity,
        budget_remaining_pct=budget_remaining_pct,
        config=cfg,
    )


def _route_to_model_keywords(
    description: str,
    *,
    complexity: Optional[TaskComplexity] = None,
    budget_remaining_pct: float = 100.0,
    config: Optional[RouterConfig] = None,
) -> ModelConfig:
    """Keyword-based model selection (legacy fallback).

    Applies the same quality-first policy and ``min_quality_tier`` floor
    as the bridge-based path.

    Args:
        description: Task description.
        complexity: Pre-classified complexity (auto-classified if ``None``).
        budget_remaining_pct: Remaining budget percentage (0--100).
        config: Optional router config override.

    Returns:
        The selected :class:`ModelConfig`.
    """
    cfg = config or _router_config

    if complexity is None:
        complexity = _classify_task_complexity_keywords(description)

    complexity_to_model = {
        TaskComplexity.SIMPLE: "claude-haiku",
        TaskComplexity.MEDIUM: "claude-sonnet",
        TaskComplexity.COMPLEX: "claude-opus",
        TaskComplexity.CRITICAL: "claude-opus",
    }
    ideal_key = complexity_to_model[complexity]

    if budget_remaining_pct < cfg.low_budget_threshold_pct:
        chosen_key = _handle_low_budget_downgrade(
            ideal_model_key=ideal_key,
            cheap_model_key="claude-haiku",
            complexity=complexity,
            description=description,
            budget_remaining_pct=budget_remaining_pct,
            config=cfg,
        )
    else:
        chosen_key = ideal_key

    chosen_key = _enforce_floor(chosen_key, cfg.min_quality_tier)
    selected = DEFAULT_MODELS[chosen_key]
    logger.info(
        "MODEL SELECTED (keywords): model='%s', tier='%s', "
        "complexity='%s', budget=%.1f%%, task='%.120s'",
        selected.name,
        _tier_of(chosen_key).value,
        complexity.value,
        budget_remaining_pct,
        description,
    )
    return selected


# ---------------------------------------------------------------------------
# Fallback chain
# ---------------------------------------------------------------------------


def get_fallback_model(
    current_model: str,
    provider: str = "anthropic",
) -> Optional[ModelConfig]:
    """Get the next fallback model in the provider's chain.

    Used when an API call to the current model fails (e.g. rate-limited or
    unavailable).  The fallback respects ``min_quality_tier`` -- it will not
    fall below the configured floor.

    Args:
        current_model: Key of the current model that failed (e.g.
            ``"claude-opus"``).
        provider: Provider to search for fallbacks.

    Returns:
        The next :class:`ModelConfig` in the fallback chain, or ``None`` if
        the chain is exhausted or the next fallback would be below the
        quality floor.
    """
    chain = FALLBACK_CHAINS.get(provider, [])
    if current_model not in chain:
        return None
    idx = chain.index(current_model)
    if idx + 1 < len(chain):
        next_key = chain[idx + 1]
        if _is_below_floor(next_key, _router_config.min_quality_tier):
            logger.info(
                "Fallback '%s' is below min_quality_tier '%s'; "
                "no further fallback available.",
                next_key,
                _router_config.min_quality_tier.value,
            )
            return None
        logger.info(
            "Falling back from '%s' to '%s'.",
            current_model,
            next_key,
        )
        return DEFAULT_MODELS[next_key]
    return None
