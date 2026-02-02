"""Shared helper for calling the Claude CLI from Python.

Provides ``call_claude`` and ``call_claude_json`` which invoke
``claude -p <prompt>`` and return the result text.
All callers should treat a ``None`` return as "Claude unavailable" and
fall back to their existing keyword-based logic.
"""

import json
import logging
import os
import subprocess
from typing import Any

logger = logging.getLogger(__name__)

# Model to use for lightweight CLI calls (literature search, TODO generation, etc.)
CLAUDE_CLI_MODEL = "claude-3-5-haiku-20241022"


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


def _extract_result_text(stdout: str) -> str | None:
    """Extract the actual response from Claude CLI JSON envelope.

    When ``--output-format json`` is used, stdout is a JSON object with
    a ``result`` key containing the actual response text.  When
    ``--output-format text`` is used, stdout is the plain response.
    This helper handles both cases.
    """
    text = stdout.strip()
    if not text:
        return None
    # Try to parse as JSON envelope
    if text.startswith("{"):
        try:
            envelope = json.loads(text)
            if isinstance(envelope, dict):
                if envelope.get("is_error"):
                    logger.debug(
                        "Claude CLI returned error: %s", envelope.get("result", "")
                    )
                    return None
                inner = envelope.get("result", "")
                if inner:
                    return inner.strip()
                return None
        except (json.JSONDecodeError, ValueError):
            pass
    # Not a JSON envelope — return as-is
    return text if text else None


def call_claude(
    prompt: str,
    *,
    timeout: int = 30,
    run_cmd=None,
) -> str | None:
    """Call Claude CLI with *prompt* and return the response text.

    Args:
        prompt: The prompt text.
        timeout: Subprocess timeout in seconds.
        run_cmd: Optional ``callable(cmd_list) -> CompletedProcess``
                 override for testing.

    Returns:
        Response text on success, ``None`` on any failure.
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
        result = run_cmd(
            [
                "claude",
                "-p",
                prompt,
                "--output-format",
                "text",
                "--model",
                CLAUDE_CLI_MODEL,
            ]
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        # Try extracting from JSON envelope (in case --output-format json was used)
        if result.stdout.strip():
            extracted = _extract_result_text(result.stdout)
            if extracted:
                return extracted
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("Claude CLI unavailable: %s", exc)
    return None


def call_gemini(prompt: str, *, run_cmd=None) -> str | None:
    """Call Google Gemini as fallback for web-access tasks.

    Uses the GOOGLE_API_KEY from environment. Returns None if unavailable.
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        return None

    try:
        payload = json.dumps(
            {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 2048},
            }
        )

        result = subprocess.run(
            [
                "curl",
                "-s",
                "-X",
                "POST",
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
                "-H",
                "Content-Type: application/json",
                "-d",
                payload,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
    except Exception:
        logger.debug("Gemini API call failed", exc_info=True)
    return None


def call_with_web_fallback(prompt: str, *, run_cmd=None) -> str | None:
    """Try Claude first, fall back to Gemini for web-access tasks."""
    result = call_claude(prompt, run_cmd=run_cmd)
    if result:
        return result
    # Try Gemini as fallback (has native web access)
    return call_gemini(prompt, run_cmd=run_cmd)


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
