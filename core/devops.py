"""DevOps engineer module — manage infrastructure, CI/CD, and deployments."""

import logging
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions for version detection
# ---------------------------------------------------------------------------

_TOOLS = {
    "docker": {"cmd": ["docker", "--version"]},
    "git": {"cmd": ["git", "--version"]},
    "node": {"cmd": ["node", "--version"]},
    "python": {"cmd": ["python3", "--version"]},
    "conda": {"cmd": ["conda", "--version"]},
}


def check_infrastructure() -> dict:
    """Check availability and versions of key infrastructure tools.

    Returns:
        dict mapping tool name to {"available": bool, "version": str}.
    """
    results: dict = {}
    for name, spec in _TOOLS.items():
        entry = {"available": False, "version": ""}
        if shutil.which(spec["cmd"][0]) is not None:
            entry["available"] = True
            try:
                proc = subprocess.run(
                    spec["cmd"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if proc.returncode == 0:
                    entry["version"] = proc.stdout.strip()
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                pass
        results[name] = entry
    return results


# ---------------------------------------------------------------------------
# DockerManager
# ---------------------------------------------------------------------------


RICET_DOCKER_IMAGE = "ricet:latest"

# ---------------------------------------------------------------------------
# OS-specific Docker installation instructions
# ---------------------------------------------------------------------------

_DOCKER_INSTALL_INSTRUCTIONS: dict[str, str] = {
    "Linux": (
        "Install Docker on Linux:\n"
        "  curl -fsSL https://get.docker.com | sh\n"
        "  sudo usermod -aG docker $USER\n"
        "  # Log out and log back in, then run: docker run hello-world"
    ),
    "Darwin": (
        "Install Docker on macOS:\n"
        "  1. Download Docker Desktop from https://www.docker.com/products/docker-desktop/\n"
        "  2. Open the .dmg and drag Docker to Applications\n"
        "  3. Launch Docker Desktop and wait for the whale icon to appear"
    ),
    "Windows": (
        "Install Docker on Windows:\n"
        "  1. Install WSL2: wsl --install\n"
        "  2. Download Docker Desktop from https://www.docker.com/products/docker-desktop/\n"
        "  3. During install, ensure 'Use WSL 2 based engine' is checked\n"
        "  4. Open Docker Desktop, then use a WSL2 terminal"
    ),
}


def get_docker_install_instructions() -> str:
    """Return Docker installation instructions for the current OS.

    Returns:
        Human-readable installation instructions string.
    """
    import platform

    system = platform.system()
    return _DOCKER_INSTALL_INSTRUCTIONS.get(
        system,
        (
            "Install Docker:\n"
            "  Visit https://docs.docker.com/get-docker/ for instructions.\n"
        ),
    )


def ensure_docker_ready() -> dict:
    """Validate that Docker is installed, the daemon is running, and the ricet image exists.

    Returns:
        dict with keys:
            "docker_installed" (bool) - docker binary found on PATH
            "daemon_running" (bool)   - docker daemon is responsive
            "image_available" (bool)  - ricet:latest image exists locally
            "ready" (bool)            - all three checks passed
            "error" (str)             - human-readable error if not ready
            "install_instructions" (str) - OS-specific install guide (if not installed)
    """
    result: dict = {
        "docker_installed": False,
        "daemon_running": False,
        "image_available": False,
        "ready": False,
        "error": "",
        "install_instructions": "",
    }

    # 1. Check binary
    if shutil.which("docker") is None:
        result["error"] = "Docker is not installed."
        result["install_instructions"] = get_docker_install_instructions()
        return result
    result["docker_installed"] = True

    # 2. Check daemon
    try:
        proc = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            result["error"] = (
                "Docker is installed but the daemon is not running.\n"
                "Start it with: sudo systemctl start docker (Linux)\n"
                "Or launch Docker Desktop (macOS / Windows)."
            )
            return result
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        result["error"] = "Could not communicate with the Docker daemon."
        return result
    result["daemon_running"] = True

    # 3. Check ricet image
    try:
        proc = subprocess.run(
            ["docker", "image", "inspect", RICET_DOCKER_IMAGE],
            capture_output=True,
            text=True,
            timeout=10,
        )
        result["image_available"] = proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        result["image_available"] = False

    if not result["image_available"]:
        result["error"] = (
            f"Docker image '{RICET_DOCKER_IMAGE}' not found locally. "
            "It will be built automatically during 'ricet init' or you can build it "
            "manually: docker build -t ricet:latest docker/"
        )
    else:
        result["ready"] = True

    return result


def build_ricet_image(dockerfile_dir: Optional[Path] = None) -> bool:
    """Build the ricet Docker image from the project's docker/ directory.

    Args:
        dockerfile_dir: Directory containing the Dockerfile. If None,
                        auto-detects from the package layout.

    Returns:
        True on success.
    """
    if dockerfile_dir is None:
        dockerfile_dir = Path(__file__).parent.parent / "docker"

    dockerfile = dockerfile_dir / "Dockerfile"
    if not dockerfile.exists():
        logger.error("Dockerfile not found at %s", dockerfile)
        return False

    logger.info(
        "Building Docker image %s from %s ...", RICET_DOCKER_IMAGE, dockerfile_dir
    )
    try:
        proc = subprocess.run(
            [
                "docker",
                "build",
                "-t",
                RICET_DOCKER_IMAGE,
                "-f",
                str(dockerfile),
                str(dockerfile_dir.parent),  # context = project root
            ],
            timeout=1200,
        )
        if proc.returncode != 0:
            logger.error("docker build failed (exit %d)", proc.returncode)
            return False
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.error("docker build error: %s", exc)
        return False


def prepare_docker_environment(project_path: Path) -> bool:
    """Pre-install all project dependencies inside the Docker container.

    Reads requirements.txt, environment.yml, and pyproject.toml from the
    project to install packages into a running (or ephemeral) container so
    that overnight runs have everything pre-cached.

    Args:
        project_path: Absolute path to the project on the host.

    Returns:
        True if preparation succeeded (or no extra deps were needed).
    """
    project_path = project_path.resolve()

    # Determine which install commands to run inside the container
    install_cmds: list[str] = []

    req_file = project_path / "requirements.txt"
    if req_file.exists():
        install_cmds.append("pip install --no-cache-dir -r /workspace/requirements.txt")

    pyproject = project_path / "pyproject.toml"
    if pyproject.exists():
        install_cmds.append(
            "pip install --no-cache-dir -e /workspace 2>/dev/null || true"
        )

    env_yml = project_path / "environment.yml"
    if env_yml.exists():
        install_cmds.append(
            "conda env update -n base -f /workspace/environment.yml 2>/dev/null || true"
        )

    if not install_cmds:
        logger.info("No dependency files found; Docker environment is ready as-is.")
        return True

    combined = " && ".join(install_cmds)
    logger.info("Installing project dependencies inside Docker container...")

    try:
        proc = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{project_path}:/workspace:ro",
                RICET_DOCKER_IMAGE,
                "bash",
                "-c",
                combined,
            ],
            timeout=600,
        )
        if proc.returncode != 0:
            logger.warning(
                "Some dependency installation steps failed (exit %d). "
                "Overnight mode may still work for tasks that don't need those packages.",
                proc.returncode,
            )
            return False
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.error("prepare_docker_environment error: %s", exc)
        return False


def test_docker_setup() -> bool:
    """Run a quick smoke test to verify the Docker environment works.

    Executes a trivial Python + Node.js check inside the ricet container.

    Returns:
        True if the smoke test passed.
    """
    try:
        proc = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                RICET_DOCKER_IMAGE,
                "bash",
                "-c",
                "python3 -c \"import typer; print('python-ok')\" && node -e \"console.log('node-ok')\"",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if (
            proc.returncode == 0
            and "python-ok" in proc.stdout
            and "node-ok" in proc.stdout
        ):
            return True
        logger.warning("Docker smoke test output unexpected: %s", proc.stdout)
        return False
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.error("Docker smoke test failed: %s", exc)
        return False


class DockerManager:
    """Manage Docker images and containers."""

    def is_available(self) -> bool:
        """Return True if the Docker daemon is reachable."""
        try:
            proc = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return proc.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    def build(self, tag: str, dockerfile: Path = Path("Dockerfile")) -> bool:
        """Build a Docker image.

        Args:
            tag: Image tag (e.g. "myapp:latest").
            dockerfile: Path to the Dockerfile.

        Returns:
            True on success.
        """
        try:
            proc = subprocess.run(
                [
                    "docker",
                    "build",
                    "-t",
                    tag,
                    "-f",
                    str(dockerfile),
                    str(dockerfile.parent or "."),
                ],
                capture_output=True,
                text=True,
                timeout=600,
            )
            if proc.returncode != 0:
                logger.error("docker build failed: %s", proc.stderr)
                return False
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            logger.error("docker build error: %s", exc)
            return False

    def run(
        self,
        tag: str,
        ports: Optional[dict] = None,
        volumes: Optional[dict] = None,
    ) -> str:
        """Run a container and return its ID.

        Args:
            tag: Image tag.
            ports: Mapping of host_port -> container_port.
            volumes: Mapping of host_path -> container_path.

        Returns:
            Container ID string, or empty string on failure.
        """
        cmd = ["docker", "run", "-d"]
        if ports:
            for host_port, container_port in ports.items():
                cmd.extend(["-p", f"{host_port}:{container_port}"])
        if volumes:
            for host_path, container_path in volumes.items():
                cmd.extend(["-v", f"{host_path}:{container_path}"])
        cmd.append(tag)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if proc.returncode != 0:
                logger.error("docker run failed: %s", proc.stderr)
                return ""
            return proc.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            logger.error("docker run error: %s", exc)
            return ""

    def stop(self, container_id: str) -> bool:
        """Stop a running container."""
        try:
            proc = subprocess.run(
                ["docker", "stop", container_id],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return proc.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    def logs(self, container_id: str, tail: int = 50) -> str:
        """Retrieve recent logs from a container."""
        try:
            proc = subprocess.run(
                ["docker", "logs", "--tail", str(tail), container_id],
                capture_output=True,
                text=True,
                timeout=15,
            )
            return proc.stdout if proc.returncode == 0 else proc.stderr
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            return str(exc)


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


def health_check(url: str, timeout: int = 10) -> dict:
    """Perform an HTTP health check.

    Args:
        url: The URL to probe (e.g. http://localhost:8080/health).
        timeout: Request timeout in seconds.

    Returns:
        dict with keys "healthy" (bool), "status_code" (int), and
        optionally "body" or "error".
    """
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {
                "healthy": 200 <= resp.status < 400,
                "status_code": resp.status,
                "body": body,
            }
    except urllib.error.HTTPError as exc:
        return {
            "healthy": False,
            "status_code": getattr(exc, "code", 0),
            "error": str(exc),
        }
    except (urllib.error.URLError, OSError) as exc:
        return {"healthy": False, "status_code": 0, "error": str(exc)}


# ---------------------------------------------------------------------------
# deploy_github_pages
# ---------------------------------------------------------------------------


def deploy_github_pages(source_dir: Path, repo_url: str) -> bool:
    """Deploy a static site directory to GitHub Pages via ``gh-pages`` branch.

    Args:
        source_dir: Local directory containing the built static site.
        repo_url: Remote repository URL.

    Returns:
        True on success.
    """
    if not Path.exists(source_dir):
        logger.error("Source directory does not exist: %s", source_dir)
        return False

    try:
        cmds = [
            ["git", "init"],
            ["git", "checkout", "-b", "gh-pages"],
            ["git", "add", "."],
            ["git", "commit", "-m", "Deploy to GitHub Pages"],
            ["git", "remote", "add", "origin", repo_url],
            ["git", "push", "--force", "origin", "gh-pages"],
        ]
        for cmd in cmds:
            proc = subprocess.run(
                cmd,
                cwd=str(source_dir),
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode != 0:
                logger.error("deploy step failed (%s): %s", cmd, proc.stderr)
                return False
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.error("deploy_github_pages error: %s", exc)
        return False


# ---------------------------------------------------------------------------
# setup_ci_cd
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, str] = {
    "python": """\
name: CI

on:
  push:
    branches: [main, master]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: pytest --tb=short
""",
    "node": """\
name: CI

on:
  push:
    branches: [main, master]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: npm ci
      - run: npm test
""",
}

_DEFAULT_TEMPLATE = """\
name: CI

on:
  push:
    branches: [main, master]
  pull_request:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "Add build steps here"
"""


def setup_ci_cd(project_path: Path, template: str = "python") -> Path:
    """Generate a GitHub Actions CI/CD workflow file.

    Args:
        project_path: Root of the project.
        template: One of "python", "node", or any string (falls back to
            a generic template).

    Returns:
        Path to the generated workflow YAML file.
    """
    workflows_dir = project_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    workflow_file = workflows_dir / "ci.yml"

    content = _TEMPLATES.get(template, _DEFAULT_TEMPLATE)
    workflow_file.write_text(content)
    logger.info("Created CI/CD workflow: %s", workflow_file)
    return workflow_file


# ---------------------------------------------------------------------------
# rotate_secrets
# ---------------------------------------------------------------------------

# Patterns that strongly suggest a secret value
_SECRET_PATTERNS = [
    re.compile(
        r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token)\s*=\s*\S+"
    ),
    re.compile(r"(?i)(password|passwd|pwd)\s*=\s*\S+"),
    re.compile(r"(?i)token\s*=\s*[\"']?\w{10,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),  # GitHub personal access token
    re.compile(r"sk-[A-Za-z0-9]{20,}"),  # OpenAI-style key
    re.compile(r"AKIA[A-Z0-9]{16}"),  # AWS access key ID
    re.compile(r"(?i)(database_url|db_url)\s*=\s*\S+"),
]

_SCAN_GLOBS = [
    "**/.env",
    "**/.env.*",
    "**/*.py",
    "**/*.js",
    "**/*.ts",
    "**/*.yml",
    "**/*.yaml",
    "**/*.json",
    "**/*.toml",
    "**/*.cfg",
]

# Directories to skip
_SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".tox",
    ".mypy_cache",
    "venv",
    ".venv",
}


def rotate_secrets(project_path: Path) -> list[str]:
    """Scan a project for secrets that should be rotated.

    Args:
        project_path: Root of the project tree.

    Returns:
        List of human-readable descriptions of secrets found.
    """
    findings: list[str] = []
    seen: set[str] = set()

    for glob_pat in _SCAN_GLOBS:
        for filepath in project_path.glob(glob_pat):
            # Skip ignored directories
            if any(part in _SKIP_DIRS for part in filepath.parts):
                continue
            if not filepath.is_file():
                continue
            try:
                text = filepath.read_text(errors="replace")
            except OSError:
                continue
            for pattern in _SECRET_PATTERNS:
                for match in pattern.finditer(text):
                    key = f"{filepath.relative_to(project_path)}:{match.group()}"
                    if key not in seen:
                        seen.add(key)
                        findings.append(
                            f"{filepath.relative_to(project_path)}: {match.group().strip()}"
                        )
    return findings
