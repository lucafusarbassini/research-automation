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

app = typer.Typer(help="Scientific Research Automation")
console = Console()

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
CONFIG_DIR = Path.home() / ".research-automation"


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

    # Initialize git
    subprocess.run(["git", "init"], cwd=project_path)
    subprocess.run(["git", "add", "-A"], cwd=project_path)
    subprocess.run(["git", "commit", "-m", "Initial project setup"], cwd=project_path)

    console.print(f"\n[green]Project created at {project_path}[/green]")
    console.print("\nNext steps:")
    console.print(f"  cd {project_path}")
    console.print("  research start")


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
