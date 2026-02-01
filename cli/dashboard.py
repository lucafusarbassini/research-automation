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


def build_agents_panel() -> Panel:
    """Build the active agents panel.

    Queries claude-flow for active agents when available, falls back to local tracker.
    """
    from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

    lines = []
    try:
        bridge = _get_bridge()
        metrics = bridge.get_metrics()
        agent_stats = metrics.get("agents", {})
        for name, info in agent_stats.items():
            lines.append(f"  [{name}] {info}")
    except ClaudeFlowUnavailable:
        pass

    if not lines:
        from core.agents import get_active_agents_status
        agents = get_active_agents_status()
        if agents:
            for a in agents:
                lines.append(f"  [{a.get('agent', '?')}] {a.get('description', '?')[:50]}")

    content = "\n".join(lines) if lines else "No active agents"
    return Panel(content, title="Active Agents", border_style="yellow")


def build_resource_panel() -> Panel:
    """Build the resource monitoring panel.

    Includes token savings and model routing stats from claude-flow when available.
    """
    from core.resources import monitor_resources

    snap = monitor_resources()
    lines = []
    if snap.ram_total_gb > 0:
        ram_pct = (snap.ram_used_gb / snap.ram_total_gb) * 100
        lines.append(f"RAM: {snap.ram_used_gb}/{snap.ram_total_gb} GB ({ram_pct:.0f}%)")
    if snap.cpu_percent > 0:
        lines.append(f"CPU: {snap.cpu_percent}%")
    if snap.disk_free_gb > 0:
        lines.append(f"Disk free: {snap.disk_free_gb} GB")

    # Claude-flow metrics
    from core.claude_flow import ClaudeFlowUnavailable, _get_bridge
    try:
        bridge = _get_bridge()
        metrics = bridge.get_metrics()
        if "tokens_used" in metrics:
            lines.append(f"Tokens: {metrics['tokens_used']}")
        if "cost_usd" in metrics:
            lines.append(f"Cost: ${metrics['cost_usd']:.4f}")
        if "model_routing" in metrics:
            lines.append(f"Routing: {metrics['model_routing']}")
    except ClaudeFlowUnavailable:
        pass

    content = "\n".join(lines) if lines else "No resource data"
    return Panel(content, title="Resources", border_style="red")


def build_plots_panel() -> Panel:
    """Build the plots/figures summary panel."""
    from cli.gallery import scan_figures

    figures = scan_figures()
    if not figures:
        content = "No figures yet"
    else:
        lines = [f"Total: {len(figures)} figures"]
        for fig in figures[-5:]:  # Last 5
            lines.append(f"  {fig.name}.{fig.format} ({fig.size_kb} KB)")
        content = "\n".join(lines)

    return Panel(content, title="Figures", border_style="white")


def build_memory_panel() -> Panel:
    """Build the knowledge/memory stats panel."""
    from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

    lines = []
    try:
        bridge = _get_bridge()
        metrics = bridge.get_metrics()
        mem_stats = metrics.get("memory", {})
        if mem_stats:
            lines.append(f"Entries: {mem_stats.get('total_entries', '?')}")
            lines.append(f"Namespaces: {mem_stats.get('namespaces', '?')}")
        else:
            lines.append("HNSW memory active")
    except ClaudeFlowUnavailable:
        pass

    # Always show local stats
    enc_stats = read_encyclopedia_stats()
    if enc_stats:
        total = sum(enc_stats.values())
        lines.append(f"Encyclopedia: {total} entries")

    content = "\n".join(lines) if lines else "No memory data"
    return Panel(content, title="Memory", border_style="cyan")


def show_dashboard() -> None:
    """Display a static snapshot of the project dashboard."""
    console.clear()
    console.print("[bold]Research Automation Dashboard[/bold]", justify="center")
    console.print(f"[dim]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]", justify="center")
    console.print()

    # Top row: Goal + Sessions
    console.print(Columns([build_goal_panel(), build_sessions_table()], equal=True))
    console.print()

    # Middle row: Agents + Resources + Memory + Figures
    console.print(Columns([
        build_agents_panel(), build_resource_panel(),
        build_memory_panel(), build_plots_panel(),
    ], equal=True))
    console.print()

    # Bottom row: TODO + Progress
    console.print(Columns([build_todo_panel(), build_progress_panel()], equal=True))


def live_dashboard(refresh_interval: float = 5.0) -> None:
    """Display a live-updating dashboard.

    Args:
        refresh_interval: Seconds between refreshes.
    """
    from time import sleep

    console.print("[bold]Live Dashboard (Ctrl+C to exit)[/bold]")

    try:
        while True:
            show_dashboard()
            sleep(refresh_interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Dashboard stopped.[/dim]")


if __name__ == "__main__":
    show_dashboard()
