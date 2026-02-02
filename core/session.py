"""Session management: tracking, snapshots, and recovery.

When claude-flow is available, session start/end also delegates to the bridge.
Local JSON dual-write is always maintained for the dashboard.
"""

import json
import logging
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

logger = logging.getLogger(__name__)

STATE_DIR = Path("state")
SESSIONS_DIR = STATE_DIR / "sessions"


@dataclass
class Session:
    name: str
    started: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "active"
    uuid: str = ""
    token_estimate: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    checkpoints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def create_session(name: Optional[str] = None) -> Session:
    """Create and persist a new session.

    Also starts a claude-flow session when available.
    """
    if name is None:
        name = datetime.now().strftime("%Y%m%d_%H%M%S")

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session = Session(name=name)
    _save_session(session)

    try:
        bridge = _get_bridge()
        bridge.start_session(name)
        logger.info("Started claude-flow session: %s", name)
    except ClaudeFlowUnavailable:
        pass

    # Log session start decision
    try:
        from core.knowledge import log_decision

        log_decision(f"session started: {name}", "new work session initiated")
    except Exception:
        pass  # Never break the main flow for logging

    logger.info("Created session: %s", name)
    return session


def load_session(name: str) -> Optional[Session]:
    """Load a session by name."""
    path = SESSIONS_DIR / f"{name}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return Session.from_dict(data)


def list_sessions() -> list[Session]:
    """List all sessions sorted by start time."""
    if not SESSIONS_DIR.exists():
        return []
    sessions = []
    for f in sorted(SESSIONS_DIR.glob("*.json")):
        data = json.loads(f.read_text())
        sessions.append(Session.from_dict(data))
    return sessions


def update_session(session: Session) -> None:
    """Update a session on disk."""
    _save_session(session)


def close_session(session: Session) -> None:
    """Mark session as completed.

    Also ends the claude-flow session when available.
    Scans accumulated progress entries for operational rules and appends them
    to the cheatsheet.
    """
    session.status = "completed"
    _save_session(session)

    try:
        bridge = _get_bridge()
        bridge.end_session(session.name)
        logger.info("Ended claude-flow session: %s", session.name)
    except ClaudeFlowUnavailable:
        pass

    # Scan session progress for operational rules
    from core.meta_rules import (
        append_to_cheatsheet,
        classify_rule_type,
        detect_operational_rule,
    )

    progress_file = STATE_DIR / "PROGRESS.md"
    if progress_file.exists():
        for line in progress_file.read_text().splitlines():
            line = line.strip()
            if line and detect_operational_rule(line):
                rule_type = classify_rule_type(line)
                append_to_cheatsheet(line, rule_type=rule_type)

    # Log session end decision
    try:
        from core.knowledge import log_decision

        log_decision(
            f"session ended: {session.name}",
            f"completed {session.tasks_completed} tasks, {session.tasks_failed} failed",
        )
    except Exception:
        pass  # Never break the main flow for logging

    logger.info("Closed session: %s", session.name)


def snapshot_state(label: str) -> Path:
    """Create a snapshot of the current state directory for recovery.

    Args:
        label: Human-readable label for the snapshot.

    Returns:
        Path to the snapshot directory.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_dir = STATE_DIR / "snapshots" / f"{timestamp}_{label}"
    snapshot_dir.parent.mkdir(parents=True, exist_ok=True)

    # Copy state (excluding snapshots themselves)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for item in STATE_DIR.iterdir():
        if item.name == "snapshots":
            continue
        dest = snapshot_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    logger.info("Created snapshot: %s", snapshot_dir)
    return snapshot_dir


def restore_snapshot(snapshot_path: Path) -> None:
    """Restore state from a snapshot.

    Args:
        snapshot_path: Path to the snapshot directory.
    """
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Snapshot not found: {snapshot_path}")

    for item in snapshot_path.iterdir():
        dest = STATE_DIR / item.name
        if dest.exists():
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    logger.info("Restored snapshot from: %s", snapshot_path)


def _save_session(session: Session) -> None:
    """Write session data to disk."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = SESSIONS_DIR / f"{session.name}.json"
    path.write_text(json.dumps(session.to_dict(), indent=2))
