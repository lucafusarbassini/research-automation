"""Verification / double-check module.

Philosophy: "Double check everything, every single claim, and make a table of
what you were able to verify."  This happens AUTOMATICALLY -- even when the user
does not explicitly ask for it.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Patterns used for extraction
# ---------------------------------------------------------------------------

# Matches paths like /foo/bar.py, ./src/main.rs, ~/docs/notes.txt
_FILE_PATH_RE = re.compile(
    r"""(?<!\w)                     # not preceded by a word char
    (?:[~/.]|[A-Za-z]:[\\/])       # starts with ~ / . / drive letter
    [A-Za-z0-9_./ \\-]+            # path body
    \.[A-Za-z0-9]+                 # must end with an extension
    """,
    re.VERBOSE,
)

# Matches "Author et al. (YYYY)" or "(Author, YYYY)" or "(Author et al., YYYY)"
_CITATION_RE = re.compile(
    r"""
    (?:
        [A-Z][a-z]+(?:\s+et\s+al\.?)?\s*\(\d{4}\)     # Smith et al. (2023)
      | \([A-Z][a-z]+(?:\s+et\s+al\.?)?,?\s*\d{4}\)    # (Smith et al., 2023)
    )
    """,
    re.VERBOSE,
)

# Simple sentence splitter for claim extraction
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

# Heuristics for "factual-looking" sentences
_FACTUAL_KEYWORDS = re.compile(
    r"\b(?:is|are|was|were|has|have|contains?|produces?|equals?|returns?|"
    r"created|invented|discovered|founded|published|located|consists?|"
    r"measures?|weighs?|costs?|runs?|outputs?|generates?|requires?)\b",
    re.IGNORECASE,
)

# Numbers / quantities -- a sign a sentence may be making a verifiable claim
_NUMBER_RE = re.compile(r"\b\d[\d,.]*\b")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class VerificationResult:
    """Outcome of a single claim verification attempt."""

    claim: str
    verified: bool
    method: str
    confidence: float = 0.0
    evidence: str = ""


# ---------------------------------------------------------------------------
# Claim extraction helpers
# ---------------------------------------------------------------------------


def _extract_factual_sentences_claude(text: str) -> list[str] | None:
    """Try extracting factual claims via Claude CLI."""
    from core.claude_helper import call_claude_json

    prompt = (
        "Extract factual claims from this text that could be verified. "
        "Return a JSON array of strings (the claims).\n\n"
        f"Text: {text[:2000]}"
    )
    result = call_claude_json(prompt)
    if result and isinstance(result, list) and len(result) > 0:
        return [str(s) for s in result]
    return None


def _extract_factual_sentences(text: str) -> list[str]:
    """Return sentences that look like factual claims worth verifying.

    Tries Claude CLI first, falls back to regex heuristics.
    """
    if not text.strip():
        return []

    claude_result = _extract_factual_sentences_claude(text)
    if claude_result is not None:
        return claude_result

    sentences = _SENTENCE_RE.split(text.strip())
    claims: list[str] = []
    for s in sentences:
        s = s.strip().rstrip(".")
        if not s:
            continue
        # Keep sentences containing factual verbs or numeric data
        if _FACTUAL_KEYWORDS.search(s) or _NUMBER_RE.search(s):
            claims.append(s)
    return claims


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def verify_claims(text: str) -> list[VerificationResult]:
    """Extract factual claims from *text* and attempt to verify each.

    Currently uses heuristic analysis (no external API calls).  Each claim is
    scored by syntactic confidence; future versions can plug in search / LLM
    verification.
    """
    sentences = _extract_factual_sentences(text)
    results: list[VerificationResult] = []
    for claim in sentences:
        # Heuristic: claims with concrete numbers get higher confidence
        has_number = bool(_NUMBER_RE.search(claim))
        confidence = 0.5 if has_number else 0.3
        results.append(
            VerificationResult(
                claim=claim,
                verified=False,  # unverified until proven
                method="heuristic-extraction",
                confidence=confidence,
                evidence="Extracted via pattern matching; awaiting external verification",
            )
        )
    return results


def build_verification_table(results: list[VerificationResult]) -> str:
    """Render *results* as a Markdown table."""
    header = "| # | Claim | Status | Method | Confidence | Evidence |"
    sep = "|---|-------|--------|--------|------------|----------|"
    if not results:
        return f"{header}\n{sep}\n| - | _No claims extracted_ | - | - | - | - |"

    rows: list[str] = []
    for i, r in enumerate(results, 1):
        status = "Verified" if r.verified else "Unverified"
        conf = f"{r.confidence:.0%}"
        # Escape pipes inside cell values
        claim = r.claim.replace("|", "\\|")
        evidence = r.evidence.replace("|", "\\|")
        rows.append(f"| {i} | {claim} | {status} | {r.method} | {conf} | {evidence} |")

    return "\n".join([header, sep, *rows])


def verify_code_output(
    code: str,
    expected_output: str,
    actual_output: str,
) -> VerificationResult:
    """Check whether *actual_output* matches *expected_output* for *code*.

    Comparison is whitespace-tolerant (leading/trailing stripped).
    """
    expected_clean = expected_output.strip()
    actual_clean = actual_output.strip()
    match = expected_clean == actual_clean
    return VerificationResult(
        claim=f"Code output matches expected: {expected_clean!r}",
        verified=match,
        method="output-comparison",
        confidence=1.0 if match else 0.0,
        evidence=(
            f"Expected: {expected_clean!r}, Got: {actual_clean!r}"
            if not match
            else "Exact match (whitespace-normalized)"
        ),
    )


def verify_file_references(text: str, project_path: Path) -> list[VerificationResult]:
    """Check that every file path mentioned in *text* actually exists.

    Paths are resolved relative to *project_path* unless they are absolute.
    """
    matches = _FILE_PATH_RE.findall(text)
    if not matches:
        return []

    results: list[VerificationResult] = []
    seen: set[str] = set()
    for raw in matches:
        raw = raw.strip()
        if raw in seen:
            continue
        seen.add(raw)

        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = project_path / path

        exists = path.exists()
        results.append(
            VerificationResult(
                claim=f"File exists: {raw}",
                verified=exists,
                method="filesystem-check",
                confidence=1.0 if exists else 0.0,
                evidence="Found on disk" if exists else "File not found",
            )
        )
    return results


def verify_citations(text: str) -> list[VerificationResult]:
    """Basic check that cited papers / references are well-formatted and plausible."""
    matches = _CITATION_RE.findall(text)
    if not matches:
        return []

    results: list[VerificationResult] = []
    seen: set[str] = set()
    for cite in matches:
        cite = cite.strip()
        if cite in seen:
            continue
        seen.add(cite)

        # Extract the year and do a basic plausibility check
        year_match = re.search(r"\d{4}", cite)
        year = int(year_match.group()) if year_match else 0
        plausible = 1900 <= year <= 2030

        results.append(
            VerificationResult(
                claim=f"Citation is well-formed: {cite}",
                verified=plausible,
                method="citation-format",
                confidence=0.7 if plausible else 0.2,
                evidence=(
                    "Year within plausible range"
                    if plausible
                    else f"Year {year} looks implausible"
                ),
            )
        )
    return results


def auto_verify_response(response: str, context: dict) -> str:
    """Wrap an agent *response* with automatic verification.

    Runs every available verifier and appends a Markdown verification table.
    This is designed to be called unconditionally on every response so that
    claims are always double-checked.

    *context* may contain:
        - ``project_path`` (str | Path): root of the project for file checks.
    """
    all_results: list[VerificationResult] = []

    # 1. General claim extraction
    all_results.extend(verify_claims(response))

    # 2. File reference checks
    project_path = context.get("project_path")
    if project_path:
        all_results.extend(verify_file_references(response, Path(project_path)))

    # 3. Citation checks
    all_results.extend(verify_citations(response))

    table = build_verification_table(all_results)

    return f"{response}\n\n---\n### Verification Report\n\n{table}\n"


# ---------------------------------------------------------------------------
# CLI adapter — ``from core.verification import verify_text``
# ---------------------------------------------------------------------------


def check_goal_fidelity(project_path: Path, *, run_cmd=None) -> dict:
    """Check whether current work aligns with GOAL.md.

    Reads GOAL.md, PROGRESS.md, and TODO.md, then asks Claude to assess
    alignment. Returns dict with score (0-100), drift_areas, recommendations.
    """
    from core.claude_helper import call_claude_json

    goal = (
        (project_path / "knowledge" / "GOAL.md").read_text()
        if (project_path / "knowledge" / "GOAL.md").exists()
        else ""
    )
    progress = (
        (project_path / "state" / "PROGRESS.md").read_text()
        if (project_path / "state" / "PROGRESS.md").exists()
        else ""
    )
    todo = (
        (project_path / "state" / "TODO.md").read_text()
        if (project_path / "state" / "TODO.md").exists()
        else ""
    )

    if not goal.strip():
        return {"score": 0, "error": "No GOAL.md found"}

    prompt = (
        "You are a research fidelity auditor. Compare the project's current progress "
        "and TODO list against its stated goal. Assess alignment.\n\n"
        f"GOAL:\n{goal[:2000]}\n\n"
        f"PROGRESS:\n{progress[:2000]}\n\n"
        f"TODO:\n{todo[:1000]}\n\n"
        'Reply as JSON: {"score": 0-100, "drift_areas": ["..."], '
        '"recommendations": ["..."], "aligned_areas": ["..."]}'
    )
    result = call_claude_json(prompt, run_cmd=run_cmd)
    if result and isinstance(result, dict):
        return result
    return {
        "score": 50,
        "drift_areas": ["Unable to assess (Claude unavailable)"],
        "recommendations": [],
    }


def verify_claims_with_claude(text: str, *, run_cmd=None) -> list[dict]:
    """Use Claude to fact-check claims in text.

    More thorough than keyword heuristics -- Claude evaluates each
    claim's plausibility, identifies unsupported assertions, and
    flags potential errors.
    """
    from core.claude_helper import call_claude_json

    prompt = (
        "You are a scientific fact-checker. Analyze the following text and "
        "identify factual claims. For each claim, assess:\n"
        "- The claim text\n"
        "- Confidence (high/medium/low) that it's accurate\n"
        "- Reasoning for your assessment\n"
        "- Whether it needs a citation\n\n"
        'Reply as JSON array: [{"claim": "...", "confidence": "high/medium/low", '
        '"reasoning": "...", "needs_citation": true/false}]\n\n'
        f"Text:\n{text[:4000]}"
    )

    result = call_claude_json(prompt, run_cmd=run_cmd)
    if result and isinstance(result, list):
        return result
    return []


def fresh_agent_audit(project_path: Path, *, run_cmd=None) -> dict:
    """Spawn a fresh Claude agent with NO context to audit the project.

    The agent reads only the project files (no conversation history)
    and reports weaknesses, gaps, and concerns.
    """
    from core.claude_helper import call_claude_json

    # Gather a snapshot of the project structure and key files
    files_summary = []
    for py_file in sorted(project_path.glob("**/*.py"))[:30]:
        if "__pycache__" in str(py_file):
            continue
        rel = py_file.relative_to(project_path)
        try:
            first_lines = py_file.read_text()[:500]
        except Exception:
            first_lines = "(unreadable)"
        files_summary.append(f"### {rel}\n{first_lines}")

    snapshot = "\n\n".join(files_summary)

    prompt = (
        "You are a fresh code auditor with NO prior context about this project. "
        "Review the following project snapshot and identify:\n"
        "1. Half-baked or incomplete features\n"
        "2. Dead code or unused modules\n"
        "3. Security concerns\n"
        "4. Missing tests or documentation\n"
        "5. Overall quality assessment (1-10)\n\n"
        'Reply as JSON: {"score": 1-10, "issues": [{"category": "...", '
        '"description": "...", "severity": "high/medium/low"}], '
        '"strengths": ["..."]}\n\n'
        f"--- PROJECT SNAPSHOT ---\n{snapshot[:12000]}"
    )

    result = call_claude_json(prompt, run_cmd=run_cmd)
    if result and isinstance(result, dict):
        return result
    return {
        "score": 0,
        "issues": [
            {
                "category": "audit",
                "description": "Could not complete audit (Claude unavailable)",
                "severity": "high",
            }
        ],
        "strengths": [],
    }


def verify_text(text: str, project_path: str = "", *, run_cmd=None) -> dict:
    """Run all verifiers on *text* and return a summary dict.

    Returns:
        Dict with ``verdict`` (str), ``claims`` (list[dict]), and
        ``file_issues`` / ``citation_issues`` for hard failures only.
    """
    # Try Claude-powered verification first
    claude_claims = verify_claims_with_claude(text, run_cmd=run_cmd)
    if claude_claims:
        # Map confidence strings to numeric values for consistent output
        _conf_map = {"high": 0.9, "medium": 0.6, "low": 0.3}
        claim_summaries = [
            {
                "claim": c.get("claim", ""),
                "confidence": _conf_map.get(c.get("confidence", "low"), 0.3),
                "status": c.get("confidence", "low"),
                "reasoning": c.get("reasoning", ""),
                "needs_citation": c.get("needs_citation", False),
                "method": "claude-verification",
            }
            for c in claude_claims
        ]
    else:
        # Fallback to keyword heuristics
        claims = verify_claims(text)
        claim_summaries = [
            {"claim": c.claim, "confidence": c.confidence, "status": "needs_review"}
            for c in claims
        ]

    file_results: list[VerificationResult] = []
    citation_results: list[VerificationResult] = []

    if project_path:
        file_results = verify_file_references(text, Path(project_path))
    citation_results = verify_citations(text)

    # File refs and citations can be definitively verified/failed.
    hard_failures = [r for r in file_results + citation_results if not r.verified]

    if hard_failures:
        verdict = "issues_found"
    elif claim_summaries:
        verdict = "claims_extracted"
    else:
        verdict = "no_claims"

    return {
        "verdict": verdict,
        "claims": claim_summaries,
        "file_issues": [r.claim for r in file_results if not r.verified],
        "citation_issues": [r.claim for r in citation_results if not r.verified],
    }
