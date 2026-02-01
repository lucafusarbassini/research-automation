"""Two-repo structure: experiments/ (messy, exploratory) vs clean/ (publication-ready).

Maintains two parallel git repositories under a single project directory so that
exploratory work stays isolated from polished, reproducible artefacts.
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "two-repo",
    "GIT_COMMITTER_NAME": "two-repo",
    "GIT_AUTHOR_EMAIL": "two-repo@localhost",
    "GIT_COMMITTER_EMAIL": "two-repo@localhost",
}


def _run_git(
    args: list[str], cwd: Path, check: bool = True
) -> subprocess.CompletedProcess:
    """Run a git command with deterministic author info."""
    env = {**os.environ, **_GIT_ENV}
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
        env=env,
    )


class TwoRepoManager:
    """Manage paired experiments/ and clean/ git repositories."""

    def __init__(self, project_path: Path) -> None:
        self.project_path = Path(project_path)
        self.experiments = self.project_path / "experiments"
        self.clean = self.project_path / "clean"

    # ── public API ──────────────────────────────────────────────────

    def init_two_repos(self) -> dict:
        """Initialise experiments/ and clean/ subdirectories with separate git repos.

        Idempotent: safe to call multiple times.

        Returns a dict like ``{"experiments": True, "clean": True}`` on success.
        """
        result: dict[str, bool] = {}
        for name, repo_dir in [
            ("experiments", self.experiments),
            ("clean", self.clean),
        ]:
            repo_dir.mkdir(parents=True, exist_ok=True)
            if not (repo_dir / ".git").is_dir():
                _run_git(["init"], cwd=repo_dir)
                # Create an initial empty commit so HEAD exists
                _run_git(
                    ["commit", "--allow-empty", "-m", f"Initialise {name} repo"],
                    cwd=repo_dir,
                )
                logger.info("Initialised %s repo at %s", name, repo_dir)
            result[name] = True
        return result

    def promote_to_clean(self, files: list[str], message: str) -> bool:
        """Copy verified files from experiments/ to clean/ and commit.

        Each path in *files* is relative to experiments/.
        Returns True if all files were promoted and committed, False on any failure.
        """
        # Validate all source files exist first
        for rel in files:
            src = self.experiments / rel
            if not src.exists():
                logger.warning("promote_to_clean: source missing – %s", src)
                return False

        # Copy
        for rel in files:
            src = self.experiments / rel
            dst = self.clean / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        # Stage and commit in clean/
        _run_git(["add", "."], cwd=self.clean)
        proc = _run_git(["commit", "-m", message], cwd=self.clean, check=False)
        if proc.returncode != 0:
            logger.warning("promote_to_clean commit failed: %s", proc.stderr)
            return False
        return True

    def get_status(self) -> dict:
        """Return status of both repos (dirty/clean, branch, commit count).

        Returns::

            {
                "experiments": {"dirty": bool, "branch": str},
                "clean":       {"dirty": bool, "branch": str},
            }
        """
        out: dict[str, dict] = {}
        for name, repo_dir in [
            ("experiments", self.experiments),
            ("clean", self.clean),
        ]:
            status_proc = _run_git(["status", "--porcelain"], cwd=repo_dir, check=False)
            dirty = len(status_proc.stdout.strip()) > 0

            branch_proc = _run_git(
                ["branch", "--show-current"], cwd=repo_dir, check=False
            )
            branch = branch_proc.stdout.strip() or "HEAD"

            out[name] = {"dirty": dirty, "branch": branch}
        return out

    def sync_shared(self, shared_files: list[str] | None = None) -> bool:
        """Sync shared files/directories from experiments/ to clean/.

        *shared_files* defaults to ``["knowledge/", "config/"]`` when not provided.
        Returns True on success, False if any source path is missing.
        """
        if shared_files is None:
            shared_files = ["knowledge/", "config/"]

        for rel in shared_files:
            src = self.experiments / rel
            if not src.exists():
                logger.warning("sync_shared: source missing – %s", src)
                return False

        for rel in shared_files:
            src = self.experiments / rel
            dst = self.clean / rel
            if src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

        return True

    def run_experiment(self, command: str) -> dict:
        """Run *command* (shell) inside experiments/ and return captured output.

        Returns::

            {"stdout": str, "stderr": str, "returncode": int}
        """
        proc = subprocess.run(
            command,
            shell=True,
            cwd=self.experiments,
            capture_output=True,
            text=True,
        )
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "returncode": proc.returncode,
        }

    def diff_repos(self) -> str:
        """Show file-level differences between experiments/ and clean/.

        Uses ``diff -rq`` to compare the two working trees, excluding .git
        directories.
        """
        proc = subprocess.run(
            ["diff", "-rq", "--exclude=.git", str(self.experiments), str(self.clean)],
            capture_output=True,
            text=True,
        )
        return proc.stdout
