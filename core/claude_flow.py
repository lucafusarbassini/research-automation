"""Bridge to claude-flow v3 CLI for swarm orchestration, vector memory, and model routing.

All methods gracefully degrade when claude-flow is not installed.
"""

import json
import logging
import shutil
import subprocess
from typing import Any, Optional

logger = logging.getLogger(__name__)

CLAUDE_FLOW_CMD = "npx"
CLAUDE_FLOW_PKG = "claude-flow@v3alpha"

# Agent type mapping: our types -> claude-flow types
AGENT_TYPE_MAP = {
    "master": "hierarchical-coordinator",
    "researcher": "researcher",
    "coder": "coder",
    "reviewer": "code-reviewer",
    "falsifier": "security-auditor",
    "writer": "api-docs",
    "cleaner": "refactorer",
}

# Reverse mapping
AGENT_TYPE_REVERSE = {v: k for k, v in AGENT_TYPE_MAP.items()}


class ClaudeFlowUnavailable(Exception):
    """Raised when claude-flow CLI is not available or fails."""


_bridge_instance: Optional["ClaudeFlowBridge"] = None


def _get_bridge() -> "ClaudeFlowBridge":
    """Get or create the singleton bridge instance.

    Returns:
        ClaudeFlowBridge instance.

    Raises:
        ClaudeFlowUnavailable: If claude-flow is not installed.
    """
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = ClaudeFlowBridge()
    if not _bridge_instance.is_available():
        raise ClaudeFlowUnavailable("claude-flow is not installed or not reachable")
    return _bridge_instance


class ClaudeFlowBridge:
    """Wrapper around the claude-flow CLI."""

    def __init__(self) -> None:
        self._available: Optional[bool] = None
        self._version: Optional[str] = None

    def _run(self, *args: str, timeout: int = 120) -> dict[str, Any]:
        """Run a claude-flow CLI command and parse JSON output.

        Args:
            *args: Arguments to pass after ``npx claude-flow@v3alpha``.
            timeout: Timeout in seconds.

        Returns:
            Parsed JSON response dict.

        Raises:
            ClaudeFlowUnavailable: On any subprocess failure.
        """
        cmd = [CLAUDE_FLOW_CMD, CLAUDE_FLOW_PKG, *args, "--json"]
        logger.debug("claude-flow cmd: %s", " ".join(cmd))

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            raise ClaudeFlowUnavailable("npx not found; is Node.js installed?")
        except subprocess.TimeoutExpired:
            raise ClaudeFlowUnavailable(f"claude-flow timed out after {timeout}s")

        if proc.returncode != 0:
            raise ClaudeFlowUnavailable(
                f"claude-flow exited {proc.returncode}: {proc.stderr.strip()}"
            )

        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            # Some commands return plain text; wrap it
            return {"output": proc.stdout.strip(), "ok": True}

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check if claude-flow CLI is reachable."""
        if self._available is not None:
            return self._available
        try:
            result = self._run("--version")
            self._version = result.get("version", result.get("output", "unknown"))
            self._available = True
        except ClaudeFlowUnavailable:
            self._available = False
        return self._available

    def get_version(self) -> str:
        """Return cached version string, or 'unavailable'."""
        if self._version is None:
            self.is_available()
        return self._version or "unavailable"

    # ------------------------------------------------------------------
    # Agent orchestration
    # ------------------------------------------------------------------

    def spawn_agent(
        self,
        agent_type: str,
        task: str,
        *,
        timeout: int = 600,
    ) -> dict[str, Any]:
        """Spawn a single claude-flow agent to perform a task.

        Args:
            agent_type: Our agent type name (e.g. 'coder').
            task: Task description / prompt.
            timeout: Max seconds.

        Returns:
            Dict with 'output', 'status', 'tokens_used', etc.
        """
        cf_type = AGENT_TYPE_MAP.get(agent_type, agent_type)
        return self._run(
            "agent", "spawn", "--type", cf_type, "--task", task, timeout=timeout
        )

    def run_swarm(
        self,
        tasks: list[dict[str, str]],
        *,
        topology: str = "hierarchical",
        timeout: int = 1800,
    ) -> dict[str, Any]:
        """Run multiple tasks as a claude-flow swarm.

        Args:
            tasks: List of dicts with 'type' and 'task' keys.
            topology: Swarm topology ('hierarchical', 'mesh', 'pipeline').
            timeout: Max seconds.

        Returns:
            Dict with per-task results.
        """
        tasks_json = json.dumps(
            [
                {
                    "type": AGENT_TYPE_MAP.get(
                        t.get("type", "coder"), t.get("type", "coder")
                    ),
                    "task": t["task"],
                }
                for t in tasks
            ]
        )
        return self._run(
            "swarm",
            "run",
            "--topology",
            topology,
            "--tasks",
            tasks_json,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Model routing
    # ------------------------------------------------------------------

    def route_model(self, description: str) -> dict[str, Any]:
        """Ask claude-flow to classify and route a task to the best model tier.

        Returns:
            Dict with 'tier', 'model', 'complexity', etc.
        """
        return self._run("router", "classify", "--description", description)

    # ------------------------------------------------------------------
    # Vector memory (HNSW)
    # ------------------------------------------------------------------

    def query_memory(self, query: str, *, top_k: int = 5) -> dict[str, Any]:
        """Semantic search over the vector memory index.

        Returns:
            Dict with 'results' list of matching entries.
        """
        return self._run("memory", "query", "--query", query, "--top-k", str(top_k))

    def store_memory(
        self,
        text: str,
        *,
        namespace: str = "knowledge",
        metadata: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Store an entry in the HNSW vector memory.

        Returns:
            Dict with 'id' of the stored entry.
        """
        args = ["memory", "store", "--text", text, "--namespace", namespace]
        if metadata:
            args.extend(["--metadata", json.dumps(metadata)])
        return self._run(*args)

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------

    def scan_security(self, path: str = ".") -> dict[str, Any]:
        """Run claude-flow security scan on the given path.

        Returns:
            Dict with 'findings' list.
        """
        return self._run("security", "scan", "--path", path)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> dict[str, Any]:
        """Retrieve system status and performance info.

        Returns:
            Dict with metric fields.
        """
        try:
            return self._run("status")
        except ClaudeFlowUnavailable:
            return {"agents": {}, "status": "unknown"}

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def start_session(self, name: str) -> dict[str, Any]:
        """Save a session checkpoint in claude-flow.

        Returns:
            Dict with session info.
        """
        try:
            return self._run("session", "save", "--name", name)
        except ClaudeFlowUnavailable:
            return {"session_id": name, "status": "local-only"}

    def end_session(self, name: str) -> dict[str, Any]:
        """Save final session state.

        Returns:
            Dict with summary stats.
        """
        try:
            return self._run("session", "save", "--name", f"{name}-end")
        except ClaudeFlowUnavailable:
            return {"session_id": name, "status": "ended"}

    # ------------------------------------------------------------------
    # Cross-repo
    # ------------------------------------------------------------------

    def multi_repo_sync(
        self,
        message: str,
        repos: list[str],
    ) -> dict[str, Any]:
        """Coordinated commit across multiple repos via claude-flow.

        Returns:
            Dict mapping repo name -> success.
        """
        return self._run(
            "repo",
            "sync",
            "--message",
            message,
            "--repos",
            json.dumps(repos),
        )
