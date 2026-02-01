#!/usr/bin/env python3
"""Interactive TUI dashboard for monitoring research sessions."""

import json
from datetime import datetime
from pathlib import Path

from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


console = Console()


def read_todo() -> str:
    """Read current TODO items."""
    path = Path("state/TODO.md")
    if not path.exists():
        return "No TODO.md found"
    return path.read_text()


def read_progress() -> str:
    """Read recent progress entries."""
    path = Path("state/PROGRESS.md")
    if not path.exists():
        return "No progress yet"
    lines = path.read_text().strip().splitlines()
    # Show last 15 entries
    return "\n".join(lines[-15:])


def read_sessions() -> list[dict]:
    """Read all session records."""
    session_dir = Path("state/sessions")
    if not session_dir.exists():
        return []
    sessions = []
    for f in sorted(session_dir.glob("*.json")):
        try:
            sessions.append(json.loads(f.read_text()))
        except json.JSONDecodeError:
            continue
    return sessions


def read_encyclopedia_stats() -> dict:
    """Get encyclopedia section counts."""
    path = Path("knowledge/ENCYCLOPEDIA.md")
    if not path.exists():
        return {}
    content = path.read_text()
    sections = ["Tricks", "Decisions", "What Works", "What Doesn't Work"]
    stats = {}
    for section in sections:
        count = content.count(f"\n- [")  # Rough count
        stats[section] = count
    return stats


def build_todo_panel() -> Panel:
    """Build the TODO panel."""
    content = read_todo()
    return Panel(content, title="TODO", border_style="cyan")


def build_progress_panel() -> Panel:
    """Build the progress panel."""
    content = read_progress()
    return Panel(content, title="Progress", border_style="green")


def build_sessions_table() -> Panel:
    """Build the sessions table."""
    sessions = read_sessions()
    table = Table(show_header=True, header_style="bold")
    table.add_column("Session")
    table.add_column("Status")
    table.add_column("Started")
    table.add_column("Tokens")

    for s in sessions[-10:]:  # Last 10 sessions
        status_style = "green" if s.get("status") == "completed" else "yellow"
        table.add_row(
            s.get("name", "?"),
            Text(s.get("status", "?"), style=status_style),
            s.get("started", "?")[:19],
            str(s.get("token_estimate", 0)),
        )

    return Panel(table, title="Sessions", border_style="blue")


def build_goal_panel() -> Panel:
    """Build the goal panel."""
    path = Path("knowledge/GOAL.md")
    if not path.exists():
        content = "No GOAL.md found"
    else:
        content = path.read_text()[:300]
    return Panel(content, title="Goal", border_style="magenta")


def show_dashboard() -> None:
    """Display a static snapshot of the project dashboard."""
    console.clear()
    console.print("[bold]Research Automation Dashboard[/bold]", justify="center")
    console.print(f"[dim]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]", justify="center")
    console.print()

    # Top row: Goal + Sessions
    console.print(Columns([build_goal_panel(), build_sessions_table()], equal=True))
    console.print()

    # Bottom row: TODO + Progress
    console.print(Columns([build_todo_panel(), build_progress_panel()], equal=True))


if __name__ == "__main__":
    show_dashboard()
