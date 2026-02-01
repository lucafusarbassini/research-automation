"""Resource management: monitoring, checkpoint policies, cleanup, decisions.

When claude-flow is available, monitor_resources merges bridge metrics with local OS stats.
"""

import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

logger = logging.getLogger(__name__)

CHECKPOINTS_DIR = Path("checkpoints")


@dataclass
class ResourceSnapshot:
    timestamp: float = 0.0
    cpu_percent: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    disk_free_gb: float = 0.0
    gpu_memory_used_mb: float = 0.0
    gpu_memory_total_mb: float = 0.0


@dataclass
class CheckpointPolicy:
    interval_minutes: int = 30
    max_checkpoints: int = 5
    min_disk_free_gb: float = 5.0
    checkpoint_dir: Path = field(default_factory=lambda: CHECKPOINTS_DIR)


def monitor_resources() -> ResourceSnapshot:
    """Take a snapshot of current system resource usage.

    Returns:
        ResourceSnapshot with current metrics.
    """
    snap = ResourceSnapshot(timestamp=time.time())

    # RAM
    try:
        if hasattr(os, "sysconf"):
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            avail_pages = os.sysconf("SC_AVPHYS_PAGES")
            if pages > 0 and page_size > 0:
                snap.ram_total_gb = round((pages * page_size) / (1024**3), 1)
                snap.ram_used_gb = round(
                    ((pages - avail_pages) * page_size) / (1024**3), 1
                )
    except (ValueError, OSError):
        pass

    # Disk
    try:
        usage = shutil.disk_usage(".")
        snap.disk_free_gb = round(usage.free / (1024**3), 1)
    except OSError:
        pass

    # CPU (simple /proc/loadavg on Linux)
    try:
        loadavg = os.getloadavg()
        cpu_count = os.cpu_count() or 1
        snap.cpu_percent = round((loadavg[0] / cpu_count) * 100, 1)
    except OSError:
        pass

    # Merge claude-flow metrics if available
    try:
        bridge = _get_bridge()
        metrics = bridge.get_metrics()
        if "gpu_memory_used_mb" in metrics:
            snap.gpu_memory_used_mb = metrics["gpu_memory_used_mb"]
        if "gpu_memory_total_mb" in metrics:
            snap.gpu_memory_total_mb = metrics["gpu_memory_total_mb"]
    except ClaudeFlowUnavailable:
        pass

    return snap


def cleanup_old_checkpoints(
    policy: Optional[CheckpointPolicy] = None,
) -> int:
    """Remove old checkpoints exceeding the policy limit.

    Args:
        policy: Checkpoint policy. Uses defaults if None.

    Returns:
        Number of checkpoints removed.
    """
    if policy is None:
        policy = CheckpointPolicy()

    ckpt_dir = policy.checkpoint_dir
    if not ckpt_dir.exists():
        return 0

    checkpoints = sorted(ckpt_dir.iterdir(), key=lambda p: p.stat().st_mtime)
    to_remove = max(0, len(checkpoints) - policy.max_checkpoints)
    removed = 0

    for ckpt in checkpoints[:to_remove]:
        try:
            if ckpt.is_dir():
                shutil.rmtree(ckpt)
            else:
                ckpt.unlink()
            removed += 1
            logger.info("Removed old checkpoint: %s", ckpt.name)
        except OSError as e:
            logger.warning("Failed to remove checkpoint %s: %s", ckpt.name, e)

    return removed


def make_resource_decision(
    snapshot: Optional[ResourceSnapshot] = None,
    policy: Optional[CheckpointPolicy] = None,
) -> dict:
    """Decide what actions to take based on current resources.

    Returns:
        Dict with keys:
        - can_proceed: bool
        - should_checkpoint: bool
        - should_cleanup: bool
        - warnings: list[str]
    """
    if snapshot is None:
        snapshot = monitor_resources()
    if policy is None:
        policy = CheckpointPolicy()

    decision = {
        "can_proceed": True,
        "should_checkpoint": False,
        "should_cleanup": False,
        "warnings": [],
    }

    # Disk space check
    if snapshot.disk_free_gb < policy.min_disk_free_gb:
        decision["should_cleanup"] = True
        decision["warnings"].append(f"Low disk space: {snapshot.disk_free_gb} GB free")
        if snapshot.disk_free_gb < 1.0:
            decision["can_proceed"] = False
            decision["warnings"].append("Critical: less than 1 GB disk space")

    # RAM check
    if snapshot.ram_total_gb > 0:
        ram_pct = snapshot.ram_used_gb / snapshot.ram_total_gb
        if ram_pct > 0.9:
            decision["warnings"].append(
                f"High RAM usage: {snapshot.ram_used_gb}/{snapshot.ram_total_gb} GB"
            )
            decision["should_checkpoint"] = True

    # CPU check
    if snapshot.cpu_percent > 95:
        decision["warnings"].append(f"High CPU usage: {snapshot.cpu_percent}%")

    return decision
