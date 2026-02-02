"""Shared helper for calling the Claude CLI from Python.

Provides ``call_claude`` and ``call_claude_json`` which invoke
``claude -p <prompt> --output-format json`` and parse the result.
All callers should treat a ``None`` return as "Claude unavailable" and
fall back to their existing keyword-based logic.
"""

import json
import logging
import os
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


def _claude_cli_available() -> bool:
    """Check if Claude CLI calls are enabled.

    Returns False when RICET_NO_CLAUDE is set (e.g. in tests) or when
    running inside pytest to avoid blocking test suites.
    """
    if os.environ.get("RICET_NO_CLAUDE", "").lower() in ("true", "1", "yes"):
        return False
    # Auto-detect pytest
    if "PYTEST_CURRENT_TEST" in os.environ:
        return False
    return True


def call_claude(
    prompt: str,
    *,
    timeout: int = 30,
    run_cmd=None,
) -> str | None:
    """Call Claude CLI with *prompt* and return the raw stdout.

    Args:
        prompt: The prompt text.
        timeout: Subprocess timeout in seconds.
        run_cmd: Optional ``callable(cmd_list) -> CompletedProcess``
                 override for testing.

    Returns:
        Stripped stdout on success, ``None`` on any failure.
    """
    if run_cmd is None:
        if not _claude_cli_available():
            return None

        def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

    try:
        result = run_cmd(["claude", "-p", prompt, "--output-format", "json"])
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("Claude CLI unavailable: %s", exc)
    return None


def call_claude_json(
    prompt: str,
    **kwargs: Any,
) -> dict | list | None:
    """Call Claude CLI and parse the response as JSON.

    Handles markdown code fences (```json ... ```) that Claude sometimes
    wraps around its output.

    Args:
        prompt: The prompt text.
        **kwargs: Forwarded to :func:`call_claude`.

    Returns:
        Parsed JSON (dict or list) on success, ``None`` on failure.
    """
    raw = call_claude(prompt, **kwargs)
    if raw is None:
        return None

    # Strip markdown code fences if present
    text = raw
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            cleaned = part.strip().removeprefix("json").strip()
            if cleaned.startswith("{") or cleaned.startswith("["):
                text = cleaned
                break

    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.debug("Could not parse Claude JSON response: %s", exc)
        return None
