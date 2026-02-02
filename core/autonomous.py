"""Autonomous routines: scheduled tasks, monitoring, purchase suggestions with confirmation gates."""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

ROUTINES_FILE = Path("state/routines.json")
AUDIT_LOG_FILE = Path("state/audit.log")


@dataclass
class ScheduledRoutine:
    name: str
    description: str
    schedule: str  # cron-like or "daily", "hourly", "weekly"
    command: str
    enabled: bool = True
    last_run: str = ""
    requires_confirmation: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ScheduledRoutine":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def _load_routines(path: Path = ROUTINES_FILE) -> list[ScheduledRoutine]:
    if not path.exists():
        return []
    try:
        return [ScheduledRoutine.from_dict(d) for d in json.loads(path.read_text())]
    except (json.JSONDecodeError, KeyError):
        return []


def _save_routines(
    routines: list[ScheduledRoutine], path: Path = ROUTINES_FILE
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([r.to_dict() for r in routines], indent=2))


def add_routine(
    routine: ScheduledRoutine,
    *,
    routines_file: Path = ROUTINES_FILE,
) -> None:
    """Add a scheduled routine.

    Args:
        routine: The routine to add.
        routines_file: Path to persist routines.
    """
    routines = _load_routines(routines_file)
    # Replace if same name exists
    routines = [r for r in routines if r.name != routine.name]
    routines.append(routine)
    _save_routines(routines, routines_file)
    logger.info("Added routine: %s", routine.name)


def list_routines(routines_file: Path = ROUTINES_FILE) -> list[ScheduledRoutine]:
    """List all scheduled routines."""
    return _load_routines(routines_file)


def monitor_topic(
    topic: str,
    *,
    sources: list[str] | None = None,
) -> dict:
    """Generate a monitoring spec for a research topic.

    In production, this would connect to arXiv, PubMed, etc.

    Args:
        topic: Research topic to monitor.
        sources: List of sources to check.

    Returns:
        Monitoring spec dict.
    """
    return {
        "topic": topic,
        "sources": sources or ["arxiv", "semantic-scholar"],
        "created": datetime.now().isoformat(),
        "status": "active",
    }


def monitor_news(
    keywords: list[str],
) -> dict:
    """Generate a news monitoring spec.

    Args:
        keywords: Keywords to monitor.

    Returns:
        News monitoring spec.
    """
    return {
        "keywords": keywords,
        "created": datetime.now().isoformat(),
        "status": "active",
    }


def suggest_purchase(
    item: str,
    reason: str,
    estimated_cost: float,
    *,
    currency: str = "USD",
) -> dict:
    """Create a purchase suggestion requiring user confirmation.

    This never executes purchases automatically - it only creates
    a suggestion that must be explicitly confirmed.

    Args:
        item: What to purchase.
        reason: Why it's needed.
        estimated_cost: Estimated cost.
        currency: Currency code.

    Returns:
        Purchase suggestion dict.
    """
    suggestion = {
        "item": item,
        "reason": reason,
        "estimated_cost": estimated_cost,
        "currency": currency,
        "status": "pending_confirmation",
        "created": datetime.now().isoformat(),
    }

    audit_log(f"PURCHASE_SUGGESTION: {item} ({estimated_cost} {currency}) - {reason}")
    logger.info("Purchase suggestion created: %s", item)
    return suggestion


def get_default_maintenance_routines() -> list[dict]:
    """Return the default daily maintenance routines for a ricet project."""
    return [
        {
            "name": "test-gen",
            "description": "Auto-generate tests for new/changed source files",
            "schedule": "daily",
            "command": "ricet test-gen",
        },
        {
            "name": "docs-update",
            "description": "Auto-update project documentation from source",
            "schedule": "daily",
            "command": "ricet docs",
        },
        {
            "name": "fidelity-check",
            "description": "Check GOAL.md alignment and flag drift",
            "schedule": "daily",
            "command": "ricet fidelity",
        },
        {
            "name": "verify-pass",
            "description": "Run verification on recent outputs",
            "schedule": "daily",
            "command": "ricet verify",
        },
        {
            "name": "claude-md-review",
            "description": "Review and simplify CLAUDE.md if it has grown too large",
            "schedule": "daily",
            "command": "ricet review-claude-md",
        },
    ]


def run_maintenance(project_path: Path, *, run_cmd=None) -> dict:
    """Run all daily maintenance tasks for a project.

    This is the 'midnight pass' that keeps the project healthy.
    Returns dict mapping routine name to success boolean.
    """
    import subprocess

    _run = run_cmd or (
        lambda cmd: subprocess.run(
            cmd, shell=True, capture_output=True, text=True, cwd=str(project_path)
        )
    )

    results = {}
    for routine in get_default_maintenance_routines():
        try:
            proc = _run(routine["command"])
            results[routine["name"]] = getattr(proc, "returncode", 0) == 0
        except Exception:
            results[routine["name"]] = False
    return results


def audit_log(
    message: str,
    *,
    audit_file: Path = AUDIT_LOG_FILE,
) -> None:
    """Append an entry to the audit log.

    Args:
        message: Log message.
        audit_file: Path to the audit log file.
    """
    audit_file.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat()
    entry = f"[{timestamp}] {message}\n"

    with open(audit_file, "a") as f:
        f.write(entry)
