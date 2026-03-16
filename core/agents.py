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

PROGRESS_FILE = Path("state/PROGRESS.md")


class AgentType(str, Enum):
    """Agent types used for task routing and claude-flow bridge dispatch.

    Note: research workflows are now handled by skills (.claude/skills/*.md),
    not agent prompt files. These enum values are still used by the routing
    functions and falsification checkpoints for claude-flow bridge dispatch.
    """

    MASTER = "master"
    RESEARCHER = "researcher"
    CODER = "coder"
    REVIEWER = "reviewer"
    FALSIFIER = "falsifier"
    WRITER = "writer"
    CLEANER = "cleaner"
    SLIDE_MAKER = "slide-maker"


# Default budget allocation (percentage of session tokens)
DEFAULT_BUDGET_SPLIT = {
    AgentType.MASTER: 15,
    AgentType.RESEARCHER: 10,
    AgentType.CODER: 25,
    AgentType.REVIEWER: 5,
    AgentType.FALSIFIER: 15,
    AgentType.WRITER: 10,
    AgentType.CLEANER: 5,
    AgentType.SLIDE_MAKER: 15,
}

# Keywords used as last-resort fallback routing
ROUTING_KEYWORDS = {
    AgentType.MASTER: ["orchestrate", "coordinate", "overnight", "autonomous"],
    AgentType.RESEARCHER: ["search", "literature", "citation", "survey", "pubmed", "arxiv"],
    AgentType.CODER: ["implement", "code", "script", "function", "bug", "fix", "test", "run"],
    AgentType.REVIEWER: ["review", "audit", "check", "inspect", "quality", "experiment"],
    AgentType.FALSIFIER: ["falsify", "leakage", "validate", "adversarial", "reproduce", "break"],
    AgentType.WRITER: ["write", "draft", "section", "abstract", "manuscript", "paper"],
    AgentType.CLEANER: ["refactor", "clean", "organize", "optimize", "retro", "retrospective"],
    AgentType.SLIDE_MAKER: ["slide", "presentation", "deck", "pptx", "powerpoint", "talk"],
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

# Agent output ring buffers for live monitoring
from collections import deque

_agent_output_buffers: dict[str, deque] = {}
_AGENT_OUTPUT_MAX = 500

# Shared output file for cross-process visibility (mobile server reads this)
_SHARED_OUTPUT_FILE = Path("/tmp/ricet-agent-output.jsonl")


def append_agent_output(agent_type: str, line: str) -> None:
    """Append a line of output to an agent's ring buffer (memory + file)."""
    line = line.rstrip()
    # In-memory (same-process access)
    if agent_type not in _agent_output_buffers:
        _agent_output_buffers[agent_type] = deque(maxlen=_AGENT_OUTPUT_MAX)
    _agent_output_buffers[agent_type].append(line)
    # File-backed (cross-process access for mobile server)
    try:
        # Rotate if >1 MB — keep last half
        if _SHARED_OUTPUT_FILE.exists() and _SHARED_OUTPUT_FILE.stat().st_size > 1_000_000:
            keep = _SHARED_OUTPUT_FILE.read_text().splitlines()[-500:]
            _SHARED_OUTPUT_FILE.write_text("\n".join(keep) + "\n")
        with open(_SHARED_OUTPUT_FILE, "a") as f:
            f.write(json.dumps({"a": agent_type, "l": line}) + "\n")
    except Exception:
        pass


def get_all_agent_outputs(last_n: int = 30) -> dict[str, list[str]]:
    """Return the last *last_n* output lines per agent type.

    Checks (in order): in-memory buffer → shared output file → project state files.
    This allows the mobile server (separate process) to see agent output.
    """
    result: dict[str, list[str]] = {}

    # 1. In-memory buffer (same process — works for overnight/programmatic agents)
    for agent, buf in _agent_output_buffers.items():
        result[agent] = list(buf)[-last_n:]

    # 2. Shared file (cross-process — another process called append_agent_output)
    if not result:
        result = _read_shared_output_file(last_n)

    # 3. Project state scanning (interactive session — no programmatic agent running)
    if not result:
        result = _scan_project_activity(last_n)

    return result


def _read_shared_output_file(last_n: int = 30) -> dict[str, list[str]]:
    """Read agent output from the shared JSONL file."""
    result: dict[str, list[str]] = {}
    try:
        if not _SHARED_OUTPUT_FILE.exists():
            return result
        # Read last chunk (avoid reading huge files)
        text = _SHARED_OUTPUT_FILE.read_text()
        lines = text.strip().splitlines()
        for raw in lines[-(last_n * 10):]:
            try:
                entry = json.loads(raw)
                agent = entry.get("a", "agent")
                line = entry.get("l", "")
                if agent not in result:
                    result[agent] = []
                result[agent].append(line)
            except (json.JSONDecodeError, KeyError):
                continue
        # Trim to last_n per agent
        for agent in result:
            result[agent] = result[agent][-last_n:]
    except Exception:
        pass
    return result


def _scan_project_activity(last_n: int = 30) -> dict[str, list[str]]:
    """Scan project state files for recent activity (interactive session fallback).

    Reads PROGRESS.md, TODO.md, and lists recently modified files to give the
    mobile dashboard something to show during interactive Claude sessions.
    """
    import time

    result: dict[str, list[str]] = {}
    cwd = Path.cwd()

    # PROGRESS.md — the agent updates this with major decisions/results
    progress = cwd / "state" / "PROGRESS.md"
    try:
        if progress.exists():
            lines = [
                l.strip()
                for l in progress.read_text().splitlines()
                if l.strip() and not l.startswith("#")
            ]
            if lines:
                result["progress"] = lines[-last_n:]
    except Exception:
        pass

    # TODO.md — current task list
    todo = cwd / "state" / "TODO.md"
    try:
        if todo.exists():
            lines = [
                l.strip()
                for l in todo.read_text().splitlines()
                if l.strip()
            ]
            if lines:
                result["tasks"] = lines[-last_n:]
    except Exception:
        pass

    # Recently modified files (lightweight: only check state/ and src/)
    try:
        recent_threshold = time.time() - 300  # last 5 minutes
        activity: list[str] = []
        scan_dirs = [cwd / "state", cwd / "src", cwd / "notebooks", cwd / "slides"]
        for scan_dir in scan_dirs:
            if not scan_dir.is_dir():
                continue
            for f in scan_dir.rglob("*"):
                if not f.is_file():
                    continue
                try:
                    mtime = f.stat().st_mtime
                except OSError:
                    continue
                if mtime > recent_threshold:
                    rel = f.relative_to(cwd)
                    if any(skip in str(rel) for skip in ["__pycache__", ".pyc"]):
                        continue
                    ts = time.strftime("%H:%M:%S", time.localtime(mtime))
                    activity.append(f"[{ts}] {rel}")
                if len(activity) >= last_n:
                    break
        if activity:
            activity.sort(reverse=True)
            result["recent-files"] = activity[:last_n]
    except Exception:
        pass

    return result


def _route_task_opus(task_description: str) -> AgentType | None:
    """Intelligent Opus-powered task routing (primary method).

    Uses Claude Opus to semantically analyze the task description and determine
    the best agent.  This goes beyond keyword matching -- Opus understands task
    *intent*, handles ambiguous or multi-domain requests, and considers the full
    context of the description.

    Returns:
        The best-fit AgentType, or ``None`` if Opus is unavailable.
    """
    from core.claude_helper import call_claude

    prompt = (
        "You are the routing brain for a multi-agent research automation system. "
        "Analyze the following task description semantically -- consider intent, "
        "domain, and required expertise, NOT just surface keywords.\n\n"
        "Agent types and their responsibilities:\n"
        "- researcher: Literature search, paper synthesis, citation management, "
        "survey creation, finding related work\n"
        "- coder: Code writing, implementation, bug fixes, feature development, "
        "scripting, test writing\n"
        "- reviewer: Code quality audits, improvement suggestions, best practices "
        "checks, architecture review\n"
        "- falsifier: Adversarial validation, data leakage detection, statistical "
        "audits, reproducibility checks, trying to break results\n"
        "- writer: Paper sections, documentation, reports, abstracts, manuscripts\n"
        "- cleaner: Refactoring, optimization, dead code removal, style fixes, "
        "formatting, code organization\n\n"
        "Reply with EXACTLY one word -- the agent type that best handles this task.\n\n"
        f"Task: {task_description[:500]}"
    )
    result = call_claude(prompt, model="opus", timeout=15)
    if result:
        word = result.strip().lower().split()[0] if result.strip() else ""
        try:
            return AgentType(word)
        except ValueError:
            pass
    return None


def _route_task_claude(task_description: str) -> AgentType | None:
    """Try routing via Claude CLI (secondary, non-Opus fallback)."""
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

    Uses a three-tier routing strategy:

    1. **Opus-powered intelligent routing** (primary) -- Claude Opus semantically
       analyzes the task description to understand intent, domain, and required
       expertise.  This is the preferred method and handles ambiguous or
       multi-domain requests accurately.
    2. **claude-flow bridge routing** (secondary) -- When claude-flow is installed,
       its built-in model routing provides an alternative intelligent path.
    3. **Keyword matching** (last-resort fallback) -- A simple keyword scorer used
       only when both Claude Opus and claude-flow are unavailable (e.g. offline
       environments or CI).

    Args:
        task_description: Natural language task description.

    Returns:
        The most appropriate agent type.
    """
    # 1. Primary: Opus-powered semantic routing
    opus_result = _route_task_opus(task_description)
    if opus_result is not None:
        return opus_result

    # 2. Secondary: claude-flow bridge routing
    try:
        bridge = _get_bridge()
        result = bridge.route_model(task_description)
        cf_agent = result.get("agent_type", "")
        from core.claude_flow import AGENT_TYPE_REVERSE

        if cf_agent in AGENT_TYPE_REVERSE:
            return AgentType(AGENT_TYPE_REVERSE[cf_agent])
    except (ClaudeFlowUnavailable, KeyError, ValueError):
        pass

    # 3. Last-resort fallback: keyword matching
    return _route_task_keywords(task_description)


def _route_task_keywords(task_description: str) -> AgentType:
    """Keyword-based task routing (last-resort fallback for offline/CI environments)."""
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
    """Load a prompt for the agent type.

    Looks for a matching skill in ``.claude/skills/`` first (the current
    system), then falls back to the bundled templates directory.

    Args:
        agent_type: The agent to load.
        project_root: Project root directory.  Defaults to ``Path.cwd()``.

    Returns:
        The prompt text, or empty string if not found.
    """
    if project_root is None:
        project_root = Path.cwd()

    # Map agent types to their corresponding skill files
    _agent_to_skill = {
        AgentType.RESEARCHER: "lit-review",
        AgentType.REVIEWER: "experiment-review",
        AgentType.WRITER: "paper-draft",
        AgentType.FALSIFIER: "falsify",
        AgentType.CODER: "reproduce",
        AgentType.CLEANER: "research-retro",
        AgentType.SLIDE_MAKER: "slides",
        AgentType.MASTER: "overnight",
    }

    skill_name = _agent_to_skill.get(agent_type, agent_type.value)
    skill_file = project_root / ".claude" / "skills" / f"{skill_name}.md"
    if skill_file.exists():
        return skill_file.read_text()

    # Fallback: try the bundled templates directory
    template_file = (
        Path(__file__).resolve().parent.parent
        / "templates"
        / ".claude"
        / "skills"
        / f"{skill_name}.md"
    )
    if template_file.exists():
        logger.info("Using template skill prompt for %s", agent_type.value)
        return template_file.read_text()
    logger.warning("Skill file not found for agent %s: %s", agent_type.value, skill_file)
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
        # Capture output to ring buffer
        if result.output:
            for line in result.output.splitlines():
                append_agent_output(agent_type.value, line)
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
    agent_label = agent_type.value

    try:
        # Use Popen to stream output line-by-line into ring buffer
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        output_lines: list[str] = []
        append_agent_output(agent_label, f"--- {task[:80]} ---")
        try:
            for line in proc.stdout:  # type: ignore[union-attr]
                output_lines.append(line)
                append_agent_output(agent_label, line)
            proc.wait(timeout=600)
        except subprocess.TimeoutExpired:
            proc.kill()
            result.status = "timeout"
            result.output = "Task timed out after 600 seconds"
            append_agent_output(agent_label, "[TIMEOUT]")
            result.ended = datetime.now().isoformat()
            _log_result(result)
            return result

        result.output = "".join(output_lines)
        result.status = "success" if proc.returncode == 0 else "failure"
    except Exception as e:
        result.status = "failure"
        result.output = str(e)
        append_agent_output(agent_label, f"[ERROR] {e}")

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


class FalsificationCheckpoint(str, Enum):
    """Named checkpoints where falsification runs during iterations."""

    AFTER_CODE_CHANGES = "after_code_changes"
    AFTER_TEST_RUN = "after_test_run"
    AFTER_RESULTS = "after_results"
    AFTER_MAJOR_CHANGE = "after_major_change"


@dataclass
class FalsificationResult:
    """Outcome of a falsification checkpoint."""

    checkpoint: str
    passed: bool
    issues: list[str] = field(default_factory=list)
    severity: str = "none"  # none, low, medium, high, critical
    output: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


def run_falsification_checkpoint(
    checkpoint: FalsificationCheckpoint | str,
    context: str,
    *,
    project_root: Path | None = None,
    dangerously_skip_permissions: bool = False,
) -> FalsificationResult:
    """Run a falsification check at a specific checkpoint during iteration.

    This is the main entry point for mid-iteration falsification. It invokes
    the Falsifier agent with checkpoint-specific instructions, then parses
    the result for critical issues.

    Args:
        checkpoint: Which checkpoint is triggering this check.
        context: Description of what just happened (code diff, test output, etc.).
        project_root: Project root for file-based checks.
        dangerously_skip_permissions: Skip permission checks (overnight mode).

    Returns:
        FalsificationResult with pass/fail and any issues found.
    """
    if isinstance(checkpoint, FalsificationCheckpoint):
        checkpoint_name = checkpoint.value
    else:
        checkpoint_name = checkpoint

    prompt = (
        f"## Falsification Checkpoint: {checkpoint_name}\n\n"
        "You are running as an inline falsification check -- NOT a full post-hoc audit.\n"
        "Focus on fast, targeted verification relevant to this checkpoint.\n\n"
        f"### What just happened\n{context[:3000]}\n\n"
        "### Your task\n"
        "1. Identify any issues introduced or revealed at this stage.\n"
        "2. Check for data leakage, statistical errors, or code correctness problems.\n"
        "3. Reply with a short structured report:\n"
        "   - PASSED or FAILED\n"
        "   - List of issues (if any), each with severity (low/medium/high/critical)\n"
        "   - One-line recommendation\n"
    )

    logger.info("Falsification checkpoint [%s]: running...", checkpoint_name)

    task_result = execute_agent_task(
        AgentType.FALSIFIER,
        prompt,
        dangerously_skip_permissions=dangerously_skip_permissions,
    )

    # Parse the falsifier output for pass/fail and issues
    output = task_result.output or ""
    output_lower = output.lower()
    passed = "failed" not in output_lower or (
        "passed" in output_lower and "failed" not in output_lower
    )

    issues: list[str] = []
    severity = "none"
    for line in output.splitlines():
        stripped = line.strip().lstrip("- ").lstrip("* ")
        if any(
            kw in stripped.lower()
            for kw in ["issue:", "problem:", "error:", "warning:", "critical:"]
        ):
            issues.append(stripped)

    if issues:
        # Determine highest severity mentioned
        for sev in ("critical", "high", "medium", "low"):
            if any(sev in issue.lower() for issue in issues):
                severity = sev
                break
        if severity == "none":
            severity = "medium"
        passed = False

    result = FalsificationResult(
        checkpoint=checkpoint_name,
        passed=passed,
        issues=issues,
        severity=severity,
        output=output,
    )

    _log_falsification_result(result)

    if not passed:
        logger.warning(
            "Falsification checkpoint [%s] FAILED: %d issues (severity=%s)",
            checkpoint_name,
            len(issues),
            severity,
        )
    else:
        logger.info("Falsification checkpoint [%s] PASSED", checkpoint_name)

    return result


def _log_falsification_result(result: FalsificationResult) -> None:
    """Append a falsification checkpoint result to the progress file."""
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    status_icon = "x" if result.passed else "!"
    timestamp = datetime.now().strftime("%H:%M")
    issue_count = len(result.issues)
    line = (
        f"- [{status_icon}] [falsifier-checkpoint] {result.checkpoint} "
        f"({issue_count} issues, severity={result.severity}) ({timestamp})\n"
    )
    with open(PROGRESS_FILE, "a") as f:
        f.write(line)


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
    from core.meta_rules import (
        append_to_cheatsheet,
        classify_rule_type,
        detect_operational_rule,
    )

    if detect_operational_rule(result.task):
        rule_type = classify_rule_type(result.task)
        append_to_cheatsheet(result.task, rule_type=rule_type)
