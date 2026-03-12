"""Bridge to claude-flow v3 CLI (DEPRECATED).

The CLI subprocess bridge is disabled. claude-flow is now used exclusively
via MCP (``claude mcp add claude-flow -- npx -y @claude-flow/cli@latest``).
All callers already handle ClaudeFlowUnavailable gracefully, so disabling
the bridge simply makes every module fall through to its local fallback.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Agent type mapping kept for any code that references it.
AGENT_TYPE_MAP = {
    "master": "hierarchical-coordinator",
    "researcher": "researcher",
    "coder": "coder",
    "reviewer": "code-reviewer",
    "falsifier": "security-auditor",
    "writer": "api-docs",
    "cleaner": "refactorer",
}

AGENT_TYPE_REVERSE = {v: k for k, v in AGENT_TYPE_MAP.items()}


class ClaudeFlowUnavailable(Exception):
    """Raised when claude-flow CLI is not available or fails."""


_bridge_instance: Optional["ClaudeFlowBridge"] = None


def _get_bridge() -> "ClaudeFlowBridge":
    """Always raises ClaudeFlowUnavailable.

    The CLI bridge is disabled -- claude-flow is accessed via MCP instead.
    All callers catch this exception and use local fallbacks.
    """
    raise ClaudeFlowUnavailable(
        "CLI bridge disabled; claude-flow is used via MCP"
    )


class ClaudeFlowBridge:
    """Stub -- kept for import compatibility only."""

    def __init__(self) -> None:
        self._available: Optional[bool] = False
        self._version: Optional[str] = None

    def is_available(self) -> bool:
        return False

    def get_version(self) -> str:
        return "unavailable"
