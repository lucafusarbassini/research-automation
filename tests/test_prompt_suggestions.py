"""Tests for the prompt suggestions / predictive follow-ups module."""

import pytest

from core.prompt_suggestions import (
    COMMON_PATTERNS,
    compress_context,
    detect_stuck_pattern,
    generate_follow_up_prompts,
    suggest_decomposition,
    suggest_next_steps,
)


# ---------------------------------------------------------------------------
# suggest_next_steps
# ---------------------------------------------------------------------------

class TestSuggestNextSteps:
    def test_returns_list_of_strings(self):
        result = suggest_next_steps(
            current_task="Write unit tests",
            progress=["Created test file"],
            goal="Full test coverage",
        )
        assert isinstance(result, list)
        assert all(isinstance(s, str) for s in result)

    def test_returns_three_to_five_suggestions(self):
        result = suggest_next_steps(
            current_task="Implement feature X",
            progress=["Designed API", "Wrote skeleton"],
            goal="Ship feature X",
        )
        assert 3 <= len(result) <= 5

    def test_empty_progress_still_returns_suggestions(self):
        result = suggest_next_steps(
            current_task="Start project",
            progress=[],
            goal="Build MVP",
        )
        assert len(result) >= 3

    def test_suggestions_are_nonempty_strings(self):
        result = suggest_next_steps(
            current_task="Debug failing CI",
            progress=["Checked logs"],
            goal="Green CI pipeline",
        )
        assert all(len(s.strip()) > 0 for s in result)


# ---------------------------------------------------------------------------
# generate_follow_up_prompts
# ---------------------------------------------------------------------------

class TestGenerateFollowUpPrompts:
    def test_returns_list_of_strings(self):
        result = generate_follow_up_prompts(
            completed_task="Wrote unit tests",
            result="All 10 tests passing",
        )
        assert isinstance(result, list)
        assert all(isinstance(s, str) for s in result)

    def test_returns_at_least_one_prompt(self):
        result = generate_follow_up_prompts(
            completed_task="Deployed to staging",
            result="Deployment successful, URL: https://staging.example.com",
        )
        assert len(result) >= 1

    def test_prompts_are_nonempty(self):
        result = generate_follow_up_prompts(
            completed_task="Refactored database layer",
            result="Reduced query count by 40%",
        )
        assert all(len(p.strip()) > 0 for p in result)


# ---------------------------------------------------------------------------
# detect_stuck_pattern
# ---------------------------------------------------------------------------

class TestDetectStuckPattern:
    def test_detects_repeated_actions(self):
        history = [
            "fix lint error",
            "run tests",
            "fix lint error",
            "run tests",
            "fix lint error",
            "run tests",
        ]
        assert detect_stuck_pattern(history) is True

    def test_no_stuck_for_progressive_history(self):
        history = [
            "design schema",
            "implement models",
            "write migrations",
            "add API endpoints",
            "write tests",
        ]
        assert detect_stuck_pattern(history) is False

    def test_short_history_not_stuck(self):
        history = ["do something"]
        assert detect_stuck_pattern(history) is False

    def test_empty_history_not_stuck(self):
        assert detect_stuck_pattern([]) is False


# ---------------------------------------------------------------------------
# suggest_decomposition
# ---------------------------------------------------------------------------

class TestSuggestDecomposition:
    def test_returns_list_of_subtasks(self):
        result = suggest_decomposition(
            "Build a full-stack web application with auth, database, and REST API"
        )
        assert isinstance(result, list)
        assert len(result) >= 2

    def test_subtasks_are_nonempty_strings(self):
        result = suggest_decomposition("Migrate monolith to microservices")
        assert all(isinstance(s, str) and len(s.strip()) > 0 for s in result)

    def test_simple_task_still_decomposes(self):
        result = suggest_decomposition("Write a function")
        assert isinstance(result, list)
        assert len(result) >= 2


# ---------------------------------------------------------------------------
# compress_context
# ---------------------------------------------------------------------------

class TestCompressContext:
    def test_short_context_returned_as_is(self):
        short = "This is a brief note."
        result = compress_context(short, max_tokens=2000)
        assert result == short

    def test_long_context_is_shortened(self):
        long_text = "word " * 5000  # ~5000 words, well over 2000 tokens
        result = compress_context(long_text, max_tokens=200)
        # Compressed output should be shorter than input
        assert len(result) < len(long_text)

    def test_preserves_some_content(self):
        context = (
            "IMPORTANT: The API key is rotated weekly. "
            + "filler " * 3000
            + "CRITICAL: Deploy only on Tuesdays."
        )
        result = compress_context(context, max_tokens=300)
        # Should keep at least some recognizable content
        assert len(result) > 0

    def test_custom_max_tokens(self):
        text = "token " * 1000
        result = compress_context(text, max_tokens=50)
        # Very aggressive compression; result must be substantially smaller
        assert len(result) < len(text)


# ---------------------------------------------------------------------------
# COMMON_PATTERNS
# ---------------------------------------------------------------------------

class TestCommonPatterns:
    def test_is_dict(self):
        assert isinstance(COMMON_PATTERNS, dict)

    def test_has_expected_keys(self):
        expected = {"research", "implementation", "debugging", "review"}
        assert expected.issubset(set(COMMON_PATTERNS.keys()))

    def test_values_are_lists_of_strings(self):
        for key, value in COMMON_PATTERNS.items():
            assert isinstance(value, list), f"COMMON_PATTERNS[{key!r}] is not a list"
            assert all(isinstance(v, str) for v in value)
