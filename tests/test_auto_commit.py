"""Tests for core.auto_commit."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from core.auto_commit import auto_commit


class _FakeResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _make_run_cmd(responses: dict[str, _FakeResult] | None = None):
    """Build a fake run_cmd that returns predefined results keyed by first arg."""
    default = _FakeResult()
    if responses is None:
        responses = {}

    def run_cmd(cmd: list[str], **kwargs):
        key = cmd[0] if cmd else ""
        # Match on the first two words for git subcommands
        if len(cmd) >= 2 and cmd[0] == "git":
            subkey = f"git {cmd[1]}"
            if subkey in responses:
                return responses[subkey]
        return responses.get(key, default)

    return run_cmd


class TestAutoCommit:
    def test_basic_commit(self):
        calls = []

        def run_cmd(cmd, **kw):
            calls.append(cmd)
            if cmd[:2] == ["git", "status"]:
                return _FakeResult(stdout="M file.py\n")
            if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
                return _FakeResult(stdout="main\n")
            return _FakeResult()

        result = auto_commit("test message", cwd="/tmp", run_cmd=run_cmd, push=False)
        assert result is True
        # Should have called git add and git commit
        cmd_strs = [" ".join(c) for c in calls]
        assert any("git add -A" in s for s in cmd_strs)
        assert any("git commit" in s for s in cmd_strs)

    def test_no_changes_skips(self):
        def run_cmd(cmd, **kw):
            if cmd[:2] == ["git", "status"]:
                return _FakeResult(stdout="")  # No changes
            return _FakeResult()

        result = auto_commit("test", cwd="/tmp", run_cmd=run_cmd)
        assert result is False

    def test_not_git_repo(self):
        def run_cmd(cmd, **kw):
            if "rev-parse" in cmd:
                return _FakeResult(returncode=128)
            return _FakeResult()

        result = auto_commit("test", cwd="/tmp", run_cmd=run_cmd)
        assert result is False

    def test_disabled_via_env(self, monkeypatch):
        monkeypatch.setenv("RICET_AUTO_COMMIT", "false")
        result = auto_commit("test")
        assert result is False

    def test_push_when_enabled(self):
        pushed = []

        def run_cmd(cmd, **kw):
            if cmd[:2] == ["git", "push"]:
                pushed.append(cmd)
            if cmd[:2] == ["git", "status"]:
                return _FakeResult(stdout="M file.py\n")
            if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
                return _FakeResult(stdout="main\n")
            return _FakeResult()

        auto_commit("test", cwd="/tmp", run_cmd=run_cmd, push=True)
        assert len(pushed) == 1
        assert pushed[0] == ["git", "push", "origin", "main"]

    def test_push_disabled(self):
        pushed = []

        def run_cmd(cmd, **kw):
            if cmd[:2] == ["git", "push"]:
                pushed.append(cmd)
            if cmd[:2] == ["git", "status"]:
                return _FakeResult(stdout="M file.py\n")
            return _FakeResult()

        auto_commit("test", cwd="/tmp", run_cmd=run_cmd, push=False)
        assert len(pushed) == 0

    def test_commit_failure(self):
        def run_cmd(cmd, **kw):
            if cmd[:2] == ["git", "status"]:
                return _FakeResult(stdout="M file.py\n")
            if cmd[:2] == ["git", "commit"]:
                return _FakeResult(returncode=1, stderr="commit failed")
            return _FakeResult()

        result = auto_commit("test", cwd="/tmp", run_cmd=run_cmd, push=False)
        assert result is False
