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


def build_verification_panel() -> Panel:
    """Build the verification results panel.

    Shows the last verification results from the state directory, or runs a
    lightweight check on the most recent progress entry.
    """
    lines: list[str] = []

    # Try reading cached verification results from state
    results_path = Path("state/verification_results.json")
    if results_path.exists():
        try:
            data = json.loads(results_path.read_text())
            for r in data[-8:]:  # Last 8 results
                status = "OK" if r.get("verified") else "??"
                conf = r.get("confidence", 0.0)
                claim = r.get("claim", "")[:60]
                lines.append(f"  [{status}] ({conf:.0%}) {claim}")
        except (json.JSONDecodeError, KeyError):
            lines.append("Corrupt results file")
    else:
        # Fall back to running verification on recent progress
        try:
            from core.verification import verify_claims

            progress = read_progress()
            if progress and progress != "No progress yet":
                # Verify only the last few lines to keep it lightweight
                last_lines = "\n".join(progress.strip().splitlines()[-5:])
                results = verify_claims(last_lines)
                if results:
                    for r in results[:6]:
                        status = "OK" if r.verified else "??"
                        claim = r.claim[:60]
                        lines.append(f"  [{status}] ({r.confidence:.0%}) {claim}")
                else:
                    lines.append("No verifiable claims found")
            else:
                lines.append("No progress to verify")
        except ImportError:
            lines.append("verification module unavailable")

    content = "\n".join(lines) if lines else "No verification data"
    return Panel(content, title="Verification", border_style="bright_yellow")


def build_task_queue_panel() -> Panel:
    """Build the task queue panel.

    Shows the current task spooler queue status. Handles the case where the
    core.task_spooler module is not available.
    """
    lines: list[str] = []
    try:
        from core.task_spooler import TaskSpooler

        ts = TaskSpooler()
        jobs = ts.status()
        if jobs:
            running = sum(1 for j in jobs if j.get("state") == "running")
            queued = sum(1 for j in jobs if j.get("state") == "queued")
            finished = sum(1 for j in jobs if j.get("state") == "finished")
            lines.append(f"Running: {running}  Queued: {queued}  Done: {finished}")
            lines.append("")
            for job in jobs[-8:]:  # Last 8 jobs
                state = job.get("state", "?")
                jid = job.get("id", "?")
                cmd = job.get("command", "")[:45]
                style_map = {"running": "bold green", "queued": "yellow", "finished": "dim"}
                style = style_map.get(state, "white")
                lines.append(f"  [{style}]#{jid}[/{style}] {state:8s} {cmd}")
        else:
            lines.append("Queue empty")
    except ImportError:
        lines.append("task_spooler module unavailable")
    except Exception as exc:
        lines.append(f"Error: {exc}")

    content = "\n".join(lines) if lines else "No queue data"
    return Panel(Text.from_markup(content), title="Task Queue", border_style="bright_blue")


def build_multi_project_panel() -> Panel:
    """Build the multi-project overview panel.

    Shows all registered projects and highlights the currently active one.
    """
    lines: list[str] = []
    try:
        from core.multi_project import get_active_project, list_projects

        projects = list_projects()
        if projects:
            for proj in projects:
                marker = ">>>" if proj.get("active") else "   "
                name = proj.get("name", "?")
                ptype = proj.get("project_type", "")
                path = proj.get("path", "")
                lines.append(f"  {marker} {name} ({ptype}) {path}")
            try:
                active = get_active_project()
                lines.insert(0, f"Active: {active.get('name', '?')}")
                lines.insert(1, "")
            except RuntimeError:
                lines.insert(0, "No active project")
                lines.insert(1, "")
        else:
            lines.append("No projects registered")
    except ImportError:
        lines.append("multi_project module unavailable")
    except Exception as exc:
        lines.append(f"Error: {exc}")

    content = "\n".join(lines) if lines else "No project data"
    return Panel(content, title="Projects", border_style="bright_magenta")


def build_mobile_panel() -> Panel:
    """Build the mobile server status panel.

    Shows whether the mobile server is running, its URL, and available routes.
    """
    lines: list[str] = []
    try:
        from core.mobile import (
            _mobile_server,
            _server_instance,
            _server_thread,
            generate_mobile_url,
        )

        if _server_thread is not None and _server_thread.is_alive():
            lines.append("Status: [bold green]RUNNING[/bold green]")
            if _server_instance is not None:
                addr = _server_instance.server_address
                lines.append(f"Address: {addr[0]}:{addr[1]}")
            if _mobile_server is not None:
                route_count = len(_mobile_server.routes)
                lines.append(f"Routes: {route_count} endpoints")
        else:
            lines.append("Status: [dim]stopped[/dim]")
            lines.append(f"Default URL: {generate_mobile_url()}")
    except ImportError:
        lines.append("mobile module unavailable")
    except Exception as exc:
        lines.append(f"Error: {exc}")

    content = "\n".join(lines) if lines else "No mobile data"
    return Panel(Text.from_markup(content), title="Mobile", border_style="bright_green")


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

    # Row 3: Verification + Task Queue + Projects
    console.print(Columns([
        build_verification_panel(), build_task_queue_panel(),
        build_multi_project_panel(),
    ], equal=True))
    console.print()

    # Row 4: Mobile + TODO + Progress
    console.print(Columns([
        build_mobile_panel(), build_todo_panel(), build_progress_panel(),
    ], equal=True))


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
