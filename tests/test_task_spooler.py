"""Tests for TaskSpooler — tsp wrapper with Python fallback."""

import subprocess
import time
from unittest.mock import MagicMock, patch

import pytest

from core.task_spooler import TaskSpooler, FallbackSpooler


# ---------------------------------------------------------------------------
# TaskSpooler (tsp backend) tests
# ---------------------------------------------------------------------------


class TestTaskSpoolerAvailability:
    """Test tsp availability detection."""

    @patch("shutil.which", return_value="/usr/bin/tsp")
    def test_is_available_when_installed(self, mock_which):
        ts = TaskSpooler()
        assert ts.is_available() is True
        mock_which.assert_called_with("tsp")

    @patch("shutil.which", return_value=None)
    def test_is_not_available_when_missing(self, mock_which):
        ts = TaskSpooler()
        assert ts.is_available() is False


class TestTaskSpoolerEnqueue:
    """Test enqueue via tsp."""

    @patch("shutil.which", return_value="/usr/bin/tsp")
    @patch("subprocess.run")
    def test_enqueue_returns_job_id(self, mock_run, _mock_which):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="7\n", stderr=""
        )
        ts = TaskSpooler()
        job_id = ts.enqueue("echo hello", label="greet")
        assert job_id == 7
        # tsp should be called with the command
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "tsp" in cmd[0]
        assert "echo hello" in " ".join(cmd)

    @patch("shutil.which", return_value="/usr/bin/tsp")
    @patch("subprocess.run")
    def test_enqueue_with_label(self, mock_run, _mock_which):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="12\n", stderr=""
        )
        ts = TaskSpooler()
        job_id = ts.enqueue("sleep 5", label="nap")
        assert job_id == 12
        cmd = mock_run.call_args[0][0]
        assert "-L" in cmd
        assert "nap" in cmd


class TestTaskSpoolerStatus:
    """Test status listing."""

    TSP_OUTPUT = (
        "ID   State      Output               E-Level  Times(r/u/s)  Command [run=1/1]\n"
        "0    finished   /tmp/ts-out.abc123   0        1.00/0.00/0.00 echo hello\n"
        "1    running    /tmp/ts-out.def456                           sleep 60\n"
        "2    queued     (file)                                       ls -la\n"
    )

    @patch("shutil.which", return_value="/usr/bin/tsp")
    @patch("subprocess.run")
    def test_status_parses_tsp_output(self, mock_run, _mock_which):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=self.TSP_OUTPUT, stderr=""
        )
        ts = TaskSpooler()
        jobs = ts.status()
        assert len(jobs) == 3
        assert jobs[0]["id"] == 0
        assert jobs[0]["state"] == "finished"
        assert jobs[1]["state"] == "running"
        assert jobs[2]["state"] == "queued"
        assert "echo hello" in jobs[0]["command"]


class TestTaskSpoolerResult:
    """Test retrieving job results."""

    @patch("shutil.which", return_value="/usr/bin/tsp")
    @patch("subprocess.run")
    def test_result_returns_output(self, mock_run, _mock_which):
        # First call: tsp -i <id> for info, second: tsp -c <id> for output
        info_result = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="Exit status: 0\nCommand: echo hello\n",
            stderr="",
        )
        cat_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="hello\n", stderr=""
        )
        mock_run.side_effect = [info_result, cat_result]
        ts = TaskSpooler()
        res = ts.result(0)
        assert res["exit_code"] == 0
        assert res["output"] == "hello\n"


class TestTaskSpoolerClear:
    """Test clearing finished jobs."""

    @patch("shutil.which", return_value="/usr/bin/tsp")
    @patch("subprocess.run")
    def test_clear_finished(self, mock_run, _mock_which):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        ts = TaskSpooler()
        count = ts.clear_finished()
        assert isinstance(count, int)
        mock_run.assert_called()


class TestTaskSpoolerSlots:
    """Test setting parallel slots."""

    @patch("shutil.which", return_value="/usr/bin/tsp")
    @patch("subprocess.run")
    def test_set_slots(self, mock_run, _mock_which):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        ts = TaskSpooler()
        ts.set_slots(4)
        cmd = mock_run.call_args[0][0]
        assert "-S" in cmd
        assert "4" in cmd


# ---------------------------------------------------------------------------
# FallbackSpooler tests (pure-Python queue)
# ---------------------------------------------------------------------------


class TestFallbackSpooler:
    """Test the Python-based fallback when tsp is not installed."""

    def test_enqueue_and_result(self):
        fb = FallbackSpooler(max_slots=2)
        try:
            job_id = fb.enqueue("echo fallback", label="test")
            assert isinstance(job_id, int)
            res = fb.wait(job_id, timeout=10)
            assert res["exit_code"] == 0
            assert "fallback" in res["output"]
        finally:
            fb.shutdown()

    def test_status_lists_jobs(self):
        fb = FallbackSpooler(max_slots=1)
        try:
            fb.enqueue("echo one")
            fb.enqueue("echo two")
            # Give a moment for execution
            time.sleep(0.5)
            jobs = fb.status()
            assert len(jobs) >= 2
            for job in jobs:
                assert "id" in job
                assert "state" in job
                assert "command" in job
        finally:
            fb.shutdown()

    def test_clear_finished_removes_done(self):
        fb = FallbackSpooler(max_slots=2)
        try:
            jid = fb.enqueue("echo done")
            fb.wait(jid, timeout=10)
            removed = fb.clear_finished()
            assert removed >= 1
            remaining = fb.status()
            for j in remaining:
                assert j["state"] != "finished"
        finally:
            fb.shutdown()

    def test_set_slots(self):
        fb = FallbackSpooler(max_slots=1)
        try:
            fb.set_slots(4)
            assert fb._max_slots == 4
        finally:
            fb.shutdown()


# ---------------------------------------------------------------------------
# Auto-selection tests
# ---------------------------------------------------------------------------


class TestAutoBackend:
    """TaskSpooler should fallback automatically when tsp missing."""

    @patch("shutil.which", return_value=None)
    def test_creates_fallback_when_tsp_missing(self, _mock_which):
        ts = TaskSpooler(auto_fallback=True)
        assert ts._fallback is not None
        assert isinstance(ts._fallback, FallbackSpooler)

    @patch("shutil.which", return_value="/usr/bin/tsp")
    def test_no_fallback_when_tsp_present(self, _mock_which):
        ts = TaskSpooler(auto_fallback=True)
        assert ts._fallback is None
