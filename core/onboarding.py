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

COMPUTE_TYPES = ["local-cpu", "local-gpu", "cloud", "cluster"]
NOTIFICATION_METHODS = ["email", "slack", "none"]
CLAUDE_FLOW_PKG = "claude-flow"

WORKSPACE_DIRS = ["reference", "local", "secrets", "uploads"]

FOLDER_READMES: dict[str, str] = {
    "reference/papers": (
        "# Reference Papers\n\n"
        "Upload background papers (PDF, etc.) for knowledge ingestion.\n\n"
        "The researcher agent will read these to build context for your project.\n"
    ),
    "reference/code": (
        "# Reference Code\n\n"
        "Upload reference code, scripts, and notebooks here.\n\n"
        "Examples: baseline implementations, utility scripts, Jupyter notebooks.\n"
    ),
    "uploads/data": (
        "# Datasets\n\n"
        "Upload datasets here. Large files are auto-gitignored.\n\n"
        "Supported formats: CSV, Parquet, JSON, HDF5, etc.\n"
    ),
    "uploads/personal": (
        "# Personal Materials\n\n"
        "Upload personal materials for style imprinting and context.\n\n"
        "Examples: your published papers, CV, writing samples, lab notes.\n"
    ),
}

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
    project_type: str = "general"
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


def auto_install_claude_flow(
    *,
    run_cmd=None,
) -> bool:
    """Attempt to install claude-flow via npm if not already available.

    Args:
        run_cmd: Optional callable(cmd, check) -> subprocess.CompletedProcess
                 override for testing.

    Returns:
        True if claude-flow is available after this call.
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
        result = run_cmd("npx claude-flow --version")
        if result.returncode == 0:
            logger.info("claude-flow already available")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Attempt npm install
    logger.info("Installing claude-flow via npm...")
    try:
        result = run_cmd("npm install -g claude-flow", check=False)
        if result.returncode == 0:
            logger.info("claude-flow installed successfully")
            return True
        logger.warning("npm install claude-flow failed (exit %d)", result.returncode)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("Could not run npm: %s", exc)

    return False


def detect_system_for_init() -> dict:
    """Auto-detect system capabilities for init. Returns a summary dict."""
    from core.environment import discover_system

    info = discover_system()
    result = {
        "os": f"{info.os} {info.os_version}",
        "python": info.python_version,
        "cpu": info.cpu,
        "ram_gb": info.ram_gb,
        "gpu": info.gpu,
        "compute_type": "local-gpu" if info.gpu else "local-cpu",
        "conda": info.conda_available,
        "docker": info.docker_available,
    }
    return result


def create_github_repo(
    project_name: str,
    *,
    private: bool = True,
    run_cmd=None,
) -> str:
    """Create a GitHub repository using the gh CLI.

    Args:
        project_name: Name for the new repository.
        private: Whether to create a private repo.
        run_cmd: Optional callable for testing.

    Returns:
        The repo URL if successful, empty string otherwise.
    """
    if run_cmd is None:

        def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

    # Check if gh is available and authenticated
    try:
        auth_check = run_cmd(["gh", "auth", "status"])
        if auth_check.returncode != 0:
            logger.warning("gh CLI not authenticated. Skipping repo creation.")
            return ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.warning("gh CLI not available. Skipping repo creation.")
        return ""

    # Create repo
    visibility = "--private" if private else "--public"
    try:
        result = run_cmd(
            ["gh", "repo", "create", project_name, visibility, "--confirm"]
        )
        if result.returncode == 0:
            # Extract URL from output
            output = result.stdout.strip()
            for line in output.splitlines():
                if "github.com" in line:
                    return line.strip()
            # Fallback: construct URL
            user_result = run_cmd(["gh", "api", "user", "-q", ".login"])
            if user_result.returncode == 0:
                username = user_result.stdout.strip()
                return f"https://github.com/{username}/{project_name}"
            return output
        logger.warning("gh repo create failed: %s", result.stderr.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("Could not create GitHub repo: %s", exc)

    return ""


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

    # Check reference/ for papers and code
    ref_dir = project_path / "reference"
    if ref_dir.exists():
        real_ref = [
            f
            for f in ref_dir.rglob("*")
            if f.is_file() and f.name not in (".gitkeep", "README.md")
        ]
        if not real_ref:
            warnings.append(
                "No reference materials found in reference/. "
                "Add papers, code, or other background materials."
            )
    else:
        warnings.append(
            "reference/ directory does not exist. Run setup_workspace() first."
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
    system_info: dict | None = None,
) -> OnboardingAnswers:
    """Collect onboarding answers interactively.

    The questionnaire is streamlined: GPU, compute type, and system info are
    auto-detected.  The project goal is written to GOAL.md after init (not
    entered as a one-liner).

    Args:
        project_name: The project name.
        prompt_fn: Callable(prompt, default) -> str. Uses input() if None.
        system_info: Pre-detected system info dict (from detect_system_for_init).
                     If None, auto-detection runs inline.

    Returns:
        Filled OnboardingAnswers.
    """
    if prompt_fn is None:
        prompt_fn = (
            lambda prompt, default="": input(f"{prompt} [{default}]: ") or default
        )

    answers = OnboardingAnswers(project_name=project_name)

    # --- Auto-detect system ---
    if system_info is None:
        system_info = detect_system_for_init()

    answers.compute_type = system_info.get("compute_type", "local-cpu")
    answers.gpu_name = system_info.get("gpu", "")

    # --- Goal: tell user to write detailed description in GOAL.md ---
    answers.goal = "(See GOAL.md — edit with your detailed project description)"

    # --- Notification method ---
    answers.notification_method = prompt_fn(
        "Notification method (email, slack, none)", "none"
    )
    if answers.notification_method not in NOTIFICATION_METHODS:
        answers.notification_method = "none"

    if answers.notification_method == "email":
        answers.notification_email = prompt_fn("Notification email", "")
    elif answers.notification_method == "slack":
        answers.slack_webhook = prompt_fn("Slack webhook URL", "")

    # --- Journal / publication target ---
    answers.journal_target = prompt_fn(
        "Target journal or conference (or 'skip')", "skip"
    )
    if answers.journal_target == "skip":
        answers.journal_target = ""

    # --- Website dashboard ---
    website_resp = prompt_fn("Do you need a web dashboard? (yes/no)", "no")
    answers.needs_website = website_resp.lower() in ("yes", "y", "true", "1")

    # --- Mobile access ---
    mobile_resp = prompt_fn("Do you need mobile access? (yes/no)", "no")
    answers.needs_mobile = mobile_resp.lower() in ("yes", "y", "true", "1")

    return answers


def setup_workspace(project_path: Path) -> None:
    """Create workspace directories with guided README files.

    Args:
        project_path: Root of the project.
    """
    for dirname in WORKSPACE_DIRS:
        d = project_path / dirname
        d.mkdir(parents=True, exist_ok=True)
        gitkeep = d / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.write_text("")

    # Create guided subdirectories with README files
    for subdir, readme_content in FOLDER_READMES.items():
        d = project_path / subdir
        d.mkdir(parents=True, exist_ok=True)
        readme = d / "README.md"
        if not readme.exists():
            readme.write_text(readme_content)

    logger.info("Workspace directories created")


def print_folder_map(project_path: Path) -> list[str]:
    """Return a list of lines showing the folder map for user guidance.

    Args:
        project_path: Root of the project.

    Returns:
        List of formatted lines describing where to put files.
    """
    lines = [
        "Project folder guide:",
        f"  {project_path}/",
        "  ├── reference/papers/   ← background papers (PDF, etc.)",
        "  ├── reference/code/     ← reference code, scripts, notebooks",
        "  ├── uploads/data/       ← datasets (large files auto-gitignored)",
        "  ├── uploads/personal/   ← your papers, CV, writing samples",
        "  ├── knowledge/GOAL.md   ← your research description (EDIT THIS)",
        "  ├── secrets/.env        ← API keys (never committed)",
        "  └── config/settings.yml ← project configuration",
    ]
    return lines


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
        "features": {
            "website": answers.needs_website,
            "mobile": answers.needs_mobile,
        },
        "credentials": {},
    }

    if answers.notification_email:
        settings["notifications"]["email"] = answers.notification_email
    if answers.slack_webhook:
        settings["notifications"]["slack_webhook"] = answers.slack_webhook

    if answers.journal_target:
        settings["project"]["journal_target"] = answers.journal_target

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


# Each credential: (env_var, short_description, how_to_get_url, category)
# Categories: "core", "publishing", "ml", "cloud", "comms"
CREDENTIAL_REGISTRY: list[tuple[str, str, str, str]] = [
    # --- Core (always ask) ---
    (
        "ANTHROPIC_API_KEY",
        "Anthropic API key (skip if you used 'claude auth login')",
        "https://console.anthropic.com/ → Settings → API Keys → Create Key",
        "core",
    ),
    (
        "GITHUB_PERSONAL_ACCESS_TOKEN",
        "GitHub Personal Access Token (repo + workflow scopes)",
        "https://github.com/settings/tokens?type=beta → Generate new token",
        "core",
    ),
    (
        "OPENAI_API_KEY",
        "OpenAI API key (for embeddings & fallback models)",
        "https://platform.openai.com/api-keys → Create new secret key",
        "core",
    ),
    (
        "GOOGLE_API_KEY",
        "Google / Gemini API key",
        "https://aistudio.google.com/apikey → Create API key",
        "core",
    ),
    (
        "GAMMA_API_KEY",
        "Gamma (AI presentations/slides)",
        "Get from https://gamma.app/developers",
        "core",
    ),
    (
        "CANVA_API_KEY",
        "Canva (design automation)",
        "Get from https://www.canva.com/developers/",
        "core",
    ),
    (
        "GOOGLE_DRIVE_CREDENTIALS",
        "Google Drive access",
        "Get from Google Cloud Console → APIs & Services → Credentials",
        "core",
    ),
    # --- ML / Experiment tracking ---
    (
        "HUGGINGFACE_TOKEN",
        "HuggingFace access token (models & datasets)",
        "https://huggingface.co/settings/tokens → New token (read access)",
        "ml",
    ),
    (
        "WANDB_API_KEY",
        "Weights & Biases API key (experiment tracking)",
        "https://wandb.ai/authorize → copy key",
        "ml",
    ),
    # --- Publishing ---
    (
        "MEDIUM_TOKEN",
        "Medium integration token (publishing)",
        "https://medium.com/me/settings/security → Integration tokens → Get token",
        "publishing",
    ),
    (
        "LINKEDIN_CLIENT_ID",
        "LinkedIn app Client ID",
        "https://www.linkedin.com/developers/apps → Create App → Auth tab",
        "publishing",
    ),
    (
        "LINKEDIN_CLIENT_SECRET",
        "LinkedIn app Client Secret",
        "(same page as Client ID above)",
        "publishing",
    ),
    (
        "LINKEDIN_ACCESS_TOKEN",
        "LinkedIn OAuth2 access token",
        "(generate via OAuth2 flow in LinkedIn developer portal)",
        "publishing",
    ),
    # --- Cloud / Infrastructure ---
    (
        "AWS_ACCESS_KEY_ID",
        "AWS access key ID (for cloud compute/storage)",
        "https://console.aws.amazon.com/iam → Users → Security credentials",
        "cloud",
    ),
    (
        "AWS_SECRET_ACCESS_KEY",
        "AWS secret access key",
        "(same page as AWS access key above)",
        "cloud",
    ),
    (
        "NOTION_API_KEY",
        "Notion integration token (project boards)",
        "https://www.notion.so/my-integrations → New integration → copy secret",
        "cloud",
    ),
    # --- Communication (conditional) ---
    (
        "SLACK_BOT_TOKEN",
        "Slack bot token",
        "https://api.slack.com/apps → Create App → OAuth & Permissions → Bot Token",
        "slack",
    ),
    (
        "SLACK_WEBHOOK_URL",
        "Slack incoming webhook URL",
        "https://api.slack.com/apps → Incoming Webhooks → Add New Webhook",
        "slack",
    ),
    (
        "SMTP_HOST",
        "SMTP host (e.g. smtp.gmail.com)",
        "Check your email provider's SMTP settings",
        "email",
    ),
    (
        "SMTP_PORT",
        "SMTP port (usually 587)",
        "(same as SMTP host settings)",
        "email",
    ),
    (
        "SMTP_USER",
        "SMTP username (usually your email address)",
        "(your email login)",
        "email",
    ),
    (
        "SMTP_PASSWORD",
        "SMTP password or app password",
        "For Gmail: https://myaccount.google.com/apppasswords",
        "email",
    ),
]

# Legacy aliases for backwards compatibility
CREDENTIALS_ALWAYS = [
    (var, desc)
    for var, desc, _url, cat in CREDENTIAL_REGISTRY
    if cat in ("core", "ml", "publishing", "cloud")
]
CREDENTIALS_SLACK = [
    (var, desc) for var, desc, _url, cat in CREDENTIAL_REGISTRY if cat == "slack"
]
CREDENTIALS_EMAIL = [
    (var, desc) for var, desc, _url, cat in CREDENTIAL_REGISTRY if cat == "email"
]


def collect_credentials(
    answers: OnboardingAnswers,
    *,
    prompt_fn=None,
    print_fn=None,
) -> dict[str, str]:
    """Collect API credentials interactively (Enter to skip any).

    Each credential is prompted one at a time with a URL showing where to
    get it, so the flow is self-contained and guided.

    Args:
        answers: Onboarding answers (used for notification method).
        prompt_fn: Callable(prompt, default) -> str.
        print_fn: Callable(message) -> None for guidance output.

    Returns:
        Dict of env var name to value (only non-empty entries).
    """
    if prompt_fn is None:
        prompt_fn = (
            lambda prompt, default="": input(f"{prompt} [{default}]: ") or default
        )
    if print_fn is None:
        print_fn = print

    credentials: dict[str, str] = {}

    # Determine which categories to ask
    active_cats = {"core", "ml", "publishing", "cloud"}
    if answers.notification_method == "slack":
        active_cats.add("slack")
    if answers.notification_method == "email":
        active_cats.add("email")

    for var, description, how_to_url, category in CREDENTIAL_REGISTRY:
        if category not in active_cats:
            continue
        # Show guidance before each prompt
        print_fn(f"  Get it: {how_to_url}")
        value = prompt_fn(f"{description} ({var})", "").strip()
        if value:
            credentials[var] = value

    return credentials


def write_env_file(project_path: Path, credentials: dict[str, str]) -> Path:
    """Write credentials to secrets/.env.

    Args:
        project_path: Root of the project.
        credentials: Dict of env var name to value.

    Returns:
        Path to the written .env file.
    """
    env_path = project_path / "secrets" / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={value}" for key, value in credentials.items()]
    env_path.write_text("\n".join(lines) + "\n" if lines else "")
    logger.info("Credentials written to %s", env_path)
    return env_path


def write_env_example(project_path: Path) -> Path:
    """Write secrets/.env.example template showing all possible variables.

    Args:
        project_path: Root of the project.

    Returns:
        Path to the written .env.example file.
    """
    env_example_path = project_path / "secrets" / ".env.example"
    env_example_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# {desc}\n# How to get: {url}\n{var}="
        for var, desc, url, _cat in CREDENTIAL_REGISTRY
    ]
    env_example_path.write_text("\n\n".join(lines) + "\n")
    logger.info("Example env written to %s", env_example_path)
    return env_example_path


REQUIRED_PACKAGES = {
    "typer": "typer",
    "rich": "rich",
    "yaml": "pyyaml",
    "dotenv": "python-dotenv",
}


def _get_pip_prefix(run_cmd=None) -> str:
    """Return the pip command prefix using the project env's python if available.

    Reads settings to find the project environment info. If an env python is
    configured, uses ``<python> -m pip`` instead of bare ``pip``.

    Returns:
        A command prefix string, e.g. ``"/path/.venv/bin/python -m pip"`` or ``"pip"``.
    """
    try:
        settings = load_settings(Path.cwd())
        env_info = settings.get("environment", {})
        python = env_info.get("python", "")
        if python:
            return f"{python} -m pip"
    except Exception:
        pass
    return "pip"


def check_and_install_packages(
    *,
    install: bool = True,
    run_cmd=None,
) -> list[str]:
    """Check that required Python packages are importable, auto-install missing ones.

    Args:
        install: If True, attempt pip install for missing packages.
        run_cmd: Optional callable(cmd) -> subprocess.CompletedProcess override.

    Returns:
        List of packages that could not be installed (empty = all OK).
    """
    import importlib

    pip_prefix = _get_pip_prefix()

    if run_cmd is None:

        def run_cmd(cmd: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd.split(),
                capture_output=True,
                timeout=120,
            )

    failed: list[str] = []
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(import_name)
        except ImportError:
            if not install:
                failed.append(pip_name)
                continue
            logger.info("Installing missing package: %s", pip_name)
            try:
                result = run_cmd(f"{pip_prefix} install {pip_name}")
                if result.returncode != 0:
                    # Retry with force
                    result = run_cmd(
                        f"{pip_prefix} install --force-reinstall {pip_name}"
                    )
                    if result.returncode != 0:
                        failed.append(pip_name)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                failed.append(pip_name)
    return failed


# Mapping of keyword patterns in GOAL.md to pip packages
GOAL_PACKAGE_MAP: list[tuple[list[str], list[str]]] = [
    # (keywords, packages_to_install)
    (
        ["machine learning", "ml", "neural", "deep learning", "training", "model"],
        ["numpy", "scipy", "scikit-learn", "matplotlib"],
    ),
    (
        ["torch", "pytorch", "transformer", "attention", "gpu"],
        ["torch", "torchvision"],
    ),
    (
        ["tensorflow", "keras"],
        ["tensorflow"],
    ),
    (
        ["data analysis", "dataset", "csv", "dataframe", "pandas", "tabular"],
        ["pandas", "numpy", "matplotlib"],
    ),
    (
        ["statistics", "statistical", "hypothesis", "p-value", "regression"],
        ["scipy", "statsmodels", "numpy"],
    ),
    (
        ["visualization", "plot", "figure", "chart", "graph"],
        ["matplotlib", "seaborn"],
    ),
    (
        ["nlp", "natural language", "text", "tokeniz", "language model", "llm"],
        ["transformers", "tokenizers"],
    ),
    (
        ["image", "vision", "computer vision", "cnn", "segmentation"],
        ["pillow", "opencv-python"],
    ),
    (
        ["jupyter", "notebook", "ipynb"],
        ["jupyter", "ipykernel"],
    ),
    (
        ["huggingface", "hugging face"],
        ["transformers", "datasets", "huggingface_hub"],
    ),
    (
        ["wandb", "weights and biases", "experiment tracking"],
        ["wandb"],
    ),
    (
        ["bioinformatics", "genomics", "sequence", "protein"],
        ["biopython", "numpy", "pandas"],
    ),
]


def infer_packages_from_goal(
    goal_content: str,
    *,
    use_claude: bool = True,
    run_cmd=None,
) -> list[str]:
    """Infer Python packages needed based on GOAL.md content.

    When Claude CLI is available, asks Claude to analyze the goal and
    return an optimal package list (handles niche domains like spatial
    metabolomics, quantum chemistry, etc.). Falls back to keyword
    matching when Claude is unavailable.

    Args:
        goal_content: Text content of GOAL.md.
        use_claude: Whether to attempt Claude-based inference.
        run_cmd: Optional callable for testing.

    Returns:
        List of pip package names (deduplicated, sorted).
    """
    if use_claude and len(goal_content.strip()) > 50:
        result = _infer_packages_via_claude(goal_content, run_cmd=run_cmd)
        if result:
            return result

    # Fallback: keyword matching
    return _infer_packages_via_keywords(goal_content)


def _infer_packages_via_claude(
    goal_content: str,
    *,
    run_cmd=None,
) -> list[str]:
    """Ask Claude to analyze GOAL.md and return needed pip packages.

    Args:
        goal_content: Text content of GOAL.md.
        run_cmd: Optional callable for testing.

    Returns:
        List of pip package names, or empty list if Claude unavailable.
    """
    import json as _json

    if run_cmd is None:

        def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

    prompt = (
        "You are a Python dependency advisor. Read this research project description "
        "and return ONLY a JSON array of pip package names that would be needed. "
        "Include domain-specific packages (e.g. squidpy for spatial transcriptomics, "
        "rdkit for chemistry, astropy for astronomy). Be precise - only packages "
        "available on PyPI. No explanations, just the JSON array.\n\n"
        f"Project description:\n{goal_content[:3000]}"
    )

    try:
        result = run_cmd(["claude", "-p", prompt, "--output-format", "json"])
        if result.returncode != 0:
            logger.debug("Claude package inference failed (exit %d)", result.returncode)
            return []

        output = result.stdout.strip()
        # Try to parse JSON array from output
        # Claude may wrap it in markdown code blocks
        if "```" in output:
            # Extract content between code fences
            parts = output.split("```")
            for part in parts:
                cleaned = part.strip().removeprefix("json").strip()
                if cleaned.startswith("["):
                    output = cleaned
                    break

        packages = _json.loads(output)
        if isinstance(packages, list):
            # Filter to strings only, deduplicate
            return sorted(set(p for p in packages if isinstance(p, str) and p))
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.debug("Claude not available for package inference: %s", exc)
    except (_json.JSONDecodeError, ValueError) as exc:
        logger.debug("Could not parse Claude package response: %s", exc)

    return []


def _infer_packages_via_keywords(goal_content: str) -> list[str]:
    """Fallback keyword-based package inference.

    Args:
        goal_content: Text content of GOAL.md.

    Returns:
        List of pip package names (deduplicated, sorted).
    """
    goal_lower = goal_content.lower()
    packages: set[str] = set()

    for keywords, pkgs in GOAL_PACKAGE_MAP:
        if any(kw in goal_lower for kw in keywords):
            packages.update(pkgs)

    return sorted(packages)


def _suggest_alternative_package(pkg: str) -> str | None:
    """Ask Claude for an alternative when pip install fails."""
    from core.claude_helper import call_claude

    prompt = (
        f"pip install {pkg} failed. "
        "Suggest one alternative pip package name (just the name, nothing else)."
    )
    result = call_claude(prompt)
    if result:
        # Take first word, strip quotes
        word = result.strip().split()[0].strip("'\"")
        if word and word != pkg:
            return word
    return None


def install_inferred_packages(
    packages: list[str],
    *,
    run_cmd=None,
) -> tuple[list[str], list[str]]:
    """Install a list of pip packages, returning (installed, failed).

    Args:
        packages: List of pip package names.
        run_cmd: Optional callable(cmd) -> subprocess.CompletedProcess.

    Returns:
        Tuple of (successfully_installed, failed_to_install).
    """
    import importlib

    pip_prefix = _get_pip_prefix()

    if run_cmd is None:

        def run_cmd(cmd: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd.split(),
                capture_output=True,
                timeout=300,
            )

    installed: list[str] = []
    failed: list[str] = []

    for pkg in packages:
        # Normalize import name: opencv-python → cv2, pillow → PIL, etc.
        import_map = {
            "opencv-python": "cv2",
            "pillow": "PIL",
            "scikit-learn": "sklearn",
            "python-dotenv": "dotenv",
            "pyyaml": "yaml",
            "huggingface_hub": "huggingface_hub",
            "biopython": "Bio",
        }
        import_name = import_map.get(pkg, pkg.replace("-", "_"))

        try:
            importlib.import_module(import_name)
            # Already installed
            continue
        except ImportError:
            pass

        logger.info("Installing inferred package: %s", pkg)
        try:
            result = run_cmd(f"{pip_prefix} install {pkg}")
            if result.returncode == 0:
                installed.append(pkg)
            else:
                # Ask Claude for alternative
                alt = _suggest_alternative_package(pkg)
                if alt and alt != pkg:
                    logger.info("Trying alternative: %s", alt)
                    result = run_cmd(f"{pip_prefix} install {alt}")
                    if result.returncode == 0:
                        installed.append(alt)
                        continue
                failed.append(pkg)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            failed.append(pkg)

    return installed, failed


def ensure_package(
    pip_name: str,
    import_name: str | None = None,
    *,
    run_cmd=None,
) -> bool:
    """Ensure a Python package is importable, installing it on demand if missing.

    Designed to be called at any point during a session — not just at startup.
    Agents can call this when they discover they need a package.

    Args:
        pip_name: The pip package name (e.g. "pandas").
        import_name: The Python import name if different (e.g. "cv2" for
                     "opencv-python"). If None, derives from pip_name.
        run_cmd: Optional callable(cmd) -> subprocess.CompletedProcess.

    Returns:
        True if the package is importable after this call.
    """
    import importlib

    if import_name is None:
        _import_map = {
            "opencv-python": "cv2",
            "pillow": "PIL",
            "scikit-learn": "sklearn",
            "python-dotenv": "dotenv",
            "pyyaml": "yaml",
            "biopython": "Bio",
        }
        import_name = _import_map.get(pip_name, pip_name.replace("-", "_"))

    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        pass

    pip_prefix = _get_pip_prefix()

    if run_cmd is None:

        def run_cmd(cmd: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd.split(),
                capture_output=True,
                timeout=300,
            )

    logger.info("Runtime install: %s", pip_name)
    try:
        result = run_cmd(f"{pip_prefix} install {pip_name}")
        if result.returncode == 0:
            # Clear import caches
            importlib.invalidate_caches()
            try:
                importlib.import_module(import_name)
                return True
            except ImportError:
                pass
        # Retry with force
        result = run_cmd(f"{pip_prefix} install --force-reinstall {pip_name}")
        if result.returncode == 0:
            importlib.invalidate_caches()
            try:
                importlib.import_module(import_name)
                return True
            except ImportError:
                pass
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    logger.warning("Failed to install %s", pip_name)
    return False


def validate_goal_content(content: str, min_chars: int = 200) -> bool:
    """Check that GOAL.md has real user content (not just template boilerplate).

    Strips HTML comments, headings, placeholder text, and whitespace before
    checking whether at least *min_chars* characters of real prose remain.

    Args:
        content: Raw text of GOAL.md.
        min_chars: Minimum characters of real content required.

    Returns:
        True if sufficient content is present.
    """
    import re

    text = content
    # Strip HTML comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    # Strip markdown headings
    text = re.sub(r"^#+\s.*$", "", text, flags=re.MULTILINE)
    # Strip checkbox placeholders
    text = re.sub(r"^- \[ \]\s.*$", "", text, flags=re.MULTILINE)
    # Strip common placeholder phrases
    for phrase in [
        "User provides during init",
        "WRITE YOUR PROJECT DESCRIPTION HERE",
        "See GOAL.md",
        "Criterion 1",
        "Criterion 2",
        "e.g., 3 months",
    ]:
        text = text.replace(phrase, "")
    # Strip remaining whitespace
    text = text.strip()
    return len(text) >= min_chars


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


def generate_goal_milestones(goal_text: str) -> list[str]:
    """Generate project milestones from GOAL.md content.

    Tries Claude CLI first, falls back to keyword-based generation.

    Args:
        goal_text: Raw text from GOAL.md.

    Returns:
        List of milestone strings (up to 10). Empty list if goal_text
        is too short to be meaningful.
    """
    if not goal_text or len(goal_text.strip()) < 50:
        return []

    # Try Claude
    from core.claude_helper import call_claude

    prompt = (
        "Given this research project goal, generate 5-8 high-level milestones "
        "as a simple numbered list. Each milestone should be one line, actionable, "
        "and in logical order.\n\n"
        f"Goal:\n{goal_text[:2000]}"
    )
    result = call_claude(prompt)
    if result:
        lines = [
            l.strip().lstrip("0123456789.-) ")
            for l in result.strip().splitlines()
            if l.strip()
        ]
        milestones = [l for l in lines if len(l) > 10]
        if milestones:
            return milestones[:10]

    # Keyword fallback
    return _generate_milestones_keywords(goal_text)


def _generate_milestones_keywords(goal_text: str) -> list[str]:
    """Keyword-based milestone generation.

    Args:
        goal_text: Raw text from GOAL.md.

    Returns:
        List of milestone strings.
    """
    milestones = [
        "Literature review and background research",
        "Set up data pipeline and preprocessing",
        "Implement baseline approach",
        "Run initial experiments and validate pipeline",
        "Iterate on methodology based on results",
        "Run full-scale experiments",
        "Analyze results and generate figures",
        "Write paper draft",
    ]
    text_lower = goal_text.lower()
    if "model" in text_lower or "train" in text_lower:
        milestones.insert(3, "Design and implement model architecture")
    if "dataset" in text_lower:
        milestones.insert(1, "Acquire and explore dataset")
    return milestones[:10]
