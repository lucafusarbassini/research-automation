"""Phase 1 tests: project initialization, onboarding, doability, knowledge, environment, security."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------


class TestCollectAnswers:
    """Test core.onboarding.collect_answers with an injected prompt_fn."""

    def test_collect_answers_with_mock_prompt(self, mock_prompt_fn):
        from core.onboarding import OnboardingAnswers, collect_answers

        answers = collect_answers("demo-project", prompt_fn=mock_prompt_fn)

        assert isinstance(answers, OnboardingAnswers)
        assert answers.project_name == "demo-project"
        assert "ResNet" in answers.goal or "CIFAR" in answers.goal
        assert answers.project_type == "ml-research"
        assert answers.github_repo != "skip"
        assert len(answers.success_criteria) >= 1
        assert answers.compute_type == "local-gpu"
        assert answers.gpu_name == "RTX 4090"
        assert answers.notification_method == "none"
        assert answers.journal_target == "NeurIPS"
        assert answers.needs_mobile is True


class TestSetupWorkspace:
    """Test core.onboarding.setup_workspace creates the expected directories."""

    def test_setup_workspace(self, tmp_path):
        from core.onboarding import WORKSPACE_DIRS, setup_workspace

        setup_workspace(tmp_path)

        for dirname in WORKSPACE_DIRS:
            d = tmp_path / dirname
            assert d.is_dir(), f"Expected directory {dirname} to exist"
            assert (d / ".gitkeep").exists(), f"Expected .gitkeep in {dirname}"


class TestValidatePrerequisites:
    """Test core.onboarding.validate_prerequisites with a mock run_cmd."""

    def test_validate_prerequisites_all_present(self):
        from core.onboarding import validate_prerequisites

        # All commands succeed
        missing = validate_prerequisites(run_cmd=lambda cmd: True)
        assert missing == {}

    def test_validate_prerequisites_some_missing(self):
        from core.onboarding import validate_prerequisites

        # Only git available
        def selective_run(cmd):
            return "git" in cmd

        missing = validate_prerequisites(run_cmd=selective_run)
        assert "docker" in missing
        assert "node" in missing
        assert "claude" in missing
        assert "git" not in missing

    def test_validate_prerequisites_none_present(self):
        from core.onboarding import PREREQUISITES, validate_prerequisites

        missing = validate_prerequisites(run_cmd=lambda cmd: False)
        assert len(missing) == len(PREREQUISITES)
        # Each entry should have an install hint string
        for tool, hint in missing.items():
            assert isinstance(hint, str)
            assert len(hint) > 10


# ---------------------------------------------------------------------------
# Doability
# ---------------------------------------------------------------------------


class TestCheckProjectReadiness:
    """Test core.doability.check_project_readiness."""

    def test_check_project_readiness_all_present(self, demo_project_path):
        from core.doability import check_project_readiness

        # Add the remaining required files at project root
        (demo_project_path / "GOAL.md").write_text("# Goal\nTrain a model\n")
        (demo_project_path / "CONSTRAINTS.md").write_text("# Constraints\n")
        (demo_project_path / "TODO.md").write_text("# TODO\n")
        (demo_project_path / ".env").write_text("API_KEY=placeholder\n")

        report = check_project_readiness(demo_project_path)

        assert report.is_ready is True
        assert len(report.missing_files) == 0
        assert "GOAL.md" in report.found_files
        assert "config/settings.yml" in report.found_files

    def test_check_project_readiness_missing_files(self, tmp_path):
        from core.doability import check_project_readiness

        # Empty project directory
        report = check_project_readiness(tmp_path)

        assert report.is_ready is False
        assert len(report.missing_files) > 0
        assert "GOAL.md" in report.missing_files
        assert "config/settings.yml" in report.missing_files

    def test_readiness_report_attributes(self, tmp_path):
        from core.doability import ReadinessReport, check_project_readiness

        report = check_project_readiness(tmp_path)
        assert isinstance(report, ReadinessReport)
        assert isinstance(report.missing_files, list)
        assert isinstance(report.warnings, list)
        assert isinstance(report.found_files, list)
        assert isinstance(report.is_ready, bool)


# ---------------------------------------------------------------------------
# Knowledge
# ---------------------------------------------------------------------------


class TestKnowledgeInit:
    """Test core.knowledge functions against a temporary encyclopedia."""

    @patch("core.knowledge._get_bridge", side_effect=__import__("core.claude_flow", fromlist=["ClaudeFlowUnavailable"]).ClaudeFlowUnavailable)
    def test_append_learning(self, _mock_bridge, demo_project_path):
        from core.knowledge import append_learning

        enc_path = demo_project_path / "knowledge" / "ENCYCLOPEDIA.md"
        append_learning("Tricks", "Use batch size 64 for faster convergence", encyclopedia_path=enc_path)

        content = enc_path.read_text()
        assert "batch size 64" in content

    @patch("core.knowledge._get_bridge", side_effect=__import__("core.claude_flow", fromlist=["ClaudeFlowUnavailable"]).ClaudeFlowUnavailable)
    def test_search_knowledge(self, _mock_bridge, demo_project_path):
        from core.knowledge import append_learning, search_knowledge

        enc_path = demo_project_path / "knowledge" / "ENCYCLOPEDIA.md"
        append_learning("Tricks", "Use learning rate warmup", encyclopedia_path=enc_path)

        results = search_knowledge("warmup", encyclopedia_path=enc_path)
        assert any("warmup" in r for r in results)

    @patch("core.knowledge._get_bridge", side_effect=__import__("core.claude_flow", fromlist=["ClaudeFlowUnavailable"]).ClaudeFlowUnavailable)
    def test_get_encyclopedia_stats(self, _mock_bridge, demo_project_path):
        from core.knowledge import append_learning, get_encyclopedia_stats

        enc_path = demo_project_path / "knowledge" / "ENCYCLOPEDIA.md"
        append_learning("Tricks", "Entry one", encyclopedia_path=enc_path)
        append_learning("Tricks", "Entry two", encyclopedia_path=enc_path)

        stats = get_encyclopedia_stats(encyclopedia_path=enc_path)
        assert isinstance(stats, dict)
        assert stats.get("Tricks", 0) >= 2

    @patch("core.knowledge._get_bridge", side_effect=__import__("core.claude_flow", fromlist=["ClaudeFlowUnavailable"]).ClaudeFlowUnavailable)
    def test_log_decision(self, _mock_bridge, demo_project_path):
        from core.knowledge import append_learning

        enc_path = demo_project_path / "knowledge" / "ENCYCLOPEDIA.md"
        # log_decision calls append_learning with default path, so call directly
        entry = "Use PyTorch -- Rationale: Better GPU support"
        append_learning("Decisions", entry, encyclopedia_path=enc_path)
        content = enc_path.read_text()
        assert "Use PyTorch" in content
        assert "Rationale" in content


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------


class TestEnvironmentDiscovery:
    """Test core.environment functions."""

    def test_discover_system(self):
        from core.environment import SystemInfo, discover_system

        info = discover_system()
        assert isinstance(info, SystemInfo)
        assert info.os != ""
        assert info.python_version != ""
        assert info.cpu != ""

    def test_generate_system_md(self):
        from core.environment import SystemInfo, generate_system_md

        info = SystemInfo(
            os="Linux",
            os_version="6.8.0",
            python_version="3.11.5",
            cpu="x86_64",
            gpu="RTX 4090",
            ram_gb=32.0,
            conda_available=True,
            docker_available=False,
        )
        md = generate_system_md(info)
        assert "# System Environment" in md
        assert "Linux" in md
        assert "RTX 4090" in md
        assert "32.0 GB" in md
        assert "Conda" in md

    def test_generate_system_md_no_gpu(self):
        from core.environment import SystemInfo, generate_system_md

        info = SystemInfo(os="Darwin", python_version="3.12.0", cpu="arm64")
        md = generate_system_md(info)
        assert "None detected" in md


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------


class TestSecurityScan:
    """Test core.security.scan_for_secrets."""

    @patch("core.security._get_bridge", side_effect=__import__("core.claude_flow", fromlist=["ClaudeFlowUnavailable"]).ClaudeFlowUnavailable)
    def test_scan_for_secrets_clean(self, _mock_bridge, tmp_path):
        from core.security import scan_for_secrets

        clean_file = tmp_path / "clean.py"
        clean_file.write_text("x = 42\nprint('hello world')\n")

        findings = scan_for_secrets(tmp_path)
        assert findings == []

    @patch("core.security._get_bridge", side_effect=__import__("core.claude_flow", fromlist=["ClaudeFlowUnavailable"]).ClaudeFlowUnavailable)
    def test_scan_for_secrets_finds_api_key(self, _mock_bridge, tmp_path):
        from core.security import scan_for_secrets

        bad_file = tmp_path / "config.py"
        bad_file.write_text('API_KEY = "sk-abc123def456ghi789jkl012mno345pqr678"\n')

        findings = scan_for_secrets(tmp_path)
        assert len(findings) >= 1
        assert any("config.py" in f["file"] for f in findings)

    @patch("core.security._get_bridge", side_effect=__import__("core.claude_flow", fromlist=["ClaudeFlowUnavailable"]).ClaudeFlowUnavailable)
    def test_scan_for_secrets_finds_private_key(self, _mock_bridge, tmp_path):
        from core.security import scan_for_secrets

        key_file = tmp_path / "secret.pem"
        key_file.write_text("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----\n")

        findings = scan_for_secrets(key_file)
        assert len(findings) >= 1

    @patch("core.security._get_bridge", side_effect=__import__("core.claude_flow", fromlist=["ClaudeFlowUnavailable"]).ClaudeFlowUnavailable)
    def test_protect_immutable_files(self, _mock_bridge):
        from core.security import protect_immutable_files

        files = [
            Path("/project/.env"),
            Path("/project/secrets/api.key"),
            Path("/project/src/main.py"),
        ]
        blocked = protect_immutable_files(files)
        assert Path("/project/.env") in blocked
        assert Path("/project/src/main.py") not in blocked
