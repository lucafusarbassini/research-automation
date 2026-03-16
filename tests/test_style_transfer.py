"""Tests for paper style transfer."""

from unittest.mock import MagicMock, patch

from core.style_transfer import (
    analyze_paper_style,
    generate_transformation_prompt,
    rewrite_in_reference_style,
    verify_no_plagiarism,
)


def test_analyze_empty():
    profile = analyze_paper_style("")
    assert profile == {}


def test_analyze_basic_fallback():
    """Without Claude, analyze_paper_style falls back to surface metrics."""
    text = "This is a simple sentence. Here is another one. And a third sentence here."
    profile = analyze_paper_style(text)
    assert isinstance(profile, dict)
    assert profile.get("avg_sentence_length", 0) > 0
    assert "_source" in profile  # fallback marker


def test_analyze_tense_past():
    text = "We trained the model. We evaluated the results. We compared the outputs. We observed improvements."
    profile = analyze_paper_style(text)
    assert profile.get("tense") == "past"


def test_generate_transformation_prompt_dicts():
    source = {"tense": "past", "voice": "passive_ratio=0.50", "hedging_level": "low", "avg_sentence_length": 10.0}
    target = {"tense": "present", "voice": "passive_ratio=0.10", "hedging_level": "high", "avg_sentence_length": 20.0}
    prompt = generate_transformation_prompt(source, target)
    assert isinstance(prompt, str)
    assert len(prompt) > 50


def test_generate_transformation_prompt_similar():
    source = {"tense": "past", "avg_sentence_length": 15.0}
    target = {"tense": "past", "avg_sentence_length": 15.5}
    prompt = generate_transformation_prompt(source, target)
    assert isinstance(prompt, str)


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


# --- rewrite_in_reference_style tests ---


def test_rewrite_in_reference_style_with_claude():
    """When Claude returns rewritten text, result includes it and profiles."""
    source = "We trained the model. We evaluated the results. We compared the outputs."
    reference = "The approach is novel. The method demonstrates strong performance across benchmarks."
    fake_rewrite = (
        "The model is trained effectively. The results demonstrate clear improvements."
    )

    with patch("core.style_transfer._call_claude_api", return_value=fake_rewrite):
        result = rewrite_in_reference_style(source, reference)

    assert result["rewritten"] == fake_rewrite
    assert "error" not in result
    assert isinstance(result["source_profile"], dict)
    assert isinstance(result["target_profile"], dict)
    assert isinstance(result["transformation_prompt"], str)
    assert isinstance(result["plagiarism_flags"], list)


def test_rewrite_in_reference_style_without_claude():
    """When Claude is unavailable, result contains error and None rewritten."""
    source = "We trained the model. We evaluated the results."
    reference = "The approach is novel. The method demonstrates strong performance."

    with patch("core.style_transfer._call_claude_api", return_value=None):
        with patch("core.claude_helper.call_claude", return_value=None):
            result = rewrite_in_reference_style(source, reference)

    assert result["rewritten"] is None
    assert "Claude unavailable" in result["error"]
    assert isinstance(result["source_profile"], dict)
    assert isinstance(result["target_profile"], dict)


def test_rewrite_in_reference_style_plagiarism_check():
    """Plagiarism flags are populated when rewritten text overlaps with reference."""
    source = "We did some original research on various topics."
    reference = (
        "the model was trained on a large corpus of scientific papers and evaluated"
    )
    copied_chunk = (
        "the model was trained on a large corpus of scientific papers and evaluated"
    )
    fake_rewrite = f"In our study, {copied_chunk} thoroughly."

    with patch("core.style_transfer._call_claude_api", return_value=fake_rewrite):
        result = rewrite_in_reference_style(source, reference, verify=True)

    assert result["rewritten"] is not None
    assert len(result["plagiarism_flags"]) > 0
    assert result["plagiarism_flags"][0]["source_index"] == 0
