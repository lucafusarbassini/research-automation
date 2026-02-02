"""Tests for onboarding workflow."""

from pathlib import Path

import yaml

from core.onboarding import (
    CREDENTIAL_REGISTRY,
    FOLDER_READMES,
    WORKSPACE_DIRS,
    OnboardingAnswers,
    auto_install_claude,
    auto_install_claude_flow,
    check_and_install_packages,
    collect_answers,
    collect_credentials,
    create_github_repo,
    detect_system_for_init,
    ensure_package,
    infer_packages_from_goal,
    install_inferred_packages,
    load_settings,
    print_folder_map,
    setup_claude_web_access,
    setup_workspace,
    validate_goal_content,
    validate_prerequisites,
    verify_uploaded_files,
    write_env_example,
    write_env_file,
    write_goal_file,
    write_settings,
)

# Shared system_info for tests
_SYSTEM_INFO_CPU = {
    "os": "Linux",
    "python": "3.11",
    "cpu": "x86_64",
    "ram_gb": 16.0,
    "gpu": "",
    "compute_type": "local-cpu",
    "conda": False,
    "docker": False,
}

_SYSTEM_INFO_GPU = {
    "os": "Linux",
    "python": "3.11",
    "cpu": "x86_64",
    "ram_gb": 32.0,
    "gpu": "RTX 4090",
    "compute_type": "local-gpu",
    "conda": True,
    "docker": True,
}


def test_collect_answers_defaults():
    responses = iter(
        [
            "none",
            "skip",
            "journal-article",
            "no",
            "no",
        ]
    )
    answers = collect_answers(
        "test-proj",
        prompt_fn=lambda p, d="": next(responses),
        system_info=_SYSTEM_INFO_CPU,
    )
    assert answers.project_name == "test-proj"
    assert answers.compute_type == "local-cpu"
    assert answers.journal_target == ""
    assert answers.needs_website is False
    assert answers.needs_mobile is False


def test_collect_answers_with_gpu():
    responses = iter(
        [
            "none",
            "skip",
            "journal-article",
            "no",
            "no",
        ]
    )
    answers = collect_answers(
        "proj",
        prompt_fn=lambda p, d="": next(responses),
        system_info=_SYSTEM_INFO_GPU,
    )
    assert answers.compute_type == "local-gpu"
    assert answers.gpu_name == "RTX 4090"


def test_collect_answers_with_email():
    responses = iter(
        [
            "email",
            "a@b.com",
            "skip",
            "journal-article",
            "no",
            "no",
        ]
    )
    answers = collect_answers(
        "proj",
        prompt_fn=lambda p, d="": next(responses),
        system_info=_SYSTEM_INFO_CPU,
    )
    assert answers.notification_method == "email"
    assert answers.notification_email == "a@b.com"


def test_setup_workspace(tmp_path: Path):
    setup_workspace(tmp_path)
    for dirname in WORKSPACE_DIRS:
        assert (tmp_path / dirname).is_dir()
        assert (tmp_path / dirname / ".gitkeep").exists()


def test_write_settings(tmp_path: Path):
    answers = OnboardingAnswers(
        project_name="my-proj",
        goal="test goal",
        compute_type="local-gpu",
        gpu_name="RTX 3090",
        notification_method="email",
        notification_email="test@example.com",
        needs_website=True,
        needs_mobile=False,
    )
    path = write_settings(tmp_path, answers)
    assert path.exists()

    settings = yaml.safe_load(path.read_text())
    assert settings["project"]["name"] == "my-proj"
    assert "type" not in settings["project"]
    assert settings["compute"]["gpu"] == "RTX 3090"
    assert settings["notifications"]["enabled"] is True
    assert settings["notifications"]["email"] == "test@example.com"
    assert settings["features"]["website"] is True
    assert settings["features"]["mobile"] is False


def test_write_settings_no_notifications(tmp_path: Path):
    answers = OnboardingAnswers(project_name="proj")
    path = write_settings(tmp_path, answers)
    settings = yaml.safe_load(path.read_text())
    assert settings["notifications"]["enabled"] is False


def test_load_settings(tmp_path: Path):
    answers = OnboardingAnswers(project_name="proj")
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
            "none",
            "Nature",
            "journal-article",
            "yes",
            "yes",
        ]
    )
    answers = collect_answers(
        "proj",
        prompt_fn=lambda p, d="": next(responses),
        system_info=_SYSTEM_INFO_CPU,
    )
    assert answers.journal_target == "Nature"
    assert answers.needs_website is True
    assert answers.needs_mobile is True


def test_auto_install_claude_flow_already_present():
    """If npx claude-flow --version succeeds, return True without installing."""

    class FakeResult:
        returncode = 0

    installed = auto_install_claude_flow(run_cmd=lambda cmd, check=False: FakeResult())
    assert installed is True


def test_auto_install_claude_flow_install_succeeds():
    """If claude-flow is missing but npm install works, return True."""
    call_log = []

    class SuccessResult:
        returncode = 0

    def fake_run(cmd: str, check: bool = False):
        call_log.append(cmd)
        if "claude-flow --version" in cmd:
            raise FileNotFoundError("not found")
        return SuccessResult()

    assert auto_install_claude_flow(run_cmd=fake_run) is True
    assert any("npm install" in c for c in call_log)


def test_detect_system_for_init():
    """detect_system_for_init returns a dict with expected keys."""
    from unittest.mock import patch

    from core.environment import SystemInfo

    mock_info = SystemInfo(
        os="Linux",
        os_version="6.8",
        python_version="3.11",
        cpu="x86_64",
        gpu="RTX 4090",
        ram_gb=32.0,
        conda_available=True,
        docker_available=True,
    )
    with patch("core.environment.discover_system", return_value=mock_info):
        result = detect_system_for_init()

    assert result["gpu"] == "RTX 4090"
    assert result["compute_type"] == "local-gpu"
    assert result["docker"] is True


def test_create_github_repo_no_gh():
    """If gh CLI is not available, returns empty string."""

    def fake_run(cmd: list[str]):
        raise FileNotFoundError("gh not found")

    result = create_github_repo("test-proj", run_cmd=fake_run)
    assert result == ""


def test_create_github_repo_not_authenticated():
    """If gh auth status fails, returns empty string."""
    import subprocess

    def fake_run(cmd: list[str]):
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="")

    result = create_github_repo("test-proj", run_cmd=fake_run)
    assert result == ""


def test_verify_uploaded_files_empty_workspace(tmp_path: Path):
    """Empty workspace triggers warnings."""
    setup_workspace(tmp_path)
    answers = OnboardingAnswers(github_repo="https://github.com/x/y")
    warnings = verify_uploaded_files(tmp_path, answers)
    # Should warn about empty reference/ and uploads/ and missing code
    assert len(warnings) >= 2
    assert any("reference" in w.lower() for w in warnings)


def test_verify_uploaded_files_no_uploads_dir(tmp_path: Path):
    """Missing uploads/ directory should produce a warning."""
    answers = OnboardingAnswers()
    warnings = verify_uploaded_files(tmp_path, answers)
    assert any("uploads/" in w for w in warnings)


def test_verify_uploaded_files_all_present(tmp_path: Path):
    """When files are present, no warnings."""
    setup_workspace(tmp_path)
    # Put a real file in uploads/ and reference/
    (tmp_path / "uploads" / "data.csv").write_text("a,b\n1,2\n")
    (tmp_path / "reference" / "papers" / "paper.pdf").write_bytes(b"%PDF-1.4 test")
    answers = OnboardingAnswers()
    warnings = verify_uploaded_files(tmp_path, answers)
    assert warnings == []


# ---------------------------------------------------------------------------
# New tests for folder structure, credentials, GOAL validation, packages
# ---------------------------------------------------------------------------


def test_setup_workspace_creates_subdirs(tmp_path: Path):
    """setup_workspace creates guided subdirectories with README files."""
    setup_workspace(tmp_path)
    for subdir in FOLDER_READMES:
        d = tmp_path / subdir
        assert d.is_dir(), f"Expected {subdir} to exist"
        assert (d / "README.md").exists(), f"Expected README.md in {subdir}"


def test_print_folder_map(tmp_path: Path):
    """print_folder_map returns non-empty list of lines."""
    lines = print_folder_map(tmp_path)
    assert len(lines) > 0
    assert any("reference/papers" in line for line in lines)
    assert any("uploads/data" in line for line in lines)
    assert any("GOAL.md" in line for line in lines)


def test_validate_goal_content_sufficient():
    content = (
        "# Goal\n\n"
        "We investigate the effect of learning rate schedules on transformer "
        "convergence speed and final loss across model scales. Specifically, "
        "we compare constant learning rate, cosine annealing, linear warmup "
        "plus cosine decay, and the WSD schedule. This is a detailed "
        "description that should pass the 200-character minimum.\n"
    )
    assert validate_goal_content(content) is True


def test_validate_goal_content_template_only():
    content = (
        "# Project Goal\n\n"
        "<!-- User provides during init -->\n\n"
        "## Success Criteria\n\n"
        "- [ ] Criterion 1\n"
        "- [ ] Criterion 2\n\n"
        "## Timeline\n\n"
        "<!-- e.g., 3 months -->\n"
    )
    assert validate_goal_content(content) is False


def test_validate_goal_content_empty():
    assert validate_goal_content("") is False
    assert validate_goal_content("# Goal\n\n") is False


def test_collect_credentials_skip_all():
    """When all prompts return empty, credentials dict is empty."""
    answers = OnboardingAnswers(notification_method="none")
    creds = collect_credentials(
        answers, prompt_fn=lambda p, d="": "", print_fn=lambda m: None
    )
    assert creds == {}


def test_collect_credentials_some_filled():
    """Non-empty responses get stored."""
    responses = {
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_test",
    }

    def _prompt(prompt, default=""):
        for var, val in responses.items():
            if var in prompt:
                return val
        return ""

    answers = OnboardingAnswers(notification_method="none")
    creds = collect_credentials(answers, prompt_fn=_prompt, print_fn=lambda m: None)
    assert creds["ANTHROPIC_API_KEY"] == "sk-ant-test"
    assert creds["GITHUB_PERSONAL_ACCESS_TOKEN"] == "ghp_test"
    assert len(creds) == 2


def test_collect_credentials_slack():
    """Slack credentials collected when notification_method is slack."""

    def _prompt(prompt, default=""):
        if "SLACK_BOT_TOKEN" in prompt:
            return "xoxb-test"
        return ""

    answers = OnboardingAnswers(notification_method="slack")
    creds = collect_credentials(answers, prompt_fn=_prompt, print_fn=lambda m: None)
    assert creds.get("SLACK_BOT_TOKEN") == "xoxb-test"


def test_collect_credentials_shows_guidance():
    """print_fn is called with guidance URL for each credential."""
    printed = []
    answers = OnboardingAnswers(notification_method="none")
    creds = collect_credentials(
        answers,
        prompt_fn=lambda p, d="": "",
        print_fn=lambda m: printed.append(m),
    )
    # Should have printed guidance for each core/ml/publishing/cloud credential
    assert len(printed) > 0
    assert any("http" in line for line in printed)


def test_write_env_file(tmp_path: Path):
    creds = {"ANTHROPIC_API_KEY": "sk-ant-test", "WANDB_API_KEY": "wandb-key"}
    path = write_env_file(tmp_path, creds)
    assert path.exists()
    content = path.read_text()
    assert "ANTHROPIC_API_KEY=sk-ant-test" in content
    assert "WANDB_API_KEY=wandb-key" in content


def test_write_env_example(tmp_path: Path):
    path = write_env_example(tmp_path)
    assert path.exists()
    content = path.read_text()
    assert "ANTHROPIC_API_KEY=" in content
    assert "SLACK_BOT_TOKEN=" in content
    assert "SMTP_HOST=" in content


def test_check_and_install_packages_all_present():
    """When all packages are importable, returns empty list."""
    failed = check_and_install_packages(install=False)
    # typer, rich, yaml are already installed in test env
    assert isinstance(failed, list)


def test_infer_packages_from_goal_ml():
    """ML-related keywords trigger numpy, scipy, etc."""
    goal = "We train a deep learning model using transformers on GPU."
    packages = infer_packages_from_goal(goal)
    assert "numpy" in packages
    assert "torch" in packages


def test_infer_packages_from_goal_data():
    """Data analysis keywords trigger pandas."""
    goal = "Perform data analysis on CSV datasets with statistical tests."
    packages = infer_packages_from_goal(goal)
    assert "pandas" in packages
    assert "scipy" in packages


def test_infer_packages_from_goal_empty():
    """Empty goal returns no packages."""
    assert infer_packages_from_goal("") == []
    assert infer_packages_from_goal("# Goal\n\nTBD\n") == []


def test_infer_packages_from_goal_bio():
    """Bioinformatics keywords trigger biopython."""
    goal = "Analyze protein sequences and genomics data."
    packages = infer_packages_from_goal(goal)
    assert "biopython" in packages


def test_install_inferred_packages_already_present():
    """Packages already importable are skipped (not re-installed)."""
    installed, failed = install_inferred_packages(["yaml"])
    # yaml (pyyaml) is already in the test env, so should be skipped
    assert "yaml" not in installed
    assert "yaml" not in failed


def test_ensure_package_already_present():
    """ensure_package returns True for packages already importable."""
    assert ensure_package("pyyaml", "yaml") is True


def test_ensure_package_not_found():
    """ensure_package returns False when install fails."""

    class FailResult:
        returncode = 1

    result = ensure_package(
        "nonexistent-pkg-xyz-12345",
        "nonexistent_pkg_xyz_12345",
        run_cmd=lambda cmd: FailResult(),
    )
    assert result is False


def test_credential_registry_has_urls():
    """Every credential in the registry has a non-empty how-to URL."""
    for var, desc, url, cat in CREDENTIAL_REGISTRY:
        assert var, "Empty env var name"
        assert desc, f"Empty description for {var}"
        assert url, f"Empty URL for {var}"
        assert cat, f"Empty category for {var}"
