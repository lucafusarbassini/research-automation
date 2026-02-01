"""Phase 7 demo tests -- Multi-project management and git worktrees."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Multi-project registry
# ---------------------------------------------------------------------------


class TestRegisterProject:
    """core.multi_project.register_project with tmp_path."""

    def test_register_project(self, tmp_path):
        from core.multi_project import ProjectRegistry

        registry_file = tmp_path / "projects.json"
        reg = ProjectRegistry(registry_file=registry_file)

        proj_dir = tmp_path / "my-project"
        proj_dir.mkdir()

        result = reg.register_project("alpha", proj_dir, project_type="research")

        assert result["name"] == "alpha"
        assert result["path"] == str(proj_dir)
        assert result["project_type"] == "research"
        assert "registered_at" in result
        # Registry file was persisted
        assert registry_file.exists()


class TestListProjects:
    """Register 2 projects then list."""

    def test_list_projects(self, tmp_path):
        from core.multi_project import ProjectRegistry

        registry_file = tmp_path / "projects.json"
        reg = ProjectRegistry(registry_file=registry_file)

        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()

        reg.register_project("alpha", dir_a)
        reg.register_project("beta", dir_b)

        projects = reg.list_projects()
        assert len(projects) == 2

        names = {p["name"] for p in projects}
        assert names == {"alpha", "beta"}

        # First registered project is active by default
        active = [p for p in projects if p["active"]]
        assert len(active) == 1
        assert active[0]["name"] == "alpha"


class TestSwitchProject:
    """Register 2, switch between them."""

    def test_switch_project(self, tmp_path):
        from core.multi_project import ProjectRegistry

        registry_file = tmp_path / "projects.json"
        reg = ProjectRegistry(registry_file=registry_file)

        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()

        reg.register_project("alpha", dir_a)
        reg.register_project("beta", dir_b)

        # Initially alpha is active
        active = reg.get_active_project()
        assert active["name"] == "alpha"

        # Switch to beta
        returned_path = reg.switch_project("beta")
        assert returned_path == dir_b

        active = reg.get_active_project()
        assert active["name"] == "beta"

        # Switch back to alpha
        reg.switch_project("alpha")
        assert reg.get_active_project()["name"] == "alpha"


class TestSyncKnowledge:
    """Create encyclopedia entries in source, sync to target."""

    def test_sync_knowledge(self, tmp_path):
        from core.multi_project import ProjectRegistry

        registry_file = tmp_path / "projects.json"
        reg = ProjectRegistry(registry_file=registry_file)

        src_dir = tmp_path / "source"
        tgt_dir = tmp_path / "target"
        src_dir.mkdir()
        tgt_dir.mkdir()

        reg.register_project("source", src_dir)
        reg.register_project("target", tgt_dir)

        # Create encyclopedia in source with entries
        kb_dir = src_dir / "knowledge"
        kb_dir.mkdir()
        (kb_dir / "ENCYCLOPEDIA.md").write_text(
            "## Tricks\n"
            "- [2026-01-15] Use batch size 64 for faster convergence\n"
            "- [2026-01-16] Pin numpy version to avoid breakage\n"
            "## Decisions\n"
        )

        # Sync
        count = reg.sync_knowledge_across("source", "target")
        assert count == 2

        # Verify target encyclopedia was created and has entries
        target_kb = tgt_dir / "knowledge" / "ENCYCLOPEDIA.md"
        assert target_kb.exists()
        content = target_kb.read_text()
        assert "batch size 64" in content
        assert "Pin numpy" in content

        # Second sync should not duplicate
        count2 = reg.sync_knowledge_across("source", "target")
        assert count2 == 0


class TestProjectManagerAdapter:
    """core.multi_project.project_manager works."""

    def test_project_manager_adapter(self, tmp_path, monkeypatch):
        from core import multi_project
        from core.multi_project import ProjectRegistry

        # Point the default registry to tmp_path
        registry_file = tmp_path / "projects.json"
        reg = ProjectRegistry(registry_file=registry_file)
        monkeypatch.setattr(multi_project, "_default_registry", reg)
        # Also override the _get_default_registry to return our instance
        monkeypatch.setattr(multi_project, "_get_default_registry", lambda: reg)

        proj_dir = tmp_path / "proj"
        proj_dir.mkdir()

        pm = multi_project.project_manager
        pm.register("test-proj", str(proj_dir), project_type="website")

        projects = pm.list_projects()
        assert len(projects) == 1
        assert projects[0]["name"] == "test-proj"

        returned_path = pm.switch("test-proj")
        assert returned_path == proj_dir


# ---------------------------------------------------------------------------
# Git worktrees
# ---------------------------------------------------------------------------


class TestGitWorktreeCreate:
    """core.git_worktrees.create_worktree with mocked subprocess."""

    def test_git_worktree_create(self, tmp_path):
        from core.git_worktrees import create_worktree

        fake_result = subprocess.CompletedProcess(
            args=["git", "worktree", "add"], returncode=0, stdout="", stderr=""
        )
        with patch(
            "core.git_worktrees.subprocess.run", return_value=fake_result
        ) as mock_run:
            wt_path = tmp_path / "wt"
            result = create_worktree("feature/test", path=wt_path)

            assert result == wt_path
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "worktree" in call_args
            assert "add" in call_args
            assert str(wt_path) in call_args
            assert "feature/test" in call_args


class TestGitWorktreeList:
    """core.git_worktrees.list_worktrees with mocked porcelain output."""

    def test_git_worktree_list(self):
        from core.git_worktrees import list_worktrees

        porcelain_output = (
            "worktree /home/user/project\n"
            "HEAD abc123\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /home/user/project/.worktrees/feature-x\n"
            "HEAD def456\n"
            "branch refs/heads/feature/x\n"
        )
        fake_result = subprocess.CompletedProcess(
            args=["git", "worktree", "list", "--porcelain"],
            returncode=0,
            stdout=porcelain_output,
            stderr="",
        )
        with patch("core.git_worktrees.subprocess.run", return_value=fake_result):
            trees = list_worktrees()

        assert len(trees) == 2
        assert trees[0]["path"] == "/home/user/project"
        assert trees[0]["head"] == "abc123"
        assert trees[0]["branch"] == "refs/heads/main"
        assert trees[1]["branch"] == "refs/heads/feature/x"


class TestGitWorktreeRemove:
    """core.git_worktrees.remove_worktree."""

    def test_git_worktree_remove(self, tmp_path):
        from core.git_worktrees import remove_worktree

        fake_result = subprocess.CompletedProcess(
            args=["git", "worktree", "remove"], returncode=0, stdout="", stderr=""
        )
        with patch(
            "core.git_worktrees.subprocess.run", return_value=fake_result
        ) as mock_run:
            success = remove_worktree(tmp_path / "some-worktree")

        assert success is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "remove" in call_args
        assert "--force" in call_args

    def test_git_worktree_remove_failure(self, tmp_path):
        from core.git_worktrees import remove_worktree

        with patch(
            "core.git_worktrees.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "git"),
        ):
            success = remove_worktree(tmp_path / "bad-worktree")

        assert success is False


class TestWorktreeManagerAdapter:
    """core.git_worktrees.worktree_manager works."""

    def test_worktree_manager_adapter(self):
        from core.git_worktrees import worktree_manager

        assert hasattr(worktree_manager, "add")
        assert hasattr(worktree_manager, "list")
        assert hasattr(worktree_manager, "remove")
        assert hasattr(worktree_manager, "prune")
        assert callable(worktree_manager.add)
        assert callable(worktree_manager.list)


class TestWorktreeContext:
    """core.git_worktrees.WorktreeContext."""

    def test_worktree_context(self, tmp_path):
        from core.git_worktrees import WorktreeContext

        create_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        remove_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        with patch("core.git_worktrees.subprocess.run", return_value=create_result):
            ctx = WorktreeContext("feature/ctx-test", path=tmp_path / "ctx-wt")

            with patch(
                "core.git_worktrees.subprocess.run",
                side_effect=[create_result, remove_result],
            ):
                # Enter creates
                wt_path = ctx.__enter__()
                assert wt_path == tmp_path / "ctx-wt"

                # Exit removes
                ctx.__exit__(None, None, None)


# ---------------------------------------------------------------------------
# Cross-repo linking
# ---------------------------------------------------------------------------


class TestCrossRepoLink:
    """core.cross_repo linking repos."""

    def test_cross_repo_link(self, tmp_path):
        from core.cross_repo import _load_linked_repos, link_repository

        repos_file = tmp_path / "linked_repos.json"

        repo = link_repository(
            name="data-pipeline",
            path="/home/user/data-pipeline",
            remote_url="https://github.com/user/data-pipeline.git",
            permissions=["read", "write"],
            repos_file=repos_file,
        )

        assert repo.name == "data-pipeline"
        assert repo.path == "/home/user/data-pipeline"
        assert repo.remote_url == "https://github.com/user/data-pipeline.git"
        assert "read" in repo.permissions
        assert "write" in repo.permissions

        # Verify persisted
        loaded = _load_linked_repos(repos_file)
        assert len(loaded) == 1
        assert loaded[0].name == "data-pipeline"

    def test_cross_repo_link_duplicate_replaces(self, tmp_path):
        from core.cross_repo import _load_linked_repos, link_repository

        repos_file = tmp_path / "linked_repos.json"

        link_repository(
            name="repo-a",
            path="/path/a",
            repos_file=repos_file,
        )
        link_repository(
            name="repo-a",
            path="/path/a-updated",
            repos_file=repos_file,
        )

        loaded = _load_linked_repos(repos_file)
        assert len(loaded) == 1
        assert loaded[0].path == "/path/a-updated"

    def test_enforce_permission_boundaries(self, tmp_path):
        from core.cross_repo import enforce_permission_boundaries, link_repository

        repos_file = tmp_path / "linked_repos.json"
        link_repository(
            name="readonly-repo",
            path="/path/ro",
            permissions=["read"],
            repos_file=repos_file,
        )

        assert (
            enforce_permission_boundaries(
                "readonly-repo", "read", repos_file=repos_file
            )
            is True
        )
        assert (
            enforce_permission_boundaries(
                "readonly-repo", "write", repos_file=repos_file
            )
            is False
        )
        assert (
            enforce_permission_boundaries("nonexistent", "read", repos_file=repos_file)
            is False
        )
