"""Auto-debug loop: run commands, analyse failures, suggest fixes, and retry."""

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class DebugResult:
    """Outcome of a single auto-debug session."""

    original_error: str
    fix_applied: str
    success: bool
    iterations: int
    final_output: str

    def get(self, key: str, default: Any = None) -> Any:
        """Dict-like access for CLI compatibility."""
        mapping = {
            "fixed": self.success,
            "patch": self.fix_applied,
            "log": self.final_output,
            "original_error": self.original_error,
            "iterations": self.iterations,
        }
        return mapping.get(key, default)


class DebugHistory:
    """Tracks all :class:`DebugResult` entries for a session."""

    def __init__(self) -> None:
        self.results: list[DebugResult] = []

    # -- mutators -----------------------------------------------------------

    def add(self, result: DebugResult) -> None:
        self.results.append(result)

    def clear(self) -> None:
        self.results.clear()

    # -- queries ------------------------------------------------------------

    def summary(self) -> dict[str, int]:
        successes = sum(1 for r in self.results if r.success)
        return {
            "total": len(self.results),
            "successes": successes,
            "failures": len(self.results) - successes,
        }

    def __len__(self) -> int:
        return len(self.results)


# ---------------------------------------------------------------------------
# Error parsing
# ---------------------------------------------------------------------------

# Pre-compiled patterns for the four error families we recognise.
_RE_PYTHON_TB_FILE = re.compile(r'File "(.+?)", line (\d+)')
_RE_PYTHON_TB_ERROR = re.compile(r"^(\w+Error):\s*(.+)", re.MULTILINE)
_RE_NPM_CODE = re.compile(r"npm ERR! code (\S+)")
_RE_LATEX_ERROR = re.compile(r"^!\s*(.+?)(?:\.|$)", re.MULTILINE)
_RE_LATEX_LINE = re.compile(r"^l\.(\d+)\s", re.MULTILINE)
_RE_PYTEST_FAIL = re.compile(r"FAILED\s+([\w/\\.]+::\w+)\s*-\s*(.+)", re.MULTILINE)


def parse_error(stderr: str) -> dict[str, Any]:
    """Extract structured error info from *stderr*.

    Recognises:
    * Python tracebacks  (``NameError``, ``ModuleNotFoundError``, etc.)
    * npm error output   (``npm ERR! code …``)
    * LaTeX errors       (``! Undefined control sequence``, etc.)
    * pytest failures    (``FAILED tests/…::test_name``)

    Returns a dict with keys ``error_type``, ``file``, ``line``, ``message``.
    Falls back to ``error_type="unknown"`` when nothing matches.
    """

    # --- Python traceback --------------------------------------------------
    tb_file_match = _RE_PYTHON_TB_FILE.search(stderr)
    tb_err_match = _RE_PYTHON_TB_ERROR.search(stderr)
    if tb_err_match:
        file_name = tb_file_match.group(1) if tb_file_match else ""
        line_no = int(tb_file_match.group(2)) if tb_file_match else 0
        return {
            "error_type": tb_err_match.group(1),
            "file": file_name,
            "line": line_no,
            "message": tb_err_match.group(2).strip(),
        }

    # --- npm ---------------------------------------------------------------
    npm_match = _RE_NPM_CODE.search(stderr)
    if npm_match:
        return {
            "error_type": "npm",
            "file": "",
            "line": 0,
            "message": f"npm error code {npm_match.group(1)}",
        }

    # --- LaTeX -------------------------------------------------------------
    latex_match = _RE_LATEX_ERROR.search(stderr)
    if latex_match:
        line_match = _RE_LATEX_LINE.search(stderr)
        return {
            "error_type": "latex",
            "file": "",
            "line": int(line_match.group(1)) if line_match else 0,
            "message": latex_match.group(1).strip(),
        }

    # --- pytest ------------------------------------------------------------
    pytest_match = _RE_PYTEST_FAIL.search(stderr)
    if pytest_match:
        node_id = pytest_match.group(1)
        file_part = node_id.split("::")[0]
        return {
            "error_type": "pytest",
            "file": file_part,
            "line": 0,
            "message": pytest_match.group(2).strip(),
        }

    # --- fallback ----------------------------------------------------------
    return {
        "error_type": "unknown",
        "file": "",
        "line": 0,
        "message": stderr.strip(),
    }


# ---------------------------------------------------------------------------
# Fix suggestion
# ---------------------------------------------------------------------------


def suggest_fix(error: dict[str, Any]) -> str:
    """Return a human-readable fix suggestion for *error*.

    The suggestion is a best-effort heuristic based on the ``error_type`` and
    ``message`` fields produced by :func:`parse_error`.
    """

    etype = error.get("error_type", "unknown")
    message = error.get("message", "")

    if etype == "NameError":
        # Likely a missing import or undefined variable.
        match = re.search(r"name '(\w+)'", message)
        name = match.group(1) if match else "the identifier"
        return (
            f"Import or define '{name}' before use. "
            f"Add 'import {name}' at the top of {error.get('file', 'the file')}."
        )

    if etype == "ModuleNotFoundError":
        match = re.search(r"No module named '([\w.]+)'", message)
        mod = match.group(1) if match else "the module"
        return f"Install the missing package: pip install {mod}"

    if etype == "SyntaxError":
        return (
            f"Fix the syntax error at {error.get('file', '?')}:{error.get('line', '?')}: "
            f"{message}"
        )

    if etype == "npm":
        return (
            f"Resolve npm issue ({message}). Try 'npm install' or check package.json."
        )

    if etype == "latex":
        return (
            f"Fix LaTeX error on line {error.get('line', '?')}: {message}. "
            "Check for typos in commands or missing packages."
        )

    if etype == "pytest":
        return f"Fix failing test in {error.get('file', '?')}: {message}"

    # Generic fallback
    return f"Investigate the error and apply a manual fix: {message}"


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------


def run_with_retry(
    command: str,
    retries: int = 3,
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """Run *command* in a shell, retrying up to *retries* times on failure.

    Returns the :class:`subprocess.CompletedProcess` of the last attempt.
    """
    last: subprocess.CompletedProcess | None = None
    for attempt in range(retries):
        last = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            **kwargs,
        )
        if last.returncode == 0:
            return last
        logger.debug(
            "Attempt %d/%d failed (rc=%d)", attempt + 1, retries, last.returncode
        )
    assert last is not None  # retries >= 1
    return last


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def auto_debug_loop(
    command: str,
    max_iterations: int = 5,
    project_path: Path = Path("."),
) -> DebugResult:
    """Run *command*, analyse failures, suggest fixes, and re-run.

    The loop executes the command (inside *project_path*), and if it exits
    with a non-zero code the error output is parsed and a fix is suggested.
    The cycle repeats up to *max_iterations* times or until the command
    succeeds.

    Returns a :class:`DebugResult` summarising the session.
    """

    original_error = ""
    fix_applied = ""

    for iteration in range(1, max_iterations + 1):
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(project_path),
        )

        if proc.returncode == 0:
            return DebugResult(
                original_error=original_error,
                fix_applied=fix_applied,
                success=True,
                iterations=iteration,
                final_output=proc.stdout,
            )

        # First failure — capture the original error text.
        if not original_error:
            original_error = proc.stderr or proc.stdout

        error_info = parse_error(proc.stderr)
        fix_applied = suggest_fix(error_info)
        logger.info(
            "Iteration %d/%d — error: %s | suggested fix: %s",
            iteration,
            max_iterations,
            error_info.get("message", ""),
            fix_applied,
        )

    # Exhausted all iterations without success.
    return DebugResult(
        original_error=original_error,
        fix_applied=fix_applied,
        success=False,
        iterations=max_iterations,
        final_output=proc.stdout,
    )
