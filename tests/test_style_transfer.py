"""Tests for paper style transfer."""

from unittest.mock import MagicMock, patch

from core.style_transfer import (
    StyleProfile,
    analyze_paper_style,
    generate_transformation_prompt,
    rewrite_in_reference_style,
    verify_no_plagiarism,
)


def test_analyze_empty():
    profile = analyze_paper_style("")
    assert profile.avg_sentence_length == 0.0


def test_analyze_basic():
    text = "This is a simple sentence. Here is another one. And a third sentence here."
    profile = analyze_paper_style(text)
    assert profile.avg_sentence_length > 0
    assert profile.vocabulary_richness > 0


def test_analyze_passive_voice():
    text = (
        "The model was trained on the dataset. The results were evaluated by experts."
    )
    profile = analyze_paper_style(text)
    assert profile.passive_voice_ratio > 0


def test_analyze_hedging():
    text = "The results may suggest that the approach could possibly work. Perhaps it indicates improvement."
    profile = analyze_paper_style(text)
    assert profile.hedging_ratio > 0


def test_analyze_citations():
    text = "Previous work \\cite{Smith2020} shows progress. As shown in \\citep{Jones2021}, results improve."
    profile = analyze_paper_style(text)
    assert profile.citation_density > 0


def test_analyze_tense_past():
    text = "We trained the model. We evaluated the results. We compared the outputs. We observed improvements."
    profile = analyze_paper_style(text)
    assert profile.tense == "past"


def test_generate_transformation_prompt_different_styles():
    source = StyleProfile(
        avg_sentence_length=10.0,
        passive_voice_ratio=0.5,
        hedging_ratio=0.01,
        tense="past",
    )
    target = StyleProfile(
        avg_sentence_length=20.0,
        passive_voice_ratio=0.1,
        hedging_ratio=0.03,
        tense="present",
    )
    prompt = generate_transformation_prompt(source, target)
    assert "longer" in prompt.lower() or "complex" in prompt.lower()
    assert "active" in prompt.lower()
    assert "present" in prompt.lower()


def test_generate_transformation_prompt_similar():
    source = StyleProfile(avg_sentence_length=15.0, passive_voice_ratio=0.3)
    target = StyleProfile(avg_sentence_length=15.5, passive_voice_ratio=0.3)
    prompt = generate_transformation_prompt(source, target)
    assert "similar" in prompt.lower() or "minor" in prompt.lower()


def test_verify_no_plagiarism_clean():
    new_text = "This is a completely original piece of writing with unique content."
    refs = ["The quick brown fox jumps over the lazy dog repeatedly and consistently."]
    flags = verify_no_plagiarism(new_text, refs)
    assert len(flags) == 0


def test_verify_no_plagiarism_overlap():
    shared = "the model was trained on a large corpus of scientific papers"
    new_text = f"In our work, {shared} and evaluated."
    refs = [f"Previous research showed that {shared} with great success."]
    flags = verify_no_plagiarism(new_text, refs)
    assert len(flags) > 0
    assert flags[0]["source_index"] == 0


def test_verify_no_plagiarism_empty_refs():
    flags = verify_no_plagiarism("Some text here", [])
    assert len(flags) == 0


def test_style_profile_to_dict():
    profile = StyleProfile(avg_sentence_length=12.5, tense="past")
    d = profile.to_dict()
    assert d["avg_sentence_length"] == 12.5
    assert d["tense"] == "past"


# --- rewrite_in_reference_style tests ---


def test_rewrite_in_reference_style_with_claude():
    """When Claude returns rewritten text, result includes it and profiles."""
    source = "We trained the model. We evaluated the results. We compared the outputs."
    reference = "The approach is novel. The method demonstrates strong performance across benchmarks."
    fake_rewrite = "The model is trained effectively. The results demonstrate clear improvements."

    def fake_run_cmd(cmd):
        return MagicMock(returncode=0, stdout=fake_rewrite)

    result = rewrite_in_reference_style(source, reference, run_cmd=fake_run_cmd)

    assert result["rewritten"] == fake_rewrite
    assert "error" not in result
    assert result["source_profile"].avg_sentence_length > 0
    assert result["target_profile"].avg_sentence_length > 0
    assert isinstance(result["transformation_prompt"], str)
    assert isinstance(result["plagiarism_flags"], list)


def test_rewrite_in_reference_style_without_claude():
    """When Claude is unavailable, result contains error and None rewritten."""
    source = "We trained the model. We evaluated the results."
    reference = "The approach is novel. The method demonstrates strong performance."

    def fake_run_cmd(cmd):
        return MagicMock(returncode=1, stdout="")

    result = rewrite_in_reference_style(source, reference, run_cmd=fake_run_cmd)

    assert result["rewritten"] is None
    assert result["error"] == "Claude unavailable"
    assert result["source_profile"].avg_sentence_length > 0
    assert result["target_profile"].avg_sentence_length > 0


def test_rewrite_in_reference_style_plagiarism_check():
    """Plagiarism flags are populated when rewritten text overlaps with reference."""
    source = "We did some original research on various topics."
    reference = "the model was trained on a large corpus of scientific papers and evaluated"
    # Simulate Claude returning text that copies a chunk from the reference
    copied_chunk = "the model was trained on a large corpus of scientific papers and evaluated"
    fake_rewrite = f"In our study, {copied_chunk} thoroughly."

    def fake_run_cmd(cmd):
        return MagicMock(returncode=0, stdout=fake_rewrite)

    result = rewrite_in_reference_style(source, reference, verify=True, run_cmd=fake_run_cmd)

    assert result["rewritten"] is not None
    assert len(result["plagiarism_flags"]) > 0
    assert result["plagiarism_flags"][0]["source_index"] == 0
