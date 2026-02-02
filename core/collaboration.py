"""Collaborative research: sync, user identification, and merge helpers.

Allows multiple researchers to use ricet on the same repo without conflicts.
"""

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def sync_before_start(
    *,
    cwd: str | Path | None = None,
    run_cmd=None,
) -> bool:
    """Pull latest changes with rebase before starting a session.

    Args:
        cwd: Working directory.
        run_cmd: Optional callable override for testing.

    Returns:
        True if pull succeeded or no remote exists.
    """
    if cwd is None:
        cwd = Path.cwd()
    cwd = str(cwd)

    if run_cmd is None:

        def run_cmd(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                **kwargs,
            )

    # Check if in a git repo
    try:
        r = run_cmd(["git", "rev-parse", "--is-inside-work-tree"], cwd=cwd)
        if r.returncode != 0:
            return True  # Not a git repo, nothing to sync
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return True

    # Check if remote exists
    try:
        r = run_cmd(["git", "remote"], cwd=cwd)
        if r.returncode != 0 or not r.stdout.strip():
            return True  # No remote configured
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return True

    # Pull with rebase
    try:
        r = run_cmd(["git", "pull", "--rebase"], cwd=cwd)
        if r.returncode != 0:
            logger.warning("git pull --rebase failed: %s", r.stderr.strip())
            return False
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def sync_after_operation(
    message: str,
    *,
    cwd: str | Path | None = None,
    run_cmd=None,
) -> bool:
    """Commit and push after an operation (delegates to auto_commit).

    Args:
        message: Commit message.
        cwd: Working directory.
        run_cmd: Optional callable override for testing.

    Returns:
        True if commit was created.
    """
    from core.auto_commit import auto_commit

    return auto_commit(message, cwd=cwd, run_cmd=run_cmd)


def get_user_id(
    *,
    run_cmd=None,
) -> str:
    """Identify the current user for collaboration tracking.

    Tries ``git config user.email``, falls back to hostname.

    Args:
        run_cmd: Optional callable override for testing.

    Returns:
        A string identifying the user.
    """
    if run_cmd is None:

        def run_cmd(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                **kwargs,
            )

    try:
        r = run_cmd(["git", "config", "user.email"])
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    import socket

    try:
        return f"{os.getenv('USER', 'unknown')}@{socket.gethostname()}"
    except Exception:
        return "unknown"


def merge_encyclopedia(ours_path: Path, theirs_text: str) -> str:
    """Merge encyclopedia content by deduplicating timestamped entries.

    Args:
        ours_path: Path to our encyclopedia file.
        theirs_text: Text content from the other branch.

    Returns:
        Merged content string.
    """
    ours_text = ours_path.read_text() if ours_path.exists() else ""
    ours_lines = set(ours_text.splitlines())
    merged_lines = ours_text.splitlines()

    for line in theirs_text.splitlines():
        if line not in ours_lines:
            merged_lines.append(line)

    return "\n".join(merged_lines)


def merge_state_file(ours_path: Path, theirs_text: str) -> str:
    """Merge state files (PROGRESS.md, etc.) by appending non-duplicate lines.

    Args:
        ours_path: Path to our state file.
        theirs_text: Text content from the other branch.

    Returns:
        Merged content string.
    """
    ours_text = ours_path.read_text() if ours_path.exists() else ""
    ours_lines = set(ours_text.splitlines())
    merged_lines = ours_text.splitlines()

    for line in theirs_text.splitlines():
        if line.strip() and line not in ours_lines:
            merged_lines.append(line)

    return "\n".join(merged_lines)
