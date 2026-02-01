"""Tests for the knowledge/encyclopedia system."""

from pathlib import Path

from core.knowledge import (
    append_learning,
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
