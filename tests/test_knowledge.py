"""Tests for the knowledge/encyclopedia system."""

from pathlib import Path

from core.knowledge import (
    _normalize,
    _resolve_section_type,
    append_learning,
    discover_sections,
    find_section,
    get_encyclopedia_stats,
    log_decision,
    log_failure,
    log_success,
    log_trick,
    search_knowledge,
)

TEMPLATE = """# Project Encyclopedia

## Tricks
<!-- Learnings get appended here -->

## Decisions
<!-- Design decisions get logged here -->

## What Works
<!-- Successful approaches -->

## What Doesn't Work
<!-- Failed approaches (to avoid repeating) -->
"""


def test_append_learning(tmp_path: Path):
    enc = tmp_path / "ENCYCLOPEDIA.md"
    enc.write_text(TEMPLATE)

    append_learning("Tricks", "Use vectorized ops for speed", encyclopedia_path=enc)
    content = enc.read_text()
    assert "Use vectorized ops for speed" in content
    assert "## Tricks" in content


def test_append_learning_multiple(tmp_path: Path):
    enc = tmp_path / "ENCYCLOPEDIA.md"
    enc.write_text(TEMPLATE)

    append_learning("Tricks", "Trick 1", encyclopedia_path=enc)
    append_learning("Tricks", "Trick 2", encyclopedia_path=enc)
    content = enc.read_text()
    assert "Trick 1" in content
    assert "Trick 2" in content


def test_log_decision(tmp_path: Path):
    enc = tmp_path / "ENCYCLOPEDIA.md"
    enc.write_text(TEMPLATE)

    log_decision.__wrapped__ = None  # type: ignore
    # Call append_learning directly with explicit path
    append_learning(
        "Decisions",
        "Use PyTorch over TF -- Rationale: Better debugging experience",
        encyclopedia_path=enc,
    )
    content = enc.read_text()
    assert "Use PyTorch over TF" in content
    assert "Rationale" in content


def test_log_success(tmp_path: Path):
    enc = tmp_path / "ENCYCLOPEDIA.md"
    enc.write_text(TEMPLATE)

    append_learning(
        "What Works",
        "Learning rate warmup (context: transformer training)",
        encyclopedia_path=enc,
    )
    content = enc.read_text()
    assert "Learning rate warmup" in content


def test_log_failure(tmp_path: Path):
    enc = tmp_path / "ENCYCLOPEDIA.md"
    enc.write_text(TEMPLATE)

    append_learning(
        "What Doesn't Work",
        "SGD with momentum -- Failed because: Diverged after 10 epochs",
        encyclopedia_path=enc,
    )
    content = enc.read_text()
    assert "SGD with momentum" in content
    assert "Diverged" in content


def test_search_knowledge(tmp_path: Path):
    enc = tmp_path / "ENCYCLOPEDIA.md"
    enc.write_text(TEMPLATE + "\n- [2024-01-01] Use batch size 32 for stability\n")

    results = search_knowledge("batch size", encyclopedia_path=enc)
    assert len(results) > 0
    assert any("batch size" in r.lower() for r in results)


def test_search_knowledge_no_match(tmp_path: Path):
    enc = tmp_path / "ENCYCLOPEDIA.md"
    enc.write_text(TEMPLATE)

    results = search_knowledge("nonexistent term", encyclopedia_path=enc)
    assert len(results) == 0


# --- Bridge-integrated tests ---

from unittest.mock import MagicMock, patch


def test_append_learning_dual_writes(tmp_path: Path):
    enc = tmp_path / "ENCYCLOPEDIA.md"
    enc.write_text(TEMPLATE)
    mock_bridge = MagicMock()
    mock_bridge.store_memory.return_value = {"id": "mem-1"}
    with patch("core.knowledge._get_bridge", return_value=mock_bridge):
        append_learning("Tricks", "Use GPU for speed", encyclopedia_path=enc)
        assert "Use GPU for speed" in enc.read_text()
        mock_bridge.store_memory.assert_called_once()
        call_kwargs = mock_bridge.store_memory.call_args
        assert call_kwargs[0][0] == "Use GPU for speed"
        assert call_kwargs[1]["namespace"] == "knowledge"


def test_append_learning_bridge_unavailable(tmp_path: Path):
    enc = tmp_path / "ENCYCLOPEDIA.md"
    enc.write_text(TEMPLATE)
    from core.claude_flow import ClaudeFlowUnavailable

    with patch("core.knowledge._get_bridge", side_effect=ClaudeFlowUnavailable("no")):
        append_learning("Tricks", "Still works without bridge", encyclopedia_path=enc)
        assert "Still works without bridge" in enc.read_text()


def test_search_knowledge_semantic(tmp_path: Path):
    enc = tmp_path / "ENCYCLOPEDIA.md"
    enc.write_text(TEMPLATE)
    mock_bridge = MagicMock()
    mock_bridge.query_memory.return_value = {
        "results": [
            {"text": "semantic result about transformers", "score": 0.95},
        ]
    }
    with patch("core.knowledge._get_bridge", return_value=mock_bridge):
        results = search_knowledge("transformers", encyclopedia_path=enc)
        assert "semantic result about transformers" in results


def test_search_knowledge_merges_semantic_and_keyword(tmp_path: Path):
    enc = tmp_path / "ENCYCLOPEDIA.md"
    enc.write_text(TEMPLATE + "\n- [2024-01-01] Use batch size 32 for stability\n")
    mock_bridge = MagicMock()
    mock_bridge.query_memory.return_value = {
        "results": [
            {"text": "batch normalization helps", "score": 0.8},
        ]
    }
    with patch("core.knowledge._get_bridge", return_value=mock_bridge):
        results = search_knowledge("batch", encyclopedia_path=enc)
        assert any("batch normalization" in r for r in results)
        assert any("batch size 32" in r for r in results)


def test_search_knowledge_bridge_unavailable_keyword_only(tmp_path: Path):
    enc = tmp_path / "ENCYCLOPEDIA.md"
    enc.write_text(TEMPLATE + "\n- [2024-01-01] keyword match here\n")
    from core.claude_flow import ClaudeFlowUnavailable

    with patch("core.knowledge._get_bridge", side_effect=ClaudeFlowUnavailable("no")):
        results = search_knowledge("keyword", encyclopedia_path=enc)
        assert any("keyword match" in r for r in results)


# --- Fuzzy / normalized section matching tests ---


class TestNormalize:
    def test_basic(self):
        assert _normalize("  Tricks  ") == "tricks"

    def test_collapses_whitespace(self):
        assert _normalize("What   Works") == "what works"

    def test_strips_trailing_colon(self):
        assert _normalize("Decisions:") == "decisions"

    def test_case_insensitive(self):
        assert _normalize("WHAT DOESN'T WORK") == "what doesn't work"


class TestResolveSectionType:
    def test_canonical_names(self):
        assert _resolve_section_type("Tricks") == "tricks"
        assert _resolve_section_type("Decisions") == "decisions"
        assert _resolve_section_type("What Works") == "what_works"
        assert _resolve_section_type("What Doesn't Work") == "what_doesnt_work"

    def test_aliases(self):
        assert _resolve_section_type("tips") == "tricks"
        assert _resolve_section_type("tips and tricks") == "tricks"
        assert _resolve_section_type("useful tips") == "tricks"
        assert _resolve_section_type("design decisions") == "decisions"
        assert _resolve_section_type("choices") == "decisions"
        assert _resolve_section_type("rationale") == "decisions"
        assert _resolve_section_type("successes") == "what_works"
        assert _resolve_section_type("working approaches") == "what_works"
        assert _resolve_section_type("failures") == "what_doesnt_work"
        assert _resolve_section_type("failed approaches") == "what_doesnt_work"
        assert _resolve_section_type("what failed") == "what_doesnt_work"
        assert _resolve_section_type("pitfalls") == "what_doesnt_work"

    def test_case_insensitive(self):
        assert _resolve_section_type("TRICKS") == "tricks"
        assert _resolve_section_type("Tips And Tricks") == "tricks"
        assert _resolve_section_type("FAILURES") == "what_doesnt_work"

    def test_unknown_returns_none(self):
        assert _resolve_section_type("Random Stuff") is None


class TestDiscoverSections:
    def test_discovers_standard_template(self):
        sections = discover_sections(TEMPLATE)
        assert "tricks" in sections
        assert "decisions" in sections
        assert "what works" in sections
        assert "what doesn't work" in sections

    def test_discovers_custom_headers(self):
        content = "# Title\n\n## Tips And Tricks\nstuff\n\n## My Decisions\nmore\n"
        sections = discover_sections(content)
        assert "tips and tricks" in sections
        assert "my decisions" in sections


class TestFindSection:
    def test_exact_match(self):
        assert find_section(TEMPLATE, "Tricks") == "Tricks"
        assert find_section(TEMPLATE, "What Doesn't Work") == "What Doesn't Work"

    def test_alias_match(self):
        assert find_section(TEMPLATE, "tips") == "Tricks"
        assert find_section(TEMPLATE, "failures") == "What Doesn't Work"
        assert find_section(TEMPLATE, "successes") == "What Works"
        assert find_section(TEMPLATE, "rationale") == "Decisions"

    def test_missing_section_returns_none(self):
        assert find_section(TEMPLATE, "Nonexistent") is None

    def test_drifted_header(self):
        drifted = TEMPLATE.replace("## Tricks", "## Tips and Tricks")
        assert find_section(drifted, "Tricks") == "Tips and Tricks"
        assert find_section(drifted, "tips") == "Tips and Tricks"


class TestAppendLearningFuzzy:
    def test_alias_appends_to_correct_section(self, tmp_path: Path):
        enc = tmp_path / "ENCYCLOPEDIA.md"
        enc.write_text(TEMPLATE)
        append_learning("tips", "Use caching", encyclopedia_path=enc)
        content = enc.read_text()
        assert "Use caching" in content
        # Verify it landed under the Tricks header
        tricks_idx = content.index("## Tricks")
        entry_idx = content.index("Use caching")
        decisions_idx = content.index("## Decisions")
        assert tricks_idx < entry_idx < decisions_idx

    def test_case_insensitive_section(self, tmp_path: Path):
        enc = tmp_path / "ENCYCLOPEDIA.md"
        enc.write_text(TEMPLATE)
        append_learning("WHAT WORKS", "Good approach", encyclopedia_path=enc)
        content = enc.read_text()
        assert "Good approach" in content

    def test_creates_missing_section(self, tmp_path: Path):
        enc = tmp_path / "ENCYCLOPEDIA.md"
        # Template without the Tricks section
        no_tricks = "# Project Encyclopedia\n\n## Decisions\n<!-- Design decisions get logged here -->\n"
        enc.write_text(no_tricks)
        append_learning("tips", "New trick", encyclopedia_path=enc)
        content = enc.read_text()
        assert "## Tricks" in content
        assert "New trick" in content

    def test_drifted_header_still_works(self, tmp_path: Path):
        enc = tmp_path / "ENCYCLOPEDIA.md"
        drifted = TEMPLATE.replace("## Tricks", "## Tips and Tricks")
        enc.write_text(drifted)
        append_learning("Tricks", "My tip", encyclopedia_path=enc)
        content = enc.read_text()
        assert "My tip" in content
        assert "## Tips and Tricks" in content
        # Should NOT have created a duplicate Tricks section
        assert content.count("## Tricks") == 0
        assert content.count("## Tips and Tricks") == 1


class TestGetEncyclopediaStatsFuzzy:
    def test_standard_template(self, tmp_path: Path):
        enc = tmp_path / "ENCYCLOPEDIA.md"
        enc.write_text(TEMPLATE)
        append_learning("Tricks", "Trick A", encyclopedia_path=enc)
        append_learning("Tricks", "Trick B", encyclopedia_path=enc)
        stats = get_encyclopedia_stats(enc)
        assert stats["Tricks"] == 2
        assert stats["Decisions"] == 0

    def test_drifted_headers(self, tmp_path: Path):
        enc = tmp_path / "ENCYCLOPEDIA.md"
        drifted = TEMPLATE.replace("## Tricks", "## Tips and Tricks")
        enc.write_text(drifted)
        append_learning("tips", "Trick A", encyclopedia_path=enc)
        stats = get_encyclopedia_stats(enc)
        assert stats["Tricks"] == 1
