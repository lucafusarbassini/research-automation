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

def _extract_factual_sentences(text: str) -> list[str]:
    """Return sentences that look like factual claims worth verifying."""
    if not text.strip():
        return []
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


def verify_text(text: str, project_path: str = "") -> dict:
    """Run all verifiers on *text* and return a summary dict.

    Returns:
        Dict with ``verdict`` (str) and ``issues`` (list[str]).
    """
    results: list[VerificationResult] = []
    results.extend(verify_claims(text))
    if project_path:
        results.extend(verify_file_references(text, Path(project_path)))
    results.extend(verify_citations(text))

    issues = [r.claim for r in results if not r.verified]
    verdict = "all_verified" if not issues else "issues_found"
    return {"verdict": verdict, "issues": issues}
