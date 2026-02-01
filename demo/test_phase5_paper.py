"""Phase 5 demo tests: paper pipeline (compile, citations, style transfer, verification)."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.paper import (
    COLORS,
    RC_PARAMS,
    add_citation,
    apply_rcparams,
    clean_paper,
    compile_paper,
    list_citations,
)
from core.style_transfer import StyleProfile, analyze_paper_style
from core.verification import (
    VerificationResult,
    build_verification_table,
    verify_citations,
    verify_claims,
    verify_file_references,
    verify_text,
)

# ---------------------------------------------------------------------------
# compile_paper (mocked)
# ---------------------------------------------------------------------------


class TestCompilePaper:
    """compile_paper delegates to 'make all' inside the paper directory."""

    def test_compile_paper_mocked_success(self, tmp_path):
        paper_dir = tmp_path / "paper"
        paper_dir.mkdir()
        (paper_dir / "Makefile").write_text("all:\n\techo ok\n")

        with patch("core.paper.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["make", "all"],
                returncode=0,
                stdout="ok",
                stderr="",
            )
            result = compile_paper(paper_dir)

        assert result is True
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args
        assert call_kwargs[0][0] == ["make", "all"]

    def test_compile_paper_no_makefile(self, tmp_path):
        paper_dir = tmp_path / "paper"
        paper_dir.mkdir()
        # No Makefile present
        result = compile_paper(paper_dir)
        assert result is False

    def test_compile_paper_mocked_failure(self, tmp_path):
        paper_dir = tmp_path / "paper"
        paper_dir.mkdir()
        (paper_dir / "Makefile").write_text("all:\n\tfalse\n")

        with patch(
            "core.paper.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "make"),
        ):
            result = compile_paper(paper_dir)

        assert result is False


# ---------------------------------------------------------------------------
# clean_paper (mocked)
# ---------------------------------------------------------------------------


class TestCleanPaper:
    """clean_paper runs 'make clean'."""

    def test_clean_paper_calls_make_clean(self, tmp_path):
        paper_dir = tmp_path / "paper"
        paper_dir.mkdir()

        with patch("core.paper.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["make", "clean"],
                returncode=0,
                stdout="",
                stderr="",
            )
            clean_paper(paper_dir)

        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["make", "clean"]


# ---------------------------------------------------------------------------
# COLORS palette
# ---------------------------------------------------------------------------


class TestFigureColors:
    """COLORS palette should contain known colorblind-safe hex codes."""

    def test_palette_has_required_keys(self):
        for key in ("blue", "orange", "green", "red", "purple", "grey"):
            assert key in COLORS, f"Missing color key: {key}"

    def test_colors_are_hex(self):
        import re

        for name, code in COLORS.items():
            assert re.match(
                r"^#[0-9A-Fa-f]{6}$", code
            ), f"Invalid hex for {name}: {code}"

    def test_colors_are_distinct(self):
        values = list(COLORS.values())
        assert len(values) == len(set(values)), "Duplicate color codes found"


# ---------------------------------------------------------------------------
# apply_rcparams
# ---------------------------------------------------------------------------


class TestApplyRcparams:
    """apply_rcparams should push RC_PARAMS into matplotlib.pyplot.rcParams."""

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("matplotlib"),
        reason="matplotlib not installed",
    )
    def test_apply_rcparams_updates_mpl(self):
        import matplotlib.pyplot as plt

        original = dict(plt.rcParams)
        apply_rcparams()
        for key, value in RC_PARAMS.items():
            assert plt.rcParams[key] == value, f"rcParam {key} not set correctly"
        # Restore original (best-effort)
        plt.rcParams.update(original)


# ---------------------------------------------------------------------------
# add_citation / list_citations
# ---------------------------------------------------------------------------


class TestCitations:
    """add_citation writes BibTeX; list_citations reads keys back."""

    def test_add_citation(self, tmp_path):
        bib = tmp_path / "refs.bib"
        add_citation(
            "Smith2023",
            author="John Smith",
            title="A Great Paper",
            year="2023",
            journal="Nature",
            bib_file=bib,
        )
        content = bib.read_text()
        assert "@article{Smith2023," in content
        assert "John Smith" in content
        assert "Nature" in content

    def test_list_citations(self, tmp_path):
        bib = tmp_path / "refs.bib"
        add_citation("Alpha2020", author="A", title="T1", year="2020", bib_file=bib)
        add_citation("Beta2021", author="B", title="T2", year="2021", bib_file=bib)
        keys = list_citations(bib)
        assert "Alpha2020" in keys
        assert "Beta2021" in keys
        assert len(keys) == 2

    def test_no_duplicate_citation(self, tmp_path):
        bib = tmp_path / "refs.bib"
        add_citation("Dup2023", author="D", title="T", year="2023", bib_file=bib)
        add_citation("Dup2023", author="D", title="T", year="2023", bib_file=bib)
        keys = list_citations(bib)
        assert keys.count("Dup2023") == 1


# ---------------------------------------------------------------------------
# style_transfer: analyze_paper_style
# ---------------------------------------------------------------------------


class TestStyleAnalysis:
    """analyze_paper_style returns a populated StyleProfile."""

    def test_analysis_with_sample_text(self):
        text = (
            "The experiment was conducted in a controlled environment. "
            "Results indicate that the treatment group showed a 15% improvement. "
            "This suggests that further investigation may be warranted. "
            "Previous work by Smith et al. (2020) supports these findings."
        )
        profile = analyze_paper_style(text)
        assert isinstance(profile, StyleProfile)
        assert profile.avg_sentence_length > 0
        assert 0 <= profile.passive_voice_ratio
        assert 0 <= profile.hedging_ratio
        assert 0 <= profile.vocabulary_richness <= 1.0

    def test_empty_text_returns_default_profile(self):
        profile = analyze_paper_style("")
        assert profile.avg_sentence_length == 0.0
        assert profile.passive_voice_ratio == 0.0


class TestStyleProfileFields:
    """StyleProfile should have all expected fields."""

    def test_expected_fields_present(self):
        expected = {
            "avg_sentence_length",
            "passive_voice_ratio",
            "hedging_ratio",
            "citation_density",
            "vocabulary_richness",
            "common_phrases",
            "tense",
        }
        actual = set(StyleProfile.__dataclass_fields__.keys())
        assert expected.issubset(actual), f"Missing fields: {expected - actual}"

    def test_to_dict_round_trip(self):
        profile = StyleProfile(
            avg_sentence_length=12.5,
            passive_voice_ratio=0.3,
            hedging_ratio=0.05,
            citation_density=0.8,
            vocabulary_richness=0.65,
            common_phrases=["in the"],
            tense="past",
        )
        d = profile.to_dict()
        assert d["avg_sentence_length"] == 12.5
        assert d["tense"] == "past"
        assert isinstance(d["common_phrases"], list)


# ---------------------------------------------------------------------------
# verification: verify_claims
# ---------------------------------------------------------------------------


class TestVerifyClaims:
    """verify_claims extracts factual sentences and returns VerificationResult list."""

    def test_factual_text_extracts_claims(self):
        text = "Python is an interpreted language. It was created by Guido van Rossum in 1991."
        results = verify_claims(text)
        assert len(results) >= 1
        for r in results:
            assert isinstance(r, VerificationResult)
            assert r.method == "heuristic-extraction"
            assert 0 < r.confidence <= 1.0

    def test_numeric_claims_get_higher_confidence(self):
        text = "The dataset contains 50000 samples. The model achieves 95% accuracy."
        results = verify_claims(text)
        assert len(results) >= 1
        # At least one claim should have the numeric confidence boost (0.5)
        confidences = [r.confidence for r in results]
        assert max(confidences) >= 0.5


# ---------------------------------------------------------------------------
# verification: verify_citations
# ---------------------------------------------------------------------------


class TestVerifyCitations:
    """verify_citations finds author-year citation patterns."""

    def test_well_formed_citation(self):
        text = "As shown by Smith et al. (2023), the method is effective."
        results = verify_citations(text)
        assert len(results) >= 1
        assert results[0].verified is True
        assert results[0].method == "citation-format"
        assert results[0].confidence >= 0.5

    def test_no_citations(self):
        text = "This text has no citations at all."
        results = verify_citations(text)
        assert results == []


# ---------------------------------------------------------------------------
# verification: verify_file_references
# ---------------------------------------------------------------------------


class TestVerifyFileReferences:
    """verify_file_references checks that mentioned paths exist on disk."""

    def test_existing_file_verified(self, tmp_path):
        # Create a file so the reference resolves
        (tmp_path / "data.csv").write_text("a,b,c")
        text = f"Load the data from ./data.csv for analysis."
        results = verify_file_references(text, tmp_path)
        assert len(results) >= 1
        found = [r for r in results if "data.csv" in r.claim]
        assert len(found) >= 1
        assert found[0].verified is True

    def test_missing_file_unverified(self, tmp_path):
        text = "See the results in ./output/results.txt for details."
        results = verify_file_references(text, tmp_path)
        assert len(results) >= 1
        assert any(r.verified is False for r in results)


# ---------------------------------------------------------------------------
# verification: build_verification_table
# ---------------------------------------------------------------------------


class TestBuildVerificationTable:
    """build_verification_table renders VerificationResult list as Markdown."""

    def test_non_empty_table(self):
        results = [
            VerificationResult(
                claim="X is Y",
                verified=True,
                method="test",
                confidence=0.9,
                evidence="ok",
            ),
            VerificationResult(
                claim="A is B",
                verified=False,
                method="test",
                confidence=0.2,
                evidence="nope",
            ),
        ]
        table = build_verification_table(results)
        assert "| #" in table
        assert "Verified" in table
        assert "Unverified" in table
        assert "X is Y" in table

    def test_empty_results(self):
        table = build_verification_table([])
        assert "No claims extracted" in table


# ---------------------------------------------------------------------------
# verification: verify_text (CLI adapter)
# ---------------------------------------------------------------------------


class TestVerifyTextAdapter:
    """verify_text returns a dict with 'verdict' and 'issues'."""

    def test_returns_proper_dict(self):
        result = verify_text("The system produces 100 widgets per hour.")
        assert "verdict" in result
        assert "issues" in result
        assert isinstance(result["issues"], list)
        assert result["verdict"] in ("all_verified", "issues_found")

    def test_clean_text_has_issues_since_unverified(self):
        result = verify_text("Python was created in 1991.")
        # Claims are extracted but not externally verified, so issues_found
        assert result["verdict"] == "issues_found"
        assert len(result["issues"]) >= 1
