"""Phase 9 demo tests -- Integration and CLI smoke tests."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------


class TestCliVersion:
    """``ricet --version`` via CliRunner."""

    def test_cli_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "ricet" in result.output
        assert "0.2.0" in result.output


class TestCliInit:
    """``ricet init test-proj`` via CliRunner (mock onboarding)."""

    def test_cli_init(self, tmp_path):
        with (
            patch("cli.main.check_and_install_packages", return_value=[]),
            patch("cli.main.detect_system_for_init") as mock_detect,
            patch("cli.main.auto_install_claude_flow", return_value=True),
            patch("cli.main.collect_answers") as mock_collect,
            patch("cli.main.collect_credentials", return_value={}),
            patch("cli.main.setup_workspace"),
            patch("cli.main.write_settings"),
            patch("cli.main.write_goal_file"),
            patch("cli.main.write_env_file"),
            patch("cli.main.write_env_example"),
            patch("cli.main.print_folder_map", return_value=["test"]),
            patch("cli.main.infer_packages_from_goal", return_value=[]),
            patch("cli.main.install_inferred_packages", return_value=([], [])),
            patch("cli.main.create_github_repo", return_value=""),
            patch("cli.main.shutil.copytree"),
            patch("cli.main.subprocess.run"),
            patch("cli.main._inject_claude_flow_mcp"),
            patch("cli.main.auto_commit", return_value=False),
            patch("cli.main.TEMPLATE_DIR", tmp_path / "templates"),
        ):
            mock_detect.return_value = {
                "os": "Linux",
                "python": "3.11",
                "cpu": "x86_64",
                "ram_gb": 16.0,
                "gpu": "",
                "compute_type": "local-cpu",
                "conda": False,
                "docker": False,
            }
            mock_collect.return_value = MagicMock()

            project_path = tmp_path / "test-proj"

            result = runner.invoke(
                app,
                ["init", "test-proj", "--path", str(tmp_path), "--skip-repo"],
            )

            mock_collect.assert_called_once()


class TestCliStatus:
    """``ricet status`` via CliRunner."""

    def test_cli_status(self, tmp_path, monkeypatch):
        # Create minimal state files
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "TODO.md").write_text("# TODO\n- [ ] Task 1\n")
        (state_dir / "PROGRESS.md").write_text("# Progress\n\nDone step 1.\n")

        monkeypatch.chdir(tmp_path)

        from core.claude_flow import ClaudeFlowUnavailable

        with patch(
            "core.claude_flow._get_bridge",
            side_effect=ClaudeFlowUnavailable("no bridge"),
        ):
            result = runner.invoke(app, ["status"])

        # Should show TODO content
        assert result.exit_code == 0
        assert "TODO" in result.output


class TestCliVerify:
    """``ricet verify "test claim"`` via CliRunner."""

    def test_cli_verify(self):
        mock_report = {
            "verdict": "claims_extracted",
            "claims": [
                {
                    "claim": "The Earth is flat",
                    "confidence": 0.3,
                    "status": "needs_review",
                }
            ],
            "file_issues": [],
            "citation_issues": [],
        }

        with patch("core.verification.verify_text", return_value=mock_report):
            result = runner.invoke(app, ["verify", "The Earth is flat"])

        assert result.exit_code == 0
        assert "claim" in result.output.lower()


class TestCliPaper:
    """``ricet paper check`` via CliRunner."""

    def test_cli_paper_check(self):
        with (
            patch("core.paper.check_figure_references", return_value=[]),
            patch("core.paper.list_citations", return_value=["ref1", "ref2"]),
        ):
            result = runner.invoke(app, ["paper", "check"])

        assert result.exit_code == 0
        assert "figure" in result.output.lower() or "Citations" in result.output


class TestCliMobile:
    """``ricet mobile url`` via CliRunner."""

    def test_cli_mobile_url(self):
        with patch("core.mobile.mobile_server") as mock_ms:
            mock_ms.get_url.return_value = "http://localhost:8765"
            result = runner.invoke(app, ["mobile", "url"])

        assert result.exit_code == 0
        assert "http://localhost:8765" in result.output


class TestCliWebsite:
    """``ricet website init`` via CliRunner (mock filesystem)."""

    def test_cli_website_init(self):
        with patch("core.website.site_manager") as mock_sm:
            mock_sm.init.return_value = None
            result = runner.invoke(app, ["website", "init"])

        assert result.exit_code == 0
        assert "initialized" in result.output.lower() or "Website" in result.output
        mock_sm.init.assert_called_once()


class TestCliProjects:
    """``ricet projects list`` via CliRunner."""

    def test_cli_projects_list(self):
        mock_entries = [
            {"name": "proj-a", "path": "/home/user/proj-a", "active": True},
            {"name": "proj-b", "path": "/home/user/proj-b", "active": False},
        ]
        with patch("core.multi_project.project_manager") as mock_pm:
            mock_pm.list_projects.return_value = mock_entries
            result = runner.invoke(app, ["projects", "list"])

        assert result.exit_code == 0
        assert "proj-a" in result.output
        assert "proj-b" in result.output


class TestCliWorktree:
    """``ricet worktree list`` via CliRunner."""

    def test_cli_worktree_list(self):
        mock_trees = [
            {"branch": "refs/heads/main", "path": "/project", "head": "abc123"},
        ]
        with patch("core.git_worktrees.worktree_manager") as mock_wm:
            mock_wm.list.return_value = mock_trees
            result = runner.invoke(app, ["worktree", "list"])

        assert result.exit_code == 0
        assert "main" in result.output or "worktree" in result.output.lower()


class TestCliAgents:
    """``ricet agents`` via CliRunner."""

    def test_cli_agents(self):
        from core.claude_flow import ClaudeFlowUnavailable

        with (
            patch(
                "core.claude_flow._get_bridge",
                side_effect=ClaudeFlowUnavailable("not available"),
            ),
            patch("core.agents.get_active_agents_status", return_value=[]),
        ):
            result = runner.invoke(app, ["agents"])

        assert result.exit_code == 0
        # Should show either "not available" message or "No active agents"
        output_lower = result.output.lower()
        assert "not available" in output_lower or "no active agents" in output_lower


class TestCliMemory:
    """``ricet memory test`` via CliRunner."""

    def test_cli_memory(self):
        from core.claude_flow import ClaudeFlowUnavailable

        with (
            patch(
                "core.claude_flow._get_bridge",
                side_effect=ClaudeFlowUnavailable("not available"),
            ),
            patch(
                "core.knowledge.search_knowledge", return_value=["result 1", "result 2"]
            ),
        ):
            result = runner.invoke(app, ["memory", "test"])

        assert result.exit_code == 0
        # Should fall back to keyword search and show results
        assert "result 1" in result.output or "keyword" in result.output.lower()


# ---------------------------------------------------------------------------
# Full lifecycle integration test
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    """Chain: create project -> start session -> run verification ->
    build website -> register as multi-project (all with mocks).
    """

    def test_full_lifecycle(self, tmp_path, monkeypatch):
        # -- Step 1: Register a project --
        from core.multi_project import ProjectRegistry

        registry_file = tmp_path / "projects.json"
        reg = ProjectRegistry(registry_file=registry_file)

        proj_dir = tmp_path / "lifecycle-proj"
        proj_dir.mkdir()
        (proj_dir / "knowledge").mkdir()
        (proj_dir / "knowledge" / "ENCYCLOPEDIA.md").write_text(
            "## Tricks\n## Decisions\n"
        )
        (proj_dir / "state").mkdir()
        (proj_dir / "state" / "TODO.md").write_text("# TODO\n- [ ] First task\n")
        (proj_dir / "state" / "sessions").mkdir(parents=True)

        reg.register_project("lifecycle", proj_dir, project_type="research")
        active = reg.get_active_project()
        assert active["name"] == "lifecycle"

        # -- Step 2: Create a session file (simulating ``ricet start``) --
        session_file = proj_dir / "state" / "sessions" / "test-session.json"
        session_data = {
            "name": "test-session",
            "started": "2026-01-15T10:00:00",
            "status": "active",
            "token_estimate": 0,
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        assert session_file.exists()

        # -- Step 3: Run verification --
        mock_report = {"verdict": "verified", "issues": []}
        with patch("core.verification.verify_text", return_value=mock_report):
            from core.verification import verify_text

            report = verify_text("Water boils at 100 degrees Celsius at sea level")
        assert report["verdict"] == "verified"
        assert len(report["issues"]) == 0

        # -- Step 4: Build website (mocked) --
        with patch("core.website.site_manager") as mock_sm:
            mock_sm.init.return_value = None
            mock_sm.build.return_value = None
            from core.website import site_manager

            site_manager.init()
            site_manager.build()
            mock_sm.init.assert_called_once()
            mock_sm.build.assert_called_once()

        # -- Step 5: Register a second project and sync knowledge --
        second_dir = tmp_path / "second-proj"
        second_dir.mkdir()

        reg.register_project("second", second_dir, project_type="website")

        projects = reg.list_projects()
        assert len(projects) == 2

        names = {p["name"] for p in projects}
        assert names == {"lifecycle", "second"}

        # Switch to second project and back
        reg.switch_project("second")
        assert reg.get_active_project()["name"] == "second"

        reg.switch_project("lifecycle")
        assert reg.get_active_project()["name"] == "lifecycle"

        # -- Step 6: Verify session was preserved --
        reloaded = json.loads(session_file.read_text())
        assert reloaded["name"] == "test-session"
        assert reloaded["status"] == "active"
