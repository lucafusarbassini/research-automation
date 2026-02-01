"""Tests for TwoRepoManager: experiments/ vs clean/ two-repo structure."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.two_repo import TwoRepoManager


@pytest.fixture
def project_dir(tmp_path):
    """Create a temporary project directory for two-repo tests."""
    return tmp_path / "my_project"


@pytest.fixture
def manager(project_dir):
    """Return a TwoRepoManager initialised on a temp project dir."""
    mgr = TwoRepoManager(project_dir)
    mgr.init_two_repos()
    return mgr


# ── init_two_repos ──────────────────────────────────────────────────


class TestInitTwoRepos:
    def test_creates_experiments_and_clean_dirs(self, project_dir):
        mgr = TwoRepoManager(project_dir)
        result = mgr.init_two_repos()

        assert (project_dir / "experiments").is_dir()
        assert (project_dir / "clean").is_dir()
        assert result["experiments"] is True
        assert result["clean"] is True

    def test_initialises_separate_git_repos(self, project_dir):
        mgr = TwoRepoManager(project_dir)
        mgr.init_two_repos()

        assert (project_dir / "experiments" / ".git").is_dir()
        assert (project_dir / "clean" / ".git").is_dir()

    def test_idempotent_reinit(self, manager, project_dir):
        """Calling init twice should not error or corrupt the repos."""
        # Write a file so experiments is non-empty
        (project_dir / "experiments" / "note.txt").write_text("hello")
        result = manager.init_two_repos()
        assert result["experiments"] is True
        assert (project_dir / "experiments" / "note.txt").read_text() == "hello"


# ── promote_to_clean ────────────────────────────────────────────────


class TestPromoteToClean:
    def test_copies_file_and_commits(self, manager, project_dir):
        exp_file = project_dir / "experiments" / "analysis.py"
        exp_file.write_text("print('result')")
        # Stage and commit in experiments first
        subprocess.run(["git", "add", "."], cwd=project_dir / "experiments", check=True)
        subprocess.run(
            ["git", "commit", "-m", "exp work"],
            cwd=project_dir / "experiments",
            check=True,
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": "test",
                "GIT_COMMITTER_NAME": "test",
                "GIT_AUTHOR_EMAIL": "t@t",
                "GIT_COMMITTER_EMAIL": "t@t",
            },
        )

        ok = manager.promote_to_clean(["analysis.py"], "Promote analysis")
        assert ok is True
        assert (project_dir / "clean" / "analysis.py").read_text() == "print('result')"

        # Verify committed in clean/
        log = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=project_dir / "clean",
            capture_output=True,
            text=True,
        )
        assert "Promote analysis" in log.stdout

    def test_promote_missing_file_returns_false(self, manager):
        ok = manager.promote_to_clean(["nonexistent.py"], "bad promote")
        assert ok is False


# ── get_status ──────────────────────────────────────────────────────


class TestGetStatus:
    def test_both_repos_clean_after_init(self, manager):
        status = manager.get_status()
        assert "experiments" in status
        assert "clean" in status
        assert status["experiments"]["dirty"] is False
        assert status["clean"]["dirty"] is False

    def test_dirty_flag_after_untracked_file(self, manager, project_dir):
        (project_dir / "experiments" / "scratch.py").write_text("x = 1")
        status = manager.get_status()
        assert status["experiments"]["dirty"] is True
        assert status["clean"]["dirty"] is False


# ── sync_shared ─────────────────────────────────────────────────────


class TestSyncShared:
    def test_syncs_shared_directory(self, manager, project_dir):
        # Create shared content in experiments
        shared = project_dir / "experiments" / "config"
        shared.mkdir(parents=True)
        (shared / "settings.yaml").write_text("key: value")

        ok = manager.sync_shared(["config/"])
        assert ok is True
        assert (
            project_dir / "clean" / "config" / "settings.yaml"
        ).read_text() == "key: value"

    def test_sync_no_source_returns_false(self, manager):
        """Syncing a path that doesn't exist in experiments should return False."""
        ok = manager.sync_shared(["nonexistent_dir/"])
        assert ok is False


# ── run_experiment ──────────────────────────────────────────────────


class TestRunExperiment:
    def test_runs_command_in_experiments_context(self, manager, project_dir):
        result = manager.run_experiment("pwd")
        assert result["returncode"] == 0
        assert "experiments" in result["stdout"]

    def test_captures_stderr_on_failure(self, manager):
        result = manager.run_experiment("ls /nonexistent_path_xyz")
        assert result["returncode"] != 0
        assert len(result["stderr"]) > 0


# ── diff_repos ──────────────────────────────────────────────────────


class TestDiffRepos:
    def test_no_diff_when_identical(self, manager):
        diff = manager.diff_repos()
        # Both empty repos, nothing to diff
        assert isinstance(diff, str)

    def test_diff_shows_divergence(self, manager, project_dir):
        (project_dir / "experiments" / "new.py").write_text("a = 1\n")
        diff = manager.diff_repos()
        assert "new.py" in diff
