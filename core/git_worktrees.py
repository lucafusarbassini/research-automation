"""Git worktrees module — parallel branch work without subagent collisions.

Uses git worktrees so multiple agents can work on different branches simultaneously
without conflicting with each other in the same working directory.
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

WORKTREES_DIR = Path(".worktrees")


def _sanitize_branch_name(branch: str) -> str:
    """Convert branch name to a safe directory name."""
    return branch.replace("/", "-").replace("\\", "-")


def create_worktree(branch: str, path: Optional[Path] = None) -> Path:
    """Create a git worktree for a branch.

    Args:
        branch: The git branch to check out in the worktree.
        path: Optional directory for the worktree. Derived from branch name if None.

    Returns:
        Path to the created worktree directory.

    Raises:
        subprocess.CalledProcessError: If git worktree add fails.
    """
    if path is None:
        path = WORKTREES_DIR / _sanitize_branch_name(branch)

    path.parent.mkdir(parents=True, exist_ok=True)

    # Check if the branch already exists
    result = subprocess.run(
        ["git", "rev-parse", "--verify", branch],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        cmd = ["git", "worktree", "add", str(path), branch]
    else:
        cmd = ["git", "worktree", "add", "-b", branch, str(path)]

    subprocess.run(cmd, check=True, capture_output=True, text=True)

    logger.info("Created worktree for branch %s at %s", branch, path)
    return path


def list_worktrees() -> list[dict]:
    """List all active git worktrees.

    Returns:
        List of dicts with keys: path, head, branch.
    """
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )

    worktrees: list[dict] = []
    current: dict = {}

    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            if current:
                worktrees.append(current)
            current = {"path": line[len("worktree ") :]}
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD ") :]
        elif line.startswith("branch "):
            current["branch"] = line[len("branch ") :]

    if current:
        worktrees.append(current)

    return worktrees


def remove_worktree(path: Path) -> bool:
    """Remove a git worktree.

    Args:
        path: Path to the worktree directory.

    Returns:
        True if removal succeeded, False otherwise.
    """
    try:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("Removed worktree at %s", path)
        return True
    except subprocess.CalledProcessError as exc:
        logger.warning("Failed to remove worktree at %s: %s", path, exc)
        return False


def run_in_worktree(branch: str, command: str) -> subprocess.CompletedProcess:
    """Execute a command inside the worktree for a given branch.

    Gets or creates the worktree, then runs the command with ``cwd`` set to it.

    Args:
        branch: Branch whose worktree to use.
        command: Shell command string to execute.

    Returns:
        The CompletedProcess from the command execution.
    """
    wt_path = ensure_branch_worktree(branch)

    return subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        cwd=wt_path,
    )


class WorktreeContext:
    """Context manager that creates a worktree on enter and removes it on exit.

    Usage::

        with WorktreeContext("feature/x") as wt_path:
            subprocess.run(["make", "test"], cwd=wt_path)
    """

    def __init__(self, branch: str, path: Optional[Path] = None):
        self.branch = branch
        self.path = path
        self._worktree_path: Optional[Path] = None

    def __enter__(self) -> Path:
        self._worktree_path = create_worktree(self.branch, self.path)
        return self._worktree_path

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._worktree_path is not None:
            remove_worktree(self._worktree_path)


def ensure_branch_worktree(branch: str) -> Path:
    """Get or create a worktree for the given branch.

    If a worktree already exists for *branch*, its path is returned directly.
    Otherwise a new worktree is created.

    Args:
        branch: The branch name.

    Returns:
        Path to the worktree directory.
    """
    for wt in list_worktrees():
        wt_branch = wt.get("branch", "")
        # Compare against both full ref and short name
        if wt_branch == f"refs/heads/{branch}" or wt_branch == branch:
            return Path(wt["path"])

    return create_worktree(branch)


def merge_worktree_results(source_branch: str, target_branch: str = "main") -> bool:
    """Merge a worktree branch back into the target branch.

    Checks out the target branch, merges source, then restores the previous
    branch. This operates on the main repository, not inside a worktree.

    Args:
        source_branch: Branch to merge from.
        target_branch: Branch to merge into (default ``"main"``).

    Returns:
        True if merge succeeded, False on conflict or error.
    """
    # Remember current branch to restore later
    try:
        current = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        current = None

    try:
        subprocess.run(
            ["git", "checkout", target_branch],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "merge", source_branch, "--no-edit"],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("Merged %s into %s", source_branch, target_branch)
        return True
    except subprocess.CalledProcessError as exc:
        logger.warning(
            "Merge of %s into %s failed: %s", source_branch, target_branch, exc
        )
        # Abort if merge is in progress
        subprocess.run(["git", "merge", "--abort"], capture_output=True)
        return False
    finally:
        if current and current != target_branch:
            subprocess.run(
                ["git", "checkout", current],
                capture_output=True,
                text=True,
            )


# ---------------------------------------------------------------------------
# CLI adapter — ``from core.git_worktrees import worktree_manager``
# ---------------------------------------------------------------------------


class _WorktreeManager:
    """Thin CLI-facing adapter wrapping the module-level worktree functions."""

    def add(self, branch: str) -> Path:
        return create_worktree(branch)

    def list(self) -> list[dict]:
        return list_worktrees()

    def remove(self, branch: str) -> bool:
        for wt in list_worktrees():
            wt_branch = wt.get("branch", "")
            if wt_branch == f"refs/heads/{branch}" or wt_branch == branch:
                return remove_worktree(Path(wt["path"]))
        logger.warning("No worktree found for branch %s", branch)
        return False

    def prune(self) -> None:
        """Prune stale worktree references using git worktree prune."""
        subprocess.run(
            ["git", "worktree", "prune"],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("Pruned stale worktrees")


worktree_manager = _WorktreeManager()
