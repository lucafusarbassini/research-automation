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

    # Check for tracking branch
    try:
        r = run_cmd(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            cwd=cwd,
        )
        if r.returncode != 0:
            return True  # No upstream tracking branch, nothing to pull
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return True

    # Stash any uncommitted changes before pulling
    stashed = False
    try:
        r = run_cmd(["git", "status", "--porcelain"], cwd=cwd)
        if r.returncode == 0 and r.stdout.strip():
            run_cmd(["git", "stash", "--include-untracked"], cwd=cwd)
            stashed = True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Pull with rebase
    try:
        r = run_cmd(["git", "pull", "--rebase"], cwd=cwd)
        if r.returncode != 0:
            logger.warning("git pull --rebase failed: %s", r.stderr.strip())
            if stashed:
                run_cmd(["git", "stash", "pop"], cwd=cwd)
            return False
        if stashed:
            run_cmd(["git", "stash", "pop"], cwd=cwd)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        if stashed:
            run_cmd(["git", "stash", "pop"], cwd=cwd)
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


def morning_sync(
    *,
    cwd: str | Path | None = None,
    main_branch: str = "main",
    push: bool = True,
    run_cmd=None,
) -> dict[str, str]:
    """Pull all user branches and merge them into *main_branch*.

    Intended to be run once per morning (or on demand via ``ricet morning-sync``)
    to consolidate contributions from multiple collaborators.

    Steps per user branch:
      1. ``git fetch origin``
      2. For each ``user-*`` branch (plus any tracking remote branch):
         a. Checkout the user branch, pull --rebase
         b. Checkout main, merge --no-ff
         c. If merge succeeds, push main
      3. Return to the original branch.

    Args:
        cwd: Repo directory (defaults to ``Path.cwd()``).
        main_branch: Name of the integration branch (default ``"main"``).
        push: Whether to push *main_branch* after merging.
        run_cmd: Optional callable override for testing.

    Returns:
        Dict mapping branch name to ``"merged"``, ``"conflict"``, or ``"skipped"``.
    """
    if cwd is None:
        cwd = Path.cwd()
    cwd = str(cwd)

    if run_cmd is None:
        def run_cmd(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd, capture_output=True, text=True, timeout=120, **kwargs
            )

    results: dict[str, str] = {}

    # Remember starting branch
    r = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    original_branch = r.stdout.strip() if r.returncode == 0 else main_branch

    # Fetch all remotes
    run_cmd(["git", "fetch", "--all", "--prune"], cwd=cwd)

    # Discover user branches: local + remote tracking user-* pattern
    branches: set[str] = set()

    r = run_cmd(["git", "branch", "-r"], cwd=cwd)
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            name = line.strip().removeprefix("origin/")
            if name.startswith("user-") or (
                name not in ("HEAD", main_branch) and "HEAD ->" not in name
            ):
                branches.add(name)

    r = run_cmd(["git", "branch"], cwd=cwd)
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            name = line.strip().lstrip("* ")
            if name.startswith("user-"):
                branches.add(name)

    if not branches:
        logger.info("morning_sync: no user branches found")
        return {}

    # Ensure we're on main
    r = run_cmd(["git", "checkout", main_branch], cwd=cwd)
    if r.returncode != 0:
        logger.warning("morning_sync: cannot checkout %s", main_branch)
        return {"error": f"cannot checkout {main_branch}"}

    run_cmd(["git", "pull", "--rebase", "origin", main_branch], cwd=cwd)

    for branch in sorted(branches):
        if branch == main_branch:
            continue
        try:
            # Update local copy of this branch
            rb = run_cmd(["git", "branch", "--list", branch], cwd=cwd)
            if rb.stdout.strip():
                run_cmd(["git", "checkout", branch], cwd=cwd)
                run_cmd(["git", "pull", "--rebase", "origin", branch], cwd=cwd)
            else:
                run_cmd(
                    ["git", "checkout", "-b", branch, f"origin/{branch}"],
                    cwd=cwd,
                )
            run_cmd(["git", "checkout", main_branch], cwd=cwd)

            # Merge
            merge_msg = f"morning-sync: merge {branch} into {main_branch}"
            r = run_cmd(
                ["git", "merge", "--no-ff", "-m", merge_msg, branch],
                cwd=cwd,
            )
            if r.returncode == 0:
                results[branch] = "merged"
                logger.info("morning_sync: merged %s", branch)
            else:
                # Abort merge on conflict, report
                run_cmd(["git", "merge", "--abort"], cwd=cwd)
                results[branch] = "conflict"
                logger.warning("morning_sync: conflict merging %s", branch)
        except Exception as exc:
            results[branch] = f"error: {exc}"

    # Push main
    if push and any(v == "merged" for v in results.values()):
        run_cmd(["git", "push", "origin", main_branch], cwd=cwd)

    # Return to original branch
    if original_branch != main_branch:
        run_cmd(["git", "checkout", original_branch], cwd=cwd)

    return results


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
