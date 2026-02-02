"""Auto-commit and push after every state-modifying CLI operation.

Controlled by environment variables:
- RICET_AUTO_COMMIT: "true" (default) or "false" to disable.
- AUTO_PUSH: "true" (default) or "false" to skip push.
"""

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def auto_commit(
    message: str,
    *,
    push: bool | None = None,
    cwd: str | Path | None = None,
    run_cmd=None,
) -> bool:
    """Stage all changes, commit, and optionally push.

    Args:
        message: Commit message.
        push: Override for push behaviour.  When *None*, reads ``AUTO_PUSH``
              env var (default ``"true"``).
        cwd: Working directory (defaults to current directory).
        run_cmd: Optional ``callable(cmd_list, **kw) -> CompletedProcess``
                 override for testing.

    Returns:
        True if a commit was created, False otherwise.
    """
    if os.environ.get("RICET_AUTO_COMMIT", "true").lower() not in ("true", "1", "yes"):
        logger.debug("Auto-commit disabled via RICET_AUTO_COMMIT")
        return False

    if cwd is None:
        cwd = Path.cwd()
    cwd = str(cwd)

    if run_cmd is None:

        def run_cmd(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                **kwargs,
            )

    # Check if we are in a git repo
    try:
        r = run_cmd(["git", "rev-parse", "--is-inside-work-tree"], cwd=cwd)
        if r.returncode != 0:
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

    # Check for changes
    try:
        r = run_cmd(["git", "status", "--porcelain"], cwd=cwd)
        if r.returncode != 0 or not r.stdout.strip():
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

    # Stage and commit
    try:
        r = run_cmd(["git", "add", "-A"], cwd=cwd)
        if r.returncode != 0:
            logger.warning("git add failed: %s", r.stderr.strip())
            return False

        r = run_cmd(["git", "commit", "-m", message], cwd=cwd)
        if r.returncode != 0:
            logger.warning("git commit failed: %s", r.stderr.strip())
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

    # Push
    should_push = (
        push
        if push is not None
        else (os.environ.get("AUTO_PUSH", "true").lower() in ("true", "1", "yes"))
    )
    if should_push:
        try:
            # Detect current branch
            br = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
            branch = br.stdout.strip() if br.returncode == 0 else "main"
            run_cmd(["git", "push", "origin", branch], cwd=cwd)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.debug("Push failed or timed out (non-fatal)")

    return True
