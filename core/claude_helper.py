"""Shared helper for calling the Claude CLI from Python.

Provides ``call_claude`` and ``call_claude_json`` which invoke
``claude -p <prompt>`` and return the result text.
All callers should treat a ``None`` return as "Claude unavailable" and
fall back to their existing heuristic logic.
"""

import json
import logging
import os
import subprocess
import tempfile
from typing import Any

logger = logging.getLogger(__name__)

# Model to use for lightweight CLI calls (literature search, TODO generation, etc.)
CLAUDE_CLI_MODEL = "claude-haiku-4-5-20251001"

# Model aliases for callers that need a specific tier
CLAUDE_MODEL_ALIASES: dict[str, str] = {
    "haiku": CLAUDE_CLI_MODEL,
    "sonnet": "claude-sonnet-4-5-20250929",
    "opus": "claude-opus-4-6",
}


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


# Tools that are ALWAYS allowed in every call_claude invocation.
_BASELINE_TOOLS = ["WebSearch", "WebFetch"]

# Prompts larger than this (bytes) are piped via stdin instead of passed as
# a command-line argument to avoid the OS ``ARG_MAX`` limit (E2BIG).
_MAX_ARG_PROMPT = 100_000  # 100 KB


def call_claude(
    prompt: str,
    *,
    model: str | None = None,
    timeout: int = 30,
    allowed_tools: list[str] | None = None,
    run_cmd=None,
) -> str | None:
    """Call Claude CLI with *prompt* and return the response text.

    WebSearch and WebFetch are always allowed.  Callers can grant
    additional tools via *allowed_tools* (e.g. MCP tools).

    Args:
        prompt: The prompt text.
        model: Optional model alias (``"haiku"``, ``"sonnet"``, ``"opus"``)
               or a full model ID.  Defaults to :data:`CLAUDE_CLI_MODEL`.
        timeout: Subprocess timeout in seconds.
        allowed_tools: Extra tool names to allow beyond WebSearch/WebFetch.
        run_cmd: Optional ``callable(cmd_list) -> CompletedProcess``
                 override for testing.

    Returns:
        Response text on success, ``None`` on any failure.
    """
    resolved_model = (
        CLAUDE_MODEL_ALIASES.get(model, model) if model else CLAUDE_CLI_MODEL
    )

    # Merge baseline tools with caller-supplied extras
    tools = list(_BASELINE_TOOLS)
    if allowed_tools:
        for t in allowed_tools:
            if t not in tools:
                tools.append(t)

    if run_cmd is None:
        if not _claude_cli_available():
            return None

        def run_cmd(cmd: list[str], **kw) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                **kw,
            )

    try:
        prompt_bytes = len(prompt.encode("utf-8"))
        if prompt_bytes > _MAX_ARG_PROMPT:
            # Large prompt: pipe via stdin to avoid OS ARG_MAX / E2BIG.
            # Without -p and with stdin piped, Claude enters pipe mode.
            cmd = [
                "claude",
                "--output-format",
                "text",
                "--model",
                resolved_model,
                "--allowedTools",
                ",".join(tools),
            ]
            result = run_cmd(cmd, input=prompt)
        else:
            cmd = [
                "claude",
                "-p",
                prompt,
                "--output-format",
                "text",
                "--model",
                resolved_model,
                "--allowedTools",
                ",".join(tools),
            ]
            result = run_cmd(cmd)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        # Try extracting from JSON envelope (in case --output-format json was used)
        if result.stdout.strip():
            extracted = _extract_result_text(result.stdout)
            if extracted:
                return extracted
        # Log failure details for debugging
        if result.returncode != 0:
            logger.warning(
                "Claude CLI failed (rc=%d): %s",
                result.returncode,
                result.stderr[:200] if result.stderr else "(no stderr)",
            )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("Claude CLI unavailable: %s", exc)
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
