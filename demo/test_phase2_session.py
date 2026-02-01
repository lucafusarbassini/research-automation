"""Phase 2 tests: session management, agent routing, model router, tokens, prompt suggestions."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.claude_flow import ClaudeFlowUnavailable


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


class TestSessionCreateAndTrack:
    """Test core.session create/load/update/close lifecycle."""

    @patch("core.session._get_bridge", side_effect=ClaudeFlowUnavailable)
    def test_session_create_and_track(self, _mock_bridge, tmp_path, monkeypatch):
        from core import session
        from core.session import (
            Session,
            close_session,
            create_session,
            list_sessions,
            load_session,
            update_session,
        )

        # Redirect session storage to tmp_path
        monkeypatch.setattr(session, "STATE_DIR", tmp_path / "state")
        monkeypatch.setattr(session, "SESSIONS_DIR", tmp_path / "state" / "sessions")

        # Create
        s = create_session("test-session-001")
        assert isinstance(s, Session)
        assert s.name == "test-session-001"
        assert s.status == "active"

        # Load
        loaded = load_session("test-session-001")
        assert loaded is not None
        assert loaded.name == "test-session-001"

        # Update
        s.tasks_completed = 3
        s.token_estimate = 5000
        update_session(s)
        reloaded = load_session("test-session-001")
        assert reloaded.tasks_completed == 3
        assert reloaded.token_estimate == 5000

        # List
        create_session("test-session-002")
        sessions = list_sessions()
        assert len(sessions) >= 2

        # Close
        close_session(s)
        final = load_session("test-session-001")
        assert final.status == "completed"


# ---------------------------------------------------------------------------
# Agent routing
# ---------------------------------------------------------------------------


class TestAgentTaskRouting:
    """Test core.agents.route_task with mocked bridge (falls back to keywords)."""

    @patch("core.agents._get_bridge", side_effect=ClaudeFlowUnavailable)
    def test_agent_task_routing(self, _mock_bridge):
        from core.agents import AgentType, route_task

        # Research task
        agent = route_task("Search the literature for transformer papers on arxiv")
        assert agent == AgentType.RESEARCHER

        # Coding task
        agent = route_task("Implement a data loader class with test coverage")
        assert agent == AgentType.CODER

        # Review task
        agent = route_task("Review and audit the code for quality issues")
        assert agent == AgentType.REVIEWER

        # Falsifier task
        agent = route_task("Validate the results and check for data leak")
        assert agent == AgentType.FALSIFIER

        # Writer task
        agent = route_task("Write the introduction and methods sections of the paper")
        assert agent == AgentType.WRITER

        # Cleaner task
        agent = route_task("Refactor and organize the codebase, lint and format")
        assert agent == AgentType.CLEANER

        # Ambiguous defaults to coder
        agent = route_task("do the thing with the stuff")
        assert agent == AgentType.CODER


class TestAgentTypesDefined:
    """Verify all expected AgentType enum values exist."""

    def test_agent_types_defined(self):
        from core.agents import AgentType

        expected = {"master", "researcher", "coder", "reviewer", "falsifier", "writer", "cleaner"}
        actual = {member.value for member in AgentType}
        assert expected == actual


# ---------------------------------------------------------------------------
# Model router
# ---------------------------------------------------------------------------


class TestModelRouterClassify:
    """Test core.model_router.classify_task_complexity."""

    @patch("core.model_router._get_bridge", side_effect=ClaudeFlowUnavailable)
    def test_model_router_classify_simple(self, _mock_bridge):
        from core.model_router import TaskComplexity, classify_task_complexity

        result = classify_task_complexity("format the list and sort it")
        assert result == TaskComplexity.SIMPLE

    @patch("core.model_router._get_bridge", side_effect=ClaudeFlowUnavailable)
    def test_model_router_classify_medium(self, _mock_bridge):
        from core.model_router import TaskComplexity, classify_task_complexity

        result = classify_task_complexity("process data and generate a report")
        assert result == TaskComplexity.MEDIUM

    @patch("core.model_router._get_bridge", side_effect=ClaudeFlowUnavailable)
    def test_model_router_classify_complex(self, _mock_bridge):
        from core.model_router import TaskComplexity, classify_task_complexity

        result = classify_task_complexity("design and architect a new system")
        assert result == TaskComplexity.COMPLEX

    @patch("core.model_router._get_bridge", side_effect=ClaudeFlowUnavailable)
    def test_model_router_classify_critical(self, _mock_bridge):
        from core.model_router import TaskComplexity, classify_task_complexity

        result = classify_task_complexity("validate and submit the paper for publication")
        assert result == TaskComplexity.CRITICAL


class TestModelRouterSelect:
    """Test core.model_router.route_to_model."""

    @patch("core.model_router._get_bridge", side_effect=ClaudeFlowUnavailable)
    def test_model_router_select_opus_for_critical(self, _mock_bridge):
        from core.model_router import ModelConfig, TaskComplexity, route_to_model

        model = route_to_model("verify the final paper submission", complexity=TaskComplexity.CRITICAL)
        assert isinstance(model, ModelConfig)
        assert "opus" in model.name

    @patch("core.model_router._get_bridge", side_effect=ClaudeFlowUnavailable)
    def test_model_router_select_haiku_for_simple(self, _mock_bridge):
        from core.model_router import ModelConfig, TaskComplexity, route_to_model

        model = route_to_model("list files", complexity=TaskComplexity.SIMPLE)
        assert "haiku" in model.name

    @patch("core.model_router._get_bridge", side_effect=ClaudeFlowUnavailable)
    def test_model_router_select_sonnet_for_medium(self, _mock_bridge):
        from core.model_router import ModelConfig, TaskComplexity, route_to_model

        model = route_to_model("process data", complexity=TaskComplexity.MEDIUM)
        assert "sonnet" in model.name

    @patch("core.model_router._get_bridge", side_effect=ClaudeFlowUnavailable)
    def test_model_router_budget_override(self, _mock_bridge):
        from core.model_router import TaskComplexity, route_to_model

        # Low budget forces haiku even for critical tasks
        model = route_to_model(
            "validate final submission",
            complexity=TaskComplexity.CRITICAL,
            budget_remaining_pct=10.0,
        )
        assert "haiku" in model.name


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


class TestTokenEstimation:
    """Test core.tokens.estimate_tokens."""

    @patch("core.tokens._get_bridge", side_effect=ClaudeFlowUnavailable)
    def test_token_estimation(self, _mock_bridge):
        from core.tokens import estimate_tokens

        text = "Hello world, this is a test sentence for token estimation."
        tokens = estimate_tokens(text)

        assert isinstance(tokens, int)
        assert tokens > 0
        # ~4 chars per token heuristic
        assert tokens == len(text) // 4

    @patch("core.tokens._get_bridge", side_effect=ClaudeFlowUnavailable)
    def test_token_estimation_empty(self, _mock_bridge):
        from core.tokens import estimate_tokens

        assert estimate_tokens("") == 0

    @patch("core.tokens._get_bridge", side_effect=ClaudeFlowUnavailable)
    def test_check_budget(self, _mock_bridge):
        from core.tokens import TokenBudget, check_budget

        budget = TokenBudget(session_limit=10_000, daily_limit=50_000)
        result = check_budget(budget, estimated_cost=500)

        assert result["can_proceed"] is True
        assert "session_used_pct" in result
        assert "daily_used_pct" in result
        assert "warning" in result

    @patch("core.tokens._get_bridge", side_effect=ClaudeFlowUnavailable)
    def test_check_budget_exceeded(self, _mock_bridge):
        from core.tokens import TokenBudget, check_budget

        budget = TokenBudget(
            session_limit=1000,
            daily_limit=5000,
            current_session=999,
            current_daily=100,
        )
        result = check_budget(budget, estimated_cost=500)
        assert result["can_proceed"] is False
        assert result["warning"] is True


# ---------------------------------------------------------------------------
# Prompt suggestions
# ---------------------------------------------------------------------------


class TestPromptSuggestions:
    """Test core.prompt_suggestions.suggest_next_steps."""

    def test_prompt_suggestions(self):
        from core.prompt_suggestions import suggest_next_steps

        steps = suggest_next_steps(
            current_task="Implement the data loader",
            progress=["Set up environment", "Downloaded dataset"],
            goal="Train a model to 95% accuracy",
        )

        assert isinstance(steps, list)
        assert 3 <= len(steps) <= 5
        assert all(isinstance(s, str) for s in steps)

    def test_prompt_suggestions_no_progress(self):
        from core.prompt_suggestions import suggest_next_steps

        steps = suggest_next_steps(
            current_task="Research transformers",
            progress=[],
            goal="Write a survey paper",
        )

        assert len(steps) >= 3

    def test_prompt_suggestions_research_category(self):
        from core.prompt_suggestions import suggest_next_steps

        steps = suggest_next_steps(
            current_task="Survey the literature",
            progress=[],
            goal="Investigate new architectures",
        )

        # Should include research-related steps
        combined = " ".join(steps).lower()
        assert any(kw in combined for kw in ["literature", "theme", "gap", "research", "question", "methodology"])


class TestDetectStuckPattern:
    """Test core.prompt_suggestions.detect_stuck_pattern."""

    def test_detect_stuck_pattern_no_loop(self):
        from core.prompt_suggestions import detect_stuck_pattern

        history = ["step A", "step B", "step C", "step D", "step E"]
        assert detect_stuck_pattern(history) is False

    def test_detect_stuck_pattern_obvious_loop(self):
        from core.prompt_suggestions import detect_stuck_pattern

        history = ["fix bug", "run tests", "fix bug", "run tests", "fix bug", "run tests"]
        assert detect_stuck_pattern(history) is True

    def test_detect_stuck_pattern_short_history(self):
        from core.prompt_suggestions import detect_stuck_pattern

        assert detect_stuck_pattern(["a", "b"]) is False

    def test_detect_stuck_pattern_single_repeat(self):
        from core.prompt_suggestions import detect_stuck_pattern

        history = ["retry", "retry", "retry", "retry"]
        assert detect_stuck_pattern(history) is True


class TestCompressContext:
    """Test core.prompt_suggestions.compress_context."""

    def test_compress_context_short_input(self):
        from core.prompt_suggestions import compress_context

        short = "This is a short context."
        result = compress_context(short, max_tokens=2000)
        assert result == short

    def test_compress_context_long_input(self):
        from core.prompt_suggestions import compress_context

        # Build a long context that exceeds 100 tokens (400 chars)
        sentences = [
            "This is an important configuration detail that must be preserved.",
            "The weather was nice today with some clouds.",
            "A critical error occurred during deployment.",
            "The cat sat on the mat quietly.",
            "Never ignore the warning signs in production logs.",
            "Some filler text that adds nothing substantial.",
            "The API token must be rotated every 90 days.",
            "Random thoughts about various unrelated topics here.",
            "The deadline is blocking all other work streams.",
            "More padding text to ensure we exceed the budget.",
        ] * 3  # Repeat to make it long enough

        long_context = " ".join(sentences)
        compressed = compress_context(long_context, max_tokens=100)

        assert len(compressed) < len(long_context)
        assert len(compressed) <= 100 * 4 + 200  # some tolerance

    def test_compress_context_preserves_high_signal(self):
        from core.prompt_suggestions import compress_context

        context = (
            "This is the important introduction to the project. "
            "Some filler padding text goes here for length. " * 20 +
            "A critical error was found in the deployment pipeline. "
            "The API token must be refreshed urgently. "
            "More random filler to pad out. " * 20 +
            "This is the essential conclusion of the analysis."
        )

        compressed = compress_context(context, max_tokens=80)
        compressed_lower = compressed.lower()
        # High-signal words should be preferentially kept
        assert "important" in compressed_lower or "critical" in compressed_lower or "essential" in compressed_lower
