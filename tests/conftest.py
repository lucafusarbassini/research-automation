"""Shared test fixtures and helpers for the research-automation test suite."""

import shutil
from unittest.mock import MagicMock, patch

import pytest


def _claude_flow_available() -> bool:
    """Check if claude-flow CLI is actually installed and reachable."""
    return shutil.which("npx") is not None


@pytest.fixture
def mock_bridge():
    """Provide a MagicMock bridge with all methods pre-configured.

    Usage:
        def test_something(mock_bridge):
            mock_bridge.spawn_agent.return_value = {"status": "success"}
            with patch("core.agents._get_bridge", return_value=mock_bridge):
                ...
    """
    bridge = MagicMock()

    # Sensible defaults
    bridge.is_available.return_value = True
    bridge.get_version.return_value = "3.0.0-mock"
    bridge.spawn_agent.return_value = {
        "status": "success",
        "output": "mock output",
        "tokens_used": 100,
    }
    bridge.run_swarm.return_value = {"results": []}
    bridge.route_model.return_value = {
        "tier": "workhorse",
        "model": "claude-sonnet-4-20250514",
        "complexity": "medium",
    }
    bridge.query_memory.return_value = {"results": []}
    bridge.store_memory.return_value = {"id": "mock-mem-id"}
    bridge.scan_security.return_value = {"findings": []}
    bridge.get_metrics.return_value = {
        "tokens_used": 0,
        "cost_usd": 0.0,
    }
    bridge.start_session.return_value = {"session_id": "mock-session"}
    bridge.end_session.return_value = {"summary": {}}
    bridge.multi_repo_sync.return_value = {}

    return bridge
