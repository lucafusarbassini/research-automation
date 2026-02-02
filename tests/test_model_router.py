"""Tests for multi-model routing."""

from core.model_router import (
    DEFAULT_MODELS,
    RouterConfig,
    TaskComplexity,
    classify_task_complexity,
    get_fallback_model,
    route_to_model,
)


def test_classify_simple():
    assert classify_task_complexity("format the output nicely") == TaskComplexity.SIMPLE
    assert classify_task_complexity("list all files") == TaskComplexity.SIMPLE


def test_classify_complex():
    assert classify_task_complexity("debug the training loop") == TaskComplexity.COMPLEX
    assert (
        classify_task_complexity("research transformer architectures")
        == TaskComplexity.COMPLEX
    )


def test_classify_critical():
    assert (
        classify_task_complexity("validate the final results")
        == TaskComplexity.CRITICAL
    )
    assert (
        classify_task_complexity("prepare to publish the paper")
        == TaskComplexity.CRITICAL
    )


def test_classify_medium_default():
    assert classify_task_complexity("implement a data loader") == TaskComplexity.MEDIUM


def test_route_simple_to_haiku():
    model = route_to_model("format this list")
    assert model.name == DEFAULT_MODELS["claude-haiku"].name


def test_route_complex_to_opus():
    model = route_to_model("debug the memory leak")
    assert model.name == DEFAULT_MODELS["claude-opus"].name


def test_route_critical_to_opus():
    model = route_to_model("validate experiment results")
    assert model.name == DEFAULT_MODELS["claude-opus"].name


def test_route_medium_to_sonnet():
    model = route_to_model("implement feature extraction")
    assert model.name == DEFAULT_MODELS["claude-sonnet"].name


def test_route_low_budget_prefers_haiku():
    cfg = RouterConfig(confirmation_callback=lambda _: True)
    model = route_to_model(
        "debug the complex issue", budget_remaining_pct=10.0, config=cfg
    )
    assert model.name == DEFAULT_MODELS["claude-haiku"].name


def test_fallback_from_opus():
    fallback = get_fallback_model("claude-opus")
    assert fallback is not None
    assert fallback.name == DEFAULT_MODELS["claude-sonnet"].name


def test_fallback_from_sonnet():
    fallback = get_fallback_model("claude-sonnet")
    assert fallback is not None
    assert fallback.name == DEFAULT_MODELS["claude-haiku"].name


def test_fallback_from_haiku_exhausted():
    fallback = get_fallback_model("claude-haiku")
    assert fallback is None


def test_fallback_unknown_model():
    fallback = get_fallback_model("gpt-4")
    assert fallback is None


# --- Bridge-integrated tests ---

from unittest.mock import MagicMock, patch

from core.model_router import (
    _classify_task_complexity_keywords,
    _route_to_model_keywords,
)


def test_classify_via_bridge():
    mock_bridge = MagicMock()
    mock_bridge.route_model.return_value = {"complexity": "critical", "tier": "oracle"}
    with patch("core.model_router._get_bridge", return_value=mock_bridge):
        assert classify_task_complexity("anything") == TaskComplexity.CRITICAL


def test_classify_via_bridge_tier_fallback():
    mock_bridge = MagicMock()
    mock_bridge.route_model.return_value = {"tier": "booster"}
    with patch("core.model_router._get_bridge", return_value=mock_bridge):
        assert classify_task_complexity("anything") == TaskComplexity.SIMPLE


def test_classify_bridge_unavailable():
    from core.claude_flow import ClaudeFlowUnavailable

    with patch(
        "core.model_router._get_bridge", side_effect=ClaudeFlowUnavailable("no")
    ):
        assert classify_task_complexity("debug something") == TaskComplexity.COMPLEX


def test_route_to_model_via_bridge():
    mock_bridge = MagicMock()
    mock_bridge.route_model.return_value = {"model": "claude-opus-4-5-20251101"}
    with patch("core.model_router._get_bridge", return_value=mock_bridge):
        model = route_to_model("complex task")
        assert model.name == DEFAULT_MODELS["claude-opus"].name


def test_route_to_model_bridge_respects_budget():
    mock_bridge = MagicMock()
    mock_bridge.route_model.return_value = {"model": "claude-opus-4-5-20251101"}
    cfg = RouterConfig(confirmation_callback=lambda _: True)
    with patch("core.model_router._get_bridge", return_value=mock_bridge):
        model = route_to_model("complex task", budget_remaining_pct=5.0, config=cfg)
        assert model.name == DEFAULT_MODELS["claude-haiku"].name


def test_keywords_fallback_functions():
    assert _classify_task_complexity_keywords("format this") == TaskComplexity.SIMPLE
    model = _route_to_model_keywords("debug the issue")
    assert model.name == DEFAULT_MODELS["claude-opus"].name


def test_route_to_model_name_used_in_agent_execution():
    """Integration-style: route_to_model().name is passed as --model in agent execution."""
    from core.agents import AgentType, _execute_agent_task_legacy

    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.stdout = "done"

    with patch("core.agents.subprocess.run", return_value=fake_proc) as mock_run:
        with patch("core.agents.get_agent_prompt", return_value="prompt"):
            # "debug the memory leak" -> COMPLEX -> claude-opus
            _execute_agent_task_legacy(AgentType.CODER, "debug the memory leak")

    cmd = mock_run.call_args[0][0]
    model_idx = cmd.index("--model")
    actual_model = cmd[model_idx + 1]

    expected = route_to_model("debug the memory leak")
    assert actual_model == expected.name
    assert actual_model == DEFAULT_MODELS["claude-opus"].name


def test_route_to_model_haiku_for_simple_task_in_execution():
    """Simple tasks route to haiku and that model name reaches the CLI command."""
    from core.agents import AgentType, _execute_agent_task_legacy

    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.stdout = "done"

    with patch("core.agents.subprocess.run", return_value=fake_proc) as mock_run:
        with patch("core.agents.get_agent_prompt", return_value="prompt"):
            _execute_agent_task_legacy(AgentType.CLEANER, "format the output list")

    cmd = mock_run.call_args[0][0]
    model_idx = cmd.index("--model")
    actual_model = cmd[model_idx + 1]
    assert actual_model == DEFAULT_MODELS["claude-haiku"].name
