"""Tests for onboarding workflow."""

from pathlib import Path

import yaml

from core.onboarding import (
    WORKSPACE_DIRS,
    OnboardingAnswers,
    collect_answers,
    load_settings,
    setup_workspace,
    write_goal_file,
    write_settings,
)


def test_collect_answers_defaults():
    responses = iter(["predict proteins", "ml-research", "skip", "skip", "flexible", "local-cpu", "none"])
    answers = collect_answers("test-proj", prompt_fn=lambda p, d="": next(responses))
    assert answers.project_name == "test-proj"
    assert answers.goal == "predict proteins"
    assert answers.project_type == "ml-research"


def test_collect_answers_with_gpu():
    responses = iter(["goal", "ml-research", "skip", "skip", "flexible", "local-gpu", "RTX 4090", "none"])
    answers = collect_answers("proj", prompt_fn=lambda p, d="": next(responses))
    assert answers.compute_type == "local-gpu"
    assert answers.gpu_name == "RTX 4090"


def test_collect_answers_with_email():
    responses = iter(["goal", "general", "skip", "skip", "flexible", "local-cpu", "email", "a@b.com"])
    answers = collect_answers("proj", prompt_fn=lambda p, d="": next(responses))
    assert answers.notification_method == "email"
    assert answers.notification_email == "a@b.com"


def test_collect_answers_invalid_project_type():
    responses = iter(["goal", "invalid-type", "skip", "skip", "flexible", "local-cpu", "none"])
    answers = collect_answers("proj", prompt_fn=lambda p, d="": next(responses))
    assert answers.project_type == "ml-research"  # Falls back to default


def test_setup_workspace(tmp_path: Path):
    setup_workspace(tmp_path)
    for dirname in WORKSPACE_DIRS:
        assert (tmp_path / dirname).is_dir()
        assert (tmp_path / dirname / ".gitkeep").exists()


def test_write_settings(tmp_path: Path):
    answers = OnboardingAnswers(
        project_name="my-proj",
        goal="test goal",
        project_type="data-analysis",
        compute_type="local-gpu",
        gpu_name="RTX 3090",
        notification_method="email",
        notification_email="test@example.com",
    )
    path = write_settings(tmp_path, answers)
    assert path.exists()

    settings = yaml.safe_load(path.read_text())
    assert settings["project"]["name"] == "my-proj"
    assert settings["project"]["type"] == "data-analysis"
    assert settings["compute"]["gpu"] == "RTX 3090"
    assert settings["notifications"]["enabled"] is True
    assert settings["notifications"]["email"] == "test@example.com"


def test_write_settings_no_notifications(tmp_path: Path):
    answers = OnboardingAnswers(project_name="proj", notification_method="none")
    path = write_settings(tmp_path, answers)
    settings = yaml.safe_load(path.read_text())
    assert settings["notifications"]["enabled"] is False


def test_load_settings(tmp_path: Path):
    answers = OnboardingAnswers(project_name="proj", project_type="general")
    write_settings(tmp_path, answers)
    settings = load_settings(tmp_path)
    assert settings["project"]["name"] == "proj"


def test_load_settings_missing(tmp_path: Path):
    settings = load_settings(tmp_path)
    assert settings == {}


def test_write_goal_file(tmp_path: Path):
    goal_dir = tmp_path / "knowledge"
    goal_dir.mkdir()
    goal_file = goal_dir / "GOAL.md"
    goal_file.write_text("# Goal\n\n<!-- User provides during init -->\n")

    answers = OnboardingAnswers(goal="Cure cancer with ML")
    write_goal_file(tmp_path, answers)

    content = goal_file.read_text()
    assert "Cure cancer with ML" in content
    assert "<!-- User provides during init -->" not in content
