"""Full onboarding workflow: questionnaire, credential collection, workspace setup."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

PROJECT_TYPES = ["ml-research", "data-analysis", "paper-writing", "computational", "general"]
COMPUTE_TYPES = ["local-cpu", "local-gpu", "cloud", "cluster"]
NOTIFICATION_METHODS = ["email", "slack", "none"]

WORKSPACE_DIRS = ["reference", "local", "secrets", "uploads"]


@dataclass
class OnboardingAnswers:
    project_name: str = ""
    goal: str = ""
    project_type: str = "ml-research"
    github_repo: str = ""
    success_criteria: list[str] = field(default_factory=list)
    timeline: str = "flexible"
    compute_type: str = "local-cpu"
    gpu_name: str = ""
    notification_method: str = "none"
    notification_email: str = ""
    slack_webhook: str = ""
    credentials: dict[str, str] = field(default_factory=dict)


def collect_answers(
    project_name: str,
    *,
    prompt_fn=None,
) -> OnboardingAnswers:
    """Collect onboarding answers interactively.

    Args:
        project_name: The project name.
        prompt_fn: Callable(prompt, default) -> str. Uses input() if None.

    Returns:
        Filled OnboardingAnswers.
    """
    if prompt_fn is None:
        prompt_fn = lambda prompt, default="": input(f"{prompt} [{default}]: ") or default

    answers = OnboardingAnswers(project_name=project_name)

    # Required
    answers.goal = prompt_fn("What is the main goal of this project?", "")
    answers.project_type = prompt_fn(
        f"Project type ({', '.join(PROJECT_TYPES)})", "ml-research"
    )
    if answers.project_type not in PROJECT_TYPES:
        answers.project_type = "ml-research"

    answers.github_repo = prompt_fn("GitHub repository URL (or 'skip')", "skip")

    # Recommended
    criteria = prompt_fn("Success criteria (comma-separated, or 'skip')", "skip")
    if criteria and criteria != "skip":
        answers.success_criteria = [c.strip() for c in criteria.split(",")]

    answers.timeline = prompt_fn("Target completion date (or 'flexible')", "flexible")

    answers.compute_type = prompt_fn(
        f"Compute resources ({', '.join(COMPUTE_TYPES)})", "local-cpu"
    )
    if answers.compute_type not in COMPUTE_TYPES:
        answers.compute_type = "local-cpu"

    if answers.compute_type == "local-gpu":
        answers.gpu_name = prompt_fn("GPU name", "")

    answers.notification_method = prompt_fn(
        f"Notification method ({', '.join(NOTIFICATION_METHODS)})", "none"
    )
    if answers.notification_method not in NOTIFICATION_METHODS:
        answers.notification_method = "none"

    if answers.notification_method == "email":
        answers.notification_email = prompt_fn("Notification email", "")
    elif answers.notification_method == "slack":
        answers.slack_webhook = prompt_fn("Slack webhook URL", "")

    return answers


def setup_workspace(project_path: Path) -> None:
    """Create workspace directories.

    Args:
        project_path: Root of the project.
    """
    for dirname in WORKSPACE_DIRS:
        d = project_path / dirname
        d.mkdir(parents=True, exist_ok=True)
        gitkeep = d / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.write_text("")
    logger.info("Workspace directories created")


def write_settings(project_path: Path, answers: OnboardingAnswers) -> Path:
    """Write the project settings file from onboarding answers.

    Args:
        project_path: Root of the project.
        answers: Collected onboarding answers.

    Returns:
        Path to the written settings file.
    """
    settings = {
        "project": {
            "name": answers.project_name,
            "type": answers.project_type,
            "created": datetime.now().isoformat(),
        },
        "compute": {
            "type": answers.compute_type,
            "gpu": answers.gpu_name,
        },
        "notifications": {
            "enabled": answers.notification_method != "none",
            "method": answers.notification_method,
        },
        "credentials": {},
    }

    if answers.notification_email:
        settings["notifications"]["email"] = answers.notification_email
    if answers.slack_webhook:
        settings["notifications"]["slack_webhook"] = answers.slack_webhook

    if answers.github_repo and answers.github_repo != "skip":
        settings["credentials"]["github_repo"] = answers.github_repo

    settings_path = project_path / "config" / "settings.yml"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(yaml.dump(settings, default_flow_style=False, sort_keys=False))

    logger.info("Settings written to %s", settings_path)
    return settings_path


def write_goal_file(project_path: Path, answers: OnboardingAnswers) -> None:
    """Write the GOAL.md file from onboarding answers.

    Args:
        project_path: Root of the project.
        answers: Collected onboarding answers.
    """
    goal_file = project_path / "knowledge" / "GOAL.md"
    if not goal_file.exists():
        return

    content = goal_file.read_text()
    content = content.replace("<!-- User provides during init -->", answers.goal)

    if answers.success_criteria:
        criteria_text = "\n".join(f"- [ ] {c}" for c in answers.success_criteria)
        content = content.replace(
            "- [ ] Criterion 1\n- [ ] Criterion 2", criteria_text
        )

    if answers.timeline and answers.timeline != "flexible":
        content = content.replace("<!-- e.g., 3 months -->", answers.timeline)

    goal_file.write_text(content)


def load_settings(project_path: Path) -> dict:
    """Load project settings from config/settings.yml.

    Args:
        project_path: Root of the project.

    Returns:
        Settings dict, or empty dict if not found.
    """
    settings_path = project_path / "config" / "settings.yml"
    if not settings_path.exists():
        return {}
    return yaml.safe_load(settings_path.read_text()) or {}
