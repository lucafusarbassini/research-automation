"""Agent orchestration: task routing, budget management, DAG execution, and supervision.

When claude-flow is available, agent execution and swarm orchestration delegate to
the bridge. Otherwise, falls back to direct Claude CLI subprocess calls.
"""

import json
import logging
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from core.claude_flow import AGENT_TYPE_MAP, ClaudeFlowUnavailable, _get_bridge

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
        "literature",
        "paper",
        "search",
        "survey",
        "review",
        "cite",
        "arxiv",
        "pubmed",
        "reference",
    ],
    AgentType.CODER: [
        "code",
        "implement",
        "write",
        "function",
        "class",
        "script",
        "bug",
        "fix",
        "feature",
        "test",
    ],
    AgentType.REVIEWER: [
        "review",
        "check",
        "audit",
        "inspect",
        "quality",
        "improve",
    ],
    AgentType.FALSIFIER: [
        "validate",
        "attack",
        "falsify",
        "verify",
        "test",
        "leak",
        "statistical",
        "reproducib",
    ],
    AgentType.WRITER: [
        "write",
        "draft",
        "paper",
        "abstract",
        "introduction",
        "methods",
        "results",
        "discussion",
        "document",
    ],
    AgentType.CLEANER: [
        "refactor",
        "clean",
        "optimize",
        "document",
        "style",
        "lint",
        "format",
        "organize",
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


@dataclass
class Task:
    id: str
    description: str
    agent: Optional[AgentType] = None
    deps: list[str] = field(default_factory=list)
    parallel: bool = True
    status: str = "pending"  # pending, running, success, failure
    result: Optional[TaskResult] = None


# Active agents tracker
_active_agents: dict[str, dict] = {}


def _route_task_claude(task_description: str) -> AgentType | None:
    """Try routing via Claude CLI."""
    from core.claude_helper import call_claude

    prompt = (
        "Which agent type best handles this task? "
        "Reply with exactly one word from: researcher, coder, reviewer, "
        "falsifier, writer, cleaner.\n\n"
        f"Task: {task_description[:500]}"
    )
    result = call_claude(prompt, timeout=10)
    if result:
        word = result.strip().lower().split()[0] if result.strip() else ""
        try:
            return AgentType(word)
        except ValueError:
            pass
    return None


def route_task(task_description: str) -> AgentType:
    """Determine which agent should handle a task.

    Tries claude-flow model routing first, then Claude CLI, falls back to keyword matching.

    Args:
        task_description: Natural language task description.

    Returns:
        The most appropriate agent type.
    """
    try:
        bridge = _get_bridge()
        result = bridge.route_model(task_description)
        # claude-flow returns an agent type suggestion we can map back
        cf_agent = result.get("agent_type", "")
        from core.claude_flow import AGENT_TYPE_REVERSE

        if cf_agent in AGENT_TYPE_REVERSE:
            return AgentType(AGENT_TYPE_REVERSE[cf_agent])
    except (ClaudeFlowUnavailable, KeyError, ValueError):
        pass

    # Try Claude CLI
    claude_result = _route_task_claude(task_description)
    if claude_result is not None:
        return claude_result

    return _route_task_keywords(task_description)


def _route_task_keywords(task_description: str) -> AgentType:
    """Keyword-based task routing (legacy fallback)."""
    task_lower = task_description.lower()
    scores: dict[AgentType, int] = {}

    for agent, keywords in ROUTING_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in task_lower)
        if score > 0:
            scores[agent] = score

    if not scores:
        return AgentType.CODER  # Default to coder

    return max(scores, key=scores.get)


def get_agent_prompt(agent_type: AgentType, *, project_root: Path | None = None) -> str:
    """Load the agent's system prompt from its markdown file.

    Looks for the prompt in the project's ``.claude/agents/`` directory first,
    then falls back to the bundled templates directory so agents always get
    their prompts even if deployment was incomplete.

    Args:
        agent_type: The agent to load.
        project_root: Project root directory.  Defaults to ``Path.cwd()``.

    Returns:
        The agent's prompt text, or empty string if not found.
    """
    if project_root is None:
        project_root = Path.cwd()
    agent_file = project_root / ".claude" / "agents" / f"{agent_type.value}.md"
    if agent_file.exists():
        return agent_file.read_text()
    # Fallback: try the bundled templates directory
    template_file = (
        Path(__file__).resolve().parent.parent
        / "templates"
        / ".claude"
        / "agents"
        / f"{agent_type.value}.md"
    )
    if template_file.exists():
        logger.info("Using template agent prompt for %s", agent_type.value)
        return template_file.read_text()
    logger.warning("Agent file not found: %s", agent_file)
    return ""


def execute_agent_task(
    agent_type: AgentType,
    task: str,
    *,
    dangerously_skip_permissions: bool = False,
) -> TaskResult:
    """Execute a task using the specified agent.

    Tries claude-flow agent spawning first, falls back to direct Claude CLI.

    Args:
        agent_type: Which agent to use.
        task: The task description/prompt.
        dangerously_skip_permissions: Whether to skip permission checks (overnight mode).

    Returns:
        TaskResult with output and status.
    """
    try:
        bridge = _get_bridge()
        cf_result = bridge.spawn_agent(agent_type.value, task)
        result = TaskResult(
            agent=agent_type,
            task=task,
            status=cf_result.get("status", "success"),
            output=cf_result.get("output", ""),
            tokens_used=cf_result.get("tokens_used", 0),
            ended=datetime.now().isoformat(),
        )
        # Auto-verify successful agent output
        from core.verification import auto_verify_response
        if result.status == "success" and result.output:
            result.output = auto_verify_response(result.output, {})
        _log_result(result)
        return result
    except ClaudeFlowUnavailable:
        pass

    result = _execute_agent_task_legacy(
        agent_type, task, dangerously_skip_permissions=dangerously_skip_permissions
    )
    # Auto-verify successful agent output (legacy path)
    from core.verification import auto_verify_response
    if result.status == "success" and result.output:
        result.output = auto_verify_response(result.output, {})
    return result


def _execute_agent_task_legacy(
    agent_type: AgentType,
    task: str,
    *,
    dangerously_skip_permissions: bool = False,
) -> TaskResult:
    """Execute a task via direct Claude CLI (legacy fallback)."""
    from core.model_router import route_to_model
    from core.tokens import select_thinking_mode

    agent_prompt = get_agent_prompt(agent_type)
    full_prompt = f"{agent_prompt}\n\n## Current Task\n\n{task}"

    # Route to appropriate model and thinking mode based on task complexity
    model_config = route_to_model(task)
    thinking_mode = select_thinking_mode(task)

    cmd = ["claude", "-p", full_prompt, "--model", model_config.name]

    # Add thinking budget for models that support it
    if model_config.supports_thinking and thinking_mode in ("extended", "ultrathink"):
        budget = "128000" if thinking_mode == "ultrathink" else "32000"
        cmd.extend(["--thinking-budget", budget])
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


def build_task_dag(tasks: list[Task]) -> dict[str, list[str]]:
    """Build a dependency graph from a list of tasks.

    Args:
        tasks: List of Task objects with deps.

    Returns:
        Dict mapping task_id -> list of task_ids that depend on it.
    """
    dependents: dict[str, list[str]] = defaultdict(list)
    for task in tasks:
        for dep in task.deps:
            dependents[dep].append(task.id)
    return dict(dependents)


def _get_ready_tasks(tasks: dict[str, Task], completed: set[str]) -> list[Task]:
    """Find tasks whose dependencies are all completed."""
    ready = []
    for task in tasks.values():
        if task.status == "pending" and all(d in completed for d in task.deps):
            ready.append(task)
    return ready


def execute_parallel_tasks(
    tasks: list[Task],
    *,
    max_workers: int = 3,
    dangerously_skip_permissions: bool = False,
    executor_fn=None,
) -> dict[str, TaskResult]:
    """Execute tasks respecting dependencies, parallelizing where possible.

    Tries claude-flow swarm orchestration when no custom executor_fn is provided.
    Falls back to ThreadPoolExecutor-based execution.

    Args:
        tasks: List of Task objects.
        max_workers: Maximum parallel executions.
        dangerously_skip_permissions: Skip permission checks.
        executor_fn: Optional callable(task) -> TaskResult for testing.

    Returns:
        Dict mapping task_id -> TaskResult.
    """
    # Try claude-flow swarm when no custom executor
    if executor_fn is None:
        try:
            bridge = _get_bridge()
            swarm_tasks = [
                {
                    "type": (t.agent or _route_task_keywords(t.description)).value,
                    "task": t.description,
                }
                for t in tasks
            ]
            cf_result = bridge.run_swarm(swarm_tasks, topology="hierarchical")
            results: dict[str, TaskResult] = {}
            cf_results_list = cf_result.get("results", [])
            for i, task in enumerate(tasks):
                if i < len(cf_results_list):
                    tr = cf_results_list[i]
                    results[task.id] = TaskResult(
                        agent=task.agent or _route_task_keywords(task.description),
                        task=task.description,
                        status=tr.get("status", "success"),
                        output=tr.get("output", ""),
                        tokens_used=tr.get("tokens_used", 0),
                        ended=datetime.now().isoformat(),
                    )
                    task.status = results[task.id].status
                    task.result = results[task.id]
                else:
                    results[task.id] = TaskResult(
                        agent=task.agent or AgentType.CODER,
                        task=task.description,
                        status="success",
                        output=cf_result.get("output", ""),
                        ended=datetime.now().isoformat(),
                    )
                    task.status = "success"
                    task.result = results[task.id]
            return results
        except ClaudeFlowUnavailable:
            pass

    return _execute_parallel_tasks_legacy(
        tasks,
        max_workers=max_workers,
        dangerously_skip_permissions=dangerously_skip_permissions,
        executor_fn=executor_fn,
    )


def _execute_parallel_tasks_legacy(
    tasks: list[Task],
    *,
    max_workers: int = 3,
    dangerously_skip_permissions: bool = False,
    executor_fn=None,
) -> dict[str, TaskResult]:
    """Legacy parallel execution using ThreadPoolExecutor."""
    task_map = {t.id: t for t in tasks}
    completed: set[str] = set()
    results: dict[str, TaskResult] = {}

    if executor_fn is None:

        def executor_fn(t: Task) -> TaskResult:
            agent = t.agent or route_task(t.description)
            return execute_agent_task(
                agent,
                t.description,
                dangerously_skip_permissions=dangerously_skip_permissions,
            )

    while len(completed) < len(tasks):
        ready = _get_ready_tasks(task_map, completed)
        if not ready:
            # Check for deadlock
            pending = [t for t in task_map.values() if t.status == "pending"]
            if pending:
                logger.error("Deadlock detected: %d tasks blocked", len(pending))
                for t in pending:
                    t.status = "failure"
                    results[t.id] = TaskResult(
                        agent=t.agent or AgentType.CODER,
                        task=t.description,
                        status="failure",
                        output="Deadlocked: unresolvable dependencies",
                    )
                    completed.add(t.id)
            break

        with ThreadPoolExecutor(max_workers=min(max_workers, len(ready))) as pool:
            future_to_task = {}
            for task in ready:
                task.status = "running"
                _active_agents[task.id] = {
                    "task_id": task.id,
                    "agent": (task.agent or route_task(task.description)).value,
                    "description": task.description[:80],
                    "started": datetime.now().isoformat(),
                }
                future_to_task[pool.submit(executor_fn, task)] = task

            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                except Exception as e:
                    result = TaskResult(
                        agent=task.agent or AgentType.CODER,
                        task=task.description,
                        status="failure",
                        output=str(e),
                    )
                task.status = result.status
                task.result = result
                results[task.id] = result
                completed.add(task.id)
                _active_agents.pop(task.id, None)

    return results


def plan_execute_iterate(
    goal: str,
    *,
    plan_fn=None,
    max_iterations: int = 5,
    dangerously_skip_permissions: bool = False,
) -> list[TaskResult]:
    """Plan-execute-iterate loop: plan tasks, execute, check results, re-plan if needed.

    Args:
        goal: High-level goal description.
        plan_fn: Callable(goal, iteration, previous_results) -> list[Task].
                 If None, creates a single task for the goal.
        max_iterations: Max planning iterations.
        dangerously_skip_permissions: Skip permissions.

    Returns:
        All accumulated TaskResults.
    """
    all_results: list[TaskResult] = []

    if plan_fn is None:
        # Default: single task
        def plan_fn(g, iteration, prev):
            if iteration == 0:
                agent = route_task(g)
                return [Task(id=f"task-{iteration}-0", description=g, agent=agent)]
            return []

    for iteration in range(max_iterations):
        tasks = plan_fn(goal, iteration, all_results)
        if not tasks:
            logger.info("No more tasks to execute at iteration %d", iteration)
            break

        results = execute_parallel_tasks(
            tasks,
            dangerously_skip_permissions=dangerously_skip_permissions,
        )
        all_results.extend(results.values())

        # Check if all succeeded
        if all(r.status == "success" for r in results.values()):
            logger.info("All tasks succeeded at iteration %d", iteration)
            break
        else:
            failed = [tid for tid, r in results.items() if r.status != "success"]
            logger.warning("Failed tasks at iteration %d: %s", iteration, failed)

    return all_results


def get_active_agents_status() -> list[dict]:
    """Get status of currently running agents.

    Returns:
        List of dicts with task_id, agent, description, started.
    """
    return list(_active_agents.values())


def _log_result(result: TaskResult) -> None:
    """Append task result to progress file."""
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)

    status_icon = {"success": "x", "failure": "!", "timeout": "?", "partial": "~"}.get(
        result.status, " "
    )
    timestamp = datetime.now().strftime("%H:%M")
    line = (
        f"- [{status_icon}] [{result.agent.value}] {result.task[:60]} ({timestamp})\n"
    )

    with open(PROGRESS_FILE, "a") as f:
        f.write(line)

    # Scan task description for operational rules and append to cheatsheet
    from core.meta_rules import detect_operational_rule, classify_rule_type, append_to_cheatsheet
    if detect_operational_rule(result.task):
        rule_type = classify_rule_type(result.task)
        append_to_cheatsheet(result.task, rule_type=rule_type)
