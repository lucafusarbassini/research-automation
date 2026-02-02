"""Tests for core.claude_helper."""

import json
import subprocess
from unittest.mock import MagicMock

import pytest

from core.claude_helper import call_claude, call_claude_json


class _FakeResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestCallClaude:
    def test_success(self):
        def run_cmd(cmd):
            return _FakeResult(stdout="  hello world  ")

        result = call_claude("test prompt", run_cmd=run_cmd)
        assert result == "hello world"

    def test_failure_returns_none(self):
        def run_cmd(cmd):
            return _FakeResult(returncode=1)

        result = call_claude("test prompt", run_cmd=run_cmd)
        assert result is None

    def test_empty_stdout_returns_none(self):
        def run_cmd(cmd):
            return _FakeResult(stdout="")

        result = call_claude("test prompt", run_cmd=run_cmd)
        assert result is None

    def test_file_not_found(self):
        def run_cmd(cmd):
            raise FileNotFoundError("claude not found")

        result = call_claude("test prompt", run_cmd=run_cmd)
        assert result is None

    def test_timeout(self):
        def run_cmd(cmd):
            raise subprocess.TimeoutExpired(cmd="claude", timeout=30)

        result = call_claude("test prompt", run_cmd=run_cmd)
        assert result is None

    def test_passes_correct_cmd(self):
        captured = []

        def run_cmd(cmd):
            captured.append(cmd)
            return _FakeResult(stdout="ok")

        call_claude("my prompt", run_cmd=run_cmd)
        assert captured[0] == [
            "claude",
            "-p",
            "my prompt",
            "--output-format",
            "json",
            "--model",
            "claude-haiku-3-5-20241022",
        ]


class TestCallClaudeJson:
    def test_plain_json(self):
        def run_cmd(cmd):
            return _FakeResult(stdout='{"key": "value"}')

        result = call_claude_json("test", run_cmd=run_cmd)
        assert result == {"key": "value"}

    def test_json_with_code_fence(self):
        def run_cmd(cmd):
            return _FakeResult(stdout='```json\n{"key": "value"}\n```')

        result = call_claude_json("test", run_cmd=run_cmd)
        assert result == {"key": "value"}

    def test_json_array(self):
        def run_cmd(cmd):
            return _FakeResult(stdout='["a", "b", "c"]')

        result = call_claude_json("test", run_cmd=run_cmd)
        assert result == ["a", "b", "c"]

    def test_invalid_json_returns_none(self):
        def run_cmd(cmd):
            return _FakeResult(stdout="not json at all")

        result = call_claude_json("test", run_cmd=run_cmd)
        assert result is None

    def test_claude_unavailable_returns_none(self):
        def run_cmd(cmd):
            raise FileNotFoundError()

        result = call_claude_json("test", run_cmd=run_cmd)
        assert result is None
