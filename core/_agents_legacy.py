"""Legacy agent execution functions (pre-claude-flow).

These are used as fallbacks when claude-flow is unavailable.
"""

import logging
import subprocess
from datetime import datetime
from typing import Optional

from core.agents import AgentType, Task, TaskResult, get_agent_prompt, route_task

logger = logging.getLogger(__name__)


def execute_agent_task_legacy(
    agent_type: AgentType,
    task: str,
    *,
    dangerously_skip_permissions: bool = False,
) -> TaskResult:
    """Execute a task using the specified agent via Claude CLI (original implementation).

    Args:
        agent_type: Which agent to use.
        task: The task description/prompt.
        dangerously_skip_permissions: Whether to skip permission checks.

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
    return result


def execute_parallel_tasks_legacy(
    tasks: list[Task],
    *,
    max_workers: int = 3,
    dangerously_skip_permissions: bool = False,
    executor_fn=None,
) -> dict[str, TaskResult]:
    """Execute tasks respecting dependencies (original implementation).

    This is the pre-claude-flow parallel execution using ThreadPoolExecutor.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from core.agents import _active_agents, _get_ready_tasks

    task_map = {t.id: t for t in tasks}
    completed: set[str] = set()
    results: dict[str, TaskResult] = {}

    if executor_fn is None:

        def executor_fn(t: Task) -> TaskResult:
            agent = t.agent or route_task(t.description)
            return execute_agent_task_legacy(
                agent,
                t.description,
                dangerously_skip_permissions=dangerously_skip_permissions,
            )

    while len(completed) < len(tasks):
        ready = _get_ready_tasks(task_map, completed)
        if not ready:
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


def route_task_legacy(task_description: str) -> AgentType:
    """Original keyword-based task routing (fallback)."""
    return route_task(task_description)
