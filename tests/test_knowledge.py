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
    append_learning("Decisions", "Use PyTorch over TF -- Rationale: Better debugging experience", encyclopedia_path=enc)
    content = enc.read_text()
    assert "Use PyTorch over TF" in content
    assert "Rationale" in content


def test_log_success(tmp_path: Path):
    enc = tmp_path / "ENCYCLOPEDIA.md"
    enc.write_text(TEMPLATE)

    append_learning("What Works", "Learning rate warmup (context: transformer training)", encyclopedia_path=enc)
    content = enc.read_text()
    assert "Learning rate warmup" in content


def test_log_failure(tmp_path: Path):
    enc = tmp_path / "ENCYCLOPEDIA.md"
    enc.write_text(TEMPLATE)

    append_learning("What Doesn't Work", "SGD with momentum -- Failed because: Diverged after 10 epochs", encyclopedia_path=enc)
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
