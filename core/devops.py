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
