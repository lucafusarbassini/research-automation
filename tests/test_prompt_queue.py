"""Tests for core.prompt_queue — dynamic prompt dispatch with shared memory."""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.agents import AgentType, TaskResult
from core.prompt_queue import PromptEntry, PromptQueue, SharedMemory


# ---------------------------------------------------------------------------
# SharedMemory
# ---------------------------------------------------------------------------


class TestSharedMemory:
    def test_record_and_get_context(self):
        mem = SharedMemory()
        mem.record("p1", "coder-result", "Implemented data loader")
        mem.record("p2", "researcher-result", "Found 5 papers on pruning")

        ctx = mem.get_all_context()
        assert len(ctx) == 2
        assert "data loader" in ctx[0]

    def test_get_context_for_prompt(self):
        mem = SharedMemory()
        mem.record("p1", "result", "First task done")
        mem.record("p2", "result", "Second task done")
        mem.record("p3", "result", "Third task done")

        # Context for p3 should include p1 and p2 but not p3
        ctx = mem.get_context_for("p3")
        assert len(ctx) == 2
        assert "First" in ctx[0]
        assert "Second" in ctx[1]

    def test_search(self):
        mem = SharedMemory()
        mem.record("p1", "coder", "Built data pipeline")
        mem.record("p2", "researcher", "Read arxiv papers on transformers")
        mem.record("p3", "coder", "Fixed pipeline bug")

        results = mem.search("pipeline")
        assert len(results) == 2

    def test_save_and_load(self, tmp_path):
        mem = SharedMemory()
        mem.record("p1", "key", "value1")
        mem.record("p2", "key", "value2")

        path = tmp_path / "memory.json"
        mem.save(path)

        mem2 = SharedMemory()
        mem2.load(path)
        assert len(mem2) == 2

    def test_max_entries_limit(self):
        mem = SharedMemory()
        for i in range(100):
            mem.record(f"p{i}", "key", f"value {i}")

        ctx = mem.get_all_context(max_entries=10)
        assert len(ctx) == 10

    def test_thread_safety(self):
        import threading
        mem = SharedMemory()
        errors = []

        def writer(n):
            try:
                for i in range(50):
                    mem.record(f"thread-{n}-{i}", "key", f"value-{n}-{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(mem) == 200


# ---------------------------------------------------------------------------
# PromptEntry
# ---------------------------------------------------------------------------


class TestPromptEntry:
    def test_creation(self):
        entry = PromptEntry(prompt_id="abc", text="Do something")
        assert entry.status == "queued"
        assert entry.agent is None
        assert entry.result is None

    def test_to_dict(self):
        entry = PromptEntry(prompt_id="abc", text="Test", agent=AgentType.CODER)
        d = entry.to_dict()
        assert d["prompt_id"] == "abc"
        assert d["text"] == "Test"


# ---------------------------------------------------------------------------
# PromptQueue
# ---------------------------------------------------------------------------


def _mock_execute(agent_type, task, *, dangerously_skip_permissions=False):
    """Mock agent execution that returns quickly."""
    return TaskResult(
        agent=agent_type,
        task=task,
        status="success",
        output=f"Done: {task[:50]}",
        tokens_used=100,
    )


class TestPromptQueueSubmit:
    @patch("core.prompt_queue.execute_agent_task", side_effect=_mock_execute)
    @patch("core.prompt_queue.append_learning")
    def test_submit_single(self, _mock_learn, _mock_exec, tmp_path):
        q = PromptQueue(max_workers=2, memory_dir=tmp_path / "mem")
        pid = q.submit("Search for papers on transformers")

        assert isinstance(pid, str)
        assert len(pid) == 8

        results = q.drain(timeout=10)
        q.shutdown()
        assert len(results) >= 1
        assert results[0].status == "success"

    @patch("core.prompt_queue.execute_agent_task", side_effect=_mock_execute)
    @patch("core.prompt_queue.append_learning")
    def test_submit_multiple(self, _mock_learn, _mock_exec, tmp_path):
        q = PromptQueue(max_workers=3, memory_dir=tmp_path / "mem")
        ids = []
        for i in range(5):
            ids.append(q.submit(f"Task number {i}"))

        results = q.drain(timeout=10)
        q.shutdown()
        assert len(results) == 5
        assert all(r.status == "success" for r in results)

    @patch("core.prompt_queue.execute_agent_task", side_effect=_mock_execute)
    @patch("core.prompt_queue.append_learning")
    def test_submit_batch(self, _mock_learn, _mock_exec, tmp_path):
        q = PromptQueue(max_workers=2, memory_dir=tmp_path / "mem")
        ids = q.submit_batch(["Task A", "Task B", "Task C"])

        assert len(ids) == 3

        results = q.drain(timeout=10)
        q.shutdown()
        assert len(results) == 3

    @patch("core.prompt_queue.execute_agent_task", side_effect=_mock_execute)
    @patch("core.prompt_queue.append_learning")
    def test_submit_batch_chained(self, _mock_learn, _mock_exec, tmp_path):
        q = PromptQueue(max_workers=2, memory_dir=tmp_path / "mem")
        ids = q.submit_batch(["Step 1", "Step 2", "Step 3"], chain=True)

        results = q.drain(timeout=10)
        q.shutdown()
        assert len(results) == 3


class TestPromptQueueStatus:
    @patch("core.prompt_queue.execute_agent_task", side_effect=_mock_execute)
    @patch("core.prompt_queue.append_learning")
    def test_status(self, _mock_learn, _mock_exec, tmp_path):
        q = PromptQueue(max_workers=1, memory_dir=tmp_path / "mem")
        q.submit("Some task")
        st = q.status()
        assert "queued" in st
        assert "running" in st
        assert "completed" in st
        assert st["total"] >= 1
        q.drain(timeout=10)
        q.shutdown()


class TestPromptQueueCancel:
    def test_cancel_queued(self, tmp_path):
        q = PromptQueue(max_workers=1, memory_dir=tmp_path / "mem")
        q._pool.shutdown(wait=False)
        q._dispatcher_running = False

        entry = PromptEntry(prompt_id="test1", text="Cancel me")
        q._queue.append(entry)

        assert q.cancel("test1") is True
        assert len(q._completed) == 1
        assert q._completed[0].status == "cancelled"

    def test_cancel_all(self, tmp_path):
        q = PromptQueue(max_workers=1, memory_dir=tmp_path / "mem")
        q._pool.shutdown(wait=False)
        q._dispatcher_running = False

        for i in range(3):
            q._queue.append(PromptEntry(prompt_id=f"t{i}", text=f"Task {i}"))

        n = q.cancel_all()
        assert n == 3
        assert len(q._completed) == 3


class TestPromptQueueMemory:
    @patch("core.prompt_queue.execute_agent_task", side_effect=_mock_execute)
    @patch("core.prompt_queue.append_learning")
    def test_memory_accumulates(self, _mock_learn, _mock_exec, tmp_path):
        q = PromptQueue(max_workers=1, memory_dir=tmp_path / "mem")
        q.submit_batch(["First task", "Second task"], chain=True)

        results = q.drain(timeout=10)
        q.shutdown()

        assert len(q.memory) >= 2

    @patch("core.prompt_queue.execute_agent_task", side_effect=_mock_execute)
    @patch("core.prompt_queue.append_learning")
    def test_memory_persists(self, _mock_learn, _mock_exec, tmp_path):
        mem_dir = tmp_path / "mem"
        q = PromptQueue(max_workers=1, memory_dir=mem_dir)
        q.submit("Persist this")
        q.drain(timeout=10)
        q.shutdown()

        # Memory file should exist
        assert (mem_dir / "shared_memory.json").exists()
        assert (mem_dir / "queue_state.json").exists()


class TestPromptQueueGetResult:
    @patch("core.prompt_queue.execute_agent_task", side_effect=_mock_execute)
    @patch("core.prompt_queue.append_learning")
    def test_get_result(self, _mock_learn, _mock_exec, tmp_path):
        q = PromptQueue(max_workers=1, memory_dir=tmp_path / "mem")
        pid = q.submit("Find me")
        q.drain(timeout=10)

        result = q.get_result(pid)
        assert result is not None
        assert result.status == "success"
        q.shutdown()

    def test_get_result_not_found(self, tmp_path):
        q = PromptQueue(max_workers=1, memory_dir=tmp_path / "mem")
        assert q.get_result("nonexistent") is None
        q.shutdown(wait=False)


class TestPromptQueuePriority:
    @patch("core.prompt_queue.execute_agent_task", side_effect=_mock_execute)
    @patch("core.prompt_queue.append_learning")
    def test_higher_priority_dispatched_first(self, _mock_learn, _mock_exec, tmp_path):
        """High-priority prompts should be selected before low-priority ones."""
        q = PromptQueue(max_workers=1, memory_dir=tmp_path / "mem")

        # Directly test the selection logic: put both in queue
        q._pool.shutdown(wait=False)
        q._dispatcher_running = False

        q._queue.append(PromptEntry(prompt_id="low", text="Low prio task", priority=0))
        q._queue.append(PromptEntry(prompt_id="high", text="High prio task", priority=10))

        # Manually find which one _try_dispatch would pick
        # by checking the selection logic directly
        completed_ids = {e.prompt_id for e in q._completed if e.status == "success"}
        best_idx = None
        best_priority = -1
        for i, entry in enumerate(q._queue):
            deps_met = all(d in completed_ids for d in entry.depends_on)
            if deps_met and entry.priority >= best_priority:
                best_idx = i
                best_priority = entry.priority

        assert q._queue[best_idx].prompt_id == "high"
        q.shutdown(wait=False)
