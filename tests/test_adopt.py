"""Tests for core.adopt."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from core.adopt import adopt_repo


class _FakeResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestAdoptLocal:
    def test_adopt_local_directory(self, tmp_path):
        # Create a minimal "existing repo"
        source_dir = tmp_path / "my-repo"
        source_dir.mkdir()
        (source_dir / "README.md").write_text(
            "# My Repo\n\nA cool project about NLP.\n"
        )
        (source_dir / ".git").mkdir()  # Fake git dir

        calls = []

        def run_cmd(cmd, **kw):
            calls.append(cmd)
            if cmd[:3] == ["git", "rev-parse", "--is-inside-work-tree"]:
                return _FakeResult(stdout="true")
            if cmd[:2] == ["git", "status"]:
                return _FakeResult(stdout="M state/TODO.md\n")
            if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
                return _FakeResult(stdout="main\n")
            return _FakeResult()

        result = adopt_repo(str(source_dir), run_cmd=run_cmd)

        assert result == source_dir
        assert (source_dir / "knowledge" / "GOAL.md").exists()
        assert (source_dir / "state" / "TODO.md").exists()
        assert (source_dir / "state" / "PROGRESS.md").exists()
        assert (source_dir / "config" / "settings.yml").exists()

        # GOAL.md should contain README content
        goal_content = (source_dir / "knowledge" / "GOAL.md").read_text()
        assert "NLP" in goal_content

    def test_adopt_creates_gitattributes(self, tmp_path):
        source_dir = tmp_path / "repo2"
        source_dir.mkdir()
        (source_dir / ".git").mkdir()

        def run_cmd(cmd, **kw):
            if cmd[:2] == ["git", "status"]:
                return _FakeResult(stdout="")  # No changes -> skip commit
            return _FakeResult()

        adopt_repo(str(source_dir), run_cmd=run_cmd)

        gitattrs = source_dir / ".gitattributes"
        assert gitattrs.exists()
        content = gitattrs.read_text()
        assert "merge=union" in content

    def test_adopt_nonexistent_path_raises(self, tmp_path):
        def run_cmd(cmd, **kw):
            return _FakeResult()

        with pytest.raises(FileNotFoundError):
            adopt_repo(str(tmp_path / "does-not-exist"), run_cmd=run_cmd)

    def test_adopt_registers_project(self, tmp_path):
        source_dir = tmp_path / "reg-test"
        source_dir.mkdir()
        (source_dir / ".git").mkdir()

        def run_cmd(cmd, **kw):
            if cmd[:2] == ["git", "status"]:
                return _FakeResult(stdout="")
            return _FakeResult()

        from core.multi_project import ProjectRegistry

        registry_file = tmp_path / ".ricet" / "projects.json"
        fake_registry = ProjectRegistry(registry_file=registry_file)
        with patch("core.adopt.CONFIG_DIR", tmp_path / ".ricet"), \
             patch("core.multi_project._default_registry", fake_registry), \
             patch("core.multi_project._get_default_registry", return_value=fake_registry):
            adopt_repo(str(source_dir), project_name="test-proj", run_cmd=run_cmd)

            assert registry_file.exists()
            data = json.loads(registry_file.read_text())
            projects = data["projects"]
            assert projects[-1]["name"] == "test-proj"


class TestAdoptUrl:
    def test_adopt_url_with_fork(self, tmp_path):
        cloned_dir = tmp_path / "forked-repo"

        def run_cmd(cmd, **kw):
            if cmd[0] == "gh" and "fork" in cmd:
                # Simulate fork + clone by creating the directory
                cloned_dir.mkdir(exist_ok=True)
                (cloned_dir / ".git").mkdir(exist_ok=True)
                (cloned_dir / "README.md").write_text("# Forked\n")
                return _FakeResult()
            if cmd[:2] == ["git", "status"]:
                return _FakeResult(stdout="M state/TODO.md\n")
            if cmd[:3] == ["git", "rev-parse", "--is-inside-work-tree"]:
                return _FakeResult(stdout="true")
            if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
                return _FakeResult(stdout="main\n")
            return _FakeResult()

        with patch("core.adopt.CONFIG_DIR", tmp_path / ".ricet"):
            result = adopt_repo(
                "https://github.com/user/forked-repo",
                target_path=tmp_path,
                run_cmd=run_cmd,
            )

        assert result == cloned_dir
        assert (cloned_dir / "state" / "TODO.md").exists()

    def test_adopt_url_no_fork(self, tmp_path):
        cloned_dir = tmp_path / "cloned"

        def run_cmd(cmd, **kw):
            if cmd[0] == "git" and cmd[1] == "clone":
                cloned_dir.mkdir(exist_ok=True)
                (cloned_dir / ".git").mkdir(exist_ok=True)
                return _FakeResult()
            if cmd[:2] == ["git", "status"]:
                return _FakeResult(stdout="")
            return _FakeResult()

        with patch("core.adopt.CONFIG_DIR", tmp_path / ".ricet"):
            result = adopt_repo(
                "https://github.com/user/cloned",
                target_path=tmp_path,
                fork=False,
                run_cmd=run_cmd,
            )

        assert result == cloned_dir
