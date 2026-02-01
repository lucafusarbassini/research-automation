"""Tests for core.auto_debug — auto-debug loop module (TDD)."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from core.auto_debug import (
    DebugHistory,
    DebugResult,
    auto_debug_loop,
    parse_error,
    run_with_retry,
    suggest_fix,
)


# ---------------------------------------------------------------------------
# 1. DebugResult dataclass
# ---------------------------------------------------------------------------


class TestDebugResult:
    def test_fields_present(self):
        r = DebugResult(
            original_error="NameError: name 'x' is not defined",
            fix_applied="Define variable x before use",
            success=True,
            iterations=2,
            final_output="OK",
        )
        assert r.original_error == "NameError: name 'x' is not defined"
        assert r.fix_applied == "Define variable x before use"
        assert r.success is True
        assert r.iterations == 2
        assert r.final_output == "OK"

    def test_defaults_not_required(self):
        """All fields are explicit — no hidden defaults."""
        with pytest.raises(TypeError):
            DebugResult()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# 2. parse_error
# ---------------------------------------------------------------------------


class TestParseError:
    def test_python_traceback(self):
        stderr = (
            'Traceback (most recent call last):\n'
            '  File "main.py", line 42, in <module>\n'
            "    foo()\n"
            "NameError: name 'foo' is not defined\n"
        )
        result = parse_error(stderr)
        assert result["error_type"] == "NameError"
        assert result["file"] == "main.py"
        assert result["line"] == 42
        assert "foo" in result["message"]

    def test_npm_error(self):
        stderr = (
            "npm ERR! code ENOENT\n"
            "npm ERR! syscall open\n"
            "npm ERR! path /app/package.json\n"
            "npm ERR! errno -2\n"
        )
        result = parse_error(stderr)
        assert result["error_type"] == "npm"
        assert "ENOENT" in result["message"]

    def test_latex_error(self):
        stderr = "! Undefined control sequence.\nl.15 \\badcommand\n"
        result = parse_error(stderr)
        assert result["error_type"] == "latex"
        assert result["line"] == 15
        assert "Undefined control sequence" in result["message"]

    def test_pytest_failure(self):
        stderr = (
            "FAILED tests/test_foo.py::test_bar - AssertionError: assert 1 == 2\n"
        )
        result = parse_error(stderr)
        assert result["error_type"] == "pytest"
        assert "test_foo.py" in result["file"]

    def test_unknown_error_returns_raw(self):
        stderr = "something completely unexpected went wrong"
        result = parse_error(stderr)
        assert result["error_type"] == "unknown"
        assert result["message"] == stderr.strip()


# ---------------------------------------------------------------------------
# 3. suggest_fix
# ---------------------------------------------------------------------------


class TestSuggestFix:
    def test_name_error_suggestion(self):
        err = {
            "error_type": "NameError",
            "file": "main.py",
            "line": 10,
            "message": "name 'pandas' is not defined",
        }
        fix = suggest_fix(err)
        assert "import" in fix.lower()

    def test_module_not_found_suggestion(self):
        err = {
            "error_type": "ModuleNotFoundError",
            "file": "app.py",
            "line": 1,
            "message": "No module named 'requests'",
        }
        fix = suggest_fix(err)
        assert "install" in fix.lower() or "pip" in fix.lower()

    def test_unknown_error_generic_suggestion(self):
        err = {"error_type": "unknown", "file": "", "line": 0, "message": "boom"}
        fix = suggest_fix(err)
        assert isinstance(fix, str)
        assert len(fix) > 0


# ---------------------------------------------------------------------------
# 4. run_with_retry
# ---------------------------------------------------------------------------


class TestRunWithRetry:
    @patch("core.auto_debug.subprocess.run")
    def test_succeeds_first_try(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args="echo hi", returncode=0, stdout="hi", stderr=""
        )
        result = run_with_retry("echo hi", retries=3)
        assert result.returncode == 0
        assert mock_run.call_count == 1

    @patch("core.auto_debug.subprocess.run")
    def test_retries_on_failure_then_succeeds(self, mock_run):
        fail = subprocess.CompletedProcess(args="cmd", returncode=1, stdout="", stderr="err")
        ok = subprocess.CompletedProcess(args="cmd", returncode=0, stdout="ok", stderr="")
        mock_run.side_effect = [fail, fail, ok]
        result = run_with_retry("cmd", retries=3)
        assert result.returncode == 0
        assert mock_run.call_count == 3

    @patch("core.auto_debug.subprocess.run")
    def test_exhausts_retries(self, mock_run):
        fail = subprocess.CompletedProcess(args="cmd", returncode=1, stdout="", stderr="err")
        mock_run.return_value = fail
        result = run_with_retry("cmd", retries=2)
        assert result.returncode == 1
        assert mock_run.call_count == 2


# ---------------------------------------------------------------------------
# 5. auto_debug_loop
# ---------------------------------------------------------------------------


class TestAutoDebugLoop:
    @patch("core.auto_debug.subprocess.run")
    def test_succeeds_immediately(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args="pytest", returncode=0, stdout="all passed", stderr=""
        )
        result = auto_debug_loop("pytest")
        assert result.success is True
        assert result.iterations == 1
        assert result.final_output == "all passed"

    @patch("core.auto_debug.subprocess.run")
    def test_fails_then_succeeds(self, mock_run):
        fail = subprocess.CompletedProcess(
            args="pytest",
            returncode=1,
            stdout="",
            stderr=(
                'Traceback (most recent call last):\n'
                '  File "main.py", line 1, in <module>\n'
                "    import foo\n"
                "ModuleNotFoundError: No module named 'foo'\n"
            ),
        )
        ok = subprocess.CompletedProcess(
            args="pytest", returncode=0, stdout="ok", stderr=""
        )
        mock_run.side_effect = [fail, ok]
        result = auto_debug_loop("pytest", max_iterations=3)
        assert result.success is True
        assert result.iterations == 2

    @patch("core.auto_debug.subprocess.run")
    def test_exhausts_iterations(self, mock_run):
        fail = subprocess.CompletedProcess(
            args="cmd",
            returncode=1,
            stdout="",
            stderr="NameError: name 'x' is not defined",
        )
        mock_run.return_value = fail
        result = auto_debug_loop("cmd", max_iterations=3)
        assert result.success is False
        assert result.iterations == 3
        assert "NameError" in result.original_error


# ---------------------------------------------------------------------------
# 6. DebugHistory
# ---------------------------------------------------------------------------


class TestDebugHistory:
    def test_add_and_retrieve(self):
        history = DebugHistory()
        r = DebugResult(
            original_error="err",
            fix_applied="fix",
            success=True,
            iterations=1,
            final_output="ok",
        )
        history.add(r)
        assert len(history) == 1
        assert history.results[0] is r

    def test_summary_counts(self):
        history = DebugHistory()
        history.add(DebugResult("e1", "f1", True, 1, "ok"))
        history.add(DebugResult("e2", "f2", False, 5, ""))
        history.add(DebugResult("e3", "f3", True, 2, "done"))
        summary = history.summary()
        assert summary["total"] == 3
        assert summary["successes"] == 2
        assert summary["failures"] == 1

    def test_clear(self):
        history = DebugHistory()
        history.add(DebugResult("e", "f", True, 1, "ok"))
        history.clear()
        assert len(history) == 0
