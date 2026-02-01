"""Agent orchestration: task routing, budget management, and supervision."""

import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

AGENTS_DIR = Path(".claude/agents")
PROGRESS_FILE = Path("state/PROGRESS.md")


class AgentType(str, Enum):
    MASTER = "master"
    RESEARCHER = "researcher"
    CODER = "coder"
    REVIEWER = "reviewer"
    FALSIFIER = "falsifier"
    WRITER = "writer"
    CLEANER = "cleaner"


# Default budget allocation (percentage of session tokens)
DEFAULT_BUDGET_SPLIT = {
    AgentType.RESEARCHER: 15,
    AgentType.CODER: 35,
    AgentType.REVIEWER: 10,
    AgentType.FALSIFIER: 20,
    AgentType.WRITER: 15,
    AgentType.CLEANER: 5,
}

# Keywords used to route tasks to agents
ROUTING_KEYWORDS = {
    AgentType.RESEARCHER: [
        "literature", "paper", "search", "survey", "review", "cite",
        "arxiv", "pubmed", "reference",
    ],
    AgentType.CODER: [
        "code", "implement", "write", "function", "class", "script",
        "bug", "fix", "feature", "test",
    ],
    AgentType.REVIEWER: [
        "review", "check", "audit", "inspect", "quality", "improve",
    ],
    AgentType.FALSIFIER: [
        "validate", "attack", "falsify", "verify", "test", "leak",
        "statistical", "reproducib",
    ],
    AgentType.WRITER: [
        "write", "draft", "paper", "abstract", "introduction", "methods",
        "results", "discussion", "document",
    ],
    AgentType.CLEANER: [
        "refactor", "clean", "optimize", "document", "style", "lint",
        "format", "organize",
    ],
}


@dataclass
class TaskResult:
    agent: AgentType
    task: str
    status: str  # "success", "failure", "partial"
    output: str = ""
    tokens_used: int = 0
    started: str = field(default_factory=lambda: datetime.now().isoformat())
    ended: Optional[str] = None


def route_task(task_description: str) -> AgentType:
    """Determine which agent should handle a task based on keywords.

    Args:
        task_description: Natural language task description.

    Returns:
        The most appropriate agent type.
    """
    task_lower = task_description.lower()
    scores: dict[AgentType, int] = {}

    for agent, keywords in ROUTING_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in task_lower)
        if score > 0:
            scores[agent] = score

    if not scores:
        return AgentType.CODER  # Default to coder

    return max(scores, key=scores.get)


def get_agent_prompt(agent_type: AgentType) -> str:
    """Load the agent's system prompt from its markdown file.

    Args:
        agent_type: The agent to load.

    Returns:
        The agent's prompt text, or empty string if not found.
    """
    agent_file = AGENTS_DIR / f"{agent_type.value}.md"
    if agent_file.exists():
        return agent_file.read_text()
    logger.warning("Agent file not found: %s", agent_file)
    return ""


def execute_agent_task(
    agent_type: AgentType,
    task: str,
    *,
    dangerously_skip_permissions: bool = False,
) -> TaskResult:
    """Execute a task using the specified agent via Claude CLI.

    Args:
        agent_type: Which agent to use.
        task: The task description/prompt.
        dangerously_skip_permissions: Whether to skip permission checks (overnight mode).

    Returns:
        TaskResult with output and status.
    """
    agent_prompt = get_agent_prompt(agent_type)
    full_prompt = f"{agent_prompt}\n\n## Current Task\n\n{task}"

    cmd = ["claude", "-p", full_prompt]
    if dangerously_skip_permissions:
        cmd.insert(1, "--dangerously-skip-permissions")

    result = TaskResult(agent=agent_type, task=task, status="running")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        result.output = proc.stdout
        result.status = "success" if proc.returncode == 0 else "failure"
    except subprocess.TimeoutExpired:
        result.status = "timeout"
        result.output = "Task timed out after 600 seconds"
    except Exception as e:
        result.status = "failure"
        result.output = str(e)

    result.ended = datetime.now().isoformat()
    _log_result(result)
    return result


def run_pipeline(
    tasks: list[tuple[AgentType, str]],
    *,
    dangerously_skip_permissions: bool = False,
) -> list[TaskResult]:
    """Run a sequence of agent tasks in order.

    Args:
        tasks: List of (agent_type, task_description) tuples.
        dangerously_skip_permissions: Whether to skip permissions.

    Returns:
        List of results in order.
    """
    results = []
    for agent_type, task in tasks:
        logger.info("Running %s: %s", agent_type.value, task[:80])
        result = execute_agent_task(
            agent_type,
            task,
            dangerously_skip_permissions=dangerously_skip_permissions,
        )
        results.append(result)

        if result.status == "failure":
            logger.error("Pipeline stopped: %s failed", agent_type.value)
            break

    return results


def _log_result(result: TaskResult) -> None:
    """Append task result to progress file."""
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)

    status_icon = {"success": "x", "failure": "!", "timeout": "?", "partial": "~"}.get(
        result.status, " "
    )
    timestamp = datetime.now().strftime("%H:%M")
    line = f"- [{status_icon}] [{result.agent.value}] {result.task[:60]} ({timestamp})\n"

    with open(PROGRESS_FILE, "a") as f:
        f.write(line)
