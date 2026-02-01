#!/usr/bin/env python3
"""Research automation CLI."""

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

from core.onboarding import (
    OnboardingAnswers,
    collect_answers,
    load_settings,
    setup_workspace,
    write_goal_file,
    write_settings,
)

__version__ = "0.1.0"


def version_callback(value: bool):
    if value:
        print(f"research-automation {__version__}")
        raise typer.Exit()


app = typer.Typer(
    help="Scientific Research Automation - manage research projects with Claude Code.",
    epilog="Run 'research COMMAND --help' for more info on a command.",
)
console = Console()


@app.callback()
def main(
    version: bool = typer.Option(None, "--version", "-v", callback=version_callback, is_eager=True, help="Show version and exit"),
):
    """Scientific Research Automation CLI."""
    pass

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
CONFIG_DIR = Path.home() / ".research-automation"
SETUP_SCRIPT = Path(__file__).parent.parent / "scripts" / "setup_claude_flow.sh"


@app.command()
def init(
    project_name: str,
    path: Path = typer.Option(Path.cwd(), help="Where to create project"),
):
    """Initialize a new research project with full onboarding."""
    project_path = path / project_name

    if project_path.exists():
        console.print(f"[red]Error: {project_path} already exists[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Creating project: {project_name}[/bold]")
    console.print("\n[bold cyan]Project Setup[/bold cyan]")

    # Full onboarding questionnaire
    def _prompt(prompt, default=""):
        return typer.prompt(prompt, default=default) if default else typer.prompt(prompt)

    answers = collect_answers(project_name, prompt_fn=_prompt)

    # Copy templates
    shutil.copytree(TEMPLATE_DIR, project_path)

    # Setup workspace folders
    setup_workspace(project_path)

    # Write settings and goal
    write_settings(project_path, answers)
    write_goal_file(project_path, answers)

    # Create state directories
    (project_path / "state" / "sessions").mkdir(parents=True, exist_ok=True)
    (project_path / "state" / "TODO.md").write_text(
        "# TODO\n\n- [ ] Review GOAL.md and refine success criteria\n"
        "- [ ] Set up environment\n- [ ] Begin first task\n"
    )
    (project_path / "state" / "PROGRESS.md").write_text("# Progress\n\n")

    # Setup claude-flow
    if SETUP_SCRIPT.exists():
        console.print("\n[bold]Setting up claude-flow...[/bold]")
        result = subprocess.run(
            ["bash", str(SETUP_SCRIPT)],
            cwd=project_path,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            console.print("[green]claude-flow ready[/green]")
        else:
            console.print("[yellow]claude-flow setup skipped (optional)[/yellow]")

    # Write claude-flow config
    cf_config_src = TEMPLATE_DIR / "config" / "claude-flow.json"
    if cf_config_src.exists():
        cf_dest = project_path / "config" / "claude-flow.json"
        cf_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cf_config_src, cf_dest)

    # Add claude-flow MCP to settings if available
    _inject_claude_flow_mcp(project_path)

    # Initialize git
    subprocess.run(["git", "init"], cwd=project_path)
    subprocess.run(["git", "add", "-A"], cwd=project_path)
    subprocess.run(["git", "commit", "-m", "Initial project setup"], cwd=project_path)

    console.print(f"\n[green]Project created at {project_path}[/green]")
    console.print("\nNext steps:")
    console.print(f"  cd {project_path}")
    console.print("  research start")


def _inject_claude_flow_mcp(project_path: Path) -> None:
    """Add claude-flow MCP entry to .claude/settings.json if it exists."""
    settings_file = project_path / ".claude" / "settings.json"
    if not settings_file.exists():
        return
    try:
        data = json.loads(settings_file.read_text())
        mcps = data.setdefault("mcpServers", {})
        mcps["claude-flow"] = {
            "command": "npx",
            "args": ["claude-flow@v3alpha", "mcp", "serve"],
        }
        settings_file.write_text(json.dumps(data, indent=2))
    except (json.JSONDecodeError, OSError):
        pass


@app.command()
def config(
    section: str = typer.Argument(None, help="Section to reconfigure (notifications, compute, credentials)"),
):
    """View or reconfigure project settings."""
    settings = load_settings(Path.cwd())
    if not settings:
        console.print("[red]No settings found. Run 'research init' first.[/red]")
        raise typer.Exit(1)

    if section is None:
        # Show current settings
        import yaml
        console.print("[bold]Current Settings:[/bold]")
        console.print(yaml.dump(settings, default_flow_style=False))
        return

    if section == "notifications":
        method = typer.prompt("Notification method (email, slack, none)", default="none")
        settings.setdefault("notifications", {})["method"] = method
        settings["notifications"]["enabled"] = method != "none"
        if method == "email":
            settings["notifications"]["email"] = typer.prompt("Email address")
        elif method == "slack":
            settings["notifications"]["slack_webhook"] = typer.prompt("Slack webhook URL")
    elif section == "compute":
        ctype = typer.prompt("Compute type (local-cpu, local-gpu, cloud, cluster)", default="local-cpu")
        settings.setdefault("compute", {})["type"] = ctype
        if ctype == "local-gpu":
            settings["compute"]["gpu"] = typer.prompt("GPU name", default="")
    elif section == "credentials":
        console.print("Credentials are stored in .env file.")
        console.print("Edit .env directly to update credentials.")
        return
    else:
        console.print(f"[red]Unknown section: {section}[/red]")
        raise typer.Exit(1)

    import yaml
    settings_path = Path.cwd() / "config" / "settings.yml"
    settings_path.write_text(yaml.dump(settings, default_flow_style=False, sort_keys=False))
    console.print("[green]Settings updated.[/green]")


@app.command()
def start(
    session_name: str = typer.Option(None, help="Name for this session"),
):
    """Start an interactive research session."""
    from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

    if session_name is None:
        session_name = datetime.now().strftime("%Y%m%d_%H%M%S")

    session_dir = Path("state/sessions")
    session_dir.mkdir(parents=True, exist_ok=True)

    session_file = session_dir / f"{session_name}.json"
    session_data = {
        "name": session_name,
        "started": datetime.now().isoformat(),
        "status": "active",
        "token_estimate": 0,
    }
    session_file.write_text(json.dumps(session_data, indent=2))

    # Start claude-flow session
    try:
        bridge = _get_bridge()
        bridge.start_session(session_name)
        console.print(f"[green]claude-flow session started: {session_name}[/green]")
    except ClaudeFlowUnavailable:
        pass

    console.print(f"[green]Session started: {session_name}[/green]")

    # Launch Claude Code
    subprocess.run(["claude", "--session-id", session_name])


@app.command()
def overnight(
    task_file: Path = typer.Option(Path("state/TODO.md"), help="Task file to execute"),
    iterations: int = typer.Option(20, help="Max iterations"),
):
    """Run overnight autonomous mode.

    Uses claude-flow swarm orchestration when available, falls back to raw claude -p loop.
    """
    from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

    console.print("[bold yellow]Starting overnight mode[/bold yellow]")
    console.print(f"Task file: {task_file}")
    console.print(f"Max iterations: {iterations}")

    if not task_file.exists():
        console.print(f"[red]Error: {task_file} not found[/red]")
        raise typer.Exit(1)

    tasks = task_file.read_text()

    # Try claude-flow swarm
    try:
        bridge = _get_bridge()
        console.print("[cyan]Using claude-flow swarm orchestration[/cyan]")
        swarm_tasks = [{"type": "coder", "task": tasks}]
        for i in range(iterations):
            console.print(f"\n[cyan]Iteration {i + 1}/{iterations}[/cyan]")
            bridge.run_swarm(swarm_tasks, topology="hierarchical")
            if Path("state/DONE").exists():
                console.print("[green]Task completed![/green]")
                break
        console.print("[bold]Overnight mode finished[/bold]")
        return
    except ClaudeFlowUnavailable:
        pass

    # Fallback: raw claude -p loop
    for i in range(iterations):
        console.print(f"\n[cyan]Iteration {i + 1}/{iterations}[/cyan]")

        result = subprocess.run(
            ["claude", "--dangerously-skip-permissions", "-p", tasks],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            console.print(f"[red]Error in iteration {i + 1}[/red]")
            console.print(result.stderr)

        # Check for completion signal
        if Path("state/DONE").exists():
            console.print("[green]Task completed![/green]")
            break

    console.print("[bold]Overnight mode finished[/bold]")


@app.command()
def status():
    """Show current project status."""
    from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

    if Path("state/TODO.md").exists():
        console.print("[bold]TODO:[/bold]")
        console.print(Path("state/TODO.md").read_text()[:500])

    if Path("state/PROGRESS.md").exists():
        console.print("\n[bold]Progress:[/bold]")
        console.print(Path("state/PROGRESS.md").read_text()[-500:])

    # Claude-flow stats
    try:
        bridge = _get_bridge()
        metrics = bridge.get_metrics()
        console.print("\n[bold]Claude-Flow:[/bold]")
        console.print(f"  Version: {bridge.get_version()}")
        if "tokens_used" in metrics:
            console.print(f"  Tokens used: {metrics['tokens_used']}")
        if "cost_usd" in metrics:
            console.print(f"  Cost: ${metrics['cost_usd']:.4f}")
    except ClaudeFlowUnavailable:
        pass


@app.command()
def list_sessions():
    """List all sessions."""
    session_dir = Path("state/sessions")
    if not session_dir.exists():
        console.print("No sessions found")
        return

    for f in sorted(session_dir.glob("*.json")):
        data = json.loads(f.read_text())
        console.print(f"  {data['name']} - {data['status']} ({data['started'][:10]})")


@app.command()
def agents():
    """Show swarm agent status."""
    from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

    try:
        bridge = _get_bridge()
        metrics = bridge.get_metrics()
        console.print("[bold]Claude-Flow Agents:[/bold]")
        agent_stats = metrics.get("agents", {})
        if agent_stats:
            for name, info in agent_stats.items():
                console.print(f"  {name}: {info}")
        else:
            console.print("  No active agents")
    except ClaudeFlowUnavailable:
        console.print("[yellow]claude-flow not available[/yellow]")
        from core.agents import get_active_agents_status
        active = get_active_agents_status()
        if active:
            for a in active:
                console.print(f"  [{a['agent']}] {a['description']}")
        else:
            console.print("  No active agents")


@app.command()
def memory(
    query: str = typer.Argument(help="Search query for vector memory"),
    top_k: int = typer.Option(5, help="Number of results"),
):
    """Search claude-flow vector memory."""
    from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

    try:
        bridge = _get_bridge()
        result = bridge.query_memory(query, top_k=top_k)
        hits = result.get("results", [])
        if hits:
            console.print(f"[bold]Memory results ({len(hits)}):[/bold]")
            for hit in hits:
                score = hit.get("score", "?")
                text = hit.get("text", "")[:100]
                console.print(f"  [{score}] {text}")
        else:
            console.print("No matches found")
    except ClaudeFlowUnavailable:
        console.print("[yellow]claude-flow not available. Using keyword search.[/yellow]")
        from core.knowledge import search_knowledge
        results = search_knowledge(query)
        for r in results[:top_k]:
            console.print(f"  {r}")


@app.command()
def metrics():
    """Show claude-flow performance metrics."""
    from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

    try:
        bridge = _get_bridge()
        m = bridge.get_metrics()
        console.print("[bold]Performance Metrics:[/bold]")
        for key, val in m.items():
            console.print(f"  {key}: {val}")
    except ClaudeFlowUnavailable:
        console.print("[yellow]claude-flow not available[/yellow]")
        from core.resources import monitor_resources
        snap = monitor_resources()
        console.print("[bold]Local Resources:[/bold]")
        if snap.ram_total_gb > 0:
            console.print(f"  RAM: {snap.ram_used_gb}/{snap.ram_total_gb} GB")
        if snap.cpu_percent > 0:
            console.print(f"  CPU: {snap.cpu_percent}%")
        console.print(f"  Disk free: {snap.disk_free_gb} GB")


@app.command()
def paper(
    action: str = typer.Argument(help="Action: build, update, modernize, check"),
):
    """Paper pipeline commands."""
    from core.paper import check_figure_references, clean_paper, compile_paper

    if action == "build":
        console.print("[bold]Compiling paper...[/bold]")
        clean_paper()
        success = compile_paper()
        if success:
            console.print("[green]Paper compiled successfully.[/green]")
        else:
            console.print("[red]Paper compilation failed. Check logs.[/red]")
            raise typer.Exit(1)

    elif action == "check":
        console.print("[bold]Checking paper...[/bold]")
        missing = check_figure_references()
        if missing:
            console.print("[yellow]Missing figures:[/yellow]")
            for fig in missing:
                console.print(f"  - {fig}")
        else:
            console.print("[green]All figure references resolved.[/green]")

        from core.paper import list_citations
        citations = list_citations()
        console.print(f"\nCitations: {len(citations)}")

    elif action == "update":
        console.print("[bold]Updating paper references...[/bold]")
        from core.paper import list_citations
        citations = list_citations()
        console.print(f"Current citations: {len(citations)}")
        console.print("Use core.paper.add_citation() to add references.")

    elif action == "modernize":
        console.print("[bold]Style analysis...[/bold]")
        from core.style_transfer import analyze_paper_style
        paper_tex = Path("paper/main.tex")
        if paper_tex.exists():
            profile = analyze_paper_style(paper_tex.read_text())
            console.print(f"  Avg sentence length: {profile.avg_sentence_length} words")
            console.print(f"  Passive voice ratio: {profile.passive_voice_ratio}")
            console.print(f"  Hedging ratio: {profile.hedging_ratio}")
            console.print(f"  Vocabulary richness: {profile.vocabulary_richness}")
            console.print(f"  Tense: {profile.tense}")
        else:
            console.print("[red]paper/main.tex not found[/red]")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available: build, update, modernize, check")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
