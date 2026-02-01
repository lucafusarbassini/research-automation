"""Tests for devops module — Claude Code as DevOps engineer."""

import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from core.devops import (
    DockerManager,
    check_infrastructure,
    deploy_github_pages,
    health_check,
    rotate_secrets,
    setup_ci_cd,
)


# ---------------------------------------------------------------------------
# check_infrastructure
# ---------------------------------------------------------------------------

class TestCheckInfrastructure:
    """Tests for check_infrastructure()."""

    @patch("core.devops.shutil.which")
    @patch("core.devops.subprocess.run")
    def test_all_tools_available(self, mock_run, mock_which):
        mock_which.return_value = "/usr/bin/tool"
        mock_run.return_value = MagicMock(
            returncode=0, stdout="1.0.0\n", stderr=""
        )
        result = check_infrastructure()
        assert isinstance(result, dict)
        assert result["docker"]["available"] is True
        assert result["git"]["available"] is True
        assert result["python"]["available"] is True

    @patch("core.devops.shutil.which")
    @patch("core.devops.subprocess.run")
    def test_missing_tool(self, mock_run, mock_which):
        def which_side(name):
            if name == "docker":
                return None
            return f"/usr/bin/{name}"

        mock_which.side_effect = which_side
        mock_run.return_value = MagicMock(
            returncode=0, stdout="1.0.0\n", stderr=""
        )
        result = check_infrastructure()
        assert result["docker"]["available"] is False
        assert result["docker"]["version"] == ""

    @patch("core.devops.shutil.which")
    @patch("core.devops.subprocess.run")
    def test_version_command_fails(self, mock_run, mock_which):
        mock_which.return_value = "/usr/bin/git"
        mock_run.side_effect = FileNotFoundError("not found")
        result = check_infrastructure()
        # Should not raise, gracefully marks version as empty
        for tool in result.values():
            assert "available" in tool


# ---------------------------------------------------------------------------
# DockerManager
# ---------------------------------------------------------------------------

class TestDockerManager:
    """Tests for DockerManager class."""

    @patch("core.devops.subprocess.run")
    def test_is_available_true(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="Docker version 24.0\n")
        dm = DockerManager()
        assert dm.is_available() is True

    @patch("core.devops.subprocess.run")
    def test_is_available_false(self, mock_run):
        mock_run.side_effect = FileNotFoundError("docker not found")
        dm = DockerManager()
        assert dm.is_available() is False

    @patch("core.devops.subprocess.run")
    def test_build_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        dm = DockerManager()
        assert dm.build("myapp:latest") is True
        call_args = mock_run.call_args[0][0]
        assert "docker" in call_args
        assert "build" in call_args
        assert "myapp:latest" in call_args

    @patch("core.devops.subprocess.run")
    def test_build_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        dm = DockerManager()
        assert dm.build("myapp:latest") is False

    @patch("core.devops.subprocess.run")
    def test_run_returns_container_id(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="abc123def456\n", stderr=""
        )
        dm = DockerManager()
        cid = dm.run("myapp:latest", ports={"8080": "80"})
        assert cid == "abc123def456"
        call_args = mock_run.call_args[0][0]
        assert "-p" in call_args
        assert "8080:80" in call_args

    @patch("core.devops.subprocess.run")
    def test_run_with_volumes(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="container789\n", stderr=""
        )
        dm = DockerManager()
        cid = dm.run("myapp:latest", volumes={"/host/data": "/app/data"})
        assert cid == "container789"
        call_args = mock_run.call_args[0][0]
        assert "-v" in call_args
        assert "/host/data:/app/data" in call_args

    @patch("core.devops.subprocess.run")
    def test_stop_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        dm = DockerManager()
        assert dm.stop("abc123") is True

    @patch("core.devops.subprocess.run")
    def test_logs(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="line1\nline2\n", stderr=""
        )
        dm = DockerManager()
        output = dm.logs("abc123", tail=10)
        assert "line1" in output
        call_args = mock_run.call_args[0][0]
        assert "--tail" in call_args
        assert "10" in call_args


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    """Tests for health_check()."""

    @patch("core.devops.urllib.request.urlopen")
    def test_healthy(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"status": "ok"}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        result = health_check("http://localhost:8080/health")
        assert result["healthy"] is True
        assert result["status_code"] == 200

    @patch("core.devops.urllib.request.urlopen")
    def test_unhealthy_timeout(self, mock_urlopen):
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("timeout")
        result = health_check("http://localhost:8080/health")
        assert result["healthy"] is False
        assert "error" in result


# ---------------------------------------------------------------------------
# deploy_github_pages
# ---------------------------------------------------------------------------

class TestDeployGithubPages:
    """Tests for deploy_github_pages()."""

    @patch("core.devops.subprocess.run")
    @patch("core.devops.Path.exists", return_value=True)
    @patch("core.devops.Path.is_dir", return_value=True)
    def test_deploy_success(self, _is_dir, _exists, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = deploy_github_pages(
            Path("/tmp/site"), "https://github.com/user/repo.git"
        )
        assert result is True

    @patch("core.devops.Path.exists", return_value=False)
    def test_deploy_missing_source(self, _exists):
        result = deploy_github_pages(
            Path("/nonexistent"), "https://github.com/user/repo.git"
        )
        assert result is False


# ---------------------------------------------------------------------------
# setup_ci_cd
# ---------------------------------------------------------------------------

class TestSetupCiCd:
    """Tests for setup_ci_cd()."""

    def test_python_template(self, tmp_path):
        result = setup_ci_cd(tmp_path, template="python")
        assert result.exists()
        content = result.read_text()
        assert "python" in content.lower() or "pytest" in content.lower()
        assert "on:" in content  # Valid GitHub Actions YAML

    def test_node_template(self, tmp_path):
        result = setup_ci_cd(tmp_path, template="node")
        assert result.exists()
        content = result.read_text()
        assert "node" in content.lower() or "npm" in content.lower()

    def test_unknown_template_defaults(self, tmp_path):
        result = setup_ci_cd(tmp_path, template="unknown_lang")
        assert result.exists()


# ---------------------------------------------------------------------------
# rotate_secrets
# ---------------------------------------------------------------------------

class TestRotateSecrets:
    """Tests for rotate_secrets()."""

    def test_finds_env_files(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("API_KEY=sk-abc123\nDATABASE_URL=postgres://...\n")
        flagged = rotate_secrets(tmp_path)
        assert isinstance(flagged, list)
        assert len(flagged) >= 1
        assert any("API_KEY" in s for s in flagged)

    def test_no_secrets(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text("# Hello\nNo secrets here.\n")
        flagged = rotate_secrets(tmp_path)
        assert flagged == []

    def test_finds_hardcoded_tokens(self, tmp_path):
        src = tmp_path / "config.py"
        src.write_text('TOKEN = "ghp_1234567890abcdefghijklmno"\nDEBUG = True\n')
        flagged = rotate_secrets(tmp_path)
        assert len(flagged) >= 1
        assert any("TOKEN" in s for s in flagged)
