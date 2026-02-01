"""Tests for onboarding workflow."""

from pathlib import Path

import yaml

from core.onboarding import (
    WORKSPACE_DIRS,
    OnboardingAnswers,
    auto_install_claude,
    collect_answers,
    load_settings,
    setup_claude_web_access,
    setup_workspace,
    validate_prerequisites,
    verify_uploaded_files,
    write_goal_file,
    write_settings,
)


def test_collect_answers_defaults():
    responses = iter(
        [
            "predict proteins",
            "ml-research",
            "skip",
            "skip",
            "flexible",
            "local-cpu",
            "none",
            "skip",
            "no",
            "no",
        ]
    )
    answers = collect_answers("test-proj", prompt_fn=lambda p, d="": next(responses))
    assert answers.project_name == "test-proj"
    assert answers.goal == "predict proteins"
    assert answers.project_type == "ml-research"
    assert answers.journal_target == ""
    assert answers.needs_website is False
    assert answers.needs_mobile is False


def test_collect_answers_with_gpu():
    responses = iter(
        [
            "goal",
            "ml-research",
            "skip",
            "skip",
            "flexible",
            "local-gpu",
            "RTX 4090",
            "none",
            "skip",
            "no",
            "no",
        ]
    )
    answers = collect_answers("proj", prompt_fn=lambda p, d="": next(responses))
    assert answers.compute_type == "local-gpu"
    assert answers.gpu_name == "RTX 4090"


def test_collect_answers_with_email():
    responses = iter(
        [
            "goal",
            "general",
            "skip",
            "skip",
            "flexible",
            "local-cpu",
            "email",
            "a@b.com",
            "skip",
            "no",
            "no",
        ]
    )
    answers = collect_answers("proj", prompt_fn=lambda p, d="": next(responses))
    assert answers.notification_method == "email"
    assert answers.notification_email == "a@b.com"


def test_collect_answers_invalid_project_type():
    responses = iter(
        [
            "goal",
            "invalid-type",
            "skip",
            "skip",
            "flexible",
            "local-cpu",
            "none",
            "skip",
            "no",
            "no",
        ]
    )
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


# ---------------------------------------------------------------------------
# New tests for prerequisite validation, auto-install, web access, file
# verification, and new onboarding fields.
# ---------------------------------------------------------------------------


def test_validate_prerequisites_all_present():
    """When every tool is found, the result should be empty."""
    missing = validate_prerequisites(run_cmd=lambda cmd: True)
    assert missing == {}


def test_validate_prerequisites_some_missing():
    """When docker and claude are missing, they appear with install hints."""

    def fake_run(cmd: str) -> bool:
        if "docker" in cmd or "claude" in cmd:
            return False
        return True

    missing = validate_prerequisites(run_cmd=fake_run)
    assert "docker" in missing
    assert "claude" in missing
    assert "node" not in missing
    assert "git" not in missing
    # Each value should be a non-empty install hint string
    assert len(missing["docker"]) > 0


def test_auto_install_claude_already_present():
    """If claude --version succeeds, return True without installing."""

    class FakeResult:
        returncode = 0

    installed = auto_install_claude(run_cmd=lambda cmd, check=False: FakeResult())
    assert installed is True


def test_auto_install_claude_install_succeeds():
    """If claude is missing but npm install works, return True."""
    call_log = []

    class SuccessResult:
        returncode = 0

    class FailResult:
        returncode = 1

    def fake_run(cmd: str, check: bool = False):
        call_log.append(cmd)
        if cmd == "claude --version":
            raise FileNotFoundError("not found")
        return SuccessResult()

    assert auto_install_claude(run_cmd=fake_run) is True
    assert any("npm install" in c for c in call_log)


def test_auto_install_claude_install_fails():
    """If both claude and npm fail, return False."""

    def fake_run(cmd: str, check: bool = False):
        raise FileNotFoundError("not found")

    assert auto_install_claude(run_cmd=fake_run) is False


def test_setup_claude_web_access_default():
    url = setup_claude_web_access()
    assert url == "http://localhost:7860"


def test_setup_claude_web_access_custom():
    url = setup_claude_web_access(host="0.0.0.0", port=9000)
    assert url == "http://0.0.0.0:9000"


def test_collect_answers_new_fields():
    """Verify journal_target, needs_website, needs_mobile are collected."""
    responses = iter(
        [
            "goal",
            "paper-writing",
            "skip",
            "acc > 90%",
            "2025-12",
            "local-cpu",
            "none",
            "Nature",
            "yes",
            "yes",
        ]
    )
    answers = collect_answers("proj", prompt_fn=lambda p, d="": next(responses))
    assert answers.journal_target == "Nature"
    assert answers.needs_website is True
    assert answers.needs_mobile is True


def test_verify_uploaded_files_empty_workspace(tmp_path: Path):
    """Empty workspace triggers warnings."""
    setup_workspace(tmp_path)
    answers = OnboardingAnswers(
        project_type="paper-writing", github_repo="https://github.com/x/y"
    )
    warnings = verify_uploaded_files(tmp_path, answers)
    # Should warn about empty reference/ and uploads/ and missing code
    assert len(warnings) >= 2
    assert any("reference" in w.lower() for w in warnings)


def test_verify_uploaded_files_no_uploads_dir(tmp_path: Path):
    """Missing uploads/ directory should produce a warning."""
    answers = OnboardingAnswers(project_type="general")
    warnings = verify_uploaded_files(tmp_path, answers)
    assert any("uploads/" in w for w in warnings)


def test_verify_uploaded_files_all_present(tmp_path: Path):
    """When files are present, no warnings for general project."""
    setup_workspace(tmp_path)
    # Put a real file in uploads/
    (tmp_path / "uploads" / "data.csv").write_text("a,b\n1,2\n")
    answers = OnboardingAnswers(project_type="general")
    warnings = verify_uploaded_files(tmp_path, answers)
    assert warnings == []
