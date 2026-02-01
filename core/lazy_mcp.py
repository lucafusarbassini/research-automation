"""Lazy-loading MCP module — only load tools when actually needed.

Philosophy: 'AI context is like milk; best served fresh and condensed.'

Registers MCPs with metadata (tier, trigger keywords, config) but defers
the actual loading until the moment a task requires them.  Provides
context-cost estimation and an optimiser that suggests which MCPs to
unload when context budget is tight.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List

logger = logging.getLogger(__name__)

# Rough per-MCP token overhead (description + tool schemas).
# Keyed by tier; higher tiers tend to expose more tools.
_DEFAULT_TOKEN_COST_BY_TIER: Dict[int, int] = {
    1: 800,
    2: 1200,
    3: 1800,
}
_FALLBACK_TOKEN_COST = 1000


@dataclass
class _MCPEntry:
    """Internal bookkeeping for a registered MCP."""

    name: str
    config: dict
    tier: int
    trigger_keywords: list[str]
    loaded: bool = False
    # Normalised keywords for fast matching
    _keywords_lower: list[str] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self._keywords_lower = [kw.lower() for kw in self.trigger_keywords]


class LazyMCPLoader:
    """Manages deferred MCP loading.

    MCPs are *registered* up-front with metadata, but only *loaded* into the
    active context when a task actually needs them.  The optimiser can later
    suggest unloading MCPs that are no longer relevant to free up tokens.
    """

    def __init__(self) -> None:
        self._registry: Dict[str, _MCPEntry] = {}

    # ── Registration ────────────────────────────────────────────────

    def register_mcp(
        self,
        name: str,
        config: dict,
        tier: int,
        trigger_keywords: list[str],
    ) -> None:
        """Register an MCP for lazy loading.

        If *name* is already registered the entry is silently overwritten
        (latest-write-wins), which allows hot-reloading config changes.
        """
        self._registry[name] = _MCPEntry(
            name=name,
            config=config,
            tier=tier,
            trigger_keywords=trigger_keywords,
        )
        logger.debug(
            "Registered MCP %s (tier %d, keywords=%s)", name, tier, trigger_keywords
        )

    # ── Task matching ───────────────────────────────────────────────

    def get_needed_mcps(self, task: str) -> list[str]:
        """Determine which registered MCPs are relevant for *task*.

        Matching is case-insensitive keyword containment: if any of an
        MCP's trigger keywords appear as a substring of *task*, that MCP
        is considered needed.
        """
        task_lower = task.lower()
        needed: list[str] = []
        for entry in self._registry.values():
            if any(kw in task_lower for kw in entry._keywords_lower):
                needed.append(entry.name)
        return needed

    # ── Loading / unloading ─────────────────────────────────────────

    def load_mcp(self, name: str) -> dict:
        """Load (initialise) a registered MCP, returning its metadata.

        Raises ``KeyError`` if the MCP has not been registered.
        Idempotent: loading an already-active MCP is a no-op that still
        returns its metadata.
        """
        if name not in self._registry:
            raise KeyError(f"MCP '{name}' is not registered")

        entry = self._registry[name]
        if not entry.loaded:
            logger.info("Loading MCP %s (tier %d)", name, entry.tier)
            entry.loaded = True

        return {
            "name": entry.name,
            "config": entry.config,
            "tier": entry.tier,
            "trigger_keywords": entry.trigger_keywords,
        }

    def unload_mcp(self, name: str) -> None:
        """Unload an MCP to free context.

        No-op if the MCP is not currently loaded or not registered at all.
        """
        entry = self._registry.get(name)
        if entry is not None and entry.loaded:
            logger.info("Unloading MCP %s", name)
            entry.loaded = False

    def get_active_mcps(self) -> list[str]:
        """Return names of all currently loaded MCPs."""
        return [e.name for e in self._registry.values() if e.loaded]

    # ── Context optimisation ────────────────────────────────────────

    def optimize_context(
        self,
        active_mcps: list[str],
        current_task: str,
    ) -> list[str]:
        """Suggest MCPs to unload to save context budget.

        Strategy:
        1. Any active MCP whose keywords do NOT match the *current_task*
           is a candidate for unloading.
        2. Candidates are sorted by tier descending (drop expensive /
           niche MCPs before essential ones).

        Returns a list of MCP names ordered from "most beneficial to drop"
        to "least beneficial to drop".
        """
        task_lower = current_task.lower()
        candidates: list[_MCPEntry] = []

        for name in active_mcps:
            entry = self._registry.get(name)
            if entry is None:
                continue
            # Keep if any keyword matches
            if any(kw in task_lower for kw in entry._keywords_lower):
                continue
            candidates.append(entry)

        # Higher tier first → drop those before essentials
        candidates.sort(key=lambda e: e.tier, reverse=True)
        return [c.name for c in candidates]

    def estimate_context_cost(self, mcps: list[str]) -> int:
        """Estimate the token cost of having *mcps* loaded.

        Uses a per-tier heuristic; unknown MCP names contribute zero.
        """
        total = 0
        for name in mcps:
            entry = self._registry.get(name)
            if entry is None:
                continue
            total += _DEFAULT_TOKEN_COST_BY_TIER.get(entry.tier, _FALLBACK_TOKEN_COST)
        return total
