"""Tests for doability assessment module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from core.doability import (
    DoabilityReport,
    ReadinessReport,
    assess_doability,
    check_project_readiness,
    extract_missing_requirements,
    generate_clarifying_questions,
)


# ---------------------------------------------------------------------------
# DoabilityReport dataclass
# ---------------------------------------------------------------------------


def test_doability_report_defaults():
    report = DoabilityReport()
    assert report.is_feasible is False
    assert report.missing_info == []
    assert report.suggestions == []
    assert report.risk_level == "unknown"
    assert report.checklist == {}


def test_doability_report_custom_values():
    report = DoabilityReport(
        is_feasible=True,
        missing_info=["dataset"],
        suggestions=["use public data"],
        risk_level="low",
        checklist={"goal_defined": True},
    )
    assert report.is_feasible is True
    assert report.missing_info == ["dataset"]
    assert report.risk_level == "low"
    assert report.checklist["goal_defined"] is True


# ---------------------------------------------------------------------------
# assess_doability
# ---------------------------------------------------------------------------


def test_assess_doability_well_defined_goal():
    """A specific goal with resources should be feasible."""
    report = assess_doability(
        goal="Train a ResNet-50 on CIFAR-10 to 95% accuracy",
        constraints={"timeline": "2 weeks", "compute": "1xA100"},
        available_resources={"dataset": "CIFAR-10", "gpu": "A100", "framework": "PyTorch"},
    )
    assert isinstance(report, DoabilityReport)
    assert report.is_feasible is True
    assert report.risk_level in ("low", "medium", "high", "unknown")


def test_assess_doability_vague_goal():
    """A vague goal should flag missing info."""
    report = assess_doability(
        goal="do something with data",
        constraints={},
        available_resources={},
    )
    assert report.is_feasible is False
    assert len(report.missing_info) > 0


def test_assess_doability_missing_compute():
    """Goal requiring GPU but no GPU listed should note missing resource."""
    report = assess_doability(
        goal="Train a large language model with 7B parameters",
        constraints={"timeline": "1 month"},
        available_resources={},
    )
    assert any("resource" in item.lower() or "compute" in item.lower() or "gpu" in item.lower()
               for item in report.missing_info + report.suggestions)


def test_assess_doability_returns_checklist():
    """Report must always contain a checklist dict."""
    report = assess_doability(
        goal="Analyse CSV sales data and produce summary statistics",
        constraints={"deadline": "Friday"},
        available_resources={"dataset": "sales.csv"},
    )
    assert isinstance(report.checklist, dict)
    assert len(report.checklist) > 0


def test_assess_doability_risk_level_valid():
    """Risk level must be one of the known values."""
    report = assess_doability(
        goal="Replicate a Nature paper from scratch",
        constraints={},
        available_resources={},
    )
    assert report.risk_level in ("low", "medium", "high", "unknown")


# ---------------------------------------------------------------------------
# check_project_readiness
# ---------------------------------------------------------------------------


def test_check_project_readiness_complete(tmp_path):
    """A fully set-up project directory should be ready."""
    (tmp_path / "GOAL.md").write_text("Train a classifier on public data.\n")
    (tmp_path / "CONSTRAINTS.md").write_text("Timeline: 1 week\n")
    (tmp_path / "TODO.md").write_text("- step 1\n")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "settings.yml").write_text("model: resnet\n")
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-test\n")

    report = check_project_readiness(tmp_path)
    assert isinstance(report, ReadinessReport)
    assert report.is_ready is True
    assert len(report.missing_files) == 0


def test_check_project_readiness_missing_goal(tmp_path):
    """Missing GOAL.md should mark the project as not ready."""
    (tmp_path / "CONSTRAINTS.md").write_text("x\n")
    (tmp_path / "TODO.md").write_text("x\n")

    report = check_project_readiness(tmp_path)
    assert report.is_ready is False
    assert "GOAL.md" in report.missing_files


def test_check_project_readiness_missing_settings(tmp_path):
    """Missing config/settings.yml should appear in missing files."""
    (tmp_path / "GOAL.md").write_text("Goal.\n")
    (tmp_path / "CONSTRAINTS.md").write_text("c\n")
    (tmp_path / "TODO.md").write_text("t\n")
    (tmp_path / ".env").write_text("KEY=val\n")

    report = check_project_readiness(tmp_path)
    assert "config/settings.yml" in report.missing_files


def test_check_project_readiness_paper_needs_template(tmp_path):
    """If GOAL.md mentions paper writing, a templates dir should exist."""
    (tmp_path / "GOAL.md").write_text("Write a paper for NeurIPS.\n")
    (tmp_path / "CONSTRAINTS.md").write_text("c\n")
    (tmp_path / "TODO.md").write_text("t\n")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "settings.yml").write_text("x\n")
    (tmp_path / ".env").write_text("KEY=val\n")

    report = check_project_readiness(tmp_path)
    assert any("template" in f.lower() for f in report.missing_files) or \
        any("template" in w.lower() for w in report.warnings)


def test_check_project_readiness_missing_env(tmp_path):
    """Missing .env should be flagged."""
    (tmp_path / "GOAL.md").write_text("Goal.\n")
    (tmp_path / "CONSTRAINTS.md").write_text("c\n")
    (tmp_path / "TODO.md").write_text("t\n")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "settings.yml").write_text("x\n")

    report = check_project_readiness(tmp_path)
    assert ".env" in report.missing_files


# ---------------------------------------------------------------------------
# extract_missing_requirements
# ---------------------------------------------------------------------------


def test_extract_missing_requirements_vague_prompt():
    """A vague prompt should yield several missing requirements."""
    missing = extract_missing_requirements("train a model")
    assert isinstance(missing, list)
    assert len(missing) >= 2  # e.g. dataset, architecture, metric


def test_extract_missing_requirements_specific_prompt():
    """A detailed prompt should have fewer (possibly zero) missing items."""
    prompt = (
        "Train a ResNet-50 on CIFAR-10 using PyTorch, targeting 95% accuracy, "
        "evaluated with top-1 accuracy, on a single A100 GPU"
    )
    missing = extract_missing_requirements(prompt)
    assert isinstance(missing, list)
    assert len(missing) < 3  # mostly specified


def test_extract_missing_requirements_empty_prompt():
    """An empty prompt should flag everything as missing."""
    missing = extract_missing_requirements("")
    assert len(missing) > 0


# ---------------------------------------------------------------------------
# generate_clarifying_questions
# ---------------------------------------------------------------------------


def test_generate_clarifying_questions_produces_questions():
    """Should return at least one question per missing item."""
    missing = ["dataset", "metric"]
    questions = generate_clarifying_questions(missing)
    assert isinstance(questions, list)
    assert len(questions) >= len(missing)


def test_generate_clarifying_questions_empty_input():
    """No missing items means no questions needed."""
    questions = generate_clarifying_questions([])
    assert questions == []


def test_generate_clarifying_questions_strings():
    """Every question should be a non-empty string."""
    questions = generate_clarifying_questions(["compute", "deadline", "output_format"])
    for q in questions:
        assert isinstance(q, str)
        assert len(q) > 0
