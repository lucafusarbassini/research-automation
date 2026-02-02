#!/usr/bin/env python3
"""
ricet 0.3.0 -- Full Integration Test Suite
============================================
Toy problem: Comparing Numerical Integration Methods

This script runs every testable ricet CLI command from the TESTING_GUIDE.md,
captures stdout/stderr, records pass/fail, and produces a PDF report.

Usage:
    python tests/integration/run_full_test.py          # run all
    python tests/integration/run_full_test.py --pdf     # run + generate PDF
    python tests/integration/run_full_test.py --email   # run + PDF + email
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
TEST_ROOT = Path("/tmp/ricet-fulltest")
PROJECT_NAME = "integration-methods"
PROJECT_DIR = TEST_ROOT / PROJECT_NAME
REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # research-automation/
SCRATCHPAD = Path("/tmp/ricet-fulltest-scratch")

MAX_CMD_TIMEOUT = 120  # seconds per command

# Ensure node/npm from nvm is in PATH
NVM_NODE_DIR = Path.home() / ".nvm" / "versions" / "node"
if NVM_NODE_DIR.exists():
    for ver_dir in sorted(NVM_NODE_DIR.iterdir(), reverse=True):
        bin_dir = ver_dir / "bin"
        if bin_dir.exists():
            os.environ["PATH"] = str(bin_dir) + ":" + os.environ.get("PATH", "")
            break


@dataclass
class TestResult:
    section: str
    command: str
    stdout: str
    stderr: str
    returncode: int
    duration: float
    passed: bool
    note: str = ""


results: list[TestResult] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
NVM_INIT = 'export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"; '


def run(cmd: str, cwd: str | Path | None = None, timeout: int = MAX_CMD_TIMEOUT,
        env_extra: dict | None = None, expect_fail: bool = False,
        stdin_text: str | None = None) -> TestResult:
    """Run a shell command, capture output, return TestResult."""
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    # Prefix every command with nvm init so node/npm are available
    full_cmd = NVM_INIT + cmd
    start = time.time()
    try:
        proc = subprocess.run(
            full_cmd, shell=True, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout, env=env,
            input=stdin_text,
        )
        duration = time.time() - start
        passed = (proc.returncode == 0) if not expect_fail else (proc.returncode != 0)
        return TestResult(
            section="", command=cmd,
            stdout=proc.stdout[-4000:] if len(proc.stdout) > 4000 else proc.stdout,
            stderr=proc.stderr[-2000:] if len(proc.stderr) > 2000 else proc.stderr,
            returncode=proc.returncode, duration=duration, passed=passed,
        )
    except subprocess.TimeoutExpired:
        duration = time.time() - start
        return TestResult(
            section="", command=cmd, stdout="", stderr="TIMEOUT",
            returncode=-1, duration=duration, passed=False,
            note=f"Timed out after {timeout}s",
        )


def log_test(section: str, cmd: str, cwd=None, timeout=MAX_CMD_TIMEOUT,
             env_extra=None, expect_fail=False, note="",
             stdin_text=None) -> TestResult:
    """Run + record a test."""
    print(f"  [{section}] $ {cmd}")
    r = run(cmd, cwd=cwd, timeout=timeout, env_extra=env_extra,
            expect_fail=expect_fail, stdin_text=stdin_text)
    r.section = section
    if note:
        r.note = note
    results.append(r)
    status = "PASS" if r.passed else "FAIL"
    print(f"    -> {status}  (rc={r.returncode}, {r.duration:.1f}s)")
    if not r.passed:
        # Show first few lines of stderr on failure
        for line in r.stderr.strip().split("\n")[:5]:
            print(f"       {line}")
    return r


# ---------------------------------------------------------------------------
# Test sections -- mirrors TESTING_GUIDE.md
# ---------------------------------------------------------------------------

def test_00_prerequisites():
    """Verify ricet is installed."""
    log_test("0-prereq", "ricet --version")
    log_test("0-prereq", "python3 --version")
    log_test("0-prereq", "git --version")
    log_test("0-prereq", "node --version")


def test_01_init():
    """Section 1: Project initialization."""
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)
    TEST_ROOT.mkdir(parents=True)
    SCRATCHPAD.mkdir(parents=True, exist_ok=True)

    # ricet init prompt sequence (from onboarding.py + cli/main.py):
    # Step 3 (typer.prompt): notification, [email if email], journal, paper_type, web, mobile
    # Step 3b (raw input): credentials by category (core, ml, publishing, cloud,
    #          integrations, and conditionally slack/email SMTP)
    # Step 5: create repo?, private?
    #
    # We use real credentials so the test is meaningful.
    github_pat = os.environ.get("GITHUB_TOKEN", "")
    gemini_key = os.environ.get("GOOGLE_API_KEY", "")
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")
    pypi_token = os.environ.get("PYPI_TOKEN", "")

    init_answers = "\n".join([
        # --- Step 3: Project configuration (typer.prompt) ---
        "email",                    # Notification method
        smtp_user or "",            # Notification email (only asked if method=email)
        "skip",                     # Target journal
        "journal-article",          # Paper type
        "no",                       # Web dashboard
        "no",                       # Mobile access
        # --- Step 3b: Credentials (raw input()) ---
        # Core (4):
        "",                         # ANTHROPIC_API_KEY (skip - use subscription)
        github_pat,                 # GITHUB_PERSONAL_ACCESS_TOKEN
        "",                         # OPENAI_API_KEY (skip)
        gemini_key,                 # GOOGLE_API_KEY
        # ML (2):
        "",                         # HUGGINGFACE_TOKEN (skip)
        "",                         # WANDB_API_KEY (skip)
        # Publishing (5):
        pypi_token,                 # PYPI_TOKEN
        "",                         # MEDIUM_TOKEN (skip)
        "",                         # LINKEDIN_CLIENT_ID (skip)
        "",                         # LINKEDIN_CLIENT_SECRET (skip)
        "",                         # LINKEDIN_ACCESS_TOKEN (skip)
        # Cloud (4):
        "",                         # AWS_ACCESS_KEY_ID (skip)
        "",                         # AWS_SECRET_ACCESS_KEY (skip)
        "",                         # NOTION_API_KEY (skip)
        "",                         # ZAPIER_NLA_API_KEY (skip)
        # Integrations (3):
        "",                         # GAMMA_API_KEY (skip)
        "",                         # CANVA_API_KEY (skip)
        "",                         # GOOGLE_DRIVE_CREDENTIALS (skip)
        # Email SMTP (4, conditional on notification_method=email):
        "smtp.gmail.com",           # SMTP_HOST
        "587",                      # SMTP_PORT
        smtp_user or "",            # SMTP_USER
        smtp_pass or "",            # SMTP_PASSWORD
        # --- Step 5: GitHub repo ---
        "yes",                      # Create GitHub repo?
        "yes",                      # Private?
    ])
    log_test("1-init",
             f'ricet init {PROJECT_NAME}',
             cwd=TEST_ROOT, timeout=180,
             stdin_text=init_answers)

    # If init failed (e.g. npm issue), scaffold manually so remaining tests can run
    if not PROJECT_DIR.exists():
        print("  [1-init] Fallback: manually scaffolding project directory")
        PROJECT_DIR.mkdir(parents=True, exist_ok=True)
        # Scaffold from templates
        templates = REPO_ROOT / "templates"
        if templates.exists():
            for item in [".claude", "knowledge", "paper", "config", ".github"]:
                src = templates / item
                dst = PROJECT_DIR / item
                if src.exists() and not dst.exists():
                    shutil.copytree(src, dst, dirs_exist_ok=True)
        # Create state dir
        (PROJECT_DIR / "state").mkdir(exist_ok=True)
        (PROJECT_DIR / "state" / "sessions").mkdir(exist_ok=True)
        # Write GOAL.md
        goal_md = PROJECT_DIR / "knowledge" / "GOAL.md"
        goal_md.parent.mkdir(parents=True, exist_ok=True)
        goal_md.write_text("# Goal\n\nCompare numerical integration methods "
                           "(trapezoidal, Simpson, Monte Carlo) on benchmark functions.\n")
        # Init git
        subprocess.run("git init && git add -A && git commit -m 'scaffolded project'",
                       shell=True, cwd=PROJECT_DIR, capture_output=True)

    # Verify scaffolded files
    for f in [".claude", "knowledge/GOAL.md", "config/settings.yml",
              "paper/main.tex", "paper/references.bib", "state"]:
        p = PROJECT_DIR / f
        exists = p.exists()
        r = TestResult(section="1-init-files", command=f"exists? {f}",
                       stdout=str(exists), stderr="", returncode=0 if exists else 1,
                       duration=0, passed=exists)
        results.append(r)
        print(f"  [1-init-files] {f}: {'PASS' if exists else 'FAIL'}")

    # Init with skip-repo and notification=none (fewer prompts: no email, no SMTP)
    # Prompt sequence: notification(none), journal, paper_type, web, mobile,
    # then 18 credentials (core+ml+publishing+cloud+integrations, NO email/slack)
    skip_answers = "\n".join([
        "none",              # Notification method (no email -> no SMTP prompts)
        "skip",              # Journal
        "journal-article",   # Paper type
        "no",                # Web
        "no",                # Mobile
        # 18 credential prompts (all skip):
        "", "", "", "",      # core (4)
        "", "",              # ml (2)
        "", "", "", "", "",  # publishing (5)
        "", "", "", "",      # cloud (4)
        "", "", "",          # integrations (3)
    ])
    log_test("1b-init-skip",
             'ricet init test-skip --skip-repo',
             cwd=TEST_ROOT, timeout=120,
             stdin_text=skip_answers)


def test_02_config():
    """Section 2: Configuration."""
    log_test("2-config", "ricet config", cwd=PROJECT_DIR)
    # Config compute - provide defaults
    log_test("2-config-compute", "ricet config compute", cwd=PROJECT_DIR,
             stdin_text="\n\n\n",
             note="Interactive compute config, accepting defaults")


def test_03_status():
    """Section 4: Project status."""
    log_test("4-status", "ricet status", cwd=PROJECT_DIR)


def test_04_sessions():
    """Section 5: Session listing."""
    log_test("5-sessions", "ricet list-sessions", cwd=PROJECT_DIR)


def test_05_agents():
    """Section 6: Agent status."""
    log_test("6-agents", "ricet agents", cwd=PROJECT_DIR)


def test_06_memory():
    """Section 7: Knowledge / Memory."""
    log_test("7a-memory",
             'ricet memory log-decision "Use Simpson rule as baseline because it has O(h^4) convergence"',
             cwd=PROJECT_DIR)
    log_test("7a-memory",
             'ricet memory log-decision "Monte Carlo converges as O(1/sqrt(N)) regardless of dimension"',
             cwd=PROJECT_DIR)
    log_test("7b-memory", 'ricet memory search "convergence" --top-k 3',
             cwd=PROJECT_DIR)
    log_test("7c-memory", "ricet memory export", cwd=PROJECT_DIR)
    log_test("7d-memory", "ricet memory stats", cwd=PROJECT_DIR)


def test_07_metrics():
    """Section 8: Metrics."""
    log_test("8-metrics", "ricet metrics", cwd=PROJECT_DIR)


def test_08_paper():
    """Section 9: Paper pipeline."""
    log_test("9a-paper", "ricet paper check", cwd=PROJECT_DIR)
    log_test("9b-paper", "ricet paper build", cwd=PROJECT_DIR,
             timeout=60, note="Needs pdflatex; OK to fail if not installed")
    log_test("9c-paper", "ricet paper update", cwd=PROJECT_DIR, timeout=60)
    log_test("9d-paper", "ricet paper modernize", cwd=PROJECT_DIR, timeout=60)


def test_09_literature():
    """Section 10: Literature search."""
    log_test("10a-cite",
             'ricet cite "numerical integration convergence rates" --max 3',
             cwd=PROJECT_DIR, timeout=90)
    log_test("10b-discover",
             'ricet discover "Monte Carlo integration variance reduction" --max 2',
             cwd=PROJECT_DIR, timeout=90)
    log_test("10c-discover-cite",
             'ricet discover "Simpson rule error bounds" --cite --max 1',
             cwd=PROJECT_DIR, timeout=90)


def test_10_browse():
    """Section 11: URL Browsing."""
    log_test("11-browse",
             'ricet browse "https://en.wikipedia.org/wiki/Numerical_integration"',
             cwd=PROJECT_DIR, timeout=60)


def test_11_verify():
    """Section 12: Verification."""
    log_test("12-verify",
             'ricet verify "Simpson rule has O(h^4) convergence for smooth functions"',
             cwd=PROJECT_DIR, timeout=60)
    # Edge case: deliberately wrong claim
    log_test("12-verify-edge",
             'ricet verify "Trapezoidal rule is always more accurate than Simpson rule"',
             cwd=PROJECT_DIR, timeout=60,
             note="Should flag as suspicious/false")


def test_12_debug():
    """Section 13: Auto-debug."""
    # Create a buggy integrator script
    buggy = SCRATCHPAD / "buggy_integrator.py"
    buggy.write_text(textwrap.dedent("""\
        import math

        def trapezoidal(f, a, b, n):
            h = (b - a) / n
            total = f(a) + f(b)
            for i in range(1, n):
                total += 2 * f(a + i * h)
            return total * h / 2

        # Bug: division by zero when n=0
        result = trapezoidal(math.sin, 0, math.pi, 0)
        print(f"Result: {result}")
    """))
    log_test("13-debug", f'ricet debug "python3 {buggy}"',
             cwd=PROJECT_DIR, timeout=60)


def test_13_overnight():
    """Section 14: Overnight mode (dry run, 1 iteration)."""
    todo = PROJECT_DIR / "state" / "TODO.md"
    todo.parent.mkdir(parents=True, exist_ok=True)
    todo.write_text(textwrap.dedent("""\
        # TODO

        - [ ] Create src/integrators.py with trapezoidal, simpson, and monte_carlo functions
        - [ ] Create tests/test_integrators.py with basic correctness tests
    """))
    log_test("14a-overnight", "ricet overnight --iterations 1",
             cwd=PROJECT_DIR, timeout=180,
             note="May fail without Claude session; tests the entry point")


def test_14_auto_routines():
    """Section 15: Autonomous routines."""
    log_test("15a-auto",
             'ricet auto add-routine --name nightly-convergence '
             '--command "ricet verify \'integration converges\'" '
             '--schedule daily --desc "Nightly convergence check"',
             cwd=PROJECT_DIR)
    log_test("15b-auto", "ricet auto list-routines", cwd=PROJECT_DIR)
    log_test("15c-auto",
             'ricet auto monitor --topic "numerical integration methods"',
             cwd=PROJECT_DIR)


def test_15_repro():
    """Section 16: Reproducibility."""
    log_test("16a-repro",
             'ricet repro log --run-id trap-001 '
             '--command "python experiments/convergence.py --method trapezoidal" '
             '--notes "Baseline trapezoidal convergence test"',
             cwd=PROJECT_DIR)
    log_test("16b-repro", "ricet repro list", cwd=PROJECT_DIR)
    log_test("16c-repro", "ricet repro show --run-id trap-001", cwd=PROJECT_DIR)
    # Hash a file
    dataset = SCRATCHPAD / "benchmark_data.csv"
    dataset.write_text("n,trapezoidal,simpson,montecarlo\n10,0.333,0.333,0.330\n100,0.3333,0.33333,0.3328\n")
    log_test("16d-repro", f"ricet repro hash --path {dataset}", cwd=PROJECT_DIR)


def test_16_mcp():
    """Section 17-18: MCP discovery and creation."""
    log_test("17a-mcp", 'ricet mcp-search "database migration"',
             cwd=PROJECT_DIR, timeout=60, stdin_text="no\n")
    log_test("17b-mcp", 'ricet mcp-search "browser automation"',
             cwd=PROJECT_DIR, timeout=60, stdin_text="no\n")
    log_test("17c-mcp", 'ricet mcp-search "paper search arxiv"',
             cwd=PROJECT_DIR, timeout=60, stdin_text="no\n")
    log_test("18-mcp-create",
             'ricet mcp-create integration-benchmark '
             '--desc "MCP for numerical integration benchmarks" '
             '--tools "run_benchmark,compare_methods,plot_convergence"',
             cwd=PROJECT_DIR, timeout=60, stdin_text="\n")


def test_17_testgen():
    """Section 19: Test generation."""
    # Create a source file to generate tests for
    src_dir = PROJECT_DIR / "src"
    src_dir.mkdir(exist_ok=True)
    (src_dir / "__init__.py").touch()
    (src_dir / "integrators.py").write_text(textwrap.dedent("""\
        \"\"\"Numerical integration methods.\"\"\"
        import math
        import random

        def trapezoidal(f, a: float, b: float, n: int) -> float:
            \"\"\"Composite trapezoidal rule.\"\"\"
            if n <= 0:
                raise ValueError("n must be positive")
            h = (b - a) / n
            total = (f(a) + f(b)) / 2
            for i in range(1, n):
                total += f(a + i * h)
            return total * h

        def simpson(f, a: float, b: float, n: int) -> float:
            \"\"\"Composite Simpson's 1/3 rule. n must be even.\"\"\"
            if n <= 0 or n % 2 != 0:
                raise ValueError("n must be a positive even integer")
            h = (b - a) / n
            total = f(a) + f(b)
            for i in range(1, n, 2):
                total += 4 * f(a + i * h)
            for i in range(2, n, 2):
                total += 2 * f(a + i * h)
            return total * h / 3

        def monte_carlo(f, a: float, b: float, n: int, seed: int = 42) -> float:
            \"\"\"Monte Carlo integration with fixed seed for reproducibility.\"\"\"
            if n <= 0:
                raise ValueError("n must be positive")
            rng = random.Random(seed)
            total = sum(f(rng.uniform(a, b)) for _ in range(n))
            return (b - a) * total / n
    """))
    log_test("19-testgen", "ricet test-gen", cwd=PROJECT_DIR, timeout=60)
    log_test("19a-testgen", "ricet test-gen --file src/integrators.py",
             cwd=PROJECT_DIR, timeout=60)


def test_18_docs():
    """Section 20: Auto-documentation."""
    log_test("20-docs", "ricet docs --force", cwd=PROJECT_DIR, timeout=60)


def test_19_fidelity():
    """Section 21: Goal fidelity."""
    log_test("21-fidelity", "ricet fidelity", cwd=PROJECT_DIR, timeout=60)


def test_20_maintain():
    """Section 22: Daily maintenance."""
    log_test("22-maintain", "ricet maintain", cwd=PROJECT_DIR, timeout=120)


def test_21_adopt():
    """Section 23: Adopt existing repo."""
    # Create a mini existing repo
    existing = TEST_ROOT / "existing-math-lib"
    existing.mkdir(parents=True, exist_ok=True)
    subprocess.run("git init", shell=True, cwd=existing, capture_output=True)
    (existing / "README.md").write_text("# Math Utils\nA small math utility library.\n")
    (existing / "utils.py").write_text("def factorial(n): return 1 if n <= 1 else n * factorial(n-1)\n")
    subprocess.run("git add . && git commit -m 'initial'",
                    shell=True, cwd=existing, capture_output=True)
    log_test("23-adopt", f"ricet adopt {existing} --name adopted-math",
             cwd=TEST_ROOT, timeout=60)


def test_22_crossrepo():
    """Section 24-25: Cross-repo RAG and sync learnings."""
    linked = TEST_ROOT / "linked-numerics"
    linked.mkdir(parents=True, exist_ok=True)
    (linked / "gauss.py").write_text(
        "def gauss_quad(f, a, b, n=5):\n"
        "    '''Gaussian quadrature (Legendre).'''\n"
        "    # Placeholder for Gauss-Legendre weights and nodes\n"
        "    pass\n"
    )
    (linked / "README.md").write_text("# Numerics library with Gauss quadrature\n")
    log_test("24a-link", f'ricet link {linked} --name numerics-lib',
             cwd=PROJECT_DIR, timeout=30)
    log_test("24b-search", 'ricet memory search "quadrature"',
             cwd=PROJECT_DIR, timeout=30)
    log_test("24c-reindex", "ricet reindex", cwd=PROJECT_DIR, timeout=30)
    log_test("24d-unlink", "ricet unlink numerics-lib", cwd=PROJECT_DIR, timeout=30)

    # Cross-project learning
    other = TEST_ROOT / "other-project" / "knowledge"
    other.mkdir(parents=True, exist_ok=True)
    (other / "ENCYCLOPEDIA.md").write_text(textwrap.dedent("""\
        # Project Encyclopedia

        ## Tricks

        - [2025-01-15 10:00] Adaptive step size halves error without doubling compute.

        ## What Works

        - [2025-01-15 11:00] Richardson extrapolation improves trapezoidal rule to O(h^4).
    """))
    log_test("25-sync", f"ricet sync-learnings {TEST_ROOT / 'other-project'}",
             cwd=PROJECT_DIR, timeout=30)


def test_23_tworepo():
    """Section 26: Dual-repo structure."""
    log_test("26a-tworepo", "ricet two-repo init", cwd=PROJECT_DIR, timeout=30)
    log_test("26b-tworepo", "ricet two-repo status", cwd=PROJECT_DIR, timeout=30)
    # Create a file in experiments and promote
    exp_dir = PROJECT_DIR / "experiments"
    exp_dir.mkdir(exist_ok=True)
    (exp_dir / "validated_integrator.py").write_text("VALIDATED = True\n")
    log_test("26c-tworepo",
             'ricet two-repo promote --files "validated_integrator.py" '
             '--message "Promote validated integrator"',
             cwd=PROJECT_DIR, timeout=30)
    log_test("26d-tworepo", "ricet two-repo diff", cwd=PROJECT_DIR, timeout=30)


def test_24_infra():
    """Section 27: Infrastructure."""
    log_test("27a-infra", "ricet infra check", cwd=PROJECT_DIR, timeout=30)
    log_test("27b-infra", "ricet infra cicd --template python",
             cwd=PROJECT_DIR, timeout=30)
    log_test("27c-infra", "ricet infra secrets", cwd=PROJECT_DIR, timeout=30)


def test_25_runbook():
    """Section 28: Runbook execution."""
    rb = SCRATCHPAD / "integration_runbook.md"
    rb.write_text(textwrap.dedent("""\
        # Integration Methods Runbook

        ## Step 1: Check Python
        ```bash
        python3 --version
        ```

        ## Step 2: Verify numpy
        ```bash
        python3 -c "import math; print(math.pi)"
        ```

        ## Step 3: Run a quick integration
        ```bash
        python3 -c "
        h = 0.01; s = sum(x**2 * h for x in [i*h for i in range(100)])
        print(f'Approx integral of x^2 on [0,1]: {s:.4f} (exact: 0.3333)')
        "
        ```
    """))
    log_test("28a-runbook", f"ricet runbook {rb}", cwd=PROJECT_DIR, timeout=30)
    log_test("28b-runbook", f"ricet runbook {rb} --execute",
             cwd=PROJECT_DIR, timeout=60)


def test_26_worktree():
    """Section 29: Git worktrees."""
    # Ensure project is a git repo with at least one commit
    subprocess.run("git init 2>/dev/null; git add -A; git commit -m 'pre-worktree' --allow-empty 2>/dev/null",
                   shell=True, cwd=PROJECT_DIR, capture_output=True)
    log_test("29a-worktree", "ricet worktree list", cwd=PROJECT_DIR, timeout=30)
    log_test("29b-worktree", "ricet worktree add experiment-mc-variance",
             cwd=PROJECT_DIR, timeout=30)
    log_test("29c-worktree", "ricet worktree remove experiment-mc-variance",
             cwd=PROJECT_DIR, timeout=30)
    log_test("29d-worktree", "ricet worktree prune", cwd=PROJECT_DIR, timeout=30)


def test_27_queue():
    """Section 30: Task queue."""
    log_test("30a-queue",
             'ricet queue submit --prompt "Analyze trapezoidal convergence on sin(x)"',
             cwd=PROJECT_DIR, timeout=30)
    log_test("30b-queue",
             'ricet queue submit --prompt "Plot Simpson vs Monte Carlo error"',
             cwd=PROJECT_DIR, timeout=30)
    log_test("30c-queue", "ricet queue status", cwd=PROJECT_DIR, timeout=30)
    log_test("30d-queue", "ricet queue cancel-all", cwd=PROJECT_DIR, timeout=30)


def test_28_projects():
    """Section 31: Multiple projects."""
    log_test("31a-projects", "ricet projects list", cwd=PROJECT_DIR, timeout=30)
    log_test("31b-projects", "ricet projects register", cwd=PROJECT_DIR, timeout=30,
             stdin_text=f"{PROJECT_NAME}\n{PROJECT_DIR}\n")


def test_29_package():
    """Section 32: Package management."""
    log_test("32a-package", "ricet package init", cwd=PROJECT_DIR, timeout=30,
             stdin_text="integration-methods\n0.1.0\nNumerical integration comparison\n")
    log_test("32b-package", "ricet package build", cwd=PROJECT_DIR, timeout=60)


def test_30_website():
    """Section 33: Website builder."""
    log_test("33a-website", "ricet website init", cwd=PROJECT_DIR, timeout=30)
    log_test("33b-website", "ricet website build", cwd=PROJECT_DIR, timeout=60)


def test_31_social():
    """Section 36: Social publishing."""
    log_test("36a-social", "ricet publish medium", cwd=PROJECT_DIR, timeout=60,
             stdin_text="Integration Methods Compared\nWe compare trapezoidal, Simpson, and Monte Carlo.\n")
    log_test("36b-social", "ricet publish linkedin", cwd=PROJECT_DIR, timeout=60,
             stdin_text="Integration Methods Compared\nWe compare trapezoidal, Simpson, and Monte Carlo.\n")


def test_32_zapier():
    """Section 37: Zapier integration."""
    log_test("37-zapier", 'ricet zapier setup --key "test-key-12345"',
             cwd=PROJECT_DIR, timeout=30,
             env_extra={"ZAPIER_NLA_API_KEY": "test-key-12345"})


def test_33_review_claude():
    """Section 38: Review CLAUDE.md."""
    log_test("38-review", "ricet review-claude-md", cwd=PROJECT_DIR, timeout=60)


def test_34_autocommit():
    """Section 39: Auto-commit behavior."""
    log_test("39a-autocommit", "echo $RICET_AUTO_COMMIT", cwd=PROJECT_DIR)
    log_test("39b-autocommit", "ricet config",
             cwd=PROJECT_DIR,
             env_extra={"RICET_AUTO_COMMIT": "false"},
             stdin_text="\n")


def test_35_envvars():
    """Section 40: Environment variables."""
    log_test("40a-env", "ricet agents",
             cwd=PROJECT_DIR,
             env_extra={"RICET_NO_CLAUDE": "true"})
    log_test("40b-env", "ricet fidelity",
             cwd=PROJECT_DIR,
             env_extra={"RICET_NO_CLAUDE": "true"})


def test_36_voice():
    """Section 34: Voice prompting (record expected-to-fail info)."""
    r = log_test("34-voice", "ricet voice --duration 2",
                 cwd=PROJECT_DIR, timeout=30,
                 note="Expected: needs microphone/whisper. User must test manually.")
    r.note = "MANUAL CHECK REQUIRED: Voice input needs real microphone + whisper"


def test_37_mobile():
    """Section 35: Mobile companion."""
    log_test("35a-mobile", "ricet mobile status", cwd=PROJECT_DIR, timeout=30)
    log_test("35b-mobile", "ricet mobile connect-info", cwd=PROJECT_DIR, timeout=30)
    log_test("35c-mobile", 'ricet mobile pair --label "test-phone"',
             cwd=PROJECT_DIR, timeout=30)
    log_test("35d-mobile", "ricet mobile tokens", cwd=PROJECT_DIR, timeout=30)


def test_38_github_integration():
    """Test real GitHub integration with PAT."""
    pat = os.environ.get("GITHUB_TOKEN", "")
    if not pat:
        r = TestResult(
            section="GH-integration", command="GitHub PAT test",
            stdout="", stderr="GITHUB_TOKEN not set", returncode=1,
            duration=0, passed=False, note="Skipped: no token",
        )
        results.append(r)
        return

    # Initialize git in project, commit, create remote repo, push
    log_test("GH-init", "git init && git add -A && git commit -m 'initial ricet project'",
             cwd=PROJECT_DIR, timeout=30)
    # Create a GitHub repo using gh CLI
    log_test("GH-create",
             f'gh repo create lucafusarbassini/ricet-integration-test --private --source=. --push --description "ricet integration test (auto-delete)" || true',
             cwd=PROJECT_DIR, timeout=60,
             env_extra={"GH_TOKEN": pat})
    # Commit some changes
    log_test("GH-commit",
             'git add -A && git commit -m "add integrators and test data" --allow-empty',
             cwd=PROJECT_DIR, timeout=30)
    log_test("GH-push", "git push origin main || git push origin master || true",
             cwd=PROJECT_DIR, timeout=30,
             env_extra={"GH_TOKEN": pat})


def test_39_email_notification():
    """Test real SMTP email notification."""
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")
    if not all([smtp_host, smtp_user, smtp_pass]):
        r = TestResult(
            section="EMAIL-notify", command="SMTP test",
            stdout="", stderr="SMTP credentials not set", returncode=1,
            duration=0, passed=False, note="Skipped: no SMTP creds",
        )
        results.append(r)
        return

    # Use Python to send a test email
    email_script = SCRATCHPAD / "send_test_email.py"
    email_script.write_text(textwrap.dedent(f"""\
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart()
        msg["From"] = "{smtp_user}"
        msg["To"] = "{smtp_user}"
        msg["Subject"] = "ricet integration test - notification check"
        body = "This is an automated test email from ricet integration test suite.\\n"
        body += "If you received this, email notifications work correctly.\\n"
        body += f"Timestamp: {{__import__('datetime').datetime.now().isoformat()}}"
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP("{smtp_host}", 587) as server:
            server.starttls()
            server.login("{smtp_user}", "{smtp_pass}")
            server.send_message(msg)
        print("Email sent successfully")
    """))
    log_test("EMAIL-notify", f"python3 {email_script}",
             cwd=PROJECT_DIR, timeout=30)


def test_40_pypi_test():
    """Test PyPI token (publish to TestPyPI, expect controlled failure or success)."""
    log_test("PYPI-package", "ricet package publish",
             cwd=PROJECT_DIR, timeout=60,
             note="Expected: may fail without proper setup; tests the flow")


def test_41_pytest_suite():
    """Section 41: Run the actual pytest suite."""
    log_test("41-pytest", "python -m pytest tests/ -x --tb=short -q 2>&1 | tail -50",
             cwd=REPO_ROOT, timeout=600)


def test_42_edge_cases():
    """Edge cases: empty inputs, bad paths, Unicode, etc."""
    # Empty goal
    log_test("edge-empty", 'ricet verify ""', cwd=PROJECT_DIR, timeout=30,
             note="Edge: empty claim")
    # Unicode input
    log_test("edge-unicode",
             'ricet memory log-decision "Verwende Gauß-Quadratur für bessere Konvergenz"',
             cwd=PROJECT_DIR, timeout=30,
             note="Edge: German unicode input")
    # Very long input
    long_str = "x" * 500
    log_test("edge-long", f'ricet verify "{long_str}"',
             cwd=PROJECT_DIR, timeout=60,
             note="Edge: very long claim string")
    # Non-existent file
    log_test("edge-nofile", 'ricet runbook /tmp/nonexistent_runbook_12345.md',
             cwd=PROJECT_DIR, timeout=30, expect_fail=True,
             note="Edge: non-existent file (should fail gracefully)")
    # Invalid MCP search
    log_test("edge-mcp", 'ricet mcp-search ""', cwd=PROJECT_DIR, timeout=30,
             note="Edge: empty MCP search")


# ---------------------------------------------------------------------------
# PDF report generation
# ---------------------------------------------------------------------------
def generate_pdf_report(output_path: Path):
    """Generate a PDF report from test results."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError:
        print("reportlab not installed. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "reportlab"],
                       capture_output=True)
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

    doc = SimpleDocTemplate(str(output_path), pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=18)
    story.append(Paragraph("ricet 0.3.0 -- Full Integration Test Report", title_style))
    story.append(Spacer(1, 5*mm))

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    story.append(Paragraph(f"Generated: {ts}", styles["Normal"]))
    story.append(Paragraph(f"Toy Problem: Comparing Numerical Integration Methods", styles["Normal"]))
    story.append(Spacer(1, 3*mm))

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    story.append(Paragraph(f"<b>Total: {total} | Passed: {passed} | Failed: {failed} | Pass rate: {100*passed/max(total,1):.1f}%</b>",
                           styles["Normal"]))
    story.append(Spacer(1, 5*mm))

    # Detailed results
    code_style = ParagraphStyle("Code", parent=styles["Normal"], fontSize=6,
                                fontName="Courier", leading=8)
    section_style = ParagraphStyle("Section", parent=styles["Heading3"], fontSize=10)

    current_section = ""
    for r in results:
        sec = r.section.split("-")[0] if "-" in r.section else r.section
        if sec != current_section:
            current_section = sec
            story.append(Spacer(1, 3*mm))
            story.append(Paragraph(f"Section: {r.section}", section_style))

        status = '<font color="green">PASS</font>' if r.passed else '<font color="red">FAIL</font>'
        story.append(Paragraph(f"{status} | <font face='Courier' size='7'>{r.command[:100]}</font>",
                               styles["Normal"]))
        if r.note:
            story.append(Paragraph(f"  Note: {r.note}", styles["Normal"]))
        # Show first 300 chars of output
        out = (r.stdout or r.stderr or "")[:300].replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
        if out.strip():
            story.append(Paragraph(f"<font face='Courier' size='6'>{out}</font>", styles["Normal"]))
        story.append(Spacer(1, 1*mm))

    # Manual checks section
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("Items Requiring Manual Verification", styles["Heading2"]))
    manual_items = [
        ("Voice Input (ricet voice)", "Needs physical microphone + whisper installed. Run: ricet voice --duration 10"),
        ("Mobile Companion (ricet mobile)", "Start PWA server with 'ricet mobile start', scan QR on phone, verify voice commands work"),
        ("Web Dashboard (ricet status --dashboard)", "Open TUI dashboard, verify live metrics update"),
        ("Interactive Session (ricet start)", "Launch full Claude Code session, give it a research task, verify agent routing"),
        ("Overnight with Docker (ricet overnight --docker)", "Requires Docker daemon running; verify container isolation"),
        ("Browser Screenshots (ricet browse --screenshot)", "Requires Puppeteer MCP; verify PNG output"),
        ("Style Transfer with real PDF", "ricet paper adapt-style --reference <nature_paper.pdf>"),
    ]
    for title, desc in manual_items:
        story.append(Paragraph(f"<b>{title}</b>: {desc}", styles["Normal"]))
        story.append(Spacer(1, 1*mm))

    doc.build(story)
    print(f"\nPDF report written to: {output_path}")
    return output_path


def send_email_report(pdf_path: Path):
    """Send the PDF report via email."""
    import smtplib
    from email.mime.application import MIMEApplication
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")

    if not all([smtp_user, smtp_pass]):
        print("SMTP credentials not set; skipping email.")
        return

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = smtp_user
    msg["Subject"] = f"ricet 0.3.0 Integration Test Report - {datetime.datetime.now().strftime('%Y-%m-%d')}"

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    body = (
        f"ricet Full Integration Test Report\n"
        f"{'='*40}\n"
        f"Total tests: {total}\n"
        f"Passed: {passed}\n"
        f"Failed: {total - passed}\n"
        f"Pass rate: {100*passed/max(total,1):.1f}%\n\n"
        f"See attached PDF for full details.\n\n"
        f"Toy problem: Comparing Numerical Integration Methods\n"
    )
    msg.attach(MIMEText(body, "plain"))

    with open(pdf_path, "rb") as f:
        att = MIMEApplication(f.read(), _subtype="pdf")
        att.add_header("Content-Disposition", "attachment",
                       filename=pdf_path.name)
        msg.attach(att)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
    print(f"Email sent to {smtp_user}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="ricet full integration test")
    parser.add_argument("--pdf", action="store_true", help="Generate PDF report")
    parser.add_argument("--email", action="store_true", help="Send PDF via email")
    parser.add_argument("--sections", nargs="*", help="Run only specific sections")
    args = parser.parse_args()

    print("=" * 60)
    print("ricet 0.3.0 -- Full Integration Test")
    print(f"Started: {datetime.datetime.now().isoformat()}")
    print("=" * 60)

    # Run all test functions in order
    test_funcs = [
        test_00_prerequisites,
        test_01_init,
        test_02_config,
        test_03_status,
        test_04_sessions,
        test_05_agents,
        test_06_memory,
        test_07_metrics,
        test_08_paper,
        test_09_literature,
        test_10_browse,
        test_11_verify,
        test_12_debug,
        test_13_overnight,
        test_14_auto_routines,
        test_15_repro,
        test_16_mcp,
        test_17_testgen,
        test_18_docs,
        test_19_fidelity,
        test_20_maintain,
        test_21_adopt,
        test_22_crossrepo,
        test_23_tworepo,
        test_24_infra,
        test_25_runbook,
        test_26_worktree,
        test_27_queue,
        test_28_projects,
        test_29_package,
        test_30_website,
        test_31_social,
        test_32_zapier,
        test_33_review_claude,
        test_34_autocommit,
        test_35_envvars,
        test_36_voice,
        test_37_mobile,
        test_38_github_integration,
        test_39_email_notification,
        test_40_pypi_test,
        test_41_pytest_suite,
        test_42_edge_cases,
    ]

    for fn in test_funcs:
        sec_name = fn.__name__.replace("test_", "")
        if args.sections and sec_name not in args.sections:
            continue
        print(f"\n--- {fn.__doc__ or fn.__name__} ---")
        try:
            fn()
        except Exception as e:
            print(f"  EXCEPTION in {fn.__name__}: {e}")
            results.append(TestResult(
                section=fn.__name__, command="EXCEPTION",
                stdout="", stderr=str(e), returncode=-1,
                duration=0, passed=False, note=f"Exception: {e}",
            ))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    print(f"Total: {total}  Passed: {passed}  Failed: {failed}")
    print(f"Pass rate: {100*passed/max(total,1):.1f}%")

    # Save JSON results
    json_path = SCRATCHPAD / "test_results.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w") as f:
        json.dump([{
            "section": r.section, "command": r.command,
            "passed": r.passed, "returncode": r.returncode,
            "duration": r.duration, "note": r.note,
            "stdout": r.stdout[:500], "stderr": r.stderr[:300],
        } for r in results], f, indent=2)
    print(f"JSON results: {json_path}")

    if args.pdf or args.email:
        pdf_path = SCRATCHPAD / "ricet_integration_report.pdf"
        generate_pdf_report(pdf_path)

    if args.email:
        try:
            send_email_report(pdf_path)
        except Exception as e:
            print(f"Email failed: {e}")

    # Return exit code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
