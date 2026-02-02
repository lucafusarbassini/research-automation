"""Tests for core.collaboration."""

from pathlib import Path

import pytest

from core.collaboration import (
    get_user_id,
    merge_encyclopedia,
    merge_state_file,
    sync_before_start,
)


class _FakeResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestSyncBeforeStart:
    def test_pulls_with_rebase(self):
        calls = []

        def run_cmd(cmd, **kw):
            calls.append(cmd)
            if cmd == ["git", "remote"]:
                return _FakeResult(stdout="origin\n")
            return _FakeResult()

        result = sync_before_start(cwd="/tmp", run_cmd=run_cmd)
        assert result is True
        cmd_strs = [" ".join(c) for c in calls]
        assert any("pull --rebase" in s for s in cmd_strs)

    def test_no_remote_skips(self):
        def run_cmd(cmd, **kw):
            if cmd == ["git", "remote"]:
                return _FakeResult(stdout="")
            return _FakeResult()

        result = sync_before_start(cwd="/tmp", run_cmd=run_cmd)
        assert result is True

    def test_not_git_repo(self):
        def run_cmd(cmd, **kw):
            if "rev-parse" in cmd:
                return _FakeResult(returncode=128)
            return _FakeResult()

        result = sync_before_start(cwd="/tmp", run_cmd=run_cmd)
        assert result is True  # Not a git repo -> nothing to sync

    def test_pull_failure(self):
        def run_cmd(cmd, **kw):
            if cmd == ["git", "remote"]:
                return _FakeResult(stdout="origin\n")
            if "pull" in cmd:
                return _FakeResult(returncode=1, stderr="conflict")
            return _FakeResult()

        result = sync_before_start(cwd="/tmp", run_cmd=run_cmd)
        assert result is False


class TestGetUserId:
    def test_from_git_email(self):
        def run_cmd(cmd, **kw):
            return _FakeResult(stdout="user@example.com\n")

        uid = get_user_id(run_cmd=run_cmd)
        assert uid == "user@example.com"

    def test_fallback_hostname(self):
        def run_cmd(cmd, **kw):
            return _FakeResult(returncode=1)

        uid = get_user_id(run_cmd=run_cmd)
        assert "@" in uid  # Should be user@hostname


class TestMergeEncyclopedia:
    def test_deduplicates(self, tmp_path):
        ours = tmp_path / "ENCYCLOPEDIA.md"
        ours.write_text("# Tricks\n- [2026-01-01] trick A\n- [2026-01-02] trick B\n")
        theirs = "# Tricks\n- [2026-01-02] trick B\n- [2026-01-03] trick C\n"

        merged = merge_encyclopedia(ours, theirs)
        lines = merged.splitlines()
        assert lines.count("- [2026-01-02] trick B") == 1
        assert "- [2026-01-03] trick C" in lines

    def test_ours_missing(self, tmp_path):
        ours = tmp_path / "nonexistent.md"
        theirs = "line 1\nline 2\n"

        merged = merge_encyclopedia(ours, theirs)
        assert "line 1" in merged
        assert "line 2" in merged


class TestMergeStateFile:
    def test_appends_new_lines(self, tmp_path):
        ours = tmp_path / "PROGRESS.md"
        ours.write_text("# Progress\n\n- Step 1 done\n")
        theirs = "# Progress\n\n- Step 1 done\n- Step 2 done\n"

        merged = merge_state_file(ours, theirs)
        assert "Step 2 done" in merged
        # "Step 1 done" should appear only once
        assert merged.count("Step 1 done") == 1

    def test_empty_lines_ignored(self, tmp_path):
        ours = tmp_path / "PROGRESS.md"
        ours.write_text("# Progress\n")
        theirs = "\n\n\n"

        merged = merge_state_file(ours, theirs)
        # Empty lines should not be appended
        assert merged.strip() == "# Progress"
