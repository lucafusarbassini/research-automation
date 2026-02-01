"""Tests for agent routing and orchestration."""

from core.agents import AgentType, route_task


def test_route_to_researcher():
    assert route_task("search for papers on transformers") == AgentType.RESEARCHER
    assert route_task("literature review on GANs") == AgentType.RESEARCHER


def test_route_to_coder():
    assert route_task("implement the training loop") == AgentType.CODER
    assert route_task("fix the bug in data loading") == AgentType.CODER


def test_route_to_reviewer():
    assert route_task("review the code quality") == AgentType.REVIEWER


def test_route_to_falsifier():
    assert route_task("validate the experimental results") == AgentType.FALSIFIER
    assert route_task("falsify and verify the data leakage") == AgentType.FALSIFIER


def test_route_to_writer():
    assert route_task("draft the introduction section") == AgentType.WRITER
    assert route_task("write the abstract") == AgentType.WRITER


def test_route_to_cleaner():
    assert route_task("refactor the preprocessing module") == AgentType.CLEANER
    assert route_task("optimize the data pipeline") == AgentType.CLEANER


def test_route_default():
    # Unrecognized tasks default to coder
    assert route_task("do something vague") == AgentType.CODER
