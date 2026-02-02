"""Prompt suggestions and predictive follow-ups module.

Provides intelligent next-step suggestions, follow-up prompt generation,
stuck-pattern detection, task decomposition, and context compression.

Philosophy: "Break down large problems into smaller ones" and
"AI context is like milk; best served fresh and condensed."
"""

import logging
import re
from collections import Counter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# COMMON_PATTERNS: maps task types to typical follow-up sequences
# ---------------------------------------------------------------------------

COMMON_PATTERNS: dict[str, list[str]] = {
    "research": [
        "Gather and survey existing literature",
        "Identify key themes and gaps",
        "Formulate research questions",
        "Design methodology",
        "Collect and analyze data",
        "Synthesize findings and write up",
    ],
    "implementation": [
        "Define requirements and acceptance criteria",
        "Design architecture and interfaces",
        "Implement core logic",
        "Write unit and integration tests",
        "Refactor and optimize",
        "Document and ship",
    ],
    "debugging": [
        "Reproduce the issue reliably",
        "Gather logs and error messages",
        "Formulate hypotheses",
        "Isolate the root cause",
        "Implement and verify the fix",
        "Add regression tests",
    ],
    "review": [
        "Read through the changeset for understanding",
        "Check correctness and edge cases",
        "Evaluate test coverage",
        "Assess performance implications",
        "Verify documentation updates",
        "Provide actionable feedback",
    ],
    "deployment": [
        "Run pre-deployment checks",
        "Back up current state",
        "Deploy to staging and smoke-test",
        "Deploy to production",
        "Monitor metrics and logs",
        "Communicate status to stakeholders",
    ],
    "writing": [
        "Outline the structure",
        "Write the first draft",
        "Revise for clarity and flow",
        "Get peer feedback",
        "Final polish and proofread",
    ],
}

# Keywords used to match a task description to a pattern category.
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "research": [
        "research",
        "survey",
        "literature",
        "study",
        "explore",
        "investigate",
        "analyze data",
    ],
    "implementation": [
        "implement",
        "build",
        "create",
        "develop",
        "code",
        "feature",
        "module",
        "function",
    ],
    "debugging": [
        "debug",
        "fix",
        "bug",
        "error",
        "issue",
        "broken",
        "failing",
        "crash",
    ],
    "review": ["review", "PR", "pull request", "code review", "feedback", "audit"],
    "deployment": ["deploy", "release", "ship", "rollout", "CI", "CD", "pipeline"],
    "writing": ["write", "document", "draft", "blog", "paper", "README", "docs"],
}


def _match_category(text: str) -> str | None:
    """Match text against known task categories using keyword heuristics."""
    text_lower = text.lower()
    best_category = None
    best_count = 0
    for category, keywords in _CATEGORY_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw.lower() in text_lower)
        if count > best_count:
            best_count = count
            best_category = category
    return best_category if best_count > 0 else None


# ---------------------------------------------------------------------------
# suggest_next_steps
# ---------------------------------------------------------------------------


def _suggest_next_steps_claude(
    current_task: str,
    progress: list[str],
    goal: str,
) -> list[str] | None:
    """Try getting next steps from Claude CLI."""
    from core.claude_helper import call_claude_json

    progress_text = "; ".join(progress[-5:]) if progress else "none"
    prompt = (
        "Given this progress and goal, suggest 3-5 concrete next steps. "
        "Return a JSON array of strings.\n\n"
        f"Current task: {current_task[:200]}\n"
        f"Progress so far: {progress_text}\n"
        f"Goal: {goal[:200]}"
    )
    result = call_claude_json(prompt)
    if result and isinstance(result, list) and len(result) >= 3:
        return [str(s) for s in result[:5]]
    return None


def suggest_next_steps(
    current_task: str,
    progress: list[str],
    goal: str,
) -> list[str]:
    """Given the current task state, suggest 3-5 logical next steps.

    Tries Claude CLI first, falls back to keyword-based pattern matching.

    Args:
        current_task: Description of the task currently being worked on.
        progress: List of steps already completed.
        goal: The overarching goal.

    Returns:
        A list of 3-5 suggested next steps as plain-English strings.
    """
    # Try Claude CLI
    claude_result = _suggest_next_steps_claude(current_task, progress, goal)
    if claude_result is not None:
        return claude_result

    suggestions: list[str] = []

    # Try to match to a known pattern and pick steps after current progress.
    category = _match_category(current_task) or _match_category(goal)
    if category and category in COMMON_PATTERNS:
        pattern_steps = COMMON_PATTERNS[category]
        # Skip steps that look already done (fuzzy match against progress).
        remaining = _filter_remaining_steps(pattern_steps, progress)
        suggestions.extend(remaining)

    # Always add generic but useful suggestions derived from the inputs.
    generic = _generate_generic_suggestions(current_task, progress, goal)
    for g in generic:
        if g not in suggestions:
            suggestions.append(g)

    # Ensure we return exactly 3-5.
    if len(suggestions) < 3:
        fillers = [
            f"Validate that '{goal}' acceptance criteria are met",
            "Review work done so far for completeness",
            "Document decisions and rationale",
            "Identify risks or blockers",
            "Get feedback from a collaborator",
        ]
        for f in fillers:
            if f not in suggestions:
                suggestions.append(f)
            if len(suggestions) >= 3:
                break

    return suggestions[:5]


def _filter_remaining_steps(pattern_steps: list[str], progress: list[str]) -> list[str]:
    """Return pattern steps that have not yet been accomplished."""
    progress_lower = {p.lower() for p in progress}
    remaining: list[str] = []
    for step in pattern_steps:
        # Fuzzy: skip if any progress item shares significant words.
        step_words = set(re.findall(r"\w{4,}", step.lower()))
        already_done = any(
            len(step_words & set(re.findall(r"\w{4,}", p))) >= 2 for p in progress_lower
        )
        if not already_done:
            remaining.append(step)
    return remaining


def _generate_generic_suggestions(
    current_task: str,
    progress: list[str],
    goal: str,
) -> list[str]:
    """Produce generic next-step suggestions based on context."""
    suggestions: list[str] = []

    if not progress:
        suggestions.append(f"Break '{current_task}' into smaller, testable steps")
    else:
        last = progress[-1]
        suggestions.append(f"Verify the outcome of: {last}")

    suggestions.append(f"Identify what remains between current state and '{goal}'")
    suggestions.append(f"Write or update tests related to '{current_task}'")
    return suggestions


# ---------------------------------------------------------------------------
# generate_follow_up_prompts
# ---------------------------------------------------------------------------


def generate_follow_up_prompts(
    completed_task: str,
    result: str,
) -> list[str]:
    """After a task completes, suggest relevant follow-up prompts.

    Args:
        completed_task: Description of what was just finished.
        result: The outcome or output of the task.

    Returns:
        A list of follow-up prompt strings the user might want to run next.
    """
    prompts: list[str] = []

    # Pattern-based follow-ups.
    category = _match_category(completed_task)
    if category and category in COMMON_PATTERNS:
        steps = COMMON_PATTERNS[category]
        # Suggest the last few steps as prompts.
        for step in steps[-3:]:
            prompts.append(f"Now {step.lower()}")

    # Result-aware follow-ups.
    if "error" in result.lower() or "fail" in result.lower():
        prompts.append(
            f"Investigate why '{completed_task}' produced errors: {result[:120]}"
        )
    if (
        "success" in result.lower()
        or "passing" in result.lower()
        or "deployed" in result.lower()
    ):
        prompts.append(f"Run a broader validation after: {completed_task}")
        prompts.append("Update documentation to reflect the changes")

    # Generic follow-ups.
    prompts.append(f"Summarize what was accomplished in '{completed_task}'")
    prompts.append(f"Identify follow-on tasks after completing '{completed_task}'")

    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for p in prompts:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    return unique


# ---------------------------------------------------------------------------
# detect_stuck_pattern
# ---------------------------------------------------------------------------


def detect_stuck_pattern(history: list[str]) -> bool:
    """Detect if the user/agent is going in circles.

    Looks for repeated subsequences in the action history. A cycle of length
    N is detected when the same ordered subsequence appears at least twice
    in the recent history.

    Args:
        history: Ordered list of action descriptions (most recent last).

    Returns:
        True if a repetitive loop is detected.
    """
    if len(history) < 4:
        return False

    # Normalize entries for comparison.
    normalized = [h.strip().lower() for h in history]

    # Check for cycles of length 1..len//2.
    for cycle_len in range(1, len(normalized) // 2 + 1):
        # Slide a window and count how many times the same subsequence repeats.
        subseqs: list[tuple[str, ...]] = []
        for i in range(0, len(normalized) - cycle_len + 1):
            subseqs.append(tuple(normalized[i : i + cycle_len]))

        counts = Counter(subseqs)
        most_common_count = counts.most_common(1)[0][1]
        if most_common_count >= 3 and cycle_len <= 3:
            return True
        if most_common_count >= 2 and cycle_len >= 2:
            return True

    return False


# ---------------------------------------------------------------------------
# suggest_decomposition
# ---------------------------------------------------------------------------


def suggest_decomposition(complex_task: str) -> list[str]:
    """Break a complex task into smaller, actionable subtasks.

    Philosophy: "Break down large problems into smaller ones."

    Args:
        complex_task: A description of a large or complex task.

    Returns:
        An ordered list of subtask descriptions.
    """
    subtasks: list[str] = []

    # 1. Always start with understanding.
    subtasks.append(f"Clarify requirements and scope for: {complex_task}")

    # 2. Try to match a known pattern for more specific breakdown.
    category = _match_category(complex_task)
    if category and category in COMMON_PATTERNS:
        for step in COMMON_PATTERNS[category][1:]:  # skip first since we added clarify
            subtasks.append(step)
    else:
        # Generic decomposition for unrecognised tasks.
        subtasks.append("Research existing solutions and prior art")
        subtasks.append("Design the approach and define interfaces")
        subtasks.append("Implement the core functionality in small increments")
        subtasks.append("Write tests to verify each increment")
        subtasks.append("Integrate, review, and iterate")

    # 3. Final step: validate and wrap up.
    subtasks.append(
        f"Validate the complete result against the original goal: {complex_task}"
    )

    return subtasks


# ---------------------------------------------------------------------------
# compress_context
# ---------------------------------------------------------------------------


def compress_context(context: str, max_tokens: int = 2000) -> str:
    """Compress context while preserving key information.

    Philosophy: "AI context is like milk; best served fresh and condensed."

    Uses a simple heuristic token estimate (~4 chars per token) and
    aggressively trims low-signal content while keeping sentences that
    contain high-signal markers.

    Args:
        context: The full context string.
        max_tokens: Approximate maximum number of tokens in the output.

    Returns:
        A compressed version of the context.
    """
    chars_budget = max_tokens * 4  # rough chars-per-token estimate

    if len(context) <= chars_budget:
        return context

    # Split into sentences (simple heuristic).
    sentences = re.split(r"(?<=[.!?])\s+", context)
    if not sentences:
        return context[:chars_budget]

    # Score each sentence by signal density.
    high_signal_words = {
        "important",
        "critical",
        "must",
        "required",
        "key",
        "essential",
        "error",
        "warning",
        "note",
        "todo",
        "fixme",
        "hack",
        "bug",
        "api",
        "config",
        "secret",
        "password",
        "token",
        "deploy",
        "deadline",
        "blocking",
        "urgent",
        "never",
        "always",
    }

    scored: list[tuple[float, int, str]] = []
    for idx, sentence in enumerate(sentences):
        words = set(re.findall(r"\w+", sentence.lower()))
        signal = len(words & high_signal_words)
        # Boost first and last sentences (they tend to carry framing info).
        if idx == 0 or idx == len(sentences) - 1:
            signal += 2
        scored.append((signal, idx, sentence))

    # Sort by signal descending, then by original order for tie-breaking.
    scored.sort(key=lambda t: (-t[0], t[1]))

    # Greedily pick sentences until budget is exhausted.
    selected_indices: set[int] = set()
    running_len = 0
    for _signal, idx, sentence in scored:
        if running_len + len(sentence) + 1 > chars_budget:
            continue
        selected_indices.add(idx)
        running_len += len(sentence) + 1

    if not selected_indices:
        # Fallback: just truncate.
        return context[:chars_budget]

    # Reconstruct in original order.
    compressed_parts = [sentences[i] for i in sorted(selected_indices)]
    return " ".join(compressed_parts)
