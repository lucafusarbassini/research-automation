"""Tests for MCP auto-discovery and classification."""

from core.mcps import (
    classify_task,
    get_mcps_for_task,
    get_priority_mcps,
    install_priority_mcps,
    load_mcp_config,
)


def test_load_mcp_config():
    config = load_mcp_config()
    assert "tier1_essential" in config
    assert "mcps" in config["tier1_essential"]


def test_classify_task_always_includes_tier1():
    tiers = classify_task("anything at all")
    assert "tier1_essential" in tiers


def test_classify_task_data_keywords():
    tiers = classify_task("query the database for results")
    assert "tier2_data" in tiers


def test_classify_task_ml_keywords():
    tiers = classify_task("train the neural network model")
    assert "tier3_ml" in tiers


def test_classify_task_math_keywords():
    tiers = classify_task("compute the derivative of f(x)")
    assert "tier4_math" in tiers


def test_classify_task_paper_keywords():
    tiers = classify_task("write the paper manuscript")
    assert "tier5_paper" in tiers


def test_classify_task_multiple_tiers():
    tiers = classify_task("train a model and write a paper about the data")
    assert "tier3_ml" in tiers
    assert "tier5_paper" in tiers
    assert "tier2_data" in tiers


def test_get_mcps_for_task_includes_essentials():
    mcps = get_mcps_for_task("simple task")
    assert "git" in mcps
    assert "filesystem" in mcps


def test_get_mcps_for_task_ml():
    mcps = get_mcps_for_task("train a neural network")
    assert "jupyter-mcp-server" in mcps
    assert "huggingface-mcp" in mcps


# --- Bridge-integrated tests ---

from unittest.mock import MagicMock, patch

from core.mcps import get_claude_flow_mcp_config


def test_get_claude_flow_mcp_config_available():
    mock_bridge = MagicMock()
    with patch("core.mcps._get_bridge", return_value=mock_bridge):
        config = get_claude_flow_mcp_config()
        assert "tier0_claude_flow" in config
        assert "claude-flow" in config["tier0_claude_flow"]["mcps"]


def test_config_has_tier0_orchestration():
    """tier0_orchestration section exists with sequential-thinking and claude-flow."""
    config = load_mcp_config()
    assert "tier0_orchestration" in config
    mcps = config["tier0_orchestration"]["mcps"]
    assert "sequential-thinking" in mcps
    assert "claude-flow" in mcps


def test_config_has_puppeteer_in_tier1():
    """Puppeteer should be in tier1_essential."""
    config = load_mcp_config()
    assert "puppeteer" in config["tier1_essential"]["mcps"]


def test_config_has_apidog_in_tier2():
    """Apidog should be in tier2_data."""
    config = load_mcp_config()
    assert "apidog-mcp" in config["tier2_data"]["mcps"]


def test_get_priority_mcps_includes_sequential_thinking():
    """get_priority_mcps always returns sequential-thinking as tier-0."""
    from core.claude_flow import ClaudeFlowUnavailable

    with patch("core.mcps._get_bridge", side_effect=ClaudeFlowUnavailable("no")):
        mcps = get_priority_mcps()
    assert "sequential-thinking" in mcps
    assert mcps["sequential-thinking"]["tier"] == 0


def test_get_priority_mcps_includes_claude_flow_when_available():
    """get_priority_mcps includes claude-flow when the bridge is available."""
    mock_bridge = MagicMock()
    with patch("core.mcps._get_bridge", return_value=mock_bridge):
        mcps = get_priority_mcps()
    assert "claude-flow" in mcps
    assert mcps["claude-flow"]["tier"] == 0


def test_install_priority_mcps_returns_dict():
    """install_priority_mcps returns a dict mapping names to booleans."""
    from core.claude_flow import ClaudeFlowUnavailable

    with (
        patch("core.mcps._get_bridge", side_effect=ClaudeFlowUnavailable("no")),
        patch("core.mcps.install_mcp", return_value=True) as mock_install,
    ):
        results = install_priority_mcps()
    assert isinstance(results, dict)
    # sequential-thinking should be present
    assert "sequential-thinking" in results


def test_get_claude_flow_mcp_config_unavailable():
    from core.claude_flow import ClaudeFlowUnavailable

    with patch("core.mcps._get_bridge", side_effect=ClaudeFlowUnavailable("no")):
        config = get_claude_flow_mcp_config()
        assert config == {}
