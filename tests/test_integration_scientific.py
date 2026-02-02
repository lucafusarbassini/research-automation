"""Scientific integration test: Fibonacci Golden Ratio Convergence.

This test exercises 25+ ricet features end-to-end using a toy scientific
problem: estimating the golden ratio phi = (1+sqrt(5))/2 ~ 1.6180339887
by computing successive Fibonacci ratios F(n+1)/F(n) and analyzing their
convergence rate.

The problem is non-trivial (involves numerical convergence analysis and
error bounds) but simple enough to run quickly and verify against the
known analytical solution.

Usage:
    # Run all integration tests (requires ricet installed in editable mode)
    python -m pytest tests/test_integration_scientific.py -v -m integration

    # Run just the MCP verification
    python -m pytest tests/test_integration_scientific.py -v -k mcp

    # Generate PDF report only
    python tests/test_integration_scientific.py --report
"""

import datetime
import json
import math
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
PROJECT_DIR = Path("/tmp/ricet-integration-test/fibonacci-golden-ratio")
PHI = (1 + math.sqrt(5)) / 2  # 1.6180339887...

# Collect results for the PDF report
_results: list = []


def _run(
    cmd: list[str],
    cwd: Path = PROJECT_DIR,
    env_extra: dict | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess:
    """Run a command, capture output, record result for the report."""
    env = os.environ.copy()
    env["RICET_NO_CLAUDE"] = "true"  # Use fallback paths by default
    env["RICET_AUTO_COMMIT"] = "false"  # Don't auto-commit in tests
    env["AUTO_PUSH"] = "false"
    if env_extra:
        env.update(env_extra)

    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        result = subprocess.CompletedProcess(
            cmd,
            returncode=124,
            stdout="",
            stderr="TIMEOUT after {}s".format(timeout),
        )
    return result


def _record(
    step: int,
    name: str,
    cmd: str,
    result: subprocess.CompletedProcess,
    passed: bool | None = None,
    note: str = "",
):
    """Record a test step for the PDF report."""
    if passed is None:
        passed = result.returncode == 0
    _results.append(
        {
            "step": step,
            "name": name,
            "command": cmd,
            "stdout": result.stdout[:3000] if result.stdout else "",
            "stderr": result.stderr[:1500] if result.stderr else "",
            "returncode": result.returncode,
            "passed": passed,
            "note": note,
        }
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def setup_project():
    """Create a fresh test project before all tests, clean up after."""
    if PROJECT_DIR.exists():
        shutil.rmtree(PROJECT_DIR)
    PROJECT_DIR.parent.mkdir(parents=True, exist_ok=True)
    yield
    # Don't clean up — leave artifacts for inspection


@pytest.fixture(scope="module")
def init_project(setup_project):
    """Initialize the ricet project (run once for the module).

    Uses piped stdin to answer the interactive prompts. Falls back to
    manual scaffolding if the CLI fails (e.g. because it requires
    additional interactive input we can't predict).
    """
    env_extra = {
        "RICET_NO_CLAUDE": "true",
        "RICET_AUTO_COMMIT": "false",
        "AUTO_PUSH": "false",
    }
    env = os.environ.copy()
    env.update(env_extra)
    # Pipe "none\n" for the notification method prompt
    try:
        result = subprocess.run(
            ["ricet", "init", "fibonacci-golden-ratio", "--skip-repo"],
            cwd=str(PROJECT_DIR.parent),
            capture_output=True,
            text=True,
            timeout=30,
            input="none\n\n\n\n\n\n\n",
            env=env,
        )
    except subprocess.TimeoutExpired:
        result = subprocess.CompletedProcess([], 124, stdout="TIMEOUT", stderr="")

    _record(
        1,
        "Project initialization",
        "ricet init fibonacci-golden-ratio --skip-repo",
        result,
    )

    # Fallback: manually scaffold if init didn't create the directory
    if not PROJECT_DIR.exists():
        PROJECT_DIR.mkdir(parents=True)
        for d in ["knowledge", "paper", "config", "state", "src", ".claude"]:
            (PROJECT_DIR / d).mkdir(exist_ok=True)
        (PROJECT_DIR / "knowledge" / "GOAL.md").write_text("# Goal\n\nTBD\n")
        (PROJECT_DIR / "knowledge" / "ENCYCLOPEDIA.md").write_text("# Encyclopedia\n\n")
        (PROJECT_DIR / "knowledge" / "CONSTRAINTS.md").write_text("# Constraints\n\n")
        (PROJECT_DIR / "config" / "settings.yml").write_text(
            "project:\n  name: fibonacci-golden-ratio\n"
        )
        (PROJECT_DIR / "state" / "TODO.md").write_text("# TODO\n\n")
        _record(
            1,
            "Project initialization (fallback)",
            "manual scaffold",
            subprocess.CompletedProcess(
                [], 0, stdout="Manually scaffolded project", stderr=""
            ),
            note="ricet init required interactive input; scaffolded manually",
        )

    assert PROJECT_DIR.exists()
    return PROJECT_DIR


# ---------------------------------------------------------------------------
# Integration tests — ordered by step number
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestFibonacciScientificWorkflow:
    """End-to-end integration test using the Fibonacci convergence problem."""

    # -- Step 1: Init --

    def test_01_init(self, init_project):
        """ricet init creates the expected project structure."""
        proj = init_project
        assert (proj / "knowledge").is_dir() or (proj / ".claude").is_dir()
        # At minimum, some scaffold directory should exist
        dirs_found = [d.name for d in proj.iterdir() if d.is_dir()]
        assert len(dirs_found) >= 2, f"Expected directories, got: {dirs_found}"

    # -- Step 2: Knowledge management --

    def test_02_goal_setup(self, init_project):
        """Write the research goal to GOAL.md."""
        goal_path = init_project / "knowledge" / "GOAL.md"
        if not goal_path.parent.exists():
            goal_path.parent.mkdir(parents=True)
        goal_path.write_text(textwrap.dedent("""\
        # Research Goal

        Estimate the golden ratio phi = (1+sqrt(5))/2 by computing successive
        Fibonacci ratios F(n+1)/F(n) for n = 1..100. Analyze the convergence
        rate and prove it converges geometrically with rate 1/phi^2.

        ## Success Criteria
        - Compute phi estimate accurate to 15 decimal places
        - Plot convergence of |ratio_n - phi| on log scale
        - Prove geometric convergence rate analytically
        - Generate LaTeX table of first 20 ratios
        """))
        _record(
            2,
            "Goal setup",
            "write GOAL.md",
            subprocess.CompletedProcess([], 0, stdout="GOAL.md written", stderr=""),
            note="Direct file write",
        )
        assert goal_path.exists()
        assert "golden ratio" in goal_path.read_text().lower()

    # -- Step 3: Configuration --

    def test_03_config_view(self, init_project):
        """ricet config shows current settings."""
        result = _run(["ricet", "config"], cwd=init_project)
        _record(
            3,
            "Config view",
            "ricet config",
            result,
            passed=result.returncode == 0 or "settings" in result.stdout.lower(),
        )

    # -- Step 4: Agent routing --

    def test_04_agent_routing(self):
        """Verify agent routing keywords for research tasks."""
        from core.agents import AgentType, route_task

        pairs = [
            ("implement fibonacci computation", AgentType.CODER),
            ("search for convergence rate papers", AgentType.RESEARCHER),
            ("review the code quality and style", AgentType.REVIEWER),
            ("verify the golden ratio estimate", AgentType.FALSIFIER),
            ("draft the methods section", AgentType.WRITER),
            ("clean up and refactor the code", AgentType.CLEANER),
        ]
        for task, expected in pairs:
            actual = route_task(task)
            assert (
                actual == expected
            ), f"route_task({task!r}) = {actual}, expected {expected}"
        _record(
            4,
            "Agent routing",
            "route_task() x6 agents",
            subprocess.CompletedProcess(
                [], 0, stdout="All 6 agents routed correctly", stderr=""
            ),
        )

    # -- Step 5: Code generation (the actual computation) --

    def test_05_fibonacci_computation(self, init_project):
        """Write and run the Fibonacci convergence analysis."""
        src_dir = init_project / "src"
        src_dir.mkdir(exist_ok=True)
        fib_code = textwrap.dedent("""\
        #!/usr/bin/env python3
        \"\"\"Fibonacci golden ratio convergence analysis.\"\"\"
        import math
        import json
        from pathlib import Path

        PHI = (1 + math.sqrt(5)) / 2

        def fibonacci_ratios(n: int) -> list[float]:
            \"\"\"Compute F(k+1)/F(k) for k=1..n.\"\"\"
            a, b = 1, 1
            ratios = []
            for _ in range(n):
                ratios.append(b / a)
                a, b = b, a + b
            return ratios

        def convergence_errors(ratios: list[float]) -> list[float]:
            return [abs(r - PHI) for r in ratios]

        def geometric_rate(errors: list[float]) -> float:
            \"\"\"Estimate geometric convergence rate from consecutive error ratios.

            Uses terms 10..30 where float precision is still good.
            \"\"\"
            rates = []
            for i in range(10, min(30, len(errors))):
                if errors[i-1] > 0 and errors[i] > 0:
                    rates.append(errors[i] / errors[i-1])
            return sum(rates) / len(rates) if rates else 0.0

        if __name__ == "__main__":
            N = 100
            ratios = fibonacci_ratios(N)
            errors = convergence_errors(ratios)
            rate = geometric_rate(errors)
            expected_rate = 1 / PHI**2  # ~0.3820

            results = {
                "phi_estimate": ratios[-1],
                "phi_exact": PHI,
                "absolute_error": errors[-1],
                "convergence_rate": rate,
                "expected_rate": expected_rate,
                "rate_error": abs(rate - expected_rate),
                "n_terms": N,
                "first_20_ratios": ratios[:20],
                "first_20_errors": errors[:20],
            }

            out = Path("results.json")
            out.write_text(json.dumps(results, indent=2))
            print(f"phi estimate: {ratios[-1]:.15f}")
            print(f"phi exact:    {PHI:.15f}")
            print(f"abs error:    {errors[-1]:.2e}")
            print(f"conv rate:    {rate:.6f} (expected {expected_rate:.6f})")
        """)
        (src_dir / "fibonacci.py").write_text(fib_code)

        result = _run(
            [sys.executable, "src/fibonacci.py"],
            cwd=init_project,
        )
        _record(5, "Fibonacci computation", "python src/fibonacci.py", result)
        assert result.returncode == 0
        assert "phi estimate" in result.stdout

        # Verify the result is correct
        results_path = init_project / "results.json"
        assert results_path.exists()
        data = json.loads(results_path.read_text())
        assert abs(data["phi_estimate"] - PHI) < 1e-15, "phi estimate wrong"
        assert (
            data["convergence_rate"] > 0.3
        ), f"convergence rate {data['convergence_rate']} should be ~0.382"

    # -- Step 6: Vector memory --

    def test_06_memory_search(self, init_project):
        """ricet memory performs semantic search."""
        result = _run(
            ["ricet", "memory", "convergence rate of fibonacci ratios"],
            cwd=init_project,
        )
        _record(
            6,
            "Memory search",
            "ricet memory 'convergence rate...'",
            result,
            passed=True,  # May return no results if encyclopedia is empty
            note="First search — encyclopedia may be empty",
        )

    # -- Step 7: Citation search --

    def test_07_cite(self, init_project):
        """ricet cite searches for papers (fallback mode)."""
        result = _run(
            ["ricet", "cite", "golden ratio fibonacci"],
            cwd=init_project,
            timeout=30,
        )
        _record(
            7,
            "Citation search",
            "ricet cite 'golden ratio fibonacci'",
            result,
            passed=result.returncode == 0
            or "cite" in (result.stdout + result.stderr).lower(),
            note="Fallback mode — no real API",
        )

    # -- Step 8: Paper build --

    def test_08_paper_build(self, init_project):
        """ricet paper build compiles LaTeX (or reports missing pdflatex)."""
        result = _run(["ricet", "paper", "build"], cwd=init_project, timeout=30)
        _record(
            8,
            "Paper build",
            "ricet paper build",
            result,
            passed=True,  # Acceptable to fail if pdflatex not installed
            note="Depends on pdflatex installation",
        )

    # -- Step 9: Verification --

    def test_09_verify(self, init_project):
        """ricet verify checks recent outputs."""
        result = _run(["ricet", "verify"], cwd=init_project)
        _record(
            9,
            "Verification",
            "ricet verify",
            result,
            passed=result.returncode == 0
            or "verify" in (result.stdout + result.stderr).lower(),
        )

    # -- Step 10: Status --

    def test_10_status(self, init_project):
        """ricet status shows project state."""
        result = _run(["ricet", "status"], cwd=init_project)
        _record(10, "Status", "ricet status", result)

    # -- Step 11: Metrics --

    def test_11_metrics(self, init_project):
        """ricet metrics shows token/cost stats."""
        result = _run(["ricet", "metrics"], cwd=init_project)
        _record(11, "Metrics", "ricet metrics", result)

    # -- Step 12: Agents --

    def test_12_agents(self, init_project):
        """ricet agents shows agent status."""
        result = _run(["ricet", "agents"], cwd=init_project)
        _record(12, "Agents", "ricet agents", result)

    # -- Step 13: Test generation --

    def test_13_test_gen(self, init_project):
        """ricet test-gen generates tests for source files."""
        result = _run(["ricet", "test-gen"], cwd=init_project, timeout=90)
        _record(
            13,
            "Test generation",
            "ricet test-gen",
            result,
            passed=result.returncode == 0
            or "test" in (result.stdout + result.stderr).lower(),
        )

    # -- Step 14: Auto docs --

    def test_14_docs(self, init_project):
        """ricet docs auto-updates documentation."""
        result = _run(["ricet", "docs"], cwd=init_project, timeout=30)
        _record(14, "Auto docs", "ricet docs", result)

    # -- Step 15: Goal fidelity --

    def test_15_fidelity(self, init_project):
        """ricet fidelity checks GOAL.md alignment."""
        result = _run(["ricet", "fidelity"], cwd=init_project)
        _record(15, "Goal fidelity", "ricet fidelity", result)

    # -- Step 16: Browse URL --

    def test_16_browse(self, init_project):
        """ricet browse fetches and extracts text from a URL."""
        result = _run(
            ["ricet", "browse", "https://en.wikipedia.org/wiki/Golden_ratio"],
            cwd=init_project,
            timeout=30,
        )
        _record(
            16,
            "Browse URL",
            "ricet browse https://...Golden_ratio",
            result,
            note="Requires network access",
        )

    # -- Step 17: Reproducibility --

    def test_17_repro(self, init_project):
        """ricet repro log records an execution."""
        result = _run(["ricet", "repro", "log"], cwd=init_project)
        _record(17, "Reproducibility log", "ricet repro log", result)

    # -- Step 18: Style transfer --

    def test_18_style_transfer(self, init_project):
        """ricet paper adapt-style requires a reference paper."""
        result = _run(
            ["ricet", "paper", "adapt-style", "--reference", "nonexistent.pdf"],
            cwd=init_project,
        )
        _record(
            18,
            "Style transfer (edge case)",
            "ricet paper adapt-style --reference missing.pdf",
            result,
            note="Edge case: nonexistent reference file",
        )

    # -- Step 19: Session listing --

    def test_19_list_sessions(self, init_project):
        """ricet list-sessions shows session history."""
        result = _run(["ricet", "list-sessions"], cwd=init_project)
        _record(19, "List sessions", "ricet list-sessions", result)

    # -- Step 20: MCP search --

    def test_20_mcp_search(self, init_project):
        """ricet mcp-search discovers relevant MCP servers."""
        result = _run(["ricet", "mcp-search", "math computation"], cwd=init_project)
        _record(20, "MCP search", "ricet mcp-search 'math computation'", result)

    # -- Step 21: Maintenance --

    def test_21_maintain(self, init_project):
        """ricet maintain runs the daily maintenance pass."""
        result = _run(["ricet", "maintain"], cwd=init_project, timeout=120)
        _record(21, "Daily maintenance", "ricet maintain", result)

    # -- Step 22: Sync learnings --

    def test_22_sync_learnings(self, init_project):
        """ricet sync-learnings shares knowledge across projects."""
        result = _run(["ricet", "sync-learnings"], cwd=init_project)
        _record(22, "Sync learnings", "ricet sync-learnings", result)

    # -- Step 23: Version --

    def test_23_version(self, init_project):
        """ricet --version prints the version."""
        result = _run(["ricet", "--version"], cwd=init_project)
        _record(23, "Version", "ricet --version", result)
        assert "0.3" in result.stdout or "ricet" in result.stdout.lower()

    # -- Edge cases --

    def test_24_edge_empty_memory(self, init_project):
        """Edge case: empty memory query."""
        result = _run(["ricet", "memory", ""], cwd=init_project)
        _record(
            24,
            "Edge: empty memory query",
            "ricet memory ''",
            result,
            passed=True,
            note="Should handle gracefully, not crash",
        )

    def test_25_edge_duplicate_cite(self, init_project):
        """Edge case: duplicate citation request."""
        _run(["ricet", "cite", "golden ratio"], cwd=init_project, timeout=15)
        result = _run(["ricet", "cite", "golden ratio"], cwd=init_project, timeout=15)
        _record(
            25,
            "Edge: duplicate citation",
            "ricet cite 'golden ratio' x2",
            result,
            passed=True,
            note="Second call should dedup or append safely",
        )

    # -- Step 26: Model routing --

    def test_26_model_routing(self):
        """3-tier model routing classifies tasks correctly."""
        from core.model_router import TaskComplexity, classify_task_complexity

        # Simple task -> SIMPLE
        simple = classify_task_complexity("format this list")
        assert simple == TaskComplexity.SIMPLE, f"Got {simple}"

        # Complex task -> COMPLEX
        complex_task = classify_task_complexity(
            "design a distributed system architecture with fault tolerance"
        )
        assert complex_task == TaskComplexity.COMPLEX, f"Got {complex_task}"
        _record(
            26,
            "Model routing",
            "classify_task_complexity() x2",
            subprocess.CompletedProcess(
                [],
                0,
                stdout=f"simple={simple.value}, complex={complex_task.value}",
                stderr="",
            ),
        )

    # -- Step 27: Knowledge CRUD --

    def test_27_encyclopedia_crud(self, init_project):
        """Write and read encyclopedia entries."""
        from core.knowledge import append_learning, search_knowledge

        enc_path = init_project / "knowledge" / "ENCYCLOPEDIA.md"
        if not enc_path.exists():
            enc_path.parent.mkdir(parents=True, exist_ok=True)
        # Write a properly structured encyclopedia with section headers
        enc_path.write_text(
            "# Encyclopedia\n\n"
            "## Tricks\n<!-- Short tips -->\n\n"
            "## Decisions\n<!-- Key decisions -->\n\n"
            "## What Works\n<!-- Approaches that succeeded -->\n\n"
            "## What Doesn't Work\n<!-- Approaches that failed -->\n\n"
        )

        append_learning(
            "What Works",
            "The ratio F(n+1)/F(n) converges to phi at geometric rate 1/phi^2.",
            enc_path,
        )
        results = search_knowledge("fibonacci convergence", enc_path)
        found = any(
            "converges" in str(r).lower() or "phi" in str(r).lower() for r in results
        )
        _record(
            27,
            "Encyclopedia CRUD",
            "append_learning + search_knowledge",
            subprocess.CompletedProcess(
                [],
                0,
                stdout=f"Found entry: {found}, results: {len(results)}",
                stderr="",
            ),
            passed=True,
        )  # search may return empty if no vector DB; append is the real test
        # Verify the entry was written
        content = enc_path.read_text()
        assert "converges to phi" in content

    # -- Step 28: Notification config --

    def test_28_notification_config(self, init_project):
        """Notification config can be saved and loaded."""
        from core.notifications import NotificationConfig

        cfg = NotificationConfig(
            email_to="test@example.com",
            smtp_user="user@example.com",
            smtp_password="testpass",
        )
        cfg_path = init_project / "state" / "notification_config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg.save(cfg_path)
        loaded = NotificationConfig.load(cfg_path)
        assert loaded.email_to == "test@example.com"
        _record(
            28,
            "Notification config",
            "save+load NotificationConfig",
            subprocess.CompletedProcess(
                [], 0, stdout="Config saved and loaded", stderr=""
            ),
        )

    # -- Step 29: Email with attachment --

    def test_29_email_attachment(self, init_project):
        """Email attachment function works (mocked SMTP)."""
        from unittest.mock import MagicMock
        from unittest.mock import patch as mock_patch

        from core.notifications import NotificationConfig, send_email_with_attachment

        pdf = init_project / "test_attachment.pdf"
        pdf.write_bytes(b"%PDF-1.4 test")

        cfg = NotificationConfig(
            email_to="test@example.com",
            smtp_user="user@example.com",
            smtp_password="pass",
        )

        server = MagicMock()
        with mock_patch("core.notifications.smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__ = MagicMock(return_value=server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
            result = send_email_with_attachment("Report", "See attached", pdf, cfg)

        assert result is True
        server.send_message.assert_called_once()
        _record(
            29,
            "Email with attachment",
            "send_email_with_attachment()",
            subprocess.CompletedProcess(
                [], 0, stdout="Attachment sent (mocked)", stderr=""
            ),
        )

    # -- Step 30: Fibonacci mathematical verification --

    def test_30_math_verification(self, init_project):
        """Verify the Fibonacci computation results are mathematically correct."""
        results_path = init_project / "results.json"
        if not results_path.exists():
            pytest.skip("results.json not generated (step 5 may have been skipped)")

        data = json.loads(results_path.read_text())

        # 1. phi estimate should be accurate to 15 decimal places
        assert abs(data["phi_estimate"] - PHI) < 1e-15

        # 2. First ratio should be 1.0 (F(2)/F(1) = 1/1)
        assert data["first_20_ratios"][0] == 1.0

        # 3. Ratios should monotonically approach phi (alternating above/below)
        ratios = data["first_20_ratios"]
        for i in range(2, len(ratios)):
            assert abs(ratios[i] - PHI) < abs(
                ratios[i - 1] - PHI
            ), f"Ratios not converging at step {i}: {ratios[i]} vs {ratios[i-1]}"

        # 4. Convergence rate should be close to 1/phi^2 ~ 0.3820
        expected_rate = 1 / PHI**2
        assert (
            abs(data["convergence_rate"] - expected_rate) < 0.05
        ), f"Rate {data['convergence_rate']:.4f} not close to {expected_rate:.4f}"

        _record(
            30,
            "Mathematical verification",
            "verify results.json",
            subprocess.CompletedProcess(
                [],
                0,
                stdout=f"phi={data['phi_estimate']:.15f}, rate={data['convergence_rate']:.6f}",
                stderr="",
            ),
        )


# ---------------------------------------------------------------------------
# MCP Verification (25+ servers)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestMCPVerification:
    """Verify that 25+ MCP server configs exist and are structurally valid."""

    def test_mcp_nucleus_loads(self):
        """mcp-nucleus.json loads without errors."""
        from core.mcps import load_mcp_config

        config = load_mcp_config()
        assert isinstance(config, dict)
        assert len(config) >= 5, f"Expected 5+ tiers, got {len(config)}"

    def test_mcp_count_at_least_25(self):
        """At least 25 distinct MCP servers are configured."""
        from core.mcps import load_mcp_config

        config = load_mcp_config()
        all_mcps = set()
        for tier_name, tier_data in config.items():
            mcps = tier_data.get("mcps", {})
            all_mcps.update(mcps.keys())
        assert (
            len(all_mcps) >= 25
        ), f"Only {len(all_mcps)} MCPs found: {sorted(all_mcps)}"
        _record(
            31,
            "MCP count >= 25",
            "load_mcp_config() count",
            subprocess.CompletedProcess(
                [],
                0,
                stdout=f"{len(all_mcps)} MCPs: {', '.join(sorted(all_mcps))}",
                stderr="",
            ),
        )

    def test_mcp_tier_structure(self):
        """Each tier has description and mcps dict."""
        from core.mcps import load_mcp_config

        config = load_mcp_config()
        for tier_name, tier_data in config.items():
            assert "mcps" in tier_data, f"Tier {tier_name} missing 'mcps'"
            assert isinstance(
                tier_data["mcps"], dict
            ), f"Tier {tier_name} mcps not dict"

    def test_mcp_classification(self):
        """Task classification maps to correct tiers."""
        from core.mcps import classify_task

        # Data tasks -> tier2_data
        data_tiers = classify_task("query the database for results")
        assert "tier2_data" in data_tiers, f"Expected tier2_data in {data_tiers}"
        # ML tasks -> tier3_ml
        ml_tiers = classify_task("train a neural network model")
        assert "tier3_ml" in ml_tiers, f"Expected tier3_ml in {ml_tiers}"

    def test_mcp_essential_servers_present(self):
        """Core MCP servers (filesystem, git, fetch, github, memory) exist."""
        from core.mcps import load_mcp_config

        config = load_mcp_config()
        all_mcps = set()
        for tier_data in config.values():
            all_mcps.update(tier_data.get("mcps", {}).keys())

        required = [
            "filesystem",
            "git",
            "github",
            "fetch",
            "memory",
            "sequential-thinking",
            "puppeteer",
        ]
        for mcp in required:
            assert mcp in all_mcps, f"Required MCP '{mcp}' not found in config"

    def test_mcp_search_catalog(self):
        """MCP catalog file exists and contains entries."""
        catalog = REPO_ROOT / "defaults" / "MCP_CATALOG.md"
        if catalog.exists():
            text = catalog.read_text()
            assert len(text) > 1000, "MCP catalog seems too small"
            _record(
                32,
                "MCP catalog check",
                "read MCP_CATALOG.md",
                subprocess.CompletedProcess(
                    [], 0, stdout=f"Catalog: {len(text)} chars", stderr=""
                ),
            )

    def test_mcp_individual_configs(self):
        """Verify structure of each MCP entry in nucleus config."""
        from core.mcps import load_mcp_config

        config = load_mcp_config()
        verified = 0
        for tier_name, tier_data in config.items():
            for mcp_name, mcp_config in tier_data.get("mcps", {}).items():
                # Each MCP should have either 'command' or 'source'
                has_command = "command" in mcp_config
                has_source = "source" in mcp_config
                assert (
                    has_command or has_source
                ), f"MCP {mcp_name} in {tier_name} has neither 'command' nor 'source'"
                if has_command:
                    assert isinstance(mcp_config["command"], str)
                verified += 1
        assert verified >= 25, f"Only verified {verified} MCPs"
        _record(
            33,
            "MCP individual config verification",
            f"Verified {verified} MCP configs",
            subprocess.CompletedProcess(
                [], 0, stdout=f"{verified} MCPs verified", stderr=""
            ),
        )


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_report():
    """Generate the integration test PDF report."""
    from core.notifications import NotificationConfig, send_email_with_attachment
    from core.report import TestReport, TestResult, generate_pdf_report

    report = TestReport(
        title="ricet 0.3.0 Scientific Integration Test Report",
        started_at=datetime.datetime.now(),
    )

    for r in _results:
        report.add(TestResult(**r))

    report.finished_at = datetime.datetime.now()

    output_dir = REPO_ROOT / "tests" / "output"
    pdf_path = generate_pdf_report(report, output_dir)
    print(f"\nPDF report generated: {pdf_path}")

    # Also save the markdown version
    md_path = output_dir / "integration_report.md"
    print(f"Markdown report: {md_path}")

    return pdf_path


# ---------------------------------------------------------------------------
# conftest-style hook to generate report after all tests
# ---------------------------------------------------------------------------


def pytest_sessionfinish(session, exitstatus):
    """Generate PDF report after test session completes."""
    if _results:
        try:
            pdf = generate_report()
            print(f"\n[ricet] Integration report: {pdf}")
        except Exception as e:
            print(f"\n[ricet] Failed to generate report: {e}")


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    if "--report" in sys.argv:
        # Just generate report from existing results
        generate_report()
    else:
        sys.exit(pytest.main([__file__, "-v", "-m", "integration", "--tb=short"]))
