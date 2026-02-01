"""Task spooler integration — wraps the `tsp` CLI with a pure-Python fallback."""

import logging
import re
import shutil
import subprocess
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure-Python fallback (used when tsp is not installed)
# ---------------------------------------------------------------------------


class FallbackSpooler:
    """Minimal task queue backed by concurrent.futures."""

    def __init__(self, max_slots: int = 2) -> None:
        self._max_slots = max_slots
        self._pool = ThreadPoolExecutor(max_workers=max_slots)
        self._lock = threading.Lock()
        self._next_id = 0
        # job_id -> {future, command, label, state, result}
        self._jobs: dict[int, dict] = {}

    # -- internal -----------------------------------------------------------

    @staticmethod
    def _run_command(command: str) -> dict:
        """Execute *command* in a shell and capture output."""
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=3600,
            )
            return {
                "exit_code": proc.returncode,
                "output": proc.stdout,
                "stderr": proc.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"exit_code": -1, "output": "", "stderr": "timeout"}

    def _submit(self, job_id: int, command: str) -> None:
        future = self._pool.submit(self._run_command, command)

        def _on_done(f: Future, jid: int = job_id) -> None:
            with self._lock:
                entry = self._jobs.get(jid)
                if entry is not None:
                    entry["state"] = "finished"
                    entry["result"] = f.result()

        future.add_done_callback(_on_done)
        self._jobs[job_id]["future"] = future
        self._jobs[job_id]["state"] = "running"

    # -- public API ---------------------------------------------------------

    def enqueue(self, command: str, label: str = "") -> int:
        with self._lock:
            job_id = self._next_id
            self._next_id += 1
            self._jobs[job_id] = {
                "command": command,
                "label": label,
                "state": "queued",
                "future": None,
                "result": None,
            }
        self._submit(job_id, command)
        return job_id

    def status(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "id": jid,
                    "state": info["state"],
                    "command": info["command"],
                    "label": info["label"],
                }
                for jid, info in self._jobs.items()
            ]

    def result(self, job_id: int) -> dict:
        with self._lock:
            entry = self._jobs.get(job_id)
        if entry is None:
            raise KeyError(f"Unknown job id: {job_id}")
        if entry["result"] is not None:
            return entry["result"]
        # Not finished yet — return partial info
        return {"exit_code": None, "output": "", "stderr": "", "state": entry["state"]}

    def wait(self, job_id: int, timeout: int = 3600) -> dict:
        with self._lock:
            entry = self._jobs.get(job_id)
        if entry is None:
            raise KeyError(f"Unknown job id: {job_id}")
        future: Optional[Future] = entry.get("future")
        if future is not None:
            future.result(timeout=timeout)
        return self.result(job_id)

    def clear_finished(self) -> int:
        with self._lock:
            to_remove = [
                jid for jid, info in self._jobs.items() if info["state"] == "finished"
            ]
            for jid in to_remove:
                del self._jobs[jid]
            return len(to_remove)

    def set_slots(self, n: int) -> None:
        self._max_slots = n
        # Recreate the pool with updated worker count.  Running jobs will
        # finish in the old pool; new submissions use the new one.
        self._pool = ThreadPoolExecutor(max_workers=n)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False)


# ---------------------------------------------------------------------------
# TaskSpooler — primary interface
# ---------------------------------------------------------------------------


class TaskSpooler:
    """Wrapper around the ``tsp`` (task-spooler) command-line tool.

    When *auto_fallback* is ``True`` (the default) and ``tsp`` is not found on
    ``$PATH``, all operations are transparently routed to a pure-Python
    :class:`FallbackSpooler` backed by :mod:`concurrent.futures`.
    """

    def __init__(self, *, auto_fallback: bool = True, tsp_bin: str = "tsp") -> None:
        self._tsp = tsp_bin
        self._fallback: Optional[FallbackSpooler] = None
        if auto_fallback and not self.is_available():
            logger.info("tsp not found — using Python fallback spooler")
            self._fallback = FallbackSpooler()

    # -- availability -------------------------------------------------------

    def is_available(self) -> bool:
        """Return ``True`` if the ``tsp`` binary is on ``$PATH``."""
        return shutil.which(self._tsp) is not None

    # -- helpers ------------------------------------------------------------

    def _run(self, args: list[str], **kwargs) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self._tsp, *args],
            capture_output=True,
            text=True,
            **kwargs,
        )

    # -- public API ---------------------------------------------------------

    def enqueue(self, command: str, label: str = "") -> int:
        """Add *command* to the queue and return its integer job ID."""
        if self._fallback:
            return self._fallback.enqueue(command, label=label)
        args: list[str] = []
        if label:
            args += ["-L", label]
        # tsp expects the command as separate shell words; wrapping in sh -c
        # keeps things simple and handles pipes/redirections.
        args += ["sh", "-c", command]
        proc = self._run(args)
        proc.check_returncode()
        return int(proc.stdout.strip())

    def status(self) -> list[dict]:
        """Return a list of dicts describing every job in the queue."""
        if self._fallback:
            return self._fallback.status()
        proc = self._run([])
        proc.check_returncode()
        lines = proc.stdout.strip().splitlines()
        if not lines:
            return []
        jobs: list[dict] = []
        # Header is always the first line — skip it.
        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 2:
                continue
            job_id = int(parts[0])
            state = parts[1]
            # The command is everything after the last known fixed column.
            # tsp output is whitespace-aligned; command starts after Times or
            # E-Level columns.  A simple heuristic: find the state token and
            # grab the tail.
            cmd_match = re.search(
                r"^\d+\s+\S+\s+\S+\s+(?:\S+\s+)?(?:\S+\s+)?(.*)", line
            )
            command = cmd_match.group(1).strip() if cmd_match else ""
            jobs.append({"id": job_id, "state": state, "command": command})
        return jobs

    def result(self, job_id: int) -> dict:
        """Get the result of a completed job (exit code + captured output)."""
        if self._fallback:
            return self._fallback.result(job_id)
        # tsp -i <id> → job info (exit status, command, …)
        info_proc = self._run(["-i", str(job_id)])
        info_proc.check_returncode()
        exit_code = None
        for info_line in info_proc.stdout.splitlines():
            m = re.match(r"Exit status:\s*(\S+)", info_line)
            if m:
                try:
                    exit_code = int(m.group(1))
                except ValueError:
                    exit_code = None
        # tsp -c <id> → captured stdout of the job
        cat_proc = self._run(["-c", str(job_id)])
        output = cat_proc.stdout
        return {"exit_code": exit_code, "output": output}

    def wait(self, job_id: int, timeout: int = 3600) -> dict:
        """Block until *job_id* finishes (or *timeout* seconds elapse)."""
        if self._fallback:
            return self._fallback.wait(job_id, timeout=timeout)
        # tsp -w <id> blocks until the job finishes.
        self._run(["-w", str(job_id)], timeout=timeout)
        return self.result(job_id)

    def clear_finished(self) -> int:
        """Remove finished jobs from the queue.  Returns count removed."""
        if self._fallback:
            return self._fallback.clear_finished()
        before = self.status()
        self._run(["-C"])
        after = self.status()
        return len(before) - len(after)

    def set_slots(self, n: int) -> None:
        """Set number of parallel execution slots."""
        if self._fallback:
            self._fallback.set_slots(n)
            return
        proc = self._run(["-S", str(n)])
        proc.check_returncode()
