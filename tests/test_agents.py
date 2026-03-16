"""Tests for agent routing and orchestration."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from core.agents import (
    AgentType,
    TaskResult,
    _route_task_keywords,
    execute_agent_task,
    get_agent_prompt,
    route_task,
)


def test_route_to_researcher():
    assert route_task("search for papers on transformers") == AgentType.RESEARCHER
    assert route_task("literature review on GANs") == AgentType.RESEARCHER


def test_route_to_coder():
    assert route_task("implement the training loop") == AgentType.CODER
    assert route_task("fix the bug in data loading") == AgentType.CODER


def test_route_to_reviewer():
    assert route_task("review the code quality") == AgentType.REVIEWER


def test_route_to_falsifier():
    assert route_task("falsify and verify the data leakage") == AgentType.FALSIFIER
    assert route_task("detect leakage in the training pipeline") == AgentType.FALSIFIER


def test_route_to_writer():
    assert route_task("draft the introduction section") == AgentType.WRITER
    assert route_task("write the abstract") == AgentType.WRITER


def test_route_to_cleaner():
    assert route_task("refactor the preprocessing module") == AgentType.CLEANER
    assert route_task("optimize the data pipeline") == AgentType.CLEANER


def test_route_default():
    # Unrecognized tasks default to coder
    assert route_task("do something vague") == AgentType.CODER


# --- Bridge-integrated tests ---


def test_route_task_keywords_fallback():
    """_route_task_keywords always uses keyword matching."""
    assert _route_task_keywords("search for papers") == AgentType.RESEARCHER
    assert _route_task_keywords("unknown thing") == AgentType.CODER


def test_route_task_via_bridge():
    """When bridge returns a valid agent_type, route_task uses it."""
    mock_bridge = MagicMock()
    mock_bridge.route_model.return_value = {"agent_type": "researcher"}
    with patch("core.agents._get_bridge", return_value=mock_bridge):
        assert route_task("anything") == AgentType.RESEARCHER


def test_route_task_bridge_unavailable_falls_back():
    """When bridge raises, route_task falls back to keyword matching."""
    from core.claude_flow import ClaudeFlowUnavailable

    with patch("core.agents._get_bridge", side_effect=ClaudeFlowUnavailable("nope")):
        assert route_task("implement the feature") == AgentType.CODER


def test_execute_agent_task_via_bridge():
    """When bridge is available, execute_agent_task uses spawn_agent."""
    mock_bridge = MagicMock()
    mock_bridge.spawn_agent.return_value = {
        "status": "success",
        "output": "done via claude-flow",
        "tokens_used": 500,
    }
    with patch("core.agents._get_bridge", return_value=mock_bridge):
        result = execute_agent_task(AgentType.CODER, "fix the bug")
        assert result.status == "success"
        assert "done via claude-flow" in result.output
        assert result.tokens_used == 500
        mock_bridge.spawn_agent.assert_called_once_with("coder", "fix the bug")


def test_execute_agent_task_bridge_fallback():
    """When bridge is unavailable, execute_agent_task falls back to legacy."""
    from core.claude_flow import ClaudeFlowUnavailable

    with patch("core.agents._get_bridge", side_effect=ClaudeFlowUnavailable("nope")):
        with patch("core.agents._execute_agent_task_legacy") as mock_legacy:
            mock_legacy.return_value = TaskResult(
                agent=AgentType.CODER,
                task="test",
                status="success",
            )
            result = execute_agent_task(AgentType.CODER, "test")
            assert result.status == "success"
            mock_legacy.assert_called_once()


def test_execute_agent_task_legacy_includes_model_flag():
    """_execute_agent_task_legacy must include --model in the subprocess command."""
    from core.agents import _execute_agent_task_legacy

    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.stdout = iter(["output line\n"])
    fake_proc.wait = MagicMock()

    with patch("core.agents.subprocess.Popen", return_value=fake_proc) as mock_popen:
        with patch("core.agents.get_agent_prompt", return_value="You are a coder."):
            _execute_agent_task_legacy(AgentType.CODER, "implement a data loader")

    cmd = mock_popen.call_args[0][0]
    assert "--model" in cmd, f"--model flag missing from command: {cmd}"


def test_execute_agent_task_legacy_model_with_skip_permissions():
    """--model flag should be present even with dangerously_skip_permissions."""
    from core.agents import _execute_agent_task_legacy

    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.stdout = iter(["output line\n"])
    fake_proc.wait = MagicMock()

    with patch("core.agents.subprocess.Popen", return_value=fake_proc) as mock_popen:
        with patch("core.agents.get_agent_prompt", return_value="You are a coder."):
            _execute_agent_task_legacy(
                AgentType.CODER,
                "implement feature",
                dangerously_skip_permissions=True,
            )

    cmd = mock_popen.call_args[0][0]
    assert "--model" in cmd
    assert "--dangerously-skip-permissions" in cmd


# --- Agent prompt loading tests ---


def test_get_agent_prompt_from_project(tmp_path):
    """get_agent_prompt loads from project .claude/skills/ when files exist."""
    # CODER maps to skill "reproduce"
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "reproduce.md").write_text("You are the reproduce skill.")

    result = get_agent_prompt(AgentType.CODER, project_root=tmp_path)
    assert result == "You are the reproduce skill."


def test_get_agent_prompt_from_templates(tmp_path):
    """get_agent_prompt falls back to templates when project files are missing."""
    # CODER maps to skill "reproduce"
    result = get_agent_prompt(AgentType.CODER, project_root=tmp_path)
    template_file = (
        Path(__file__).resolve().parent.parent
        / "templates"
        / ".claude"
        / "skills"
        / "reproduce.md"
    )
    assert template_file.exists(), f"Template file missing: {template_file}"
    assert result == template_file.read_text()
    assert len(result) > 0


def test_get_agent_prompt_project_overrides_template(tmp_path):
    """Project skill prompt takes priority over template."""
    # RESEARCHER maps to skill "lit-review"
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "lit-review.md").write_text("Custom lit-review prompt.")

    result = get_agent_prompt(AgentType.RESEARCHER, project_root=tmp_path)
    assert result == "Custom lit-review prompt."


def test_skill_template_prompts_are_nonempty():
    """All agent types have non-empty template skill files."""
    from core.agents import get_agent_prompt as _gap

    templates_dir = (
        Path(__file__).resolve().parent.parent / "templates" / ".claude" / "skills"
    )
    # Agent-to-skill mapping (mirrors get_agent_prompt._agent_to_skill)
    agent_to_skill = {
        AgentType.RESEARCHER: "lit-review",
        AgentType.REVIEWER: "experiment-review",
        AgentType.WRITER: "paper-draft",
        AgentType.FALSIFIER: "falsify",
        AgentType.CODER: "reproduce",
        AgentType.CLEANER: "research-retro",
        AgentType.SLIDE_MAKER: "slides",
        AgentType.MASTER: "overnight",
    }
    for agent_type, skill_name in agent_to_skill.items():
        skill_file = templates_dir / f"{skill_name}.md"
        assert skill_file.exists(), f"Missing skill template for {agent_type.value} -> {skill_name}"
        content = skill_file.read_text()
        assert (
            len(content.strip()) > 50
        ), f"Skill template for {skill_name} is too short ({len(content)} chars)"


def test_get_agent_prompt_fallback_finds_template(tmp_path):
    """get_agent_prompt finds template even when project has no skills."""
    result = get_agent_prompt(AgentType.CODER, project_root=tmp_path)
    # Template fallback should find reproduce.md
    assert len(result) > 0
