"""Tests for MCP auto-discovery and classification."""

from core.mcps import classify_task, get_mcps_for_task, load_mcp_config


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
