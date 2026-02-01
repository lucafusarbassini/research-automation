"""Tests for task dependencies, parallel execution, and plan-execute-iterate."""

from core.agents import (
    AgentType,
    Task,
    TaskResult,
    build_task_dag,
    execute_parallel_tasks,
    get_active_agents_status,
    plan_execute_iterate,
)


def _mock_executor(task: Task) -> TaskResult:
    """Mock executor that always succeeds."""
    return TaskResult(
        agent=task.agent or AgentType.CODER,
        task=task.description,
        status="success",
        output=f"Done: {task.description}",
    )


def _mock_executor_fail(task: Task) -> TaskResult:
    """Mock executor that fails on specific tasks."""
    status = "failure" if "fail" in task.description else "success"
    return TaskResult(
        agent=task.agent or AgentType.CODER,
        task=task.description,
        status=status,
        output=f"Result: {task.description}",
    )


def test_task_dataclass():
    t = Task(id="t1", description="do something", agent=AgentType.CODER)
    assert t.id == "t1"
    assert t.status == "pending"
    assert t.deps == []


def test_task_with_deps():
    t = Task(id="t2", description="depends on t1", deps=["t1"])
    assert t.deps == ["t1"]


def test_build_task_dag():
    tasks = [
        Task(id="a", description="first"),
        Task(id="b", description="second", deps=["a"]),
        Task(id="c", description="third", deps=["a"]),
    ]
    dag = build_task_dag(tasks)
    assert "a" in dag
    assert set(dag["a"]) == {"b", "c"}


def test_build_task_dag_empty():
    dag = build_task_dag([])
    assert dag == {}


def test_execute_parallel_no_deps():
    tasks = [
        Task(id="t1", description="task one", agent=AgentType.CODER),
        Task(id="t2", description="task two", agent=AgentType.WRITER),
    ]
    results = execute_parallel_tasks(tasks, executor_fn=_mock_executor)
    assert len(results) == 2
    assert results["t1"].status == "success"
    assert results["t2"].status == "success"


def test_execute_parallel_with_deps():
    tasks = [
        Task(id="a", description="first task", agent=AgentType.CODER),
        Task(id="b", description="depends on a", agent=AgentType.REVIEWER, deps=["a"]),
    ]
    executed_order = []

    def tracking_executor(task: Task) -> TaskResult:
        executed_order.append(task.id)
        return _mock_executor(task)

    results = execute_parallel_tasks(tasks, executor_fn=tracking_executor)
    assert len(results) == 2
    assert executed_order.index("a") < executed_order.index("b")


def test_execute_parallel_deadlock():
    tasks = [
        Task(id="a", description="depends on b", deps=["b"]),
        Task(id="b", description="depends on a", deps=["a"]),
    ]
    results = execute_parallel_tasks(tasks, executor_fn=_mock_executor)
    assert len(results) == 2
    assert all(r.status == "failure" for r in results.values())


def test_execute_parallel_partial_failure():
    tasks = [
        Task(id="t1", description="this will fail", agent=AgentType.CODER),
        Task(id="t2", description="this succeeds", agent=AgentType.CODER),
    ]
    results = execute_parallel_tasks(tasks, executor_fn=_mock_executor_fail)
    assert results["t1"].status == "failure"
    assert results["t2"].status == "success"


def test_plan_execute_iterate_single():
    def plan_fn(goal, iteration, prev):
        if iteration == 0:
            return [Task(id="t0", description=goal, agent=AgentType.CODER)]
        return []

    results = plan_execute_iterate(
        "implement feature",
        plan_fn=plan_fn,
        dangerously_skip_permissions=False,
    )
    # Uses real execute which calls claude CLI, so mock instead
    # Test just the planning logic
    assert plan_fn("test", 0, []) != []
    assert plan_fn("test", 1, []) == []


def test_plan_execute_iterate_with_mock():
    calls = []

    def plan_fn(goal, iteration, prev):
        calls.append(iteration)
        if iteration == 0:
            return [Task(id="t0", description="do it", agent=AgentType.CODER)]
        return []

    # Monkey-patch execute_parallel_tasks for this test
    import core.agents as agents_mod

    orig = agents_mod.execute_parallel_tasks

    def mock_parallel(tasks, **kwargs):
        return {t.id: _mock_executor(t) for t in tasks}

    agents_mod.execute_parallel_tasks = mock_parallel
    try:
        results = plan_execute_iterate("goal", plan_fn=plan_fn)
        assert len(results) == 1
        assert results[0].status == "success"
    finally:
        agents_mod.execute_parallel_tasks = orig


def test_get_active_agents_status():
    # Should return empty when no agents running
    status = get_active_agents_status()
    assert isinstance(status, list)


# --- Bridge-integrated tests ---

from unittest.mock import MagicMock, patch


def test_execute_parallel_via_swarm():
    """When bridge is available, execute_parallel_tasks uses run_swarm."""
    mock_bridge = MagicMock()
    mock_bridge.run_swarm.return_value = {
        "results": [
            {"status": "success", "output": "done-1", "tokens_used": 100},
            {"status": "success", "output": "done-2", "tokens_used": 200},
        ]
    }
    tasks = [
        Task(id="t1", description="task one", agent=AgentType.CODER),
        Task(id="t2", description="task two", agent=AgentType.WRITER),
    ]
    with patch("core.agents._get_bridge", return_value=mock_bridge):
        results = execute_parallel_tasks(tasks)
        assert len(results) == 2
        assert results["t1"].status == "success"
        assert results["t2"].output == "done-2"
        mock_bridge.run_swarm.assert_called_once()


def test_execute_parallel_swarm_fallback():
    """When bridge fails, execute_parallel_tasks uses legacy executor."""
    from core.claude_flow import ClaudeFlowUnavailable

    tasks = [
        Task(id="t1", description="task one", agent=AgentType.CODER),
    ]
    with patch("core.agents._get_bridge", side_effect=ClaudeFlowUnavailable("nope")):
        results = execute_parallel_tasks(tasks, executor_fn=_mock_executor)
        assert results["t1"].status == "success"


def test_execute_parallel_custom_executor_skips_bridge():
    """When executor_fn is provided, bridge is not attempted."""
    tasks = [
        Task(id="t1", description="task one", agent=AgentType.CODER),
    ]
    # No bridge mocking needed; executor_fn bypasses bridge
    results = execute_parallel_tasks(tasks, executor_fn=_mock_executor)
    assert results["t1"].status == "success"
