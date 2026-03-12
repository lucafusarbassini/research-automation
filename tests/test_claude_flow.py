"""Tests for the claude-flow bridge stub (CLI bridge disabled, MCP used instead)."""

import pytest

from core.claude_flow import (
    AGENT_TYPE_MAP,
    ClaudeFlowBridge,
    ClaudeFlowUnavailable,
    _get_bridge,
)


class TestBridgeDisabled:
    def test_get_bridge_always_raises(self):
        with pytest.raises(ClaudeFlowUnavailable, match="CLI bridge disabled"):
            _get_bridge()

    def test_bridge_is_not_available(self):
        bridge = ClaudeFlowBridge()
        assert bridge.is_available() is False

    def test_bridge_version_unavailable(self):
        bridge = ClaudeFlowBridge()
        assert bridge.get_version() == "unavailable"


class TestAgentTypeMap:
    def test_all_our_types_mapped(self):
        expected = {
            "master",
            "researcher",
            "coder",
            "reviewer",
            "falsifier",
            "writer",
            "cleaner",
        }
        assert expected == set(AGENT_TYPE_MAP.keys())
