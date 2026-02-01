"""Phase 4 demo tests: autonomous/overnight mode (auto-debug, task spooler, routines, resources)."""

import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.auto_debug import DebugResult, auto_debug_loop, parse_error, suggest_fix
from core.task_spooler import FallbackSpooler, TaskSpooler
from core.autonomous import ScheduledRoutine, add_routine, list_routines
from core.claude_flow import ClaudeFlowUnavailable
from core.resources import ResourceSnapshot, monitor_resources


# ---------------------------------------------------------------------------
# auto_debug: parse_error
# ---------------------------------------------------------------------------


class TestParseError:
    """parse_error should recognise Python, npm, and LaTeX error patterns."""

    def test_python_name_error(self):
        stderr = (
            'Traceback (most recent call last):\n'
            '  File "app.py", line 42\n'
            "NameError: name 'foo' is not defined"
        )
        result = parse_error(stderr)
        assert result["error_type"] == "NameError"
        assert result["file"] == "app.py"
        assert result["line"] == 42
        assert "foo" in result["message"]

    def test_python_module_not_found(self):
        stderr = (
            'Traceback (most recent call last):\n'
            '  File "run.py", line 1\n'
            "ModuleNotFoundError: No module named 'numpy'"
        )
        result = parse_error(stderr)
        assert result["error_type"] == "ModuleNotFoundError"
        assert "numpy" in result["message"]

    def test_npm_error(self):
        stderr = "npm ERR! code ENOENT\nnpm ERR! syscall open"
        result = parse_error(stderr)
        assert result["error_type"] == "npm"
        assert "ENOENT" in result["message"]

    def test_latex_error(self):
        stderr = "! Undefined control sequence.\nl.15 \\badcommand"
        result = parse_error(stderr)
        assert result["error_type"] == "latex"
        assert result["line"] == 15
        assert "Undefined control sequence" in result["message"]

    def test_unknown_fallback(self):
        stderr = "Something went wrong"
        result = parse_error(stderr)
        assert result["error_type"] == "unknown"
        assert result["message"] == "Something went wrong"


# ---------------------------------------------------------------------------
# auto_debug: suggest_fix
# ---------------------------------------------------------------------------


class TestSuggestFix:
    """suggest_fix should return actionable text for known error types."""

    def test_suggest_import_for_name_error(self):
        error = {"error_type": "NameError", "message": "name 'os' is not defined", "file": "main.py", "line": 5}
        fix = suggest_fix(error)
        assert "os" in fix
        assert "import" in fix.lower() or "Import" in fix

    def test_suggest_pip_install_for_module_error(self):
        error = {"error_type": "ModuleNotFoundError", "message": "No module named 'requests'", "file": "", "line": 0}
        fix = suggest_fix(error)
        assert "pip install" in fix
        assert "requests" in fix

    def test_suggest_npm_fix(self):
        error = {"error_type": "npm", "message": "npm error code ENOENT", "file": "", "line": 0}
        fix = suggest_fix(error)
        assert "npm" in fix.lower()

    def test_suggest_latex_fix(self):
        error = {"error_type": "latex", "message": "Undefined control sequence", "file": "", "line": 15}
        fix = suggest_fix(error)
        assert "LaTeX" in fix or "latex" in fix.lower()

    def test_unknown_error_generic_suggestion(self):
        error = {"error_type": "unknown", "message": "oops"}
        fix = suggest_fix(error)
        assert len(fix) > 0
        assert "oops" in fix


# ---------------------------------------------------------------------------
# auto_debug: auto_debug_loop
# ---------------------------------------------------------------------------


class TestAutoDebugLoop:
    """auto_debug_loop orchestrates parse + suggest + retry."""

    def test_loop_success_on_second_try(self):
        """Mocked subprocess succeeds on the second call."""
        fail_proc = subprocess.CompletedProcess(
            args="cmd", returncode=1,
            stdout="", stderr="NameError: name 'x' is not defined",
        )
        ok_proc = subprocess.CompletedProcess(
            args="cmd", returncode=0,
            stdout="All good", stderr="",
        )
        with patch("core.auto_debug.subprocess.run", side_effect=[fail_proc, ok_proc]):
            result = auto_debug_loop("fake_cmd", max_iterations=5)

        assert result.success is True
        assert result.iterations == 2
        assert result.final_output == "All good"
        assert result.original_error != ""

    def test_loop_exhaust_all_iterations(self):
        """All iterations fail -- success should be False."""
        fail_proc = subprocess.CompletedProcess(
            args="cmd", returncode=1,
            stdout="", stderr="SyntaxError: invalid syntax",
        )
        max_iter = 3
        with patch("core.auto_debug.subprocess.run", return_value=fail_proc):
            result = auto_debug_loop("bad_cmd", max_iterations=max_iter)

        assert result.success is False
        assert result.iterations == max_iter
        assert "SyntaxError" in result.original_error


# ---------------------------------------------------------------------------
# DebugResult dict compatibility
# ---------------------------------------------------------------------------


class TestDebugResultDictCompat:
    """DebugResult.get() should behave like dict access for CLI compat."""

    def test_get_fixed(self):
        dr = DebugResult(
            original_error="err", fix_applied="patch", success=True,
            iterations=1, final_output="ok",
        )
        assert dr.get("fixed") is True
        assert dr.get("patch") == "patch"
        assert dr.get("log") == "ok"
        assert dr.get("iterations") == 1

    def test_get_missing_key_returns_default(self):
        dr = DebugResult(
            original_error="", fix_applied="", success=False,
            iterations=0, final_output="",
        )
        assert dr.get("nonexistent") is None
        assert dr.get("nonexistent", 42) == 42


# ---------------------------------------------------------------------------
# task_spooler: FallbackSpooler
# ---------------------------------------------------------------------------


class TestTaskSpoolerEnqueueStatus:
    """FallbackSpooler (pure-Python) should enqueue and report status."""

    def test_enqueue_returns_id_and_status(self):
        spooler = FallbackSpooler(max_slots=2)
        try:
            job_id = spooler.enqueue("echo hello", label="greeting")
            assert isinstance(job_id, int)
            assert job_id >= 0

            statuses = spooler.status()
            assert len(statuses) >= 1
            entry = next(s for s in statuses if s["id"] == job_id)
            assert entry["label"] == "greeting"
            assert entry["state"] in ("queued", "running", "finished")

            # Wait and check result
            res = spooler.wait(job_id, timeout=10)
            assert res["exit_code"] == 0
            assert "hello" in res["output"]
        finally:
            spooler.shutdown()

    def test_task_spooler_auto_fallback(self):
        """TaskSpooler with auto_fallback creates FallbackSpooler when tsp missing."""
        ts = TaskSpooler(auto_fallback=True, tsp_bin="__nonexistent_tsp__")
        assert ts._fallback is not None
        job_id = ts.enqueue("echo test", label="t")
        res = ts.wait(job_id, timeout=10)
        assert res["exit_code"] == 0
        if ts._fallback:
            ts._fallback.shutdown()


# ---------------------------------------------------------------------------
# autonomous: RoutineManager (add_routine / list_routines)
# ---------------------------------------------------------------------------


class TestAutonomousRoutineManager:
    """add_routine + list_routines act as a simple routine manager."""

    def test_add_and_list_routines(self, tmp_path):
        routines_file = tmp_path / "routines.json"

        routine = ScheduledRoutine(
            name="nightly-backup",
            description="Back up project data",
            schedule="daily",
            command="tar czf backup.tar.gz data/",
        )
        add_routine(routine, routines_file=routines_file)

        loaded = list_routines(routines_file=routines_file)
        assert len(loaded) == 1
        assert loaded[0].name == "nightly-backup"
        assert loaded[0].schedule == "daily"
        assert loaded[0].enabled is True

    def test_replace_existing_routine(self, tmp_path):
        routines_file = tmp_path / "routines.json"

        r1 = ScheduledRoutine(name="job", description="v1", schedule="hourly", command="echo v1")
        r2 = ScheduledRoutine(name="job", description="v2", schedule="weekly", command="echo v2")

        add_routine(r1, routines_file=routines_file)
        add_routine(r2, routines_file=routines_file)

        loaded = list_routines(routines_file=routines_file)
        assert len(loaded) == 1
        assert loaded[0].description == "v2"
        assert loaded[0].schedule == "weekly"


# ---------------------------------------------------------------------------
# resources: monitor_resources + disk check
# ---------------------------------------------------------------------------


class TestResourceMonitoring:
    """monitor_resources should return a ResourceSnapshot with plausible values."""

    def test_monitor_resources_returns_snapshot(self):
        with patch("core.resources._get_bridge", side_effect=ClaudeFlowUnavailable("no bridge")):
            snap = monitor_resources()
        assert isinstance(snap, ResourceSnapshot)
        assert snap.timestamp > 0

    def test_resource_snapshot_has_ram(self):
        with patch("core.resources._get_bridge", side_effect=ClaudeFlowUnavailable("no bridge")):
            snap = monitor_resources()
        # On Linux, ram_total_gb should be positive; on other OSes it may be 0.
        assert snap.ram_total_gb >= 0
        assert snap.ram_used_gb >= 0


class TestResourceCheckDisk:
    """Disk monitoring should return a sensible free-space value."""

    def test_disk_free_positive(self):
        with patch("core.resources._get_bridge", side_effect=ClaudeFlowUnavailable("no bridge")):
            snap = monitor_resources()
        # We expect at least some free disk space on any real system.
        assert snap.disk_free_gb > 0
