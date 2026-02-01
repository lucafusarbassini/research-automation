"""Tests for multi-model routing."""

from core.model_router import (
    DEFAULT_MODELS,
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
    assert classify_task_complexity("research transformer architectures") == TaskComplexity.COMPLEX


def test_classify_critical():
    assert classify_task_complexity("validate the final results") == TaskComplexity.CRITICAL
    assert classify_task_complexity("prepare to publish the paper") == TaskComplexity.CRITICAL


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
    model = route_to_model("debug the complex issue", budget_remaining_pct=10.0)
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
