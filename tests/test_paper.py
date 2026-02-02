"""Tests for core.paper citation pipeline."""

from pathlib import Path
from unittest.mock import patch

import pytest

from core.paper import generate_citation_key


def test_generate_citation_key():
    assert generate_citation_key("Smith, John and Doe, Jane", "2024") == "Smith2024"
    assert generate_citation_key("van der Berg, A.", "2023") == "Berg2023"
    assert generate_citation_key("", "2024") == "Unknown2024"


def test_search_and_cite_with_claude(tmp_path):
    import json

    from core.paper import search_and_cite

    bib = tmp_path / "references.bib"
    bib.write_text("")

    mock_response = json.dumps([
        {
            "title": "Attention Is All You Need",
            "authors": "Vaswani, A.",
            "year": "2017",
            "journal": "NeurIPS",
            "doi": "10.x/y",
            "entry_type": "article",
        }
    ])
    with patch("core.claude_helper.call_with_web_fallback") as mock:
        mock.return_value = mock_response
        results = search_and_cite("transformers", bib_file=bib, max_results=3)

    assert len(results) == 1
    assert results[0]["key"] == "Vaswani2017"
    assert bib.read_text()  # Should have content


def test_search_and_cite_no_claude(tmp_path):
    from core.paper import search_and_cite

    bib = tmp_path / "references.bib"
    bib.write_text("")
    # Claude unavailable in tests -> returns empty
    results = search_and_cite("anything", bib_file=bib)
    assert results == []
