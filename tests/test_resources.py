"""Tests for resource management."""

import time
from pathlib import Path

from core.resources import (
    CheckpointPolicy,
    ResourceSnapshot,
    cleanup_old_checkpoints,
    make_resource_decision,
    monitor_resources,
)


def test_monitor_resources():
    snap = monitor_resources()
    assert snap.timestamp > 0
    assert snap.ram_total_gb >= 0


def test_monitor_resources_has_disk():
    snap = monitor_resources()
    assert snap.disk_free_gb > 0


def test_cleanup_old_checkpoints(tmp_path: Path):
    ckpt_dir = tmp_path / "checkpoints"
    ckpt_dir.mkdir()
    for i in range(7):
        f = ckpt_dir / f"ckpt_{i}.pt"
        f.write_text(f"checkpoint {i}")
        # Stagger mtimes
        time.sleep(0.01)

    policy = CheckpointPolicy(max_checkpoints=3, checkpoint_dir=ckpt_dir)
    removed = cleanup_old_checkpoints(policy)
    assert removed == 4
    assert len(list(ckpt_dir.iterdir())) == 3


def test_cleanup_no_checkpoints(tmp_path: Path):
    policy = CheckpointPolicy(checkpoint_dir=tmp_path / "empty")
    assert cleanup_old_checkpoints(policy) == 0


def test_make_resource_decision_healthy():
    snap = ResourceSnapshot(
        disk_free_gb=50.0,
        ram_used_gb=4.0,
        ram_total_gb=16.0,
        cpu_percent=30.0,
    )
    decision = make_resource_decision(snap)
    assert decision["can_proceed"] is True
    assert decision["should_cleanup"] is False
    assert len(decision["warnings"]) == 0


def test_make_resource_decision_low_disk():
    snap = ResourceSnapshot(disk_free_gb=3.0, ram_total_gb=16.0, ram_used_gb=8.0)
    decision = make_resource_decision(snap)
    assert decision["should_cleanup"] is True
    assert any("disk" in w.lower() for w in decision["warnings"])


def test_make_resource_decision_critical_disk():
    snap = ResourceSnapshot(disk_free_gb=0.5, ram_total_gb=16.0, ram_used_gb=8.0)
    decision = make_resource_decision(snap)
    assert decision["can_proceed"] is False


def test_make_resource_decision_high_ram():
    snap = ResourceSnapshot(
        disk_free_gb=50.0,
        ram_used_gb=15.0,
        ram_total_gb=16.0,
    )
    decision = make_resource_decision(snap)
    assert decision["should_checkpoint"] is True
    assert any("ram" in w.lower() for w in decision["warnings"])


# --- Bridge-integrated tests ---

from unittest.mock import MagicMock, patch


def test_monitor_resources_merges_bridge_gpu():
    mock_bridge = MagicMock()
    mock_bridge.get_metrics.return_value = {
        "gpu_memory_used_mb": 4096.0,
        "gpu_memory_total_mb": 8192.0,
    }
    with patch("core.resources._get_bridge", return_value=mock_bridge):
        snap = monitor_resources()
        assert snap.gpu_memory_used_mb == 4096.0
        assert snap.gpu_memory_total_mb == 8192.0


def test_monitor_resources_bridge_unavailable():
    from core.claude_flow import ClaudeFlowUnavailable

    with patch("core.resources._get_bridge", side_effect=ClaudeFlowUnavailable("no")):
        snap = monitor_resources()
        assert snap.timestamp > 0
        assert snap.gpu_memory_used_mb == 0.0
