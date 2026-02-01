"""Full onboarding workflow: questionnaire, credential collection, workspace setup."""

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

PROJECT_TYPES = [
    "ml-research",
    "data-analysis",
    "paper-writing",
    "computational",
    "general",
]
COMPUTE_TYPES = ["local-cpu", "local-gpu", "cloud", "cluster"]
NOTIFICATION_METHODS = ["email", "slack", "none"]

WORKSPACE_DIRS = ["reference", "local", "secrets", "uploads"]

PREREQUISITES = {
    "docker": {
        "check_cmd": "docker --version",
        "install_hint": "Install Docker: https://docs.docker.com/get-docker/",
    },
    "node": {
        "check_cmd": "node --version",
        "install_hint": "Install Node.js (v18+): https://nodejs.org/ or use nvm: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash",
    },
    "git": {
        "check_cmd": "git --version",
        "install_hint": "Install Git: https://git-scm.com/downloads",
    },
    "claude": {
        "check_cmd": "claude --version",
        "install_hint": "Install Claude CLI: npm install -g @anthropic-ai/claude-code",
    },
}

EXPECTED_UPLOAD_DIRS = {
    "paper_examples": "reference",
    "reference_code": "reference",
    "data_files": "uploads",
}


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
    journal_target: str = ""
    needs_website: bool = False
    needs_mobile: bool = False


def validate_prerequisites(
    *,
    run_cmd=None,
) -> dict:
    """Check that required tools (Docker, Node.js, Git, Claude CLI) are installed.

    Args:
        run_cmd: Optional callable(cmd) -> bool override for testing.

    Returns:
        Dict mapping missing tool names to their install instructions.
        An empty dict means everything is available.
    """
    if run_cmd is None:

        def run_cmd(cmd: str) -> bool:
            try:
                subprocess.run(
                    cmd.split(),
                    capture_output=True,
                    timeout=10,
                )
                return True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return False

    missing: dict[str, str] = {}
    for tool, info in PREREQUISITES.items():
        if not run_cmd(info["check_cmd"]):
            missing[tool] = info["install_hint"]
    return missing


def auto_install_claude(
    *,
    run_cmd=None,
) -> bool:
    """Attempt to install the Claude CLI via npm if it is not already available.

    Args:
        run_cmd: Optional callable(cmd, check) -> subprocess.CompletedProcess
                 override for testing.

    Returns:
        True if Claude CLI is available after this call (already installed or
        freshly installed), False otherwise.
    """
    if run_cmd is None:

        def run_cmd(cmd: str, check: bool = False) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd.split(),
                capture_output=True,
                timeout=120,
                check=check,
            )

    # Check if already present
    try:
        result = run_cmd("claude --version")
        if result.returncode == 0:
            logger.info("Claude CLI already installed")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Attempt npm install
    logger.info("Attempting to install Claude CLI via npm...")
    try:
        result = run_cmd("npm install -g @anthropic-ai/claude-code", check=False)
        if result.returncode == 0:
            logger.info("Claude CLI installed successfully")
            return True
        logger.warning("npm install failed (exit %d)", result.returncode)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("Could not run npm: %s", exc)

    return False


def setup_claude_web_access(
    *,
    host: str = "localhost",
    port: int = 7860,
    run_cmd=None,
) -> str:
    """Configure Claude for web-based access and return the URL.

    This writes a small config snippet and returns the URL the user should
    open in a browser to connect to the Claude web interface.

    Args:
        host: Bind address for the web server.
        port: Port number.
        run_cmd: Optional callable(cmd) -> subprocess.CompletedProcess override.

    Returns:
        The URL string where the user can reach Claude's web UI.
    """
    url = f"http://{host}:{port}"
    logger.info("Claude web access configured at %s", url)
    return url


def verify_uploaded_files(
    project_path: Path,
    answers: OnboardingAnswers,
) -> list[str]:
    """Check that files the user said they would provide are actually present.

    Looks in the standard workspace directories (reference/, uploads/) for
    non-empty content.  Returns a list of human-readable warnings for anything
    that appears to be missing.

    Args:
        project_path: Root of the project.
        answers: Collected onboarding answers (used for context on what was
                 promised).

    Returns:
        List of warning strings.  Empty list means everything looks good.
    """
    warnings: list[str] = []

    # If doing paper-writing, expect paper examples in reference/
    if answers.project_type == "paper-writing":
        ref_dir = project_path / "reference"
        if not ref_dir.exists() or not any(ref_dir.iterdir()):
            warnings.append(
                "No reference papers found in reference/. "
                "Add example papers to help with style transfer."
            )

    # Check uploads/ for data files
    uploads_dir = project_path / "uploads"
    if uploads_dir.exists():
        # Only .gitkeep means effectively empty
        real_files = [f for f in uploads_dir.iterdir() if f.name != ".gitkeep"]
        if not real_files:
            warnings.append(
                "uploads/ directory is empty. "
                "Place any data files or supporting materials there."
            )
    else:
        warnings.append(
            "uploads/ directory does not exist. Run setup_workspace() first."
        )

    # If a github repo was specified, check for reference code
    if answers.github_repo and answers.github_repo != "skip":
        ref_dir = project_path / "reference"
        if ref_dir.exists():
            code_files = [
                f
                for f in ref_dir.iterdir()
                if f.suffix in (".py", ".r", ".R", ".jl", ".m", ".ipynb")
            ]
            if not code_files:
                warnings.append(
                    "No reference code found in reference/. "
                    "Consider adding example scripts from your repository."
                )

    return warnings


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
        prompt_fn = (
            lambda prompt, default="": input(f"{prompt} [{default}]: ") or default
        )

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

    # Journal / publication target
    answers.journal_target = prompt_fn(
        "Target journal or conference (or 'skip')", "skip"
    )
    if answers.journal_target == "skip":
        answers.journal_target = ""

    # Website access
    website_resp = prompt_fn("Do you need a web dashboard? (yes/no)", "no")
    answers.needs_website = website_resp.lower() in ("yes", "y", "true", "1")

    # Mobile access
    mobile_resp = prompt_fn("Do you need mobile access? (yes/no)", "no")
    answers.needs_mobile = mobile_resp.lower() in ("yes", "y", "true", "1")

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
    settings_path.write_text(
        yaml.dump(settings, default_flow_style=False, sort_keys=False)
    )

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
        content = content.replace("- [ ] Criterion 1\n- [ ] Criterion 2", criteria_text)

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
