"""Session management: tracking, snapshots, and recovery.

When claude-flow is available, session start/end also delegates to the bridge.
Local JSON dual-write is always maintained for the dashboard.
"""

import json
import logging
import shutil
import subprocess
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


def generate_review_report(session: Optional[Session] = None) -> Path:
    """Generate a concise review report of code changes made during the session.

    Collects all files modified since the session started (via git diff),
    categorizes them by change type, highlights files that need human review,
    and writes a markdown report to state/review-report-{timestamp}.md.

    Args:
        session: The session that just ended.  Used to label the report.

    Returns:
        Path to the generated report file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = STATE_DIR / f"review-report-{timestamp}.md"
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    session_label = session.name if session else "unknown"

    # --- Collect changed files from git ---
    new_files: list[str] = []
    modified_files: list[str] = []
    deleted_files: list[str] = []

    try:
        # Get files changed since last commit before the session.
        # Use --name-status to classify add/modify/delete.
        diff_result = subprocess.run(
            ["git", "diff", "--name-status", "HEAD~1"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if diff_result.returncode != 0:
            # Fallback: diff against working tree
            diff_result = subprocess.run(
                ["git", "diff", "--name-status"],
                capture_output=True,
                text=True,
                timeout=15,
            )

        for line in diff_result.stdout.strip().splitlines():
            parts = line.split("\t", 1)
            if len(parts) < 2:
                continue
            status_code, filepath = parts[0].strip(), parts[1].strip()
            if status_code.startswith("A"):
                new_files.append(filepath)
            elif status_code.startswith("D"):
                deleted_files.append(filepath)
            else:
                modified_files.append(filepath)

        # Also pick up untracked files that were added during the session
        untracked_result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        for f in untracked_result.stdout.strip().splitlines():
            f = f.strip()
            if f and f not in new_files:
                new_files.append(f)

    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("Could not collect git diff for review report")

    # --- Identify files needing human review ---
    # Patterns that warrant careful human inspection
    _REVIEW_PATTERNS = {
        "config": [
            "config/",
            ".yml",
            ".yaml",
            ".json",
            ".toml",
            ".ini",
            ".cfg",
            ".env",
        ],
        "security": [
            "secret",
            "auth",
            "token",
            "password",
            "credential",
            "key",
            ".env",
        ],
        "algorithm": ["algorithm", "model", "loss", "optimizer", "metric", "score"],
        "infrastructure": ["docker", "ci/", ".github/", "deploy", "terraform", "helm"],
        "data_pipeline": ["pipeline", "etl", "transform", "migration", "schema"],
    }

    needs_review: dict[str, list[str]] = {}
    all_changed = new_files + modified_files

    for filepath in all_changed:
        fp_lower = filepath.lower()
        for category, patterns in _REVIEW_PATTERNS.items():
            if any(pat in fp_lower for pat in patterns):
                needs_review.setdefault(category, []).append(filepath)
                break

    # New files always deserve a look
    for filepath in new_files:
        if filepath not in [f for files in needs_review.values() for f in files]:
            needs_review.setdefault("new_code", []).append(filepath)

    # --- Build the report ---
    lines: list[str] = []
    lines.append(f"# Review Report  --  Session `{session_label}`")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    total = len(new_files) + len(modified_files) + len(deleted_files)
    lines.append(f"**Total changes:** {total} file(s)")
    lines.append(f"- New: {len(new_files)}")
    lines.append(f"- Modified: {len(modified_files)}")
    lines.append(f"- Deleted: {len(deleted_files)}")
    lines.append("")

    # Files needing review
    if needs_review:
        lines.append("## Files Needing Human Review")
        lines.append("")
        _CATEGORY_LABELS = {
            "config": "Configuration Changes",
            "security": "Security-Sensitive Files",
            "algorithm": "New Algorithms / Models",
            "infrastructure": "Infrastructure / CI-CD",
            "data_pipeline": "Data Pipeline Changes",
            "new_code": "New Code (no other category)",
        }
        for category, files in needs_review.items():
            label = _CATEGORY_LABELS.get(category, category.replace("_", " ").title())
            lines.append(f"### {label}")
            for f in files:
                lines.append(f"- `{f}`")
            lines.append("")
    else:
        lines.append("## Files Needing Human Review")
        lines.append("")
        lines.append("No files flagged for special review.")
        lines.append("")

    # Full change listing
    if new_files:
        lines.append("## New Files")
        for f in new_files:
            lines.append(f"- `{f}`")
        lines.append("")

    if modified_files:
        lines.append("## Modified Files")
        for f in modified_files:
            lines.append(f"- `{f}`")
        lines.append("")

    if deleted_files:
        lines.append("## Deleted Files")
        for f in deleted_files:
            lines.append(f"- `{f}`")
        lines.append("")

    if total == 0:
        lines.append("_No file changes detected._")
        lines.append("")

    report_text = "\n".join(lines) + "\n"
    report_path.write_text(report_text)
    logger.info("Review report written to %s", report_path)

    # --- Print terminal summary ---
    _print_terminal_summary(
        needs_review, new_files, modified_files, deleted_files, report_path
    )

    return report_path


def _print_terminal_summary(
    needs_review: dict[str, list[str]],
    new_files: list[str],
    modified_files: list[str],
    deleted_files: list[str],
    report_path: Path,
) -> None:
    """Print a concise review summary to the terminal."""
    total = len(new_files) + len(modified_files) + len(deleted_files)
    review_count = sum(len(v) for v in needs_review.values())

    print()
    print("=" * 60)
    print("  SESSION REVIEW REPORT")
    print("=" * 60)
    print(f"  Total changes: {total} file(s)")
    print(f"    New:      {len(new_files)}")
    print(f"    Modified: {len(modified_files)}")
    print(f"    Deleted:  {len(deleted_files)}")
    print()

    if review_count:
        print(f"  ** {review_count} file(s) flagged for human review **")
        for category, files in needs_review.items():
            label = category.replace("_", " ").title()
            print(f"    [{label}]")
            for f in files[:5]:
                print(f"      - {f}")
            if len(files) > 5:
                print(f"      ... and {len(files) - 5} more")
    else:
        print("  No files flagged for special review.")

    print()
    print(f"  Full report: {report_path}")
    print("=" * 60)
    print()


def _save_session(session: Session) -> None:
    """Write session data to disk."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = SESSIONS_DIR / f"{session.name}.json"
    path.write_text(json.dumps(session.to_dict(), indent=2))
