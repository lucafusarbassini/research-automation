"""Tests for git worktrees module — parallel branch work without subagent collisions."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from core.git_worktrees import (
    WorktreeContext,
    create_worktree,
    ensure_branch_worktree,
    list_worktrees,
    merge_worktree_results,
    remove_worktree,
    run_in_worktree,
)

# ---------------------------------------------------------------------------
# create_worktree
# ---------------------------------------------------------------------------


@patch("core.git_worktrees.subprocess.run")
def test_create_worktree_default_path(mock_run, tmp_path):
    """create_worktree derives path from branch name when path is None."""
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )

    with patch("core.git_worktrees.WORKTREES_DIR", tmp_path / "worktrees"):
        result = create_worktree("feature/new-parser")

    assert "feature-new-parser" in str(result)
    assert mock_run.call_count == 2  # rev-parse check + worktree add
    # Second call is the actual worktree add
    cmd = mock_run.call_args_list[1][0][0]
    assert cmd[:3] == ["git", "worktree", "add"]
    assert "feature/new-parser" in cmd


@patch("core.git_worktrees.subprocess.run")
def test_create_worktree_explicit_path(mock_run, tmp_path):
    """create_worktree uses explicit path when provided."""
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )

    target = tmp_path / "my-worktree"
    result = create_worktree("dev", path=target)

    assert result == target
    cmd = mock_run.call_args[0][0]
    assert str(target) in cmd


@patch("core.git_worktrees.subprocess.run")
def test_create_worktree_git_failure(mock_run):
    """create_worktree raises on git failure."""
    mock_run.side_effect = subprocess.CalledProcessError(
        1, "git", stderr="fatal: branch exists"
    )

    with pytest.raises(subprocess.CalledProcessError):
        create_worktree("broken-branch")


# ---------------------------------------------------------------------------
# list_worktrees
# ---------------------------------------------------------------------------


@patch("core.git_worktrees.subprocess.run")
def test_list_worktrees(mock_run):
    """list_worktrees parses porcelain output into dicts."""
    porcelain = (
        "worktree /home/user/project\n"
        "HEAD abc1234\n"
        "branch refs/heads/main\n"
        "\n"
        "worktree /home/user/project/.worktrees/feat\n"
        "HEAD def5678\n"
        "branch refs/heads/feat\n"
        "\n"
    )
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout=porcelain, stderr=""
    )

    trees = list_worktrees()

    assert len(trees) == 2
    assert trees[0]["path"] == "/home/user/project"
    assert trees[0]["branch"] == "refs/heads/main"
    assert trees[1]["head"] == "def5678"


# ---------------------------------------------------------------------------
# remove_worktree
# ---------------------------------------------------------------------------


@patch("core.git_worktrees.subprocess.run")
def test_remove_worktree_success(mock_run):
    """remove_worktree returns True on success."""
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )

    assert remove_worktree(Path("/tmp/wt")) is True
    cmd = mock_run.call_args[0][0]
    assert cmd == ["git", "worktree", "remove", "--force", "/tmp/wt"]


@patch("core.git_worktrees.subprocess.run")
def test_remove_worktree_failure(mock_run):
    """remove_worktree returns False on error."""
    mock_run.side_effect = subprocess.CalledProcessError(1, "git")

    assert remove_worktree(Path("/tmp/gone")) is False


# ---------------------------------------------------------------------------
# run_in_worktree
# ---------------------------------------------------------------------------


@patch("core.git_worktrees.remove_worktree")
@patch("core.git_worktrees.subprocess.run")
@patch("core.git_worktrees.ensure_branch_worktree")
def test_run_in_worktree(mock_ensure, mock_run, mock_remove):
    """run_in_worktree executes command inside the worktree directory."""
    wt_path = Path("/tmp/worktrees/feat")
    mock_ensure.return_value = wt_path
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="ok", stderr=""
    )

    result = run_in_worktree("feat", "echo hello")

    mock_ensure.assert_called_once_with("feat")
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["cwd"] == wt_path


# ---------------------------------------------------------------------------
# WorktreeContext
# ---------------------------------------------------------------------------


@patch("core.git_worktrees.remove_worktree")
@patch("core.git_worktrees.create_worktree")
def test_worktree_context_manager(mock_create, mock_remove):
    """WorktreeContext creates on enter, removes on exit."""
    wt_path = Path("/tmp/worktrees/ctx-branch")
    mock_create.return_value = wt_path

    with WorktreeContext("ctx-branch") as path:
        assert path == wt_path

    mock_create.assert_called_once_with("ctx-branch", None)
    mock_remove.assert_called_once_with(wt_path)


@patch("core.git_worktrees.remove_worktree")
@patch("core.git_worktrees.create_worktree")
def test_worktree_context_cleans_up_on_exception(mock_create, mock_remove):
    """WorktreeContext still removes worktree when body raises."""
    wt_path = Path("/tmp/worktrees/explode")
    mock_create.return_value = wt_path

    with pytest.raises(RuntimeError):
        with WorktreeContext("explode") as path:
            raise RuntimeError("boom")

    mock_remove.assert_called_once_with(wt_path)


# ---------------------------------------------------------------------------
# ensure_branch_worktree
# ---------------------------------------------------------------------------


@patch("core.git_worktrees.create_worktree")
@patch("core.git_worktrees.list_worktrees")
def test_ensure_branch_worktree_existing(mock_list, mock_create):
    """ensure_branch_worktree returns existing path when worktree already exists."""
    mock_list.return_value = [
        {"path": "/tmp/worktrees/feat", "head": "abc", "branch": "refs/heads/feat"},
    ]

    result = ensure_branch_worktree("feat")

    assert result == Path("/tmp/worktrees/feat")
    mock_create.assert_not_called()


@patch("core.git_worktrees.create_worktree")
@patch("core.git_worktrees.list_worktrees")
def test_ensure_branch_worktree_creates_new(mock_list, mock_create):
    """ensure_branch_worktree creates worktree when none exists for branch."""
    mock_list.return_value = []
    mock_create.return_value = Path("/tmp/worktrees/new-feat")

    result = ensure_branch_worktree("new-feat")

    assert result == Path("/tmp/worktrees/new-feat")
    mock_create.assert_called_once_with("new-feat")


# ---------------------------------------------------------------------------
# merge_worktree_results
# ---------------------------------------------------------------------------


@patch("core.git_worktrees.subprocess.run")
def test_merge_worktree_results_success(mock_run):
    """merge_worktree_results returns True on clean merge."""
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )

    assert merge_worktree_results("feature-x", "main") is True

    cmds = [c[0][0] for c in mock_run.call_args_list]
    # Should checkout target, merge source, then checkout back
    assert ["git", "checkout", "main"] in cmds
    assert ["git", "merge", "feature-x", "--no-edit"] in cmds


@patch("core.git_worktrees.subprocess.run")
def test_merge_worktree_results_conflict(mock_run):
    """merge_worktree_results returns False on merge conflict."""

    def side_effect(cmd, **kwargs):
        if "merge" in cmd and "--abort" not in cmd:
            raise subprocess.CalledProcessError(1, "git", stderr="CONFLICT")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    mock_run.side_effect = side_effect

    assert merge_worktree_results("conflict-branch", "main") is False
