#!/usr/bin/env python3
"""Research automation CLI."""

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(help="Scientific Research Automation")
console = Console()

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
CONFIG_DIR = Path.home() / ".research-automation"


@app.command()
def init(
    project_name: str,
    path: Path = typer.Option(Path.cwd(), help="Where to create project"),
):
    """Initialize a new research project."""
    project_path = path / project_name

    if project_path.exists():
        console.print(f"[red]Error: {project_path} already exists[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Creating project: {project_name}[/bold]")

    # Interactive onboarding
    console.print("\n[bold cyan]Project Setup[/bold cyan]")

    goal = typer.prompt("What is the main goal of this project?")

    project_type = typer.prompt(
        "Project type",
        type=typer.Choice(["ml-research", "data-analysis", "paper-writing", "general"]),
        default="ml-research",
    )

    # Copy templates
    shutil.copytree(TEMPLATE_DIR, project_path)

    # Customize GOAL.md
    goal_file = project_path / "knowledge" / "GOAL.md"
    goal_content = goal_file.read_text()
    goal_content = goal_content.replace("<!-- User provides during init -->", goal)
    goal_file.write_text(goal_content)

    # Create state directories
    (project_path / "state" / "sessions").mkdir(parents=True, exist_ok=True)
    (project_path / "state" / "TODO.md").write_text(
        f"# TODO\n\n- [ ] Review GOAL.md and refine success criteria\n"
        f"- [ ] Set up environment\n- [ ] Begin first task\n"
    )
    (project_path / "state" / "PROGRESS.md").write_text("# Progress\n\n")

    # Initialize git
    subprocess.run(["git", "init"], cwd=project_path)
    subprocess.run(["git", "add", "-A"], cwd=project_path)
    subprocess.run(["git", "commit", "-m", "Initial project setup"], cwd=project_path)

    console.print(f"\n[green]Project created at {project_path}[/green]")
    console.print("\nNext steps:")
    console.print(f"  cd {project_path}")
    console.print("  research start")


@app.command()
def start(
    session_name: str = typer.Option(None, help="Name for this session"),
):
    """Start an interactive research session."""
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

    console.print(f"[green]Session started: {session_name}[/green]")

    # Launch Claude Code
    subprocess.run(["claude", "--session-id", session_name])


@app.command()
def overnight(
    task_file: Path = typer.Option(Path("state/TODO.md"), help="Task file to execute"),
    iterations: int = typer.Option(20, help="Max iterations"),
):
    """Run overnight autonomous mode."""
    console.print("[bold yellow]Starting overnight mode[/bold yellow]")
    console.print(f"Task file: {task_file}")
    console.print(f"Max iterations: {iterations}")

    if not task_file.exists():
        console.print(f"[red]Error: {task_file} not found[/red]")
        raise typer.Exit(1)

    tasks = task_file.read_text()

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
    if Path("state/TODO.md").exists():
        console.print("[bold]TODO:[/bold]")
        console.print(Path("state/TODO.md").read_text()[:500])

    if Path("state/PROGRESS.md").exists():
        console.print("\n[bold]Progress:[/bold]")
        console.print(Path("state/PROGRESS.md").read_text()[-500:])


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


if __name__ == "__main__":
    app()
