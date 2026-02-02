#!/usr/bin/env python3
"""ricet CLI - Scientific research automation powered by Claude Code."""

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

from core.auto_commit import auto_commit
from core.onboarding import (
    OnboardingAnswers,
    auto_install_claude_flow,
    check_and_install_packages,
    collect_answers,
    collect_credentials,
    create_github_repo,
    detect_system_for_init,
    ensure_package,
    infer_packages_from_goal,
    install_inferred_packages,
    load_settings,
    print_folder_map,
    setup_workspace,
    validate_goal_content,
    write_env_example,
    write_env_file,
    write_goal_file,
    write_settings,
)

__version__ = "0.2.0"


def version_callback(value: bool):
    if value:
        print(f"ricet {__version__}")
        raise typer.Exit()


app = typer.Typer(
    help="ricet - Scientific research automation powered by Claude Code.",
    epilog="Run 'ricet COMMAND --help' for more info on a command.",
)
console = Console()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """ricet CLI - Scientific research automation powered by Claude Code."""
    pass


TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
CONFIG_DIR = Path.home() / ".ricet"
SETUP_SCRIPT = Path(__file__).parent.parent / "scripts" / "setup_claude_flow.sh"


@app.command()
def init(
    project_name: str,
    path: Path = typer.Option(Path.cwd(), help="Where to create project"),
    skip_repo: bool = typer.Option(False, help="Skip GitHub repo creation"),
):
    """Initialize a new research project with full onboarding."""
    project_path = path / project_name

    if project_path.exists():
        console.print(f"[red]Error: {project_path} already exists[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Creating project: {project_name}[/bold]")

    # --- Step 0: Check Python packages ---
    console.print("\n[bold cyan]Step 0: Checking Python packages...[/bold cyan]")
    failed_pkgs = check_and_install_packages()
    if failed_pkgs:
        console.print(
            f"[red]Could not install: {', '.join(failed_pkgs)}. "
            f"Run: pip install {' '.join(failed_pkgs)}[/red]"
        )
    else:
        console.print("  [green]All required packages available[/green]")

    # --- Step 1: Auto-detect system ---
    console.print("\n[bold cyan]Step 1: Detecting system...[/bold cyan]")
    system_info = detect_system_for_init()

    console.print(f"  OS:      {system_info['os']}")
    console.print(f"  Python:  {system_info['python']}")
    console.print(f"  CPU:     {system_info['cpu']}")
    console.print(f"  RAM:     {system_info['ram_gb']} GB")
    if system_info["gpu"]:
        console.print(f"  GPU:     [green]{system_info['gpu']}[/green]")
        console.print(f"  Compute: [green]local-gpu (auto-detected)[/green]")
    else:
        console.print("  GPU:     [dim]None detected[/dim]")
        console.print("  Compute: local-cpu")
    if system_info["docker"]:
        console.print("  Docker:  [green]Available[/green]")
    if system_info["conda"]:
        console.print("  Conda:   [green]Available[/green]")

    # --- Step 2: Install claude-flow ---
    console.print("\n[bold cyan]Step 2: Setting up claude-flow...[/bold cyan]")
    cf_ok = auto_install_claude_flow()
    if cf_ok:
        console.print("  [green]claude-flow is ready[/green]")
    else:
        console.print(
            "  [yellow]claude-flow not available (optional, install Node.js + npm)[/yellow]"
        )

    # --- Step 3: Streamlined questionnaire ---
    console.print("\n[bold cyan]Step 3: Project configuration[/bold cyan]")

    def _prompt(prompt, default=""):
        return (
            typer.prompt(prompt, default=default) if default else typer.prompt(prompt)
        )

    answers = collect_answers(project_name, prompt_fn=_prompt, system_info=system_info)

    # --- Step 3b: Collect API credentials ---
    console.print("\n[bold cyan]Step 3b: API credentials[/bold cyan]")
    console.print("  [dim]Press Enter to skip any credential you don't have yet.[/dim]")

    credentials = collect_credentials(
        answers,
        prompt_fn=_prompt,
        print_fn=lambda msg: console.print(f"[dim]{msg}[/dim]"),
    )
    if credentials:
        console.print(f"  [green]{len(credentials)} credential(s) collected[/green]")
    else:
        console.print(
            "  [dim]No credentials entered (can be added later in secrets/.env)[/dim]"
        )

    # --- Step 4: Create project structure ---
    console.print("\n[bold cyan]Step 4: Creating project...[/bold cyan]")

    # Copy templates
    if TEMPLATE_DIR.exists():
        shutil.copytree(TEMPLATE_DIR, project_path)
    else:
        project_path.mkdir(parents=True)

    # Setup workspace folders
    setup_workspace(project_path)

    # Write settings, goal, and credentials
    write_settings(project_path, answers)
    write_goal_file(project_path, answers)
    write_env_file(project_path, credentials)
    write_env_example(project_path)

    # Create state directories
    (project_path / "state" / "sessions").mkdir(parents=True, exist_ok=True)
    (project_path / "state" / "TODO.md").write_text(
        "# TODO\n\n- [ ] Edit GOAL.md with detailed project description\n"
        "- [ ] Set up environment\n- [ ] Begin first task\n"
    )
    (project_path / "state" / "PROGRESS.md").write_text("# Progress\n\n")

    # Write GOAL.md prompt for user
    goal_file = project_path / "knowledge" / "GOAL.md"
    if goal_file.exists():
        goal_content = goal_file.read_text()
        if "<!-- User provides during init -->" in goal_content:
            goal_content = goal_content.replace(
                "<!-- User provides during init -->",
                "<!-- WRITE YOUR PROJECT DESCRIPTION HERE -->\n"
                "<!-- Be detailed: at least one full page. Describe your research\n"
                "     question, methodology, expected outcomes, and constraints. -->\n",
            )
            goal_file.write_text(goal_content)

    # Write claude-flow config
    cf_config_src = TEMPLATE_DIR / "config" / "claude-flow.json"
    if cf_config_src.exists():
        cf_dest = project_path / "config" / "claude-flow.json"
        cf_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cf_config_src, cf_dest)

    # Add claude-flow MCP to settings if available
    _inject_claude_flow_mcp(project_path)

    # --- Step 5: GitHub repo creation ---
    repo_url = ""
    if not skip_repo:
        console.print("\n[bold cyan]Step 5: GitHub repository[/bold cyan]")
        create_repo = _prompt("Create a GitHub repo for this project? (yes/no)", "yes")
        if create_repo.lower() in ("yes", "y"):
            private = _prompt("Private repo? (yes/no)", "yes")
            is_private = private.lower() in ("yes", "y")
            console.print(f"  Creating {'private' if is_private else 'public'} repo...")
            repo_url = create_github_repo(project_name, private=is_private)
            if repo_url:
                answers.github_repo = repo_url
                console.print(f"  [green]Repo created: {repo_url}[/green]")
                # Update settings with repo URL
                write_settings(project_path, answers)
            else:
                console.print(
                    "  [yellow]Could not create repo. "
                    "Install gh CLI and run: gh auth login[/yellow]"
                )

    # --- Step 6: Initialize git ---
    console.print("\n[bold cyan]Step 6: Initializing git...[/bold cyan]")
    subprocess.run(["git", "init"], cwd=project_path, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=project_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial project setup"],
        cwd=project_path,
        capture_output=True,
    )

    # If repo was created, add remote and push
    if repo_url:
        subprocess.run(
            ["git", "remote", "add", "origin", repo_url],
            cwd=project_path,
            capture_output=True,
        )
        console.print(
            "  [dim]Remote 'origin' added. Push with: git push -u origin main[/dim]"
        )

    auto_commit(f"ricet init: created project {project_name}", cwd=project_path)

    # --- Done ---
    console.print(f"\n[bold green]Project created at {project_path}[/bold green]")
    console.print("")

    # Print folder map
    for line in print_folder_map(project_path):
        console.print(f"  {line}")
    console.print("")

    console.print("[bold]Next steps:[/bold]")
    console.print(f"  1. cd {project_path}")
    console.print(
        "  2. Edit [bold]knowledge/GOAL.md[/bold] with your detailed project description"
    )
    console.print("     (at least 200 characters of real content)")
    console.print("  3. Add reference papers to [bold]reference/papers/[/bold]")
    console.print("  4. ricet start")


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
    section: str = typer.Argument(
        None, help="Section to reconfigure (notifications, compute, credentials)"
    ),
):
    """View or reconfigure project settings."""
    settings = load_settings(Path.cwd())
    if not settings:
        console.print("[red]No settings found. Run 'ricet init' first.[/red]")
        raise typer.Exit(1)

    if section is None:
        # Show current settings
        import yaml

        console.print("[bold]Current Settings:[/bold]")
        console.print(yaml.dump(settings, default_flow_style=False))
        return

    if section == "notifications":
        method = typer.prompt(
            "Notification method (email, slack, none)", default="none"
        )
        settings.setdefault("notifications", {})["method"] = method
        settings["notifications"]["enabled"] = method != "none"
        if method == "email":
            settings["notifications"]["email"] = typer.prompt("Email address")
        elif method == "slack":
            settings["notifications"]["slack_webhook"] = typer.prompt(
                "Slack webhook URL"
            )
    elif section == "compute":
        ctype = typer.prompt(
            "Compute type (local-cpu, local-gpu, cloud, cluster)", default="local-cpu"
        )
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
    settings_path.write_text(
        yaml.dump(settings, default_flow_style=False, sort_keys=False)
    )
    console.print("[green]Settings updated.[/green]")
    auto_commit(f"ricet config: updated {section}")


@app.command()
def start(
    session_name: str = typer.Option(None, help="Name for this session"),
):
    """Start an interactive research session.

    Loads project settings, starts enabled services (mobile, dashboard),
    saves a claude-flow session checkpoint, then launches Claude Code.
    """
    import os
    import uuid as _uuid

    from core.claude_flow import ClaudeFlowUnavailable, _get_bridge
    from core.collaboration import sync_before_start as _sync_before

    # --- Collaborative sync ---
    if not _sync_before():
        console.print(
            "[yellow]Warning: could not pull latest changes. "
            "Resolve conflicts and retry.[/yellow]"
        )

    # --- GOAL.md enforcement ---
    goal_file = Path("knowledge/GOAL.md")
    if not goal_file.exists():
        console.print("[red]knowledge/GOAL.md not found. Run 'ricet init' first.[/red]")
        raise typer.Exit(1)

    goal_content = goal_file.read_text()
    if not validate_goal_content(goal_content):
        console.print(
            "[yellow]knowledge/GOAL.md does not have enough content.[/yellow]"
        )
        console.print(
            "Please describe your research in knowledge/GOAL.md "
            "(at least 200 characters of real content)."
        )
        # Try to open editor
        editor = os.environ.get("EDITOR", os.environ.get("VISUAL", ""))
        if editor:
            console.print(f"[dim]Opening {editor}...[/dim]")
            subprocess.run([editor, str(goal_file)])
            # Re-check after editor
            goal_content = goal_file.read_text()
            if not validate_goal_content(goal_content):
                console.print(
                    "[red]GOAL.md still insufficient. "
                    "Please edit it and run 'ricet start' again.[/red]"
                )
                raise typer.Exit(1)
        else:
            console.print(
                "[red]Set $EDITOR or edit knowledge/GOAL.md manually, "
                "then run 'ricet start' again.[/red]"
            )
            raise typer.Exit(1)

    # --- Goal-aware package setup ---
    inferred = infer_packages_from_goal(goal_content)
    if inferred:
        console.print(f"[cyan]Detected project needs: {', '.join(inferred)}[/cyan]")
        installed, pkg_failed = install_inferred_packages(inferred)
        if installed:
            console.print(f"[green]Installed: {', '.join(installed)}[/green]")
        if pkg_failed:
            console.print(
                f"[yellow]Could not install: {', '.join(pkg_failed)} "
                f"(install manually with pip)[/yellow]"
            )

    # --- Quick package sanity check ---
    base_failed = check_and_install_packages()
    if base_failed:
        console.print(
            f"[yellow]Missing base packages: {', '.join(base_failed)}[/yellow]"
        )

    if session_name is None:
        session_name = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Generate a proper UUID for Claude Code (it requires valid UUIDs)
    session_uuid = str(_uuid.uuid4())

    session_dir = Path("state/sessions")
    session_dir.mkdir(parents=True, exist_ok=True)

    session_file = session_dir / f"{session_name}.json"
    session_data = {
        "name": session_name,
        "uuid": session_uuid,
        "started": datetime.now().isoformat(),
        "status": "active",
        "token_estimate": 0,
    }
    session_file.write_text(json.dumps(session_data, indent=2))

    # Load project settings
    settings = load_settings(Path.cwd())
    features = settings.get("features", {})

    # Start mobile server if enabled
    if features.get("mobile"):
        try:
            from core.mobile import mobile_server

            mobile_server.start()
            url = mobile_server.get_url()
            console.print(f"[green]Mobile server: {url}[/green]")
        except Exception as exc:
            console.print(f"[yellow]Mobile server not started: {exc}[/yellow]")

    # Show dashboard URL if website enabled
    if features.get("website"):
        console.print(
            "[dim]Web dashboard enabled. Run 'ricet website preview' in another terminal.[/dim]"
        )

    # Save claude-flow session state
    try:
        bridge = _get_bridge()
        bridge.start_session(session_name)
        console.print(f"[green]claude-flow session: {session_name}[/green]")
    except ClaudeFlowUnavailable:
        pass

    # Reindex linked repos for cross-repo RAG
    try:
        from core.cross_repo import reindex_all

        reindex_all()
    except Exception:
        pass

    auto_commit(f"ricet start: session {session_name}")

    console.print(
        f"[green]Session started: {session_name} ({session_uuid[:8]}...)[/green]"
    )

    # Launch Claude Code with a valid UUID session
    subprocess.run(["claude", "--session-id", session_uuid])


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
        auto_commit("ricet overnight: completed swarm run")
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

    auto_commit("ricet overnight: completed run")
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
        console.print(f"[bold]claude-flow {bridge.get_version()}[/bold]")
        status = bridge.get_metrics()
        console.print(
            f"  Status: {status.get('output', status.get('status', 'connected'))}"
        )
        agent_stats = status.get("agents", {})
        if agent_stats:
            for name, info in agent_stats.items():
                console.print(f"  {name}: {info}")
        else:
            console.print("  No active swarm agents")
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
        console.print(
            "[yellow]claude-flow not available. Using keyword search.[/yellow]"
        )
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
            auto_commit("ricet paper: compiled paper")
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


@app.command()
def mobile(
    action: str = typer.Argument(help="Action: start, stop, url"),
):
    """Manage mobile companion server for on-the-go monitoring."""
    try:
        from core.mobile import mobile_server
    except ImportError:
        console.print(
            "[red]core.mobile not available. Install mobile dependencies first.[/red]"
        )
        raise typer.Exit(1)

    if action == "start":
        console.print("[bold]Starting mobile server...[/bold]")
        mobile_server.start()
        console.print("[green]Mobile server started.[/green]")
    elif action == "stop":
        console.print("[bold]Stopping mobile server...[/bold]")
        mobile_server.stop()
        console.print("[green]Mobile server stopped.[/green]")
    elif action == "url":
        url = mobile_server.get_url()
        console.print(f"[bold]Mobile URL:[/bold] {url}")
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available: start, stop, url")
        raise typer.Exit(1)


@app.command()
def website(
    action: str = typer.Argument(help="Action: init, build, deploy, preview"),
):
    """Manage project website for sharing results."""
    try:
        from core.website import site_manager
    except ImportError:
        console.print(
            "[red]core.website not available. Install website dependencies first.[/red]"
        )
        raise typer.Exit(1)

    if action == "init":
        console.print("[bold]Initializing project website...[/bold]")
        site_manager.init()
        console.print("[green]Website initialized.[/green]")
    elif action == "build":
        console.print("[bold]Building website...[/bold]")
        site_manager.build()
        console.print("[green]Website built.[/green]")
    elif action == "deploy":
        console.print("[bold]Deploying website...[/bold]")
        site_manager.deploy()
        console.print("[green]Website deployed.[/green]")
    elif action == "preview":
        console.print("[bold]Starting preview server...[/bold]")
        site_manager.preview()
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available: init, build, deploy, preview")
        raise typer.Exit(1)


@app.command()
def publish(
    platform: str = typer.Argument(help="Platform: medium, linkedin"),
):
    """Draft and publish research summaries to social platforms."""
    try:
        from core.social_media import publish_to_platform
    except ImportError:
        console.print(
            "[red]core.social_media not available. Install social media dependencies first.[/red]"
        )
        raise typer.Exit(1)

    title = (
        typer.prompt("Post title", default="") if platform.lower() == "medium" else ""
    )
    body = typer.prompt("Post body")
    console.print(f"[bold]Publishing to {platform}...[/bold]")
    result = publish_to_platform(platform, title=title, body=body)
    if result.get("success"):
        url = result.get("url", "")
        console.print(f"[green]Published successfully.[/green]")
        if url:
            console.print(f"[bold]URL:[/bold] {url}")
    else:
        error = result.get("error", "Unknown error")
        console.print(f"[red]Publish failed: {error}[/red]")
        raise typer.Exit(1)


@app.command()
def verify(
    text: str = typer.Argument(help="Text or claim to verify"),
):
    """Run verification and fact-checking on a piece of text."""
    try:
        from core.verification import verify_text
    except ImportError:
        console.print(
            "[red]core.verification not available. Install verification dependencies first.[/red]"
        )
        raise typer.Exit(1)

    console.print("[bold]Running verification...[/bold]")
    report = verify_text(text)
    auto_commit("ricet verify: ran verification")
    verdict = report.get("verdict", "unknown")

    # Show hard failures (file refs, citations)
    file_issues = report.get("file_issues", [])
    citation_issues = report.get("citation_issues", [])
    if file_issues or citation_issues:
        console.print(f"\n[bold red]Verdict:[/bold red] issues_found")
        for issue in file_issues:
            console.print(f"  [red]- {issue}[/red]")
        for issue in citation_issues:
            console.print(f"  [red]- {issue}[/red]")
    elif verdict == "claims_extracted":
        claims = report.get("claims", [])
        console.print(f"\n[bold]Extracted {len(claims)} claim(s) for review:[/bold]")
        for c in claims:
            conf = f"{c['confidence']:.0%}"
            console.print(f"  [{conf}] {c['claim']}")
        console.print(
            "\n[dim]These claims were extracted heuristically. "
            "External verification not yet connected.[/dim]"
        )
    else:
        console.print("\n[green]No verifiable claims detected in the input.[/green]")


@app.command()
def debug(
    command: str = typer.Argument(help="Command or script to auto-debug"),
):
    """Run an automatic debug loop on a failing command."""
    try:
        from core.auto_debug import auto_debug_loop
    except ImportError:
        console.print(
            "[red]core.auto_debug not available. Install debug dependencies first.[/red]"
        )
        raise typer.Exit(1)

    console.print(f"[bold]Starting auto-debug for:[/bold] {command}")
    result = auto_debug_loop(command)
    auto_commit(f"ricet debug: auto-debug {command[:40]}")
    if result.get("fixed"):
        console.print("[green]Issue resolved after auto-debug.[/green]")
        if result.get("patch"):
            console.print(f"[bold]Patch:[/bold]\n{result['patch']}")
    else:
        console.print("[yellow]Auto-debug could not fully resolve the issue.[/yellow]")
        if result.get("log"):
            console.print(f"[bold]Debug log:[/bold]\n{result['log']}")


@app.command()
def projects(
    action: str = typer.Argument(help="Action: list, switch, register"),
):
    """Manage multiple research projects."""
    try:
        from core.multi_project import project_manager
    except ImportError:
        console.print(
            "[red]core.multi_project not available. Install multi-project dependencies first.[/red]"
        )
        raise typer.Exit(1)

    if action == "list":
        entries = project_manager.list_projects()
        if entries:
            console.print("[bold]Registered projects:[/bold]")
            for entry in entries:
                marker = " *" if entry.get("active") else ""
                console.print(f"  {entry['name']} — {entry['path']}{marker}")
        else:
            console.print("No projects registered yet.")
    elif action == "switch":
        name = typer.prompt("Project name to switch to")
        project_manager.switch(name)
        console.print(f"[green]Switched to project: {name}[/green]")
    elif action == "register":
        name = typer.prompt("Project name")
        path = typer.prompt("Project path", default=str(Path.cwd()))
        project_manager.register(name, path)
        auto_commit(f"ricet projects: registered {name}")
        console.print(f"[green]Registered project: {name}[/green]")
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available: list, switch, register")
        raise typer.Exit(1)


@app.command()
def worktree(
    action: str = typer.Argument(help="Action: add, list, remove, prune"),
    branch: str = typer.Argument("", help="Branch name (for add/remove)"),
):
    """Manage git worktrees for parallel experiments."""
    try:
        from core.git_worktrees import worktree_manager
    except ImportError:
        console.print(
            "[red]core.git_worktrees not available. Install worktree dependencies first.[/red]"
        )
        raise typer.Exit(1)

    if action == "add":
        if not branch:
            console.print("[red]Branch name required for add.[/red]")
            raise typer.Exit(1)
        console.print(f"[bold]Adding worktree for branch: {branch}[/bold]")
        path = worktree_manager.add(branch)
        auto_commit(f"ricet worktree: added {branch}")
        console.print(f"[green]Worktree created at {path}[/green]")
    elif action == "list":
        trees = worktree_manager.list()
        if trees:
            console.print("[bold]Active worktrees:[/bold]")
            for t in trees:
                console.print(f"  {t['branch']} → {t['path']}")
        else:
            console.print("No worktrees found.")
    elif action == "remove":
        if not branch:
            console.print("[red]Branch name required for remove.[/red]")
            raise typer.Exit(1)
        worktree_manager.remove(branch)
        auto_commit(f"ricet worktree: removed {branch}")
        console.print(f"[green]Worktree for {branch} removed.[/green]")
    elif action == "prune":
        worktree_manager.prune()
        console.print("[green]Stale worktrees pruned.[/green]")
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available: add, list, remove, prune")
        raise typer.Exit(1)


@app.command()
def queue(
    action: str = typer.Argument(..., help="submit | status | drain | cancel-all"),
    prompt: str = typer.Option("", "--prompt", "-p", help="Prompt text to submit"),
    chain: bool = typer.Option(False, "--chain", help="Chain prompts sequentially"),
    workers: int = typer.Option(3, "--workers", "-w", help="Max parallel workers"),
):
    """Queue prompts for dynamic multi-agent dispatch."""
    from core.prompt_queue import PromptQueue

    # Use a persistent queue location
    memory_dir = Path("state/prompt_memory")

    if action == "submit":
        if not prompt:
            console.print("[red]Provide --prompt/-p text to submit.[/red]")
            raise typer.Exit(1)
        q = PromptQueue(max_workers=workers, memory_dir=memory_dir)
        pid = q.submit(prompt)
        console.print(f"[green]Queued prompt {pid}: {prompt[:60]}[/green]")
        q.shutdown(wait=False)

    elif action == "status":
        q = PromptQueue(max_workers=workers, memory_dir=memory_dir)
        q.load_state()
        st = q.status()
        console.print(f"[bold]Queue Status[/bold]")
        console.print(f"  Queued:    {st['queued']}")
        console.print(f"  Running:   {st['running']}")
        console.print(f"  Completed: {st['completed']}")
        console.print(f"  Memory:    {st['memory_entries']} entries")
        q.shutdown(wait=False)

    elif action == "drain":
        q = PromptQueue(max_workers=workers, memory_dir=memory_dir)
        q.load_state()
        console.print("[bold]Draining queue (waiting for all prompts)...[/bold]")
        results = q.drain()
        for r in results:
            icon = "✓" if r.status == "success" else "✗"
            console.print(f"  {icon} [{r.prompt_id}] {r.text[:50]} → {r.status}")
        q.shutdown()

    elif action == "cancel-all":
        q = PromptQueue(max_workers=workers, memory_dir=memory_dir)
        q.load_state()
        n = q.cancel_all()
        console.print(f"[yellow]Cancelled {n} queued prompts.[/yellow]")
        q.shutdown()

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available: submit, status, drain, cancel-all")
        raise typer.Exit(1)


@app.command()
def adopt(
    source: str = typer.Argument(help="GitHub URL or local path to adopt"),
    name: str = typer.Option(None, "--name", "-n", help="Project name"),
    path: Path = typer.Option(None, "--path", help="Target directory"),
    no_fork: bool = typer.Option(False, "--no-fork", help="Clone instead of fork"),
):
    """Adopt an existing repository as a Ricet project."""
    from core.adopt import adopt_repo

    console.print(f"[bold]Adopting: {source}[/bold]")
    try:
        project_dir = adopt_repo(
            source,
            project_name=name,
            target_path=path,
            fork=not no_fork,
        )
        console.print(f"[green]Project adopted at {project_dir}[/green]")
        console.print("[bold]Next steps:[/bold]")
        console.print(f"  1. cd {project_dir}")
        console.print(
            "  2. Edit [bold]knowledge/GOAL.md[/bold] with your research description"
        )
        console.print("  3. ricet start")
    except (RuntimeError, FileNotFoundError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)


@app.command()
def link(
    repo_path: str = typer.Argument(help="Path to repository to link for RAG"),
    name: str = typer.Option(None, "--name", "-n", help="Short name for the repo"),
):
    """Link an external repository for cross-repo RAG (read-only)."""
    from core.cross_repo import link_repository

    repo_name = name or Path(repo_path).name
    link_repository(repo_name, repo_path, permissions=["read"])
    console.print(f"[green]Linked '{repo_name}' at {repo_path} (read-only)[/green]")

    # Index it immediately
    try:
        from core.cross_repo import LinkedRepo, index_linked_repo

        repo = LinkedRepo(name=repo_name, path=repo_path)
        count = index_linked_repo(repo)
        console.print(f"[green]Indexed {count} files from '{repo_name}'[/green]")
    except Exception as exc:
        console.print(f"[yellow]Indexing skipped: {exc}[/yellow]")

    auto_commit(f"ricet link: linked {repo_name}")


@app.command()
def unlink(
    name: str = typer.Argument(help="Name of the linked repo to remove"),
):
    """Remove a linked repository from cross-repo RAG."""
    from core.cross_repo import (
        LINKED_REPOS_FILE,
        _load_linked_repos,
        _save_linked_repos,
    )

    repos = _load_linked_repos()
    original_len = len(repos)
    repos = [r for r in repos if r.name != name]
    if len(repos) == original_len:
        console.print(f"[yellow]No linked repo named '{name}' found.[/yellow]")
        return
    _save_linked_repos(repos)
    console.print(f"[green]Unlinked '{name}'[/green]")
    auto_commit(f"ricet unlink: removed {name}")


@app.command()
def reindex():
    """Re-index all linked repositories for cross-repo RAG."""
    from core.cross_repo import reindex_all

    console.print("[bold]Re-indexing all linked repos...[/bold]")
    results = reindex_all()
    for repo_name, count in results.items():
        console.print(f"  {repo_name}: {count} files indexed")
    if not results:
        console.print("  No linked repos to index.")
    console.print("[green]Done.[/green]")


if __name__ == "__main__":
    app()
