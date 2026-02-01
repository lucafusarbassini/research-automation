"""Tests for the verification / double-check module."""

from pathlib import Path

from core.verification import (
    VerificationResult,
    auto_verify_response,
    build_verification_table,
    verify_citations,
    verify_claims,
    verify_code_output,
    verify_file_references,
)


# ---------------------------------------------------------------------------
# VerificationResult dataclass
# ---------------------------------------------------------------------------

def test_verification_result_fields():
    vr = VerificationResult(
        claim="Earth orbits the Sun",
        verified=True,
        method="knowledge-check",
        confidence=0.95,
        evidence="Basic astronomy",
    )
    assert vr.claim == "Earth orbits the Sun"
    assert vr.verified is True
    assert vr.method == "knowledge-check"
    assert vr.confidence == 0.95
    assert vr.evidence == "Basic astronomy"


def test_verification_result_defaults():
    """Confidence and evidence should have sensible defaults."""
    vr = VerificationResult(
        claim="test",
        verified=False,
        method="auto",
    )
    assert vr.confidence == 0.0
    assert vr.evidence == ""


# ---------------------------------------------------------------------------
# verify_claims
# ---------------------------------------------------------------------------

def test_verify_claims_returns_list():
    results = verify_claims("The file main.py contains 200 lines.")
    assert isinstance(results, list)
    assert all(isinstance(r, VerificationResult) for r in results)


def test_verify_claims_extracts_at_least_one():
    text = "Python was created by Guido van Rossum. The speed of light is 3e8 m/s."
    results = verify_claims(text)
    assert len(results) >= 1


def test_verify_claims_empty_text():
    results = verify_claims("")
    assert results == []


# ---------------------------------------------------------------------------
# build_verification_table
# ---------------------------------------------------------------------------

def test_build_verification_table_markdown_format():
    results = [
        VerificationResult("claim A", True, "auto", 0.9, "ok"),
        VerificationResult("claim B", False, "auto", 0.2, "not found"),
    ]
    table = build_verification_table(results)
    assert "| Claim" in table
    assert "| Verified" in table or "| Status" in table
    assert "claim A" in table
    assert "claim B" in table


def test_build_verification_table_empty():
    table = build_verification_table([])
    assert isinstance(table, str)
    # Should still produce a header or a meaningful message
    assert len(table) > 0


# ---------------------------------------------------------------------------
# verify_code_output
# ---------------------------------------------------------------------------

def test_verify_code_output_match():
    result = verify_code_output(
        code="print(1+1)",
        expected_output="2",
        actual_output="2",
    )
    assert result.verified is True
    assert result.confidence >= 0.9


def test_verify_code_output_mismatch():
    result = verify_code_output(
        code="print(1+1)",
        expected_output="3",
        actual_output="2",
    )
    assert result.verified is False


def test_verify_code_output_whitespace_tolerance():
    """Trailing/leading whitespace should not cause a mismatch."""
    result = verify_code_output(
        code="print('hello')",
        expected_output="hello",
        actual_output="  hello\n",
    )
    assert result.verified is True


# ---------------------------------------------------------------------------
# verify_file_references
# ---------------------------------------------------------------------------

def test_verify_file_references_existing(tmp_path: Path):
    (tmp_path / "README.md").write_text("hi")
    text = f"See {tmp_path}/README.md for details."
    results = verify_file_references(text, tmp_path)
    assert any(r.verified is True for r in results)


def test_verify_file_references_missing(tmp_path: Path):
    text = f"See {tmp_path}/nonexistent.txt for details."
    results = verify_file_references(text, tmp_path)
    assert any(r.verified is False for r in results)


def test_verify_file_references_no_paths():
    results = verify_file_references("No file paths here.", Path("/tmp"))
    assert results == []


# ---------------------------------------------------------------------------
# verify_citations
# ---------------------------------------------------------------------------

def test_verify_citations_wellformed():
    text = "As shown by Smith et al. (2023), transformers are effective."
    results = verify_citations(text)
    assert len(results) >= 1
    assert results[0].method == "citation-format"


def test_verify_citations_no_citations():
    results = verify_citations("Just a plain sentence with no references.")
    assert results == []


# ---------------------------------------------------------------------------
# auto_verify_response
# ---------------------------------------------------------------------------

def test_auto_verify_response_appends_table():
    response = "The file core/agents.py has 500 lines."
    context: dict = {"project_path": "/tmp"}
    output = auto_verify_response(response, context)
    assert "Verification" in output
    assert "|" in output  # markdown table indicator


def test_auto_verify_response_preserves_original():
    response = "Hello world."
    output = auto_verify_response(response, {})
    assert output.startswith("Hello world.")
