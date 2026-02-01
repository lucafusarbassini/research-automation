"""Phase 8 demo tests -- Advanced features: devops, reproducibility, browser,
RAG, meta-rules, lazy MCP, markdown commands, security, two-repo, automation utils.
"""

import io
import json
import re
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

# ---------------------------------------------------------------------------
# DevOps
# ---------------------------------------------------------------------------


class TestCheckInfrastructure:
    """core.devops.check_infrastructure with mocked subprocess."""

    def test_check_infrastructure(self):
        from core.devops import check_infrastructure

        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Docker version 24.0.7\n", stderr=""
        )
        with (
            patch("core.devops.subprocess.run", return_value=fake_result),
            patch("core.devops.shutil.which", return_value="/usr/bin/docker"),
        ):
            results = check_infrastructure()

        # All tools checked; at least one should be available since we mock which
        assert isinstance(results, dict)
        assert len(results) > 0
        for name, info in results.items():
            assert "available" in info
            assert "version" in info


class TestDockerManager:
    """core.devops.DockerManager methods with mock."""

    def test_is_available(self):
        from core.devops import DockerManager

        dm = DockerManager()
        fake_result = subprocess.CompletedProcess(
            args=["docker", "info"], returncode=0, stdout="info", stderr=""
        )
        with patch("core.devops.subprocess.run", return_value=fake_result):
            assert dm.is_available() is True

    def test_is_not_available(self):
        from core.devops import DockerManager

        dm = DockerManager()
        with patch("core.devops.subprocess.run", side_effect=FileNotFoundError):
            assert dm.is_available() is False

    def test_build(self, tmp_path):
        from core.devops import DockerManager

        dm = DockerManager()
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM python:3.11")

        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with patch("core.devops.subprocess.run", return_value=fake_result):
            assert dm.build("test:latest", dockerfile=dockerfile) is True

    def test_run_returns_container_id(self):
        from core.devops import DockerManager

        dm = DockerManager()
        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="abc123def456\n", stderr=""
        )
        with patch("core.devops.subprocess.run", return_value=fake_result):
            cid = dm.run("test:latest", ports={8080: 80})
            assert cid == "abc123def456"

    def test_stop(self):
        from core.devops import DockerManager

        dm = DockerManager()
        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with patch("core.devops.subprocess.run", return_value=fake_result):
            assert dm.stop("abc123") is True


class TestHealthCheck:
    """core.devops.health_check with mocked urlopen."""

    def test_health_check_healthy(self):
        from core.devops import health_check

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"status": "ok"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("core.devops.urllib.request.urlopen", return_value=mock_response):
            result = health_check("http://localhost:8080/health")

        assert result["healthy"] is True
        assert result["status_code"] == 200
        assert "ok" in result["body"]

    def test_health_check_unhealthy(self):
        import urllib.error

        from core.devops import health_check

        with patch(
            "core.devops.urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            result = health_check("http://localhost:9999/health")

        assert result["healthy"] is False
        assert result["status_code"] == 0
        assert "error" in result


class TestSetupCiCd:
    """core.devops.setup_ci_cd with tmp_path."""

    def test_setup_ci_cd_python(self, tmp_path):
        from core.devops import setup_ci_cd

        workflow = setup_ci_cd(tmp_path, template="python")

        assert workflow.exists()
        assert workflow.name == "ci.yml"
        content = workflow.read_text()
        assert "pytest" in content
        assert "actions/setup-python" in content

    def test_setup_ci_cd_node(self, tmp_path):
        from core.devops import setup_ci_cd

        workflow = setup_ci_cd(tmp_path, template="node")
        content = workflow.read_text()
        assert "npm" in content
        assert "actions/setup-node" in content

    def test_setup_ci_cd_unknown_template(self, tmp_path):
        from core.devops import setup_ci_cd

        workflow = setup_ci_cd(tmp_path, template="rust")
        content = workflow.read_text()
        # Falls back to default template
        assert "actions/checkout" in content


class TestRotateSecrets:
    """core.devops.rotate_secrets with tmp_path containing .env."""

    def test_rotate_secrets(self, tmp_path):
        from core.devops import rotate_secrets

        env_file = tmp_path / ".env"
        env_file.write_text(
            "DATABASE_URL=postgres://user:pass@host/db\n"
            "API_KEY=sk-1234567890abcdefghijk\n"
            "SAFE_VAR=hello\n"
        )

        findings = rotate_secrets(tmp_path)

        # Should find at least the API_KEY and DATABASE_URL
        assert len(findings) >= 1
        # At least one finding should reference the .env file
        assert any(".env" in f for f in findings)


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


class TestReproducibilityRunLog:
    """core.reproducibility run logging."""

    def test_run_log_roundtrip(self, tmp_path, monkeypatch):
        import core.reproducibility as repro
        from core.reproducibility import RunLog, load_run, log_run

        # Point RUNS_DIR to tmp
        monkeypatch.setattr(repro, "RUNS_DIR", tmp_path / "runs")

        run = RunLog(
            run_id="test-run-001",
            command="python train.py --epochs 10",
            parameters={"epochs": 10, "lr": 0.001},
            metrics={"accuracy": 0.95},
        )

        saved_path = log_run(run)
        assert saved_path.exists()

        loaded = load_run("test-run-001")
        assert loaded is not None
        assert loaded.run_id == "test-run-001"
        assert loaded.command == "python train.py --epochs 10"
        assert loaded.parameters["epochs"] == 10
        assert loaded.metrics["accuracy"] == 0.95


# ---------------------------------------------------------------------------
# Browser
# ---------------------------------------------------------------------------


class TestBrowserSession:
    """core.browser.BrowserSession with mocked puppeteer."""

    def test_browser_session_creation(self):
        from core.browser import BrowserSession

        with patch.object(BrowserSession, "_detect_puppeteer", return_value=False):
            session = BrowserSession()
            assert session._puppeteer_available is False

    def test_browser_session_with_puppeteer(self):
        from core.browser import BrowserSession

        with patch.object(BrowserSession, "_detect_puppeteer", return_value=True):
            session = BrowserSession(puppeteer_server="http://localhost:3000")
            assert session._puppeteer_available is True


class TestBrowserExtractText:
    """core.browser.BrowserSession.extract_text fallback."""

    def test_browser_extract_text_fallback(self):
        from core.browser import BrowserSession

        html_content = "<html><head><title>Test</title></head><body><p>Hello World</p><script>var x=1;</script></body></html>"

        with (
            patch.object(BrowserSession, "_detect_puppeteer", return_value=False),
            patch.object(BrowserSession, "_http_get", return_value=html_content),
        ):
            session = BrowserSession()
            text = session.extract_text("http://example.com")

        assert "Hello World" in text
        # Script content should be stripped
        assert "var x" not in text


# ---------------------------------------------------------------------------
# RAG MCP Index
# ---------------------------------------------------------------------------


class TestRagIndexBuildSearch:
    """core.rag_mcp.MCPIndex build and search."""

    def test_build_and_search(self):
        from core.rag_mcp import MCPEntry, MCPIndex

        entries = [
            MCPEntry(
                name="test-fs",
                description="File system operations",
                category="core",
                keywords=["file", "read", "write"],
                install_command="npx test-fs",
                config_template={"command": "npx"},
                url="https://example.com/fs",
            ),
            MCPEntry(
                name="test-db",
                description="Database operations for SQL queries",
                category="database",
                keywords=["database", "sql", "query"],
                install_command="npx test-db",
                config_template={"command": "npx"},
                url="https://example.com/db",
            ),
        ]

        index = MCPIndex()
        index.build_index(entries)

        # Search for file-related MCPs
        results = index.search("file read")
        assert len(results) >= 1
        assert results[0].name == "test-fs"

        # Search for database
        results = index.search("sql database query")
        assert len(results) >= 1
        assert results[0].name == "test-db"

        # Search with no match
        results = index.search("zz")
        assert len(results) == 0


class TestRagDefaultEntries:
    """core.rag_mcp.DEFAULT_ENTRIES has entries."""

    def test_default_entries_populated(self):
        from core.rag_mcp import DEFAULT_ENTRIES

        assert len(DEFAULT_ENTRIES) > 0
        for entry in DEFAULT_ENTRIES:
            assert entry.name
            assert entry.description
            assert entry.category
            assert isinstance(entry.keywords, list)
            assert len(entry.keywords) > 0


# ---------------------------------------------------------------------------
# Meta-rules
# ---------------------------------------------------------------------------


class TestMetaRulesDetect:
    """core.meta_rules rule detection."""

    def test_detect_operational_rule_positive(self):
        from core.meta_rules import detect_operational_rule

        assert detect_operational_rule("Always run tests before committing") is True
        assert detect_operational_rule("Never push directly to main") is True
        assert detect_operational_rule("You must use type hints") is True
        assert detect_operational_rule("Important: backup before migration") is True

    def test_detect_operational_rule_negative(self):
        from core.meta_rules import detect_operational_rule

        assert detect_operational_rule("The weather is nice today") is False
        assert detect_operational_rule("Python is a programming language") is False

    def test_classify_rule_type(self):
        from core.meta_rules import classify_rule_type

        assert classify_rule_type("Always run lint before commit") == "workflow"
        assert (
            classify_rule_type("Must not exceed 100 lines per function") == "constraint"
        )
        assert classify_rule_type("Prefer composition over inheritance") == "preference"
        assert classify_rule_type("When error occurs, check the log file") == "debug"

    def test_append_to_cheatsheet(self, tmp_path):
        from core.meta_rules import append_to_cheatsheet

        cs_path = tmp_path / "CHEATSHEET.md"

        append_to_cheatsheet(
            "Always format code with black",
            cheatsheet_path=cs_path,
        )

        assert cs_path.exists()
        content = cs_path.read_text()
        assert "Always format code with black" in content
        assert "## Workflow" in content


# ---------------------------------------------------------------------------
# Lazy MCP
# ---------------------------------------------------------------------------


class TestLazyMcpRegisterLoad:
    """core.lazy_mcp.LazyMCPLoader register + load."""

    def test_register_and_load(self):
        from core.lazy_mcp import LazyMCPLoader

        loader = LazyMCPLoader()
        loader.register_mcp(
            name="filesystem",
            config={"command": "npx", "args": ["-y", "server-fs"]},
            tier=1,
            trigger_keywords=["file", "read", "write"],
        )

        # Not loaded yet
        assert loader.get_active_mcps() == []

        # Load it
        meta = loader.load_mcp("filesystem")
        assert meta["name"] == "filesystem"
        assert meta["tier"] == 1
        assert "file" in meta["trigger_keywords"]

        # Now active
        assert "filesystem" in loader.get_active_mcps()

    def test_load_unknown_raises(self):
        from core.lazy_mcp import LazyMCPLoader

        loader = LazyMCPLoader()
        with pytest.raises(KeyError, match="not registered"):
            loader.load_mcp("nonexistent")

    def test_get_needed_mcps(self):
        from core.lazy_mcp import LazyMCPLoader

        loader = LazyMCPLoader()
        loader.register_mcp(
            "fs", {"cmd": "npx"}, tier=1, trigger_keywords=["file", "read"]
        )
        loader.register_mcp(
            "db", {"cmd": "npx"}, tier=2, trigger_keywords=["database", "sql"]
        )

        needed = loader.get_needed_mcps("I need to read a file")
        assert "fs" in needed
        assert "db" not in needed


class TestLazyMcpOptimize:
    """core.lazy_mcp.LazyMCPLoader.optimize_context."""

    def test_optimize_context(self):
        from core.lazy_mcp import LazyMCPLoader

        loader = LazyMCPLoader()
        loader.register_mcp("fs", {"cmd": "npx"}, tier=1, trigger_keywords=["file"])
        loader.register_mcp("db", {"cmd": "npx"}, tier=2, trigger_keywords=["database"])
        loader.register_mcp(
            "browser", {"cmd": "npx"}, tier=3, trigger_keywords=["web", "browser"]
        )

        # All three are active
        active = ["fs", "db", "browser"]

        # Current task only involves files
        to_drop = loader.optimize_context(active, "read a file from disk")

        # db and browser are not needed, browser (tier 3) should come first
        assert "browser" in to_drop
        assert "db" in to_drop
        assert "fs" not in to_drop
        assert to_drop.index("browser") < to_drop.index("db")

    def test_estimate_context_cost(self):
        from core.lazy_mcp import LazyMCPLoader

        loader = LazyMCPLoader()
        loader.register_mcp("fs", {"cmd": "npx"}, tier=1, trigger_keywords=["file"])
        loader.register_mcp("db", {"cmd": "npx"}, tier=2, trigger_keywords=["database"])

        cost = loader.estimate_context_cost(["fs", "db"])
        assert cost > 0
        # tier 1 = 800, tier 2 = 1200
        assert cost == 800 + 1200


# ---------------------------------------------------------------------------
# Markdown commands
# ---------------------------------------------------------------------------


class TestMarkdownExtractCode:
    """core.markdown_commands.extract_code_blocks."""

    def test_extract_code_blocks(self):
        from core.markdown_commands import extract_code_blocks

        md = (
            "# Example\n\n"
            "```python\n"
            "print('hello')\n"
            "```\n\n"
            "Some text.\n\n"
            "```bash\n"
            "echo hi\n"
            "```\n"
        )
        blocks = extract_code_blocks(md)

        assert len(blocks) == 2
        assert blocks[0]["language"] == "python"
        assert "print('hello')" in blocks[0]["code"]
        assert blocks[1]["language"] == "bash"
        assert "echo hi" in blocks[1]["code"]


class TestMarkdownParseTodo:
    """core.markdown_commands.parse_todo_to_tasks."""

    def test_parse_todo_to_tasks(self, tmp_path):
        from core.markdown_commands import parse_todo_to_tasks

        todo_file = tmp_path / "TODO.md"
        todo_file.write_text(
            "# Tasks\n\n"
            "- [x] (**P0**) Set up CI pipeline\n"
            "- [ ] (**P1**) Write documentation\n"
            "- [ ] Run benchmarks\n"
        )

        tasks = parse_todo_to_tasks(todo_file)

        assert len(tasks) == 3
        assert tasks[0]["done"] is True
        assert tasks[0]["priority"] == "P0"
        assert "CI pipeline" in tasks[0]["description"]

        assert tasks[1]["done"] is False
        assert tasks[1]["priority"] == "P1"

        assert tasks[2]["done"] is False
        assert tasks[2]["priority"] == ""
        assert "benchmarks" in tasks[2]["description"]


class TestMarkdownExecuteRunbookDry:
    """core.markdown_commands.execute_runbook dry_run."""

    def test_execute_runbook_dry_run(self):
        from core.markdown_commands import execute_runbook

        steps = [
            {
                "heading": "Setup",
                "language": "bash",
                "code": "pip install -r requirements.txt",
            },
            {"heading": "Test", "language": "python", "code": "print('test')"},
        ]

        results = execute_runbook(steps, dry_run=True)

        assert len(results) == 2
        for r in results:
            assert r["skipped"] is True
            assert r["returncode"] is None
            assert r["output"] == ""


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------


class TestSecurityScan:
    """core.security.scan_for_secrets."""

    def test_scan_for_secrets(self, tmp_path):
        from core.claude_flow import ClaudeFlowUnavailable
        from core.security import scan_for_secrets

        # Create a file with a fake secret
        py_file = tmp_path / "config.py"
        py_file.write_text(
            'API_KEY = "sk-abcdefghijklmnopqrstuvwxyz1234567890"\n'
            'SAFE_VAR = "hello"\n'
        )

        with patch(
            "core.security._get_bridge", side_effect=ClaudeFlowUnavailable("no bridge")
        ):
            findings = scan_for_secrets(tmp_path)

        assert len(findings) >= 1
        assert any("config.py" in f["file"] for f in findings)

    def test_scan_single_file(self, tmp_path):
        from core.claude_flow import ClaudeFlowUnavailable
        from core.security import scan_for_secrets

        secret_file = tmp_path / "secrets.py"
        secret_file.write_text('token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"\n')

        with patch(
            "core.security._get_bridge", side_effect=ClaudeFlowUnavailable("no bridge")
        ):
            findings = scan_for_secrets(secret_file)

        assert len(findings) >= 1


# ---------------------------------------------------------------------------
# Two-repo
# ---------------------------------------------------------------------------


class TestTwoRepoInit:
    """core.two_repo.TwoRepoManager.init_two_repos with tmp_path."""

    def test_two_repo_init(self, tmp_path):
        from core.two_repo import TwoRepoManager

        mgr = TwoRepoManager(tmp_path)
        result = mgr.init_two_repos()

        assert result["experiments"] is True
        assert result["clean"] is True

        # Directories created with .git
        assert (tmp_path / "experiments" / ".git").is_dir()
        assert (tmp_path / "clean" / ".git").is_dir()

    def test_two_repo_init_idempotent(self, tmp_path):
        from core.two_repo import TwoRepoManager

        mgr = TwoRepoManager(tmp_path)
        mgr.init_two_repos()
        # Second call should not raise
        result = mgr.init_two_repos()
        assert result["experiments"] is True
        assert result["clean"] is True


# ---------------------------------------------------------------------------
# Automation utils
# ---------------------------------------------------------------------------


class TestAutomationUtils:
    """core.automation_utils basic functions."""

    def test_data_handler_detect_format(self, tmp_path):
        from core.automation_utils import DataHandler

        csv_file = tmp_path / "data.csv"
        csv_file.write_text("a,b,c\n1,2,3\n")

        handler = DataHandler(path=csv_file)
        fmt = handler.detect_format()
        assert fmt == "csv"

    def test_data_handler_get_info(self, tmp_path):
        from core.automation_utils import DataHandler

        json_file = tmp_path / "data.json"
        json_file.write_text('{"key": "value"}')

        handler = DataHandler(path=json_file)
        info = handler.get_info()
        assert info["format"] == "json"
        assert info["size_mb"] >= 0
        assert "error" not in info

    def test_downsample_data(self):
        from core.automation_utils import downsample_data

        data = list(range(100))
        sampled = downsample_data(data, fraction=0.1, seed=42)
        assert len(sampled) == 10
        # All items come from original data
        assert all(item in data for item in sampled)

    def test_experiment_runner_save(self, tmp_path):
        from core.automation_utils import ExperimentRunner

        runner = ExperimentRunner(name="test-exp", log_dir=tmp_path / "experiments")
        runner.log_params({"lr": 0.01, "batch_size": 32})
        runner.log_metric("accuracy", 0.95)
        runner.log_metric("loss", 0.05)

        saved = runner.save()
        assert saved.exists()

        content = json.loads(saved.read_text())
        assert content["name"] == "test-exp"
        assert content["parameters"]["lr"] == 0.01
        assert content["results"]["accuracy"] == 0.95

    def test_report_generator(self, tmp_path):
        from core.automation_utils import ReportGenerator

        report = ReportGenerator(title="Test Report")
        report.add_section("Introduction", "This is a test report.")
        report.add_section("Results", "Accuracy: 95%")

        md = report.render_markdown()
        assert "# Test Report" in md
        assert "## Introduction" in md
        assert "## Results" in md
        assert "Accuracy: 95%" in md

        output = tmp_path / "report.md"
        report.save(output)
        assert output.exists()

    def test_plot_generator_spec(self):
        from core.automation_utils import PlotGenerator

        pg = PlotGenerator()
        spec = pg.generate_spec("scatter", "accuracy vs epochs", xlabel="Epochs")

        assert spec["type"] == "scatter"
        assert spec["description"] == "accuracy vs epochs"
        assert spec["kwargs"]["xlabel"] == "Epochs"
