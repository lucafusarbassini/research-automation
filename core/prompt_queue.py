"""Prompt queue with dynamic agent dispatch and persistent memory.

Users can queue as many prompts as they want. The dispatcher dynamically
routes each prompt to the appropriate sub-agent, tracks shared context
across prompts, and ensures no memory losses occur between tasks.

Usage::

    from core.prompt_queue import PromptQueue

    q = PromptQueue(max_workers=3)
    q.submit("Search arxiv for transformer pruning papers")
    q.submit("Implement the pruning algorithm from the best paper")
    q.submit("Write unit tests for the pruning module")
    q.submit("Draft the methods section describing our approach")

    # Wait for all to finish
    results = q.drain()

    # Or process results as they complete
    for result in q.iter_completed():
        print(result.prompt_id, result.status)
"""

import json
import logging
import threading
import time
import uuid
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator, Optional

from core.agents import AgentType, TaskResult, execute_agent_task, route_task
from core.knowledge import append_learning, search_knowledge

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

MEMORY_DIR = Path("state/prompt_memory")


@dataclass
class PromptEntry:
    """A single queued prompt with metadata."""

    prompt_id: str
    text: str
    agent: Optional[AgentType] = None
    priority: int = 0  # Higher = more urgent
    depends_on: list[str] = field(default_factory=list)
    status: str = "queued"  # queued, routing, running, success, failure
    result: Optional[TaskResult] = None
    context_snapshot: list[str] = field(default_factory=list)
    submitted_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if d.get("agent"):
            d["agent"] = d["agent"]  # Already string from asdict
        if d.get("result"):
            d["result"]["agent"] = d["result"]["agent"]
        return d


@dataclass
class SharedMemory:
    """Thread-safe shared context across all prompts in a queue session.

    Stores learnings, decisions, and key outputs so downstream prompts can
    reference upstream results without memory loss.
    """

    entries: list[dict] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, prompt_id: str, key: str, value: str) -> None:
        """Record a context entry (thread-safe)."""
        with self._lock:
            self.entries.append({
                "prompt_id": prompt_id,
                "key": key,
                "value": value,
                "timestamp": datetime.now().isoformat(),
            })

    def get_context_for(self, prompt_id: str, max_entries: int = 50) -> list[str]:
        """Get context lines relevant to a prompt (all entries before it)."""
        with self._lock:
            lines = []
            for e in self.entries:
                if e["prompt_id"] == prompt_id:
                    break
                lines.append(f"[{e['key']}] {e['value']}")
            return lines[-max_entries:]

    def get_all_context(self, max_entries: int = 50) -> list[str]:
        """Get all accumulated context lines."""
        with self._lock:
            return [
                f"[{e['key']}] {e['value']}" for e in self.entries
            ][-max_entries:]

    def search(self, query: str) -> list[str]:
        """Search memory entries for a query string."""
        query_lower = query.lower()
        with self._lock:
            return [
                f"[{e['key']}] {e['value']}"
                for e in self.entries
                if query_lower in e["value"].lower() or query_lower in e["key"].lower()
            ]

    def save(self, path: Path) -> None:
        """Persist memory to disk."""
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self.entries, indent=2))

    def load(self, path: Path) -> None:
        """Restore memory from disk."""
        if path.exists():
            with self._lock:
                self.entries = json.loads(path.read_text())

    def __len__(self) -> int:
        with self._lock:
            return len(self.entries)


# ---------------------------------------------------------------------------
# Prompt Queue
# ---------------------------------------------------------------------------


class PromptQueue:
    """Dynamic prompt queue with agent dispatch and shared memory.

    Prompts are routed to the appropriate agent, executed in parallel
    (respecting dependencies), and results are accumulated in shared
    memory so downstream prompts can access upstream context.

    Args:
        max_workers: Maximum concurrent agent executions.
        dangerously_skip_permissions: Pass through to agent execution.
        memory_dir: Directory for persisting queue state.
        on_complete: Optional callback(PromptEntry) called when a prompt finishes.
    """

    def __init__(
        self,
        max_workers: int = 3,
        *,
        dangerously_skip_permissions: bool = False,
        memory_dir: Optional[Path] = None,
        on_complete: Optional[Callable[["PromptEntry"], None]] = None,
    ) -> None:
        self._max_workers = max_workers
        self._skip_permissions = dangerously_skip_permissions
        self._memory_dir = memory_dir or MEMORY_DIR
        self._on_complete = on_complete

        self._lock = threading.Lock()
        self._queue: deque[PromptEntry] = deque()
        self._running: dict[str, PromptEntry] = {}
        self._completed: list[PromptEntry] = []
        self._futures: dict[str, Future] = {}

        self.memory = SharedMemory()
        self._pool = ThreadPoolExecutor(max_workers=max_workers)
        self._dispatcher_running = False
        self._dispatcher_thread: Optional[threading.Thread] = None

        # Restore memory from disk if available
        mem_path = self._memory_dir / "shared_memory.json"
        self.memory.load(mem_path)

    # -- Public API ---------------------------------------------------------

    def submit(
        self,
        prompt: str,
        *,
        agent: Optional[AgentType] = None,
        priority: int = 0,
        depends_on: Optional[list[str]] = None,
    ) -> str:
        """Queue a prompt for execution.

        Args:
            prompt: The task/prompt text.
            agent: Force a specific agent (otherwise auto-routed).
            priority: Higher priority prompts are dispatched first.
            depends_on: List of prompt_ids that must complete first.

        Returns:
            The prompt_id for tracking.
        """
        entry = PromptEntry(
            prompt_id=str(uuid.uuid4())[:8],
            text=prompt,
            agent=agent,
            priority=priority,
            depends_on=depends_on or [],
        )

        with self._lock:
            self._queue.append(entry)

        # Auto-start dispatcher if not running
        self._ensure_dispatcher()

        logger.info("Queued prompt %s: %s", entry.prompt_id, prompt[:60])
        return entry.prompt_id

    def submit_batch(
        self,
        prompts: list[str],
        *,
        chain: bool = False,
    ) -> list[str]:
        """Queue multiple prompts at once.

        Args:
            prompts: List of prompt texts.
            chain: If True, each prompt depends on the previous one.

        Returns:
            List of prompt_ids.
        """
        ids: list[str] = []
        prev_id: Optional[str] = None

        for prompt in prompts:
            deps = [prev_id] if chain and prev_id else []
            pid = self.submit(prompt, depends_on=deps)
            ids.append(pid)
            prev_id = pid

        return ids

    def status(self) -> dict:
        """Get queue status summary."""
        with self._lock:
            return {
                "queued": len(self._queue),
                "running": len(self._running),
                "completed": len(self._completed),
                "total": len(self._queue) + len(self._running) + len(self._completed),
                "memory_entries": len(self.memory),
                "prompts": {
                    "queued": [
                        {"id": e.prompt_id, "text": e.text[:60], "priority": e.priority}
                        for e in self._queue
                    ],
                    "running": [
                        {"id": e.prompt_id, "text": e.text[:60], "agent": e.agent.value if e.agent else "routing"}
                        for e in self._running.values()
                    ],
                    "completed": [
                        {"id": e.prompt_id, "text": e.text[:60], "status": e.status}
                        for e in self._completed
                    ],
                },
            }

    def get_result(self, prompt_id: str) -> Optional[PromptEntry]:
        """Get the result for a specific prompt."""
        with self._lock:
            # Check completed
            for entry in self._completed:
                if entry.prompt_id == prompt_id:
                    return entry
            # Check running
            if prompt_id in self._running:
                return self._running[prompt_id]
            # Check queued
            for entry in self._queue:
                if entry.prompt_id == prompt_id:
                    return entry
        return None

    def drain(self, timeout: int = 3600) -> list[PromptEntry]:
        """Block until all queued prompts are completed.

        Args:
            timeout: Maximum seconds to wait.

        Returns:
            All completed PromptEntry objects.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if not self._queue and not self._running:
                    return list(self._completed)
            time.sleep(0.2)
        logger.warning("drain() timed out after %ds", timeout)
        with self._lock:
            return list(self._completed)

    def iter_completed(self) -> Iterator[PromptEntry]:
        """Yield completed prompts as they finish (non-blocking generator).

        Yields completed entries that haven't been yielded before.
        Returns when queue is empty and nothing is running.
        """
        yielded: set[str] = set()
        while True:
            with self._lock:
                for entry in self._completed:
                    if entry.prompt_id not in yielded:
                        yielded.add(entry.prompt_id)
                        yield entry
                if not self._queue and not self._running:
                    # Yield any remaining
                    for entry in self._completed:
                        if entry.prompt_id not in yielded:
                            yielded.add(entry.prompt_id)
                            yield entry
                    return
            time.sleep(0.1)

    def cancel(self, prompt_id: str) -> bool:
        """Cancel a queued (not yet running) prompt."""
        with self._lock:
            for i, entry in enumerate(self._queue):
                if entry.prompt_id == prompt_id:
                    entry.status = "cancelled"
                    del self._queue[i]
                    self._completed.append(entry)
                    return True
        return False

    def cancel_all(self) -> int:
        """Cancel all queued prompts. Running prompts continue."""
        with self._lock:
            count = len(self._queue)
            for entry in self._queue:
                entry.status = "cancelled"
                self._completed.append(entry)
            self._queue.clear()
            return count

    def shutdown(self, wait: bool = True) -> None:
        """Stop the dispatcher and thread pool."""
        self._dispatcher_running = False
        self._persist()
        self._pool.shutdown(wait=wait)

    # -- Dispatcher ---------------------------------------------------------

    def _ensure_dispatcher(self) -> None:
        """Start the background dispatcher thread if not already running."""
        if self._dispatcher_running:
            return
        self._dispatcher_running = True
        self._dispatcher_thread = threading.Thread(
            target=self._dispatch_loop, daemon=True, name="prompt-dispatcher"
        )
        self._dispatcher_thread.start()

    def _dispatch_loop(self) -> None:
        """Background loop that picks prompts from the queue and dispatches them."""
        while self._dispatcher_running:
            dispatched = self._try_dispatch()
            if not dispatched:
                with self._lock:
                    if not self._queue and not self._running:
                        self._dispatcher_running = False
                        self._persist()
                        return
                time.sleep(0.1)

    def _try_dispatch(self) -> bool:
        """Try to dispatch the next eligible prompt. Returns True if dispatched."""
        with self._lock:
            if len(self._running) >= self._max_workers:
                return False

            # Find highest-priority prompt whose dependencies are met
            completed_ids = {e.prompt_id for e in self._completed if e.status == "success"}
            best_idx = None
            best_priority = -1

            for i, entry in enumerate(self._queue):
                deps_met = all(d in completed_ids for d in entry.depends_on)
                if deps_met and entry.priority >= best_priority:
                    best_idx = i
                    best_priority = entry.priority

            if best_idx is None:
                # Check for dead dependencies (failed deps)
                failed_ids = {e.prompt_id for e in self._completed if e.status == "failure"}
                for i, entry in enumerate(self._queue):
                    if any(d in failed_ids for d in entry.depends_on):
                        entry.status = "failure"
                        entry.error = "Dependency failed"
                        entry.completed_at = datetime.now().isoformat()
                        self._completed.append(entry)
                        del self._queue[i]
                        return True
                return False

            entry = self._queue[best_idx]
            del self._queue[best_idx]

            # Route to agent
            entry.status = "routing"
            if entry.agent is None:
                entry.agent = route_task(entry.text)
            entry.status = "running"
            entry.started_at = datetime.now().isoformat()

            # Build context from shared memory
            entry.context_snapshot = self.memory.get_all_context()

            self._running[entry.prompt_id] = entry

        # Submit to thread pool (outside lock)
        future = self._pool.submit(self._execute_prompt, entry)
        future.add_done_callback(lambda f, e=entry: self._on_prompt_done(e, f))

        with self._lock:
            self._futures[entry.prompt_id] = future
        return True

    def _execute_prompt(self, entry: PromptEntry) -> TaskResult:
        """Execute a single prompt with context injection."""
        # Build enriched prompt with shared memory context
        context_lines = entry.context_snapshot
        if context_lines:
            context_block = "\n".join(context_lines)
            enriched = (
                f"## Prior Context (from completed tasks)\n\n{context_block}\n\n"
                f"## Current Task\n\n{entry.text}"
            )
        else:
            enriched = entry.text

        return execute_agent_task(
            entry.agent,
            enriched,
            dangerously_skip_permissions=self._skip_permissions,
        )

    def _on_prompt_done(self, entry: PromptEntry, future: Future) -> None:
        """Callback when a prompt execution completes."""
        try:
            result = future.result()
            entry.result = result
            entry.status = result.status
        except Exception as exc:
            entry.status = "failure"
            entry.error = str(exc)
            entry.result = TaskResult(
                agent=entry.agent or AgentType.CODER,
                task=entry.text,
                status="failure",
                output=str(exc),
            )

        entry.completed_at = datetime.now().isoformat()

        # Record to shared memory
        output_summary = (entry.result.output or "")[:500]
        self.memory.record(
            entry.prompt_id,
            f"{entry.agent.value}-result" if entry.agent else "result",
            f"Task: {entry.text[:100]} | Status: {entry.status} | Output: {output_summary}",
        )

        # Also persist to knowledge base (best-effort)
        try:
            if entry.status == "success" and output_summary:
                append_learning(
                    "Queue Results",
                    f"[{entry.agent.value if entry.agent else 'unknown'}] {entry.text[:80]}: {output_summary[:200]}",
                )
        except Exception:
            pass

        with self._lock:
            self._running.pop(entry.prompt_id, None)
            self._futures.pop(entry.prompt_id, None)
            self._completed.append(entry)

        if self._on_complete:
            try:
                self._on_complete(entry)
            except Exception:
                logger.exception("on_complete callback failed for %s", entry.prompt_id)

    # -- Persistence --------------------------------------------------------

    def _persist(self) -> None:
        """Save queue state and memory to disk."""
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        self.memory.save(self._memory_dir / "shared_memory.json")

        state = {
            "completed": [e.to_dict() for e in self._completed],
            "queued": [e.to_dict() for e in self._queue],
            "saved_at": datetime.now().isoformat(),
        }
        state_path = self._memory_dir / "queue_state.json"
        state_path.write_text(json.dumps(state, indent=2, default=str))

    def load_state(self) -> None:
        """Restore queue state from disk (for resuming after restart)."""
        state_path = self._memory_dir / "queue_state.json"
        if not state_path.exists():
            return
        data = json.loads(state_path.read_text())
        # Only restore queued items (completed are historical)
        for item in data.get("queued", []):
            entry = PromptEntry(
                prompt_id=item["prompt_id"],
                text=item["text"],
                priority=item.get("priority", 0),
                depends_on=item.get("depends_on", []),
            )
            self._queue.append(entry)
        logger.info("Restored %d queued prompts from disk", len(self._queue))
