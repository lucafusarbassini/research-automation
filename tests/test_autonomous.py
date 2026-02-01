"""Tests for autonomous routines."""

from pathlib import Path

from core.autonomous import (
    ScheduledRoutine,
    add_routine,
    audit_log,
    list_routines,
    monitor_news,
    monitor_topic,
    suggest_purchase,
)


def test_scheduled_routine_roundtrip():
    r = ScheduledRoutine(name="backup", description="Daily backup", schedule="daily", command="backup.sh")
    d = r.to_dict()
    restored = ScheduledRoutine.from_dict(d)
    assert restored.name == "backup"
    assert restored.schedule == "daily"


def test_add_and_list_routines(tmp_path: Path):
    routines_file = tmp_path / "routines.json"
    r1 = ScheduledRoutine(name="check-arxiv", description="Check arXiv", schedule="daily", command="check")
    r2 = ScheduledRoutine(name="backup", description="Backup state", schedule="weekly", command="backup")
    add_routine(r1, routines_file=routines_file)
    add_routine(r2, routines_file=routines_file)

    routines = list_routines(routines_file)
    assert len(routines) == 2
    names = {r.name for r in routines}
    assert "check-arxiv" in names
    assert "backup" in names


def test_add_routine_replaces_duplicate(tmp_path: Path):
    routines_file = tmp_path / "routines.json"
    r1 = ScheduledRoutine(name="task", description="v1", schedule="daily", command="v1")
    r2 = ScheduledRoutine(name="task", description="v2", schedule="daily", command="v2")
    add_routine(r1, routines_file=routines_file)
    add_routine(r2, routines_file=routines_file)

    routines = list_routines(routines_file)
    assert len(routines) == 1
    assert routines[0].description == "v2"


def test_monitor_topic():
    spec = monitor_topic("transformer architectures")
    assert spec["topic"] == "transformer architectures"
    assert "arxiv" in spec["sources"]
    assert spec["status"] == "active"


def test_monitor_topic_custom_sources():
    spec = monitor_topic("protein folding", sources=["pubmed", "biorxiv"])
    assert "pubmed" in spec["sources"]


def test_monitor_news():
    spec = monitor_news(["AI", "robotics"])
    assert spec["keywords"] == ["AI", "robotics"]
    assert spec["status"] == "active"


def test_suggest_purchase(tmp_path: Path):
    suggestion = suggest_purchase(
        "GPU compute credits",
        "Need more compute for training",
        500.0,
        currency="USD",
    )
    assert suggestion["status"] == "pending_confirmation"
    assert suggestion["estimated_cost"] == 500.0


def test_suggest_purchase_never_auto_executes():
    suggestion = suggest_purchase("item", "reason", 100.0)
    assert suggestion["status"] == "pending_confirmation"


def test_audit_log(tmp_path: Path):
    log_file = tmp_path / "audit.log"
    audit_log("Test action 1", audit_file=log_file)
    audit_log("Test action 2", audit_file=log_file)
    content = log_file.read_text()
    assert "Test action 1" in content
    assert "Test action 2" in content
    assert content.count("[") >= 2  # timestamps
