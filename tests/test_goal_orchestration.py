"""Tests for GOAL.md-driven orchestration."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from core.onboarding import generate_goal_milestones, _generate_milestones_keywords


def test_infer_topics_from_goal_with_claude():
    """When Claude returns topics, they are used."""
    from cli.main import _infer_topics_from_goal

    with patch("core.claude_helper.call_claude_json") as mock_claude:
        mock_claude.return_value = ["deep-learning", "computer-vision", "protein-folding"]
        topics = _infer_topics_from_goal("A project about deep learning and computer vision")
        assert "deep-learning" in topics
        assert "computer-vision" in topics
        assert "ricet" in topics
        assert "research-automation" in topics


def test_infer_topics_fallback_without_claude():
    """When Claude is unavailable, returns base topics only (no hardcoded map)."""
    from cli.main import _infer_topics_from_goal

    # In pytest, Claude is auto-blocked, so this exercises the fallback
    topics = _infer_topics_from_goal("A project about deep learning")
    assert topics == ["research-automation", "ricet"]


def test_infer_topics_empty():
    from cli.main import _infer_topics_from_goal

    topics = _infer_topics_from_goal("")
    assert "ricet" in topics
    assert "research-automation" in topics


def test_infer_topics_max_20():
    from cli.main import _infer_topics_from_goal

    with patch("core.claude_helper.call_claude_json") as mock_claude:
        # Return more than 20 topics
        mock_claude.return_value = [f"topic-{i}" for i in range(25)]
        topics = _infer_topics_from_goal("some project text")
        assert len(topics) <= 20


def test_generate_milestones_keywords_basic():
    milestones = _generate_milestones_keywords(
        "This is a basic research project about data analysis."
    )
    assert len(milestones) >= 5
    assert any("literature" in m.lower() or "review" in m.lower() for m in milestones)
    assert any("paper" in m.lower() or "draft" in m.lower() for m in milestones)


def test_generate_milestones_keywords_model():
    milestones = _generate_milestones_keywords(
        "Train a transformer model on a new dataset"
    )
    assert len(milestones) >= 5
    assert any("model" in m.lower() or "architecture" in m.lower() for m in milestones)
    assert any("dataset" in m.lower() for m in milestones)


def test_generate_milestones_keywords_max_10():
    milestones = _generate_milestones_keywords(
        "Train a model on a dataset with deep learning"
    )
    assert len(milestones) <= 10


def test_generate_milestones_empty():
    assert generate_goal_milestones("") == []
    assert generate_goal_milestones("too short") == []
    assert generate_goal_milestones("   ") == []


def test_generate_milestones_falls_back_to_keywords():
    """When Claude is unavailable (pytest blocks it), falls back to keywords."""
    goal = (
        "This project trains a deep learning model on genomics data "
        "to predict protein folding structures. " * 3
    )
    milestones = generate_goal_milestones(goal)
    assert len(milestones) >= 5
    # Should contain keyword-based milestones
    assert any("literature" in m.lower() or "review" in m.lower() for m in milestones)


def test_configure_github_repo_from_goal(tmp_path):
    from cli.main import _configure_github_repo_from_goal

    goal = tmp_path / "knowledge" / "GOAL.md"
    goal.parent.mkdir(parents=True)
    goal.write_text(
        "# Goal\n\n"
        "This project investigates deep learning for protein folding prediction.\n"
    )

    calls = []

    def mock_run_cmd(cmd):
        calls.append(cmd)
        return MagicMock(returncode=0)

    _configure_github_repo_from_goal(
        tmp_path,
        "test-proj",
        "https://github.com/user/test-proj",
        run_cmd=mock_run_cmd,
    )

    # Should have called gh repo edit with description
    assert len(calls) >= 1
    assert any("--description" in str(c) for c in calls)
    # Topics always include base topics (ricet, research-automation)
    assert any("--add-topic" in str(c) for c in calls)


def test_configure_github_repo_no_goal(tmp_path):
    from cli.main import _configure_github_repo_from_goal

    calls = []

    def mock_run_cmd(cmd):
        calls.append(cmd)
        return MagicMock(returncode=0)

    # No GOAL.md file => should do nothing
    _configure_github_repo_from_goal(
        tmp_path,
        "test-proj",
        "https://github.com/user/test-proj",
        run_cmd=mock_run_cmd,
    )
    assert calls == []


def test_configure_github_repo_empty_goal(tmp_path):
    from cli.main import _configure_github_repo_from_goal

    goal = tmp_path / "knowledge" / "GOAL.md"
    goal.parent.mkdir(parents=True)
    goal.write_text("# Goal\n\n")  # Only header, no content

    calls = []

    def mock_run_cmd(cmd):
        calls.append(cmd)
        return MagicMock(returncode=0)

    _configure_github_repo_from_goal(
        tmp_path,
        "test-proj",
        "https://github.com/user/test-proj",
        run_cmd=mock_run_cmd,
    )
    # Only header lines => no meaningful content => should do nothing
    assert calls == []


def test_configure_github_repo_owner_repo_parsing(tmp_path):
    from cli.main import _configure_github_repo_from_goal

    goal = tmp_path / "knowledge" / "GOAL.md"
    goal.parent.mkdir(parents=True)
    goal.write_text("# Goal\n\nResearch into machine learning methods.\n")

    calls = []

    def mock_run_cmd(cmd):
        calls.append(cmd)
        return MagicMock(returncode=0)

    _configure_github_repo_from_goal(
        tmp_path,
        "my-proj",
        "https://github.com/myuser/my-proj.git",
        run_cmd=mock_run_cmd,
    )
    # Should parse owner/repo correctly, stripping .git
    assert any("myuser/my-proj" in str(c) for c in calls)
