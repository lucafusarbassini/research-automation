"""Sandbox management for ricet overnight autonomous mode.

Provides Python wrappers for the Docker sandbox infrastructure:
- Build and start sandbox containers
- Run overnight loops with per-iteration timeout
- Extract work as git patches
- Auto-backup of sandbox state to host
- Watchdog monitoring

All Docker commands use run_docker() from devops.py for automatic
sg-docker group activation on systems where the docker group is not
in the current session.
"""

import logging
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.devops import run_docker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SANDBOX_IMAGE = "ricet-sandbox:latest"
DEFAULT_CONTAINER_NAME = "ricet-sandbox"
DEFAULT_TIMEOUT_HOURS = 10
DEFAULT_ITERATIONS = 30
DEFAULT_ITERATION_TIMEOUT_MIN = 60


# ---------------------------------------------------------------------------
# Sandbox build & lifecycle
# ---------------------------------------------------------------------------


def get_sandbox_dir(project_path: Path) -> Path:
    """Return the sandbox/ directory inside the project."""
    return project_path / "sandbox"


def sandbox_exists(project_path: Path) -> bool:
    """Return True if the project has sandbox infrastructure set up."""
    sdir = get_sandbox_dir(project_path)
    return (sdir / "Dockerfile").exists() and (sdir / "docker-compose.sandbox.yml").exists()


def setup_sandbox(
    project_path: Path,
    *,
    dind: bool = False,
    print_fn=print,
) -> bool:
    """Copy sandbox template files into the project.

    Args:
        project_path: Root of the ricet project.
        dind: If True, use Docker-in-Docker Dockerfile.
        print_fn: Callable for status messages.

    Returns:
        True if setup succeeded.
    """
    template_sandbox = Path(__file__).parent.parent / "templates" / "sandbox"
    if not template_sandbox.exists():
        logger.error("Sandbox templates not found at %s", template_sandbox)
        return False

    dest = get_sandbox_dir(project_path)
    dest.mkdir(parents=True, exist_ok=True)

    # Copy all template files
    files_to_copy = [
        "docker-compose.sandbox.yml",
        ".env.example",
        "sandbox-entrypoint.sh",
        "watchdog.sh",
        "run-overnight.sh",
        "extract-work.sh",
        "auto-backup.sh",
        "martinprompt.md",
    ]

    for fname in files_to_copy:
        src = template_sandbox / fname
        if src.exists():
            shutil.copy2(src, dest / fname)

    # Copy the appropriate Dockerfile
    if dind:
        src_df = template_sandbox / "Dockerfile.dind"
    else:
        src_df = template_sandbox / "Dockerfile.python"

    if src_df.exists():
        shutil.copy2(src_df, dest / "Dockerfile")
        # For dind, enable privileged mode in compose
        if dind:
            compose_file = dest / "docker-compose.sandbox.yml"
            content = compose_file.read_text()
            content = content.replace(
                "# privileged: true", "privileged: true"
            )
            compose_file.write_text(content)

    # Make shell scripts executable
    for sh_file in dest.glob("*.sh"):
        sh_file.chmod(sh_file.stat().st_mode | 0o755)

    # Create .env from example if not present
    env_file = dest / ".env"
    env_example = dest / ".env.example"
    if not env_file.exists() and env_example.exists():
        shutil.copy2(env_example, env_file)

    # Create bind-mount workspace directory for VS Code visibility
    workspace_dir = project_path / "sandbox" / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    # Set WORKSPACE_PATH in .env so compose uses bind mount
    _set_env_var(env_file, "WORKSPACE_PATH", str(workspace_dir.resolve()))

    # Copy martinprompt.md to project root as well (the overnight loop reads it there)
    martinprompt_src = template_sandbox / "martinprompt.md"
    martinprompt_dst = project_path / "martinprompt.md"
    if martinprompt_src.exists() and not martinprompt_dst.exists():
        shutil.copy2(martinprompt_src, martinprompt_dst)

    # Ensure experiment and report directories exist
    (project_path / "experiments").mkdir(exist_ok=True)
    (project_path / "reports" / "figures").mkdir(parents=True, exist_ok=True)
    (project_path / "backups").mkdir(exist_ok=True)

    # Ensure state templates exist
    state_dir = project_path / "state"
    state_dir.mkdir(exist_ok=True)
    state_templates = Path(__file__).parent.parent / "templates" / "state"
    for state_file in ("MEMORY.md", "SYSTEM.md"):
        dst = state_dir / state_file
        src = state_templates / state_file
        if not dst.exists() and src.exists():
            shutil.copy2(src, dst)

    # Add sandbox-specific gitignore entries
    _update_gitignore(project_path)

    print_fn("Sandbox infrastructure copied to sandbox/")
    return True


def _set_env_var(env_file: Path, key: str, value: str) -> None:
    """Set or update a variable in a .env file."""
    lines: list[str] = []
    found = False
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.strip().startswith(f"{key}="):
                lines.append(f"{key}={value}")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f"{key}={value}")
    env_file.write_text("\n".join(lines) + "\n")


def _update_gitignore(project_path: Path):
    """Add sandbox-related patterns to .gitignore if missing."""
    gitignore = project_path / ".gitignore"
    patterns = [
        "sandbox/.env",
        "sandbox/patches/",
        "sandbox/backups/",
        "sandbox/workspace/",
    ]

    existing = ""
    if gitignore.exists():
        existing = gitignore.read_text()

    additions = []
    for pat in patterns:
        if pat not in existing:
            additions.append(pat)

    if additions:
        with gitignore.open("a") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write("\n# Sandbox\n")
            for pat in additions:
                f.write(f"{pat}\n")


def _load_sandbox_env(project_path: Path) -> dict:
    """Load sandbox .env settings."""
    env_file = get_sandbox_dir(project_path) / ".env"
    env = {
        "CONTAINER_NAME": DEFAULT_CONTAINER_NAME,
        "SANDBOX_TIMEOUT_HOURS": str(DEFAULT_TIMEOUT_HOURS),
    }
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip()
    return env


def build_sandbox(project_path: Path, print_fn=print) -> bool:
    """Build the sandbox Docker image.

    Returns True on success.
    """
    sandbox_dir = get_sandbox_dir(project_path)
    if not (sandbox_dir / "Dockerfile").exists():
        print_fn("No Dockerfile found. Run sandbox setup first.")
        return False

    print_fn("Building sandbox image...")
    try:
        proc = run_docker(
            [
                "docker", "compose",
                "-f", str(sandbox_dir / "docker-compose.sandbox.yml"),
                "build",
            ],
            capture_output=True, text=True, timeout=600,
        )
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            logger.error("Sandbox build failed (exit %d): %s", proc.returncode, stderr)
            if "unknown shorthand flag" in stderr or "is not a docker command" in stderr:
                print_fn("Docker Compose is not available.")
                print_fn("Install it:  sudo apt install docker-compose-plugin")
                print_fn("         or: pip install docker-compose")
            else:
                print_fn(f"Sandbox build failed (exit {proc.returncode})")
                if stderr:
                    for line in stderr.splitlines()[-3:]:
                        print_fn(f"  {line}")
            return False
        print_fn("Sandbox image built successfully.")
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.error("Sandbox build error: %s", exc)
        return False


def start_sandbox(
    project_path: Path,
    *,
    timeout_hours: Optional[int] = None,
    print_fn=print,
) -> bool:
    """Build and start the sandbox container.

    Args:
        project_path: Root of the ricet project.
        timeout_hours: Override watchdog timeout (hours).
        print_fn: Callable for status messages.

    Returns:
        True if container started successfully.
    """
    sandbox_dir = get_sandbox_dir(project_path)
    env = _load_sandbox_env(project_path)
    container_name = env["CONTAINER_NAME"]

    if timeout_hours is not None:
        os.environ["SANDBOX_TIMEOUT_HOURS"] = str(timeout_hours)

    # Build first
    if not build_sandbox(project_path, print_fn=print_fn):
        return False

    # Remove stale containers that block compose up
    run_docker(
        ["docker", "rm", "-f", container_name],
        capture_output=True, timeout=10,
    )
    # Also remove any renamed leftover containers (docker-compose v1 renames)
    _ps = run_docker(
        ["docker", "ps", "-aq", "--filter", f"name={container_name}"],
        capture_output=True, text=True, timeout=10,
    )
    for _cid in (_ps.stdout or "").strip().splitlines():
        if _cid.strip():
            run_docker(["docker", "rm", "-f", _cid.strip()], capture_output=True, timeout=10)

    print_fn(f"Starting sandbox container '{container_name}'...")
    try:
        proc = run_docker(
            [
                "docker", "compose",
                "-f", str(sandbox_dir / "docker-compose.sandbox.yml"),
                "up", "-d",
            ],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            logger.error("Sandbox start failed (exit %d): %s", proc.returncode, stderr)
            if stderr:
                for line in stderr.splitlines()[-3:]:
                    print_fn(f"  {line}")
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.error("Sandbox start error: %s", exc)
        return False

    # Wait for readiness
    print_fn("Waiting for sandbox to be ready...")
    time.sleep(10)

    timeout_display = timeout_hours or int(env.get("SANDBOX_TIMEOUT_HOURS", DEFAULT_TIMEOUT_HOURS))
    print_fn(f"Sandbox '{container_name}' is ready (timeout: {timeout_display}h)")
    return True


def stop_sandbox(project_path: Path, print_fn=print) -> bool:
    """Stop the sandbox container.

    Returns True on success.
    """
    sandbox_dir = get_sandbox_dir(project_path)
    print_fn("Stopping sandbox...")
    try:
        proc = run_docker(
            [
                "docker", "compose",
                "-f", str(sandbox_dir / "docker-compose.sandbox.yml"),
                "down",
            ],
            timeout=60,
        )
        if proc.returncode == 0:
            print_fn("Sandbox stopped.")
            return True
        return False
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.error("Sandbox stop error: %s", exc)
        return False


def is_sandbox_running(project_path: Path) -> bool:
    """Return True if the sandbox container is currently running."""
    env = _load_sandbox_env(project_path)
    container_name = env["CONTAINER_NAME"]
    try:
        proc = run_docker(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=10,
        )
        return container_name in proc.stdout.split()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def sandbox_status(project_path: Path) -> dict:
    """Return sandbox status information.

    Returns dict with keys: running, container_name, uptime, last_commit.
    """
    env = _load_sandbox_env(project_path)
    container_name = env["CONTAINER_NAME"]
    status = {
        "running": False,
        "container_name": container_name,
        "uptime": "",
        "last_commit": "",
        "setup": sandbox_exists(project_path),
    }

    try:
        proc = run_docker(
            [
                "docker", "ps",
                "--filter", f"name={container_name}",
                "--format", "{{.Status}}",
            ],
            capture_output=True, text=True, timeout=10,
        )
        if proc.stdout.strip():
            status["running"] = True
            status["uptime"] = proc.stdout.strip()

            # Get last git commit
            commit_proc = run_docker(
                [
                    "docker", "exec", container_name,
                    "gosu", "agent", "git", "-C", "/workspace",
                    "log", "--oneline", "-1",
                ],
                capture_output=True, text=True, timeout=10,
            )
            status["last_commit"] = commit_proc.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    return status


# ---------------------------------------------------------------------------
# Overnight loop management
# ---------------------------------------------------------------------------


def launch_overnight_loop(
    project_path: Path,
    *,
    iterations: int = DEFAULT_ITERATIONS,
    timeout_min: int = DEFAULT_ITERATION_TIMEOUT_MIN,
    print_fn=print,
) -> bool:
    """Launch the overnight loop inside the running sandbox container.

    The loop runs in the background (detached). Use `sandbox_status()` or
    watch the logs to monitor progress.

    Args:
        project_path: Root of the ricet project.
        iterations: Number of Claude iterations.
        timeout_min: Hard timeout per iteration (minutes).
        print_fn: Callable for status messages.

    Returns:
        True if the loop was launched successfully.
    """
    env = _load_sandbox_env(project_path)
    container_name = env["CONTAINER_NAME"]

    if not is_sandbox_running(project_path):
        print_fn("Sandbox is not running. Start it first with: ricet sandbox start")
        return False

    print_fn(f"Launching overnight loop ({iterations} iterations, {timeout_min}m each)...")
    try:
        proc = run_docker(
            [
                "docker", "exec", "-d", container_name,
                "gosu", "agent", "bash",
                "/workspace/sandbox/run-overnight.sh",
                str(iterations), str(timeout_min),
            ],
            timeout=30,
        )
        if proc.returncode == 0:
            print_fn("Overnight loop launched in background.")
            print_fn(f"  Monitor: docker exec {container_name} tail -f /agent-logs/claude-output.log")
            return True
        return False
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.error("Failed to launch overnight loop: %s", exc)
        return False


def watch_sandbox_logs(project_path: Path, lines: int = 50) -> str:
    """Return recent lines from the sandbox Claude output log.

    Args:
        project_path: Root of the ricet project.
        lines: Number of lines to retrieve.

    Returns:
        Log content string.
    """
    env = _load_sandbox_env(project_path)
    container_name = env["CONTAINER_NAME"]

    try:
        proc = run_docker(
            [
                "docker", "exec", container_name,
                "tail", "-n", str(lines),
                "/agent-logs/claude-output.log",
            ],
            capture_output=True, text=True, timeout=10,
        )
        return proc.stdout if proc.returncode == 0 else proc.stderr
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return f"Could not read logs: {exc}"


# ---------------------------------------------------------------------------
# Work extraction
# ---------------------------------------------------------------------------


def extract_work(
    project_path: Path,
    *,
    apply_patch: bool = False,
    print_fn=print,
) -> Optional[Path]:
    """Extract work from the sandbox as a git patch.

    Args:
        project_path: Root of the ricet project.
        apply_patch: If True, apply the patch to the project after generating.
        print_fn: Callable for status messages.

    Returns:
        Path to the generated patch file, or None if no changes.
    """
    env = _load_sandbox_env(project_path)
    container_name = env["CONTAINER_NAME"]

    if not is_sandbox_running(project_path):
        print_fn("Sandbox is not running. Start it or check volumes.")
        return None

    sandbox_dir = get_sandbox_dir(project_path)
    patch_dir = sandbox_dir / "patches"
    patch_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    patch_file = patch_dir / f"sandbox_work_{timestamp}.patch"

    print_fn("Extracting work from sandbox...")

    try:
        # Get baseline commit
        baseline_proc = run_docker(
            [
                "docker", "exec", container_name,
                "gosu", "agent", "git", "-C", "/workspace",
                "rev-list", "--max-parents=0", "HEAD",
            ],
            capture_output=True, text=True, timeout=10,
        )
        baseline = baseline_proc.stdout.strip().split("\n")[0]

        if not baseline:
            print_fn("Could not determine baseline commit.")
            return None

        # Generate diff
        diff_proc = run_docker(
            [
                "docker", "exec", container_name,
                "gosu", "agent", "bash", "-c",
                f"cd /workspace && git diff {baseline} HEAD",
            ],
            capture_output=True, text=True, timeout=60,
        )

        if not diff_proc.stdout.strip():
            print_fn("No changes detected.")
            return None

        patch_file.write_text(diff_proc.stdout)
        lines = diff_proc.stdout.count("\n")
        print_fn(f"Patch generated: {patch_file} ({lines} lines)")

        # Sync output directories
        for dir_name in ("experiments", "reports", "outputs"):
            dst = project_path / dir_name
            dst.mkdir(exist_ok=True)
            run_docker(
                [
                    "docker", "cp",
                    f"{container_name}:/workspace/{dir_name}/.",
                    str(dst) + "/",
                ],
                capture_output=True, timeout=60,
            )

        # Show summary
        stat_proc = run_docker(
            [
                "docker", "exec", container_name,
                "gosu", "agent", "bash", "-c",
                f"cd /workspace && git diff {baseline} HEAD --stat | tail -10",
            ],
            capture_output=True, text=True, timeout=10,
        )
        if stat_proc.stdout.strip():
            print_fn("Files changed:")
            print_fn(stat_proc.stdout.strip())

        # Extract logs
        log_file = patch_dir / f"sandbox_log_{timestamp}.log"
        log_proc = run_docker(
            ["docker", "exec", container_name, "cat", "/agent-logs/sandbox.log"],
            capture_output=True, text=True, timeout=10,
        )
        if log_proc.returncode == 0:
            log_file.write_text(log_proc.stdout)
            print_fn(f"Sandbox log: {log_file}")

        claude_log = patch_dir / f"claude_output_{timestamp}.log"
        claude_proc = run_docker(
            ["docker", "exec", container_name, "cat", "/agent-logs/claude-output.log"],
            capture_output=True, text=True, timeout=10,
        )
        if claude_proc.returncode == 0:
            claude_log.write_text(claude_proc.stdout)
            print_fn(f"Claude output: {claude_log}")

        # Apply if requested
        if apply_patch:
            print_fn("Applying patch to project...")
            apply_proc = subprocess.run(
                ["git", "apply", str(patch_file)],
                cwd=str(project_path),
                capture_output=True, text=True, timeout=60,
            )
            if apply_proc.returncode == 0:
                print_fn("Patch applied successfully.")
            else:
                print_fn(f"Patch apply failed: {apply_proc.stderr}")
                print_fn(f"Review manually: {patch_file}")

        return patch_file

    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.error("Extract work failed: %s", exc)
        print_fn(f"Extraction error: {exc}")
        return None


# ---------------------------------------------------------------------------
# Auto-backup
# ---------------------------------------------------------------------------


def run_backup(project_path: Path, print_fn=print) -> bool:
    """Run a single backup cycle: sync state files and outputs from sandbox.

    Returns True if backup succeeded.
    """
    env = _load_sandbox_env(project_path)
    container_name = env["CONTAINER_NAME"]

    if not is_sandbox_running(project_path):
        print_fn("Sandbox is not running.")
        return False

    # Sync output directories
    for dir_name in ("experiments", "reports", "outputs"):
        dst = project_path / dir_name
        dst.mkdir(exist_ok=True)
        run_docker(
            [
                "docker", "cp",
                f"{container_name}:/workspace/{dir_name}/.",
                str(dst) + "/",
            ],
            capture_output=True, timeout=60,
        )

    # Sync state files
    state_dir = project_path / "state"
    state_dir.mkdir(exist_ok=True)
    for state_file in ("MEMORY.md", "PROGRESS.md", "TODO.md", "SYSTEM.md"):
        run_docker(
            [
                "docker", "cp",
                f"{container_name}:/workspace/state/{state_file}",
                str(state_dir / state_file),
            ],
            capture_output=True, timeout=10,
        )

    # Get last commit info
    commit_proc = run_docker(
        [
            "docker", "exec", container_name,
            "gosu", "agent", "git", "-C", "/workspace",
            "log", "--oneline", "-1",
        ],
        capture_output=True, text=True, timeout=10,
    )
    last_commit = commit_proc.stdout.strip() if commit_proc.returncode == 0 else "unknown"
    print_fn(f"Backup complete. Last commit: {last_commit}")
    return True


def start_auto_backup(
    project_path: Path,
    *,
    interval_min: int = 20,
    print_fn=print,
) -> None:
    """Run continuous backup loop (blocking).

    This is intended to be run in a separate terminal or background process.

    Args:
        project_path: Root of the ricet project.
        interval_min: Minutes between backups.
        print_fn: Callable for status messages.
    """
    print_fn(f"Auto-backup started (interval: {interval_min}m). Press Ctrl+C to stop.")

    try:
        while True:
            if is_sandbox_running(project_path):
                ts = datetime.now().strftime("%H:%M:%S")
                print_fn(f"[{ts}] Running backup...")
                run_backup(project_path, print_fn=print_fn)
            else:
                print_fn("Sandbox not running. Waiting...")

            time.sleep(interval_min * 60)
    except KeyboardInterrupt:
        print_fn("Auto-backup stopped.")


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


def destroy_sandbox(project_path: Path, print_fn=print) -> bool:
    """Stop sandbox and remove persistent volumes.

    WARNING: This destroys all workspace data inside the sandbox.

    Returns True on success.
    """
    sandbox_dir = get_sandbox_dir(project_path)
    print_fn("Destroying sandbox (removing volumes)...")
    try:
        proc = run_docker(
            [
                "docker", "compose",
                "-f", str(sandbox_dir / "docker-compose.sandbox.yml"),
                "down", "-v",
            ],
            timeout=60,
        )
        if proc.returncode == 0:
            print_fn("Sandbox destroyed. Volumes removed.")
            return True
        return False
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.error("Sandbox destroy error: %s", exc)
        return False
