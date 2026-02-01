"""Tests for lazy MCP loading — TDD-first.

Philosophy: 'AI context is like milk; best served fresh and condensed.'
"""

import pytest

from core.lazy_mcp import LazyMCPLoader


@pytest.fixture
def loader():
    """Fresh LazyMCPLoader for each test."""
    return LazyMCPLoader()


@pytest.fixture
def loader_with_mcps(loader):
    """Loader pre-populated with a handful of MCPs across tiers."""
    loader.register_mcp(
        name="filesystem",
        config={"command": "npx", "args": ["-y", "@anthropic/mcp-filesystem"]},
        tier=1,
        trigger_keywords=["file", "read", "write", "directory"],
    )
    loader.register_mcp(
        name="github",
        config={"command": "npx", "args": ["-y", "@anthropic/mcp-github"]},
        tier=2,
        trigger_keywords=["github", "pr", "pull request", "issue", "repo"],
    )
    loader.register_mcp(
        name="browser",
        config={"command": "npx", "args": ["-y", "@anthropic/mcp-browser"]},
        tier=3,
        trigger_keywords=["browse", "web", "scrape", "fetch url"],
    )
    loader.register_mcp(
        name="memory",
        config={"command": "npx", "args": ["-y", "@anthropic/mcp-memory"]},
        tier=1,
        trigger_keywords=["remember", "recall", "memory", "knowledge"],
    )
    return loader


# ── Registration ────────────────────────────────────────────────────


class TestRegisterMCP:
    def test_register_stores_metadata(self, loader):
        loader.register_mcp(
            name="filesystem",
            config={"command": "npx"},
            tier=1,
            trigger_keywords=["file"],
        )
        # Should be registered but NOT loaded
        assert "filesystem" not in loader.get_active_mcps()

    def test_register_duplicate_overwrites(self, loader):
        loader.register_mcp("fs", {"v": 1}, tier=1, trigger_keywords=["a"])
        loader.register_mcp("fs", {"v": 2}, tier=2, trigger_keywords=["b"])
        # Latest registration wins
        info = loader.load_mcp("fs")
        assert info["config"]["v"] == 2
        assert info["tier"] == 2


# ── Task-based matching ─────────────────────────────────────────────


class TestGetNeededMCPs:
    def test_keyword_match_single(self, loader_with_mcps):
        needed = loader_with_mcps.get_needed_mcps("read the config file")
        assert "filesystem" in needed

    def test_keyword_match_multiple(self, loader_with_mcps):
        needed = loader_with_mcps.get_needed_mcps(
            "open a PR on github after reading the file"
        )
        assert "filesystem" in needed
        assert "github" in needed

    def test_no_match_returns_empty(self, loader_with_mcps):
        needed = loader_with_mcps.get_needed_mcps("calculate 2+2")
        assert needed == []

    def test_case_insensitive(self, loader_with_mcps):
        needed = loader_with_mcps.get_needed_mcps("Browse the WEB page")
        assert "browser" in needed


# ── Loading / unloading lifecycle ───────────────────────────────────


class TestLoadUnload:
    def test_load_returns_config(self, loader_with_mcps):
        info = loader_with_mcps.load_mcp("filesystem")
        assert info["config"]["command"] == "npx"
        assert "filesystem" in loader_with_mcps.get_active_mcps()

    def test_load_unknown_raises(self, loader):
        with pytest.raises(KeyError):
            loader.load_mcp("nonexistent")

    def test_unload_removes_from_active(self, loader_with_mcps):
        loader_with_mcps.load_mcp("github")
        assert "github" in loader_with_mcps.get_active_mcps()
        loader_with_mcps.unload_mcp("github")
        assert "github" not in loader_with_mcps.get_active_mcps()

    def test_unload_unknown_is_noop(self, loader_with_mcps):
        # Should not raise
        loader_with_mcps.unload_mcp("nonexistent")

    def test_double_load_is_idempotent(self, loader_with_mcps):
        loader_with_mcps.load_mcp("filesystem")
        loader_with_mcps.load_mcp("filesystem")
        assert loader_with_mcps.get_active_mcps().count("filesystem") == 1


# ── Context optimisation ────────────────────────────────────────────


class TestOptimizeContext:
    def test_suggests_unloading_irrelevant_mcps(self, loader_with_mcps):
        loader_with_mcps.load_mcp("filesystem")
        loader_with_mcps.load_mcp("github")
        loader_with_mcps.load_mcp("browser")
        to_unload = loader_with_mcps.optimize_context(
            active_mcps=loader_with_mcps.get_active_mcps(),
            current_task="open a pull request on github",
        )
        # browser and filesystem are irrelevant to the task
        assert "github" not in to_unload
        assert "browser" in to_unload

    def test_keeps_low_tier_mcps(self, loader_with_mcps):
        """Tier-1 MCPs are essential; optimiser should prefer dropping higher tiers."""
        loader_with_mcps.load_mcp("filesystem")  # tier 1
        loader_with_mcps.load_mcp("browser")  # tier 3
        to_unload = loader_with_mcps.optimize_context(
            active_mcps=loader_with_mcps.get_active_mcps(),
            current_task="something completely unrelated",
        )
        # Higher-tier MCPs should be suggested for unloading first
        if to_unload:
            # browser (tier 3) should be suggested before filesystem (tier 1)
            browser_idx = to_unload.index("browser") if "browser" in to_unload else 999
            fs_idx = (
                to_unload.index("filesystem") if "filesystem" in to_unload else 999
            )
            assert browser_idx < fs_idx


# ── Context cost estimation ─────────────────────────────────────────


class TestEstimateContextCost:
    def test_cost_scales_with_count(self, loader_with_mcps):
        cost_one = loader_with_mcps.estimate_context_cost(["filesystem"])
        cost_two = loader_with_mcps.estimate_context_cost(["filesystem", "github"])
        assert cost_two > cost_one

    def test_unknown_mcp_excluded(self, loader_with_mcps):
        # Unknown MCPs should contribute zero cost, not raise
        cost = loader_with_mcps.estimate_context_cost(["nonexistent"])
        assert cost == 0
