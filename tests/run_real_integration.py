#!/usr/bin/env python3
"""Real end-to-end integration test runner.

Runs every ricet command for real, captures actual stdout/stderr,
and generates a PDF report from the real outputs. NO MOCKS. NO PLACEHOLDERS.

Usage:
    python tests/run_real_integration.py
"""

import datetime
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
PROJECT_DIR = Path("/tmp/ricet-integration-test/fibonacci-golden-ratio")
REPORT_DIR = REPO_ROOT / "tests" / "output"
GITHUB_PAT = os.environ.get("GITHUB_PAT", "")
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")

results = []
step_counter = 0


def run_step(
    name: str,
    cmd: list[str] | str,
    cwd: Path | str | None = None,
    timeout: int = 120,
    input_text: str | None = None,
    env_extra: dict | None = None,
    shell: bool = False,
) -> dict:
    """Run a command, capture everything, record result."""
    global step_counter
    step_counter += 1

    if cwd is None:
        cwd = PROJECT_DIR
    cwd = str(cwd)

    env = os.environ.copy()
    env["RICET_AUTO_COMMIT"] = "false"
    env["AUTO_PUSH"] = "false"
    if env_extra:
        env.update(env_extra)

    cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
    print(f"\n{'='*70}")
    print(f"STEP {step_counter}: {name}")
    print(f"CMD:  {cmd_str}")
    print(f"CWD:  {cwd}")
    print(f"{'='*70}")

    start = time.time()
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            input=input_text,
            shell=shell,
        )
        elapsed = time.time() - start
        stdout = r.stdout or ""
        stderr = r.stderr or ""
        rc = r.returncode
    except subprocess.TimeoutExpired:
        elapsed = timeout
        stdout = ""
        stderr = f"TIMEOUT after {timeout}s"
        rc = 124
    except Exception as e:
        elapsed = time.time() - start
        stdout = ""
        stderr = str(e)
        rc = 1

    # Print real output
    if stdout.strip():
        print(f"STDOUT:\n{stdout[:3000]}")
    if stderr.strip():
        print(f"STDERR:\n{stderr[:1500]}")
    print(f"EXIT CODE: {rc} | TIME: {elapsed:.1f}s")

    result = {
        "step": step_counter,
        "name": name,
        "command": cmd_str,
        "stdout": stdout[:4000],
        "stderr": stderr[:2000],
        "returncode": rc,
        "passed": rc == 0,
        "elapsed": round(elapsed, 1),
        "note": "",
    }
    results.append(result)
    return result


def generate_report():
    """Generate real PDF report from collected results."""
    sys.path.insert(0, str(REPO_ROOT))
    from core.report import TestReport, TestResult, generate_pdf_report

    report = TestReport(
        title="ricet 0.3.0 — Real End-to-End Integration Test",
        started_at=(
            datetime.datetime.fromisoformat(
                results[0].get("_ts", datetime.datetime.now().isoformat())
            )
            if results
            else datetime.datetime.now()
        ),
        finished_at=datetime.datetime.now(),
    )

    for r in results:
        report.add(
            TestResult(
                step=r["step"],
                name=r["name"],
                command=r["command"],
                stdout=r["stdout"],
                stderr=r["stderr"],
                returncode=r["returncode"],
                passed=r["passed"],
                note=f"[{r['elapsed']}s] {r.get('note', '')}",
            )
        )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = generate_pdf_report(report, REPORT_DIR)

    # Also save raw JSON for inspection
    json_path = REPORT_DIR / "integration_results.json"
    json_path.write_text(json.dumps(results, indent=2))

    # Also save a detailed markdown
    md_path = REPORT_DIR / "integration_report.md"
    md_path.write_text(report.to_markdown())

    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    print(f"\n{'='*70}")
    print(f"REPORT: {passed} passed, {failed} failed, {len(results)} total")
    print(f"PDF:    {pdf_path}")
    print(f"JSON:   {json_path}")
    print(f"MD:     {md_path}")
    print(f"{'='*70}")

    return pdf_path


# ---------------------------------------------------------------------------
# THE REAL TEST
# ---------------------------------------------------------------------------


def main():
    print(f"Starting real integration test at {datetime.datetime.now().isoformat()}")
    print(f"Project dir: {PROJECT_DIR}")

    # Clean slate
    if PROJECT_DIR.exists():
        shutil.rmtree(PROJECT_DIR)
    PROJECT_DIR.parent.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # STEP 1: ricet init (with piped answers to interactive prompts)
    # -----------------------------------------------------------------------
    run_step(
        "ricet init fibonacci-golden-ratio",
        ["ricet", "init", "fibonacci-golden-ratio", "--skip-repo"],
        cwd=PROJECT_DIR.parent,
        input_text="none\n\n\n\n\n\n\n",
        timeout=60,
    )

    # Fallback scaffold if init didn't fully create the project
    if not PROJECT_DIR.exists():
        PROJECT_DIR.mkdir(parents=True)
    for d in ["knowledge", "paper", "config", "state", "src", ".claude"]:
        (PROJECT_DIR / d).mkdir(exist_ok=True)
    if not (PROJECT_DIR / "knowledge" / "ENCYCLOPEDIA.md").exists():
        (PROJECT_DIR / "knowledge" / "ENCYCLOPEDIA.md").write_text(
            "# Encyclopedia\n\n## Tricks\n<!-- Short tips -->\n\n"
            "## Decisions\n<!-- Key decisions -->\n\n"
            "## What Works\n<!-- Approaches that succeeded -->\n\n"
            "## What Doesn't Work\n<!-- Approaches that failed -->\n\n"
        )
    if not (PROJECT_DIR / "knowledge" / "GOAL.md").exists():
        (PROJECT_DIR / "knowledge" / "GOAL.md").write_text("# Goal\n\nTBD\n")
    if not (PROJECT_DIR / "state" / "TODO.md").exists():
        (PROJECT_DIR / "state" / "TODO.md").write_text("# TODO\n\n")
    if not (PROJECT_DIR / "config" / "settings.yml").exists():
        (PROJECT_DIR / "config" / "settings.yml").write_text(
            "project:\n  name: fibonacci-golden-ratio\n"
        )

    # -----------------------------------------------------------------------
    # STEP 2: Write GOAL.md
    # -----------------------------------------------------------------------
    goal_path = PROJECT_DIR / "knowledge" / "GOAL.md"
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
    run_step(
        "Write GOAL.md",
        f"cat {goal_path}",
        shell=True,
    )

    # -----------------------------------------------------------------------
    # STEP 3: Write and run fibonacci computation
    # -----------------------------------------------------------------------
    fib_code = textwrap.dedent("""\
    #!/usr/bin/env python3
    \"\"\"Fibonacci golden ratio convergence analysis.\"\"\"
    import math
    import json
    from pathlib import Path

    PHI = (1 + math.sqrt(5)) / 2

    def fibonacci_ratios(n: int) -> list[float]:
        a, b = 1, 1
        ratios = []
        for _ in range(n):
            ratios.append(b / a)
            a, b = b, a + b
        return ratios

    def convergence_errors(ratios: list[float]) -> list[float]:
        return [abs(r - PHI) for r in ratios]

    def geometric_rate(errors: list[float]) -> float:
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
        expected_rate = 1 / PHI**2

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

        Path("results.json").write_text(json.dumps(results, indent=2))
        print(f"phi estimate:     {ratios[-1]:.15f}")
        print(f"phi exact:        {PHI:.15f}")
        print(f"absolute error:   {errors[-1]:.2e}")
        print(f"convergence rate: {rate:.6f} (expected {expected_rate:.6f})")
        print(f"rate error:       {abs(rate - expected_rate):.2e}")
        print(f"first 5 ratios:   {ratios[:5]}")
        print(f"first 5 errors:   {[f'{e:.6e}' for e in errors[:5]]}")
    """)
    (PROJECT_DIR / "src" / "fibonacci.py").write_text(fib_code)

    run_step(
        "Run fibonacci computation",
        [sys.executable, "src/fibonacci.py"],
    )

    # -----------------------------------------------------------------------
    # STEP 4: ricet --version
    # -----------------------------------------------------------------------
    run_step("ricet --version", ["ricet", "--version"])

    # -----------------------------------------------------------------------
    # STEP 5: ricet config
    # -----------------------------------------------------------------------
    run_step("ricet config", ["ricet", "config"])

    # -----------------------------------------------------------------------
    # STEP 6: ricet status
    # -----------------------------------------------------------------------
    run_step("ricet status", ["ricet", "status"])

    # -----------------------------------------------------------------------
    # STEP 7: ricet agents
    # -----------------------------------------------------------------------
    run_step("ricet agents", ["ricet", "agents"])

    # -----------------------------------------------------------------------
    # STEP 8: ricet metrics
    # -----------------------------------------------------------------------
    run_step("ricet metrics", ["ricet", "metrics"])

    # -----------------------------------------------------------------------
    # STEP 9: ricet memory search (real)
    # -----------------------------------------------------------------------
    run_step(
        "ricet memory search",
        ["ricet", "memory", "search", "golden ratio convergence"],
    )

    # -----------------------------------------------------------------------
    # STEP 10: ricet cite (real Claude)
    # -----------------------------------------------------------------------
    run_step(
        "ricet cite 'golden ratio fibonacci'",
        ["ricet", "cite", "golden ratio fibonacci convergence"],
        timeout=90,
    )

    # -----------------------------------------------------------------------
    # STEP 11: ricet verify (real Claude)
    # -----------------------------------------------------------------------
    run_step(
        "ricet verify (real Claude)",
        [
            "ricet",
            "verify",
            "The golden ratio phi=1.618033988749895 and F(n+1)/F(n) converges geometrically at rate 1/phi^2",
        ],
        timeout=90,
    )

    # -----------------------------------------------------------------------
    # STEP 12: ricet paper build
    # -----------------------------------------------------------------------
    run_step("ricet paper build", ["ricet", "paper", "build"], timeout=30)

    # -----------------------------------------------------------------------
    # STEP 13: ricet fidelity (real)
    # -----------------------------------------------------------------------
    run_step("ricet fidelity", ["ricet", "fidelity"], timeout=60)

    # -----------------------------------------------------------------------
    # STEP 14: ricet browse (real URL fetch)
    # -----------------------------------------------------------------------
    run_step(
        "ricet browse Wikipedia Golden Ratio",
        ["ricet", "browse", "https://en.wikipedia.org/wiki/Golden_ratio"],
        timeout=30,
    )

    # -----------------------------------------------------------------------
    # STEP 15: ricet docs
    # -----------------------------------------------------------------------
    run_step("ricet docs", ["ricet", "docs"], timeout=30)

    # -----------------------------------------------------------------------
    # STEP 16: ricet test-gen
    # -----------------------------------------------------------------------
    run_step("ricet test-gen", ["ricet", "test-gen"], timeout=90)

    # -----------------------------------------------------------------------
    # STEP 17: ricet repro log
    # -----------------------------------------------------------------------
    run_step("ricet repro log", ["ricet", "repro", "log"])

    # -----------------------------------------------------------------------
    # STEP 18: ricet list-sessions
    # -----------------------------------------------------------------------
    run_step("ricet list-sessions", ["ricet", "list-sessions"])

    # -----------------------------------------------------------------------
    # STEP 19: ricet mcp-search
    # -----------------------------------------------------------------------
    run_step(
        "ricet mcp-search 'math computation'",
        ["ricet", "mcp-search", "math computation"],
        timeout=30,
    )

    # -----------------------------------------------------------------------
    # STEP 20: ricet sync-learnings
    # -----------------------------------------------------------------------
    run_step("ricet sync-learnings", ["ricet", "sync-learnings"])

    # -----------------------------------------------------------------------
    # STEP 21: ricet paper adapt-style (edge: missing ref)
    # -----------------------------------------------------------------------
    run_step(
        "ricet paper adapt-style (edge: missing reference)",
        ["ricet", "paper", "adapt-style", "--reference", "nonexistent.pdf"],
    )

    # -----------------------------------------------------------------------
    # STEP 22: ricet maintain
    # -----------------------------------------------------------------------
    run_step("ricet maintain", ["ricet", "maintain"], timeout=120)

    # -----------------------------------------------------------------------
    # STEP 23: Edge — empty memory query
    # -----------------------------------------------------------------------
    run_step("Edge: ricet memory search ''", ["ricet", "memory", "search", ""])

    # -----------------------------------------------------------------------
    # STEP 24: Edge — duplicate cite
    # -----------------------------------------------------------------------
    run_step(
        "Edge: duplicate ricet cite", ["ricet", "cite", "golden ratio"], timeout=60
    )

    # -----------------------------------------------------------------------
    # STEP 25: ricet discover
    # -----------------------------------------------------------------------
    run_step(
        "ricet discover 'fibonacci golden ratio'",
        ["ricet", "discover", "fibonacci golden ratio"],
        timeout=60,
    )

    # -----------------------------------------------------------------------
    # STEP 26: GitHub — configure PAT and test
    # -----------------------------------------------------------------------
    if GITHUB_PAT:
        run_step(
            "GitHub: gh auth status",
            f"echo '{GITHUB_PAT}' | gh auth login --with-token 2>&1; gh auth status",
            shell=True,
            cwd=PROJECT_DIR,
        )

        run_step(
            "GitHub: list repos",
            ["gh", "repo", "list", "--limit", "5"],
        )

        run_step(
            "GitHub: view research-automation repo",
            [
                "gh",
                "repo",
                "view",
                "lucafusarbassini/research-automation",
                "--json",
                "name,description,url",
            ],
        )
    else:
        results.append(
            {
                "step": step_counter + 1,
                "name": "GitHub tests",
                "command": "SKIPPED — no GITHUB_PAT",
                "stdout": "",
                "stderr": "",
                "returncode": -1,
                "passed": False,
                "elapsed": 0,
                "note": "Set GITHUB_PAT env var",
            }
        )
        step_counter += 1

    # -----------------------------------------------------------------------
    # STEP 29: ricet auto list
    # -----------------------------------------------------------------------
    run_step("ricet auto list", ["ricet", "auto", "list"])

    # -----------------------------------------------------------------------
    # STEP 30: ricet repro list
    # -----------------------------------------------------------------------
    run_step("ricet repro list", ["ricet", "repro", "list"])

    # -----------------------------------------------------------------------
    # STEP 31: ricet memory stats
    # -----------------------------------------------------------------------
    run_step("ricet memory stats", ["ricet", "memory", "stats"])

    # -----------------------------------------------------------------------
    # STEP 32: Python — verify results.json mathematically
    # -----------------------------------------------------------------------
    run_step(
        "Mathematical verification of results.json",
        [
            sys.executable,
            "-c",
            textwrap.dedent("""\
        import json, math
        PHI = (1 + math.sqrt(5)) / 2
        data = json.loads(open('results.json').read())
        checks = []
        checks.append(f"phi_estimate={data['phi_estimate']:.15f}")
        checks.append(f"phi_exact={PHI:.15f}")
        checks.append(f"match={abs(data['phi_estimate']-PHI) < 1e-15}")
        checks.append(f"conv_rate={data['convergence_rate']:.6f}")
        checks.append(f"expected_rate={data['expected_rate']:.6f}")
        checks.append(f"rate_match={abs(data['convergence_rate']-data['expected_rate']) < 0.01}")
        checks.append(f"first_ratio={data['first_20_ratios'][0]} (should be 1.0)")
        for c in checks:
            print(c)
        assert abs(data['phi_estimate']-PHI) < 1e-15, "PHI MISMATCH"
        assert abs(data['convergence_rate']-data['expected_rate']) < 0.01, "RATE MISMATCH"
        print("ALL MATHEMATICAL CHECKS PASSED")
        """),
        ],
    )

    # -----------------------------------------------------------------------
    # STEP 33: Notification — real email with PDF
    # -----------------------------------------------------------------------
    # Generate report first
    pdf_path = generate_report()

    if SMTP_USER and SMTP_PASS:
        run_step(
            "Send real email with PDF attachment",
            [
                sys.executable,
                "-c",
                textwrap.dedent(f"""\
            import sys; sys.path.insert(0, '{REPO_ROOT}')
            from core.notifications import send_email_with_attachment, NotificationConfig
            from pathlib import Path
            cfg = NotificationConfig(
                email_to='{SMTP_USER}',
                smtp_user='{SMTP_USER}',
                smtp_password='{SMTP_PASS}',
                smtp_host='smtp.gmail.com',
                smtp_port=587,
                throttle_seconds=0,
            )
            r = send_email_with_attachment(
                'ricet 0.3.0 REAL Integration Test — command-by-command output',
                'Attached: PDF with real command outputs from end-to-end test run.\\n'
                'Every command was actually executed. No mocks. No placeholders.',
                Path('{pdf_path}'),
                cfg,
            )
            print(f'Email sent: {{r}}')
            """),
            ],
            cwd=REPO_ROOT,
        )
    else:
        results.append(
            {
                "step": step_counter + 1,
                "name": "Email PDF",
                "command": "SKIPPED — no SMTP_USER/SMTP_PASS",
                "stdout": "",
                "stderr": "",
                "returncode": -1,
                "passed": False,
                "elapsed": 0,
                "note": "",
            }
        )
        step_counter += 1

    # Regenerate report with email step included
    generate_report()

    print(f"\nDone at {datetime.datetime.now().isoformat()}")
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    print(f"FINAL: {passed} passed, {failed} failed, {len(results)} total")


if __name__ == "__main__":
    main()
