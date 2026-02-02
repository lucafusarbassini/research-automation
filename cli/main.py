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
    generate_goal_milestones,
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

    # Ensure agent prompt files are deployed (hidden dirs may be skipped
    # on some platforms or by future ignore filters)
    agents_src = TEMPLATE_DIR / ".claude" / "agents"
    agents_dst = project_path / ".claude" / "agents"
    if agents_src.exists():
        agents_dst.mkdir(parents=True, exist_ok=True)
        for f in agents_src.iterdir():
            if f.is_file():
                shutil.copy2(f, agents_dst / f.name)

    # Setup workspace folders
    setup_workspace(project_path)

    # Write settings, goal, and credentials
    write_settings(project_path, answers)
    write_goal_file(project_path, answers)
    write_env_file(project_path, credentials)
    write_env_example(project_path)

    # Create isolated Python environment
    from core.environment import (
        create_project_env,
        discover_system,
        populate_encyclopedia_env,
    )

    env_info = create_project_env(project_name, project_path)
    console.print(
        f"  [green]Python environment: {env_info['type']} ({env_info['name']})[/green]"
    )

    # Store env info in settings
    settings_path = project_path / "config" / "settings.yml"
    if settings_path.exists():
        import yaml

        _settings = yaml.safe_load(settings_path.read_text()) or {}
        _settings["environment"] = env_info
        settings_path.write_text(
            yaml.dump(_settings, default_flow_style=False, sort_keys=False)
        )

    # Populate encyclopedia with environment details
    sys_info_obj = discover_system()
    populate_encyclopedia_env(project_path, env_info, sys_info_obj)

    # Create state directories
    (project_path / "state" / "sessions").mkdir(parents=True, exist_ok=True)

    # Generate goal-aware TODO milestones
    goal_file_for_todo = project_path / "knowledge" / "GOAL.md"
    _goal_text = goal_file_for_todo.read_text() if goal_file_for_todo.exists() else ""
    milestones = generate_goal_milestones(_goal_text)
    todo_content = "# TODO\n\n"
    if milestones:
        for m in milestones:
            todo_content += f"- [ ] {m}\n"
    else:
        todo_content += (
            "- [ ] Edit GOAL.md with detailed project description\n"
            "- [ ] Set up environment\n"
            "- [ ] Begin first task\n"
        )
    (project_path / "state" / "TODO.md").write_text(todo_content)

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
                # Set repo description and topics from GOAL.md
                _configure_github_repo_from_goal(project_path, project_name, repo_url)
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


def _configure_github_repo_from_goal(
    project_path: Path,
    project_name: str,
    repo_url: str,
    *,
    run_cmd=None,
) -> None:
    """Set GitHub repo description and topics from GOAL.md content.

    Args:
        project_path: Root of the project.
        project_name: The project name.
        repo_url: The GitHub repo URL.
        run_cmd: Optional callable for testing.
    """
    goal_file = project_path / "knowledge" / "GOAL.md"
    if not goal_file.exists():
        return

    goal_text = goal_file.read_text()
    # Extract first meaningful paragraph (skip markdown headers and blank lines)
    lines = [
        l.strip()
        for l in goal_text.splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]
    if not lines:
        return

    # Description: first 350 chars of goal content
    description = " ".join(lines)[:350]

    # Try to infer topics from goal keywords
    topics = _infer_topics_from_goal(goal_text)

    if run_cmd is None:

        def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )

    try:
        owner_repo = "/".join(repo_url.rstrip("/").split("/")[-2:]).replace(".git", "")

        run_cmd(["gh", "repo", "edit", owner_repo, "--description", description])

        if topics:
            topic_args: list[str] = []
            for t in topics[:20]:  # GitHub max 20 topics
                topic_args.extend(["--add-topic", t])
            run_cmd(["gh", "repo", "edit", owner_repo] + topic_args)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def _infer_topics_from_goal(goal_text: str) -> list[str]:
    """Extract GitHub topic tags from goal text using Claude.

    Tries Claude CLI first for flexible, context-aware topic inference.
    Falls back to a minimal keyword check only if Claude is unavailable.

    Args:
        goal_text: Raw GOAL.md content.

    Returns:
        List of GitHub topic strings (max 20).
    """
    from core.claude_helper import call_claude_json

    # Always include base topics
    base = ["research-automation", "ricet"]

    # Ask Claude to infer topics flexibly
    result = call_claude_json(
        "Given this research project description, suggest 3-10 GitHub repository "
        "topic tags. Topics must be lowercase, hyphenated, no spaces, "
        "relevant to the research domain. Reply as a JSON array of strings.\n\n"
        f"Project:\n{goal_text[:2000]}"
    )
    if result and isinstance(result, list):
        # Sanitize: lowercase, replace spaces with hyphens, strip
        topics = base + [
            t.strip().lower().replace(" ", "-")
            for t in result
            if isinstance(t, str) and t.strip()
        ]
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique = []
        for t in topics:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        return unique[:20]

    # Minimal fallback: just use base topics (no hardcoded domain map)
    return base


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

    # --- Generate requirements.txt from project env ---
    from core.environment import generate_requirements_txt

    _start_settings = load_settings(Path.cwd())
    _start_env_info = _start_settings.get("environment", {})
    if _start_env_info:
        generate_requirements_txt(Path.cwd(), _start_env_info)

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

    from core.session import create_session

    session = create_session(session_name)

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

    # Suggest next steps based on GOAL.md and PROGRESS.md
    from core.prompt_suggestions import suggest_next_steps

    progress_file = Path("state/PROGRESS.md")
    progress_lines = []
    if progress_file.exists():
        progress_lines = [
            line.strip()
            for line in progress_file.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
    suggestions = suggest_next_steps(
        current_task=session_name,
        progress=progress_lines,
        goal=goal_content,
    )
    if suggestions:
        console.print("\n[bold cyan]Suggested next steps:[/bold cyan]")
        for i, step in enumerate(suggestions, 1):
            console.print(f"  {i}. {step}")
        console.print()

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
    from core.resources import (
        cleanup_old_checkpoints,
        make_resource_decision,
        monitor_resources,
    )

    console.print("[bold yellow]Starting overnight mode[/bold yellow]")
    console.print(f"Task file: {task_file}")
    console.print(f"Max iterations: {iterations}")

    if not task_file.exists():
        console.print(f"[red]Error: {task_file} not found[/red]")
        raise typer.Exit(1)

    # --- Goal fidelity check at the start of overnight ---
    from core.verification import check_goal_fidelity

    fidelity = check_goal_fidelity(Path.cwd())
    fidelity_score = fidelity.get("score", 50)
    if fidelity.get("error"):
        console.print(f"[yellow]Fidelity check: {fidelity['error']}[/yellow]")
    else:
        console.print(f"[bold]Goal fidelity score: {fidelity_score}/100[/bold]")
        if fidelity_score < 30:
            console.print("[red]WARNING: Goal alignment is very low![/red]")
            for area in fidelity.get("drift_areas", []):
                console.print(f"  [red]- Drift: {area}[/red]")
            for rec in fidelity.get("recommendations", []):
                console.print(f"  [yellow]- Recommendation: {rec}[/yellow]")

    tasks = task_file.read_text()

    # Try claude-flow swarm
    try:
        bridge = _get_bridge()
        console.print("[cyan]Using claude-flow swarm orchestration[/cyan]")
        swarm_tasks = [{"type": "coder", "task": tasks}]
        for i in range(iterations):
            # Resource-aware scheduling
            snap = monitor_resources()
            decision = make_resource_decision(snap)
            if not decision["can_proceed"]:
                console.print(
                    f"[red]Low resources (disk: {snap.disk_free_gb:.1f}GB). Pausing.[/red]"
                )
                break
            if decision["should_checkpoint"]:
                console.print(
                    f"[yellow]High memory usage ({snap.ram_used_gb:.1f}/{snap.ram_total_gb:.1f}GB). Checkpointing.[/yellow]"
                )
                auto_commit("ricet overnight: resource checkpoint")
            if decision.get("should_cleanup"):
                cleanup_old_checkpoints()

            console.print(
                f"\n[cyan]Iteration {i + 1}/{iterations}[/cyan] "
                f"[dim](CPU: {snap.cpu_percent:.0f}%, RAM: {snap.ram_used_gb:.1f}/{snap.ram_total_gb:.1f}GB, "
                f"Disk: {snap.disk_free_gb:.0f}GB free)[/dim]"
            )
            bridge.run_swarm(swarm_tasks, topology="hierarchical")

            # Auto-trigger falsifier verification after each iteration
            from core.agents import AgentType, execute_agent_task

            console.print("[yellow]Running falsifier verification...[/yellow]")
            falsifier_task = (
                f"Falsify and validate the results from the latest iteration. "
                f"Check for: data leakage, statistical validity, confounders, "
                f"reproducibility issues. Original task: {tasks}"
            )
            falsifier_result = execute_agent_task(AgentType.FALSIFIER, falsifier_task)
            if falsifier_result.status == "success":
                console.print(
                    f"[green]Falsifier: {falsifier_result.output[:200]}[/green]"
                )
            else:
                console.print(
                    f"[yellow]Falsifier flagged issues: {falsifier_result.output[:200]}[/yellow]"
                )

            if Path("state/DONE").exists():
                console.print("[green]Task completed![/green]")
                break
        auto_commit("ricet overnight: completed swarm run")
        console.print("[bold]Overnight mode finished[/bold]")
        return
    except ClaudeFlowUnavailable:
        pass

    # Fallback: agent-based execution with plan-execute-iterate
    from core.agents import (
        AgentType,
        execute_agent_task,
        get_agent_prompt,
        plan_execute_iterate,
        route_task,
    )
    from core.model_router import route_to_model
    from core.prompt_suggestions import suggest_decomposition

    # Decompose the task into subtasks before iterating
    subtasks = suggest_decomposition(tasks)
    if subtasks:
        console.print("[cyan]Task decomposition:[/cyan]")
        for i, st in enumerate(subtasks, 1):
            console.print(f"  {i}. {st}")

    overnight_model = route_to_model(tasks)
    agent_type = route_task(tasks)
    agent_prompt = get_agent_prompt(agent_type)
    enriched_tasks = f"{agent_prompt}\n\n## Tasks\n\n{tasks}" if agent_prompt else tasks

    # Use plan_execute_iterate for complex multi-subtask work
    if len(subtasks) > 3:
        console.print(
            "[cyan]Using plan-execute-iterate strategy for complex task[/cyan]"
        )
        pipeline_results = plan_execute_iterate(
            enriched_tasks,
            max_iterations=min(iterations, 5),
            dangerously_skip_permissions=True,
        )
        for pr in pipeline_results:
            status_label = (
                "[green]OK[/green]" if pr.status == "success" else "[red]FAIL[/red]"
            )
            console.print(f"  [{pr.agent.value}] {status_label} {pr.task[:80]}")
    else:
        for i in range(iterations):
            # Resource-aware scheduling
            snap = monitor_resources()
            decision = make_resource_decision(snap)
            if not decision["can_proceed"]:
                console.print(
                    f"[red]Low resources (disk: {snap.disk_free_gb:.1f}GB). Pausing.[/red]"
                )
                break
            if decision["should_checkpoint"]:
                console.print(
                    f"[yellow]High memory usage ({snap.ram_used_gb:.1f}/{snap.ram_total_gb:.1f}GB). Checkpointing.[/yellow]"
                )
                auto_commit("ricet overnight: resource checkpoint")
            if decision.get("should_cleanup"):
                cleanup_old_checkpoints()

            console.print(
                f"\n[cyan]Iteration {i + 1}/{iterations}[/cyan] "
                f"[dim](CPU: {snap.cpu_percent:.0f}%, RAM: {snap.ram_used_gb:.1f}/{snap.ram_total_gb:.1f}GB, "
                f"Disk: {snap.disk_free_gb:.0f}GB free)[/dim]"
            )

            result = subprocess.run(
                [
                    "claude",
                    "--dangerously-skip-permissions",
                    "-p",
                    enriched_tasks,
                    "--model",
                    overnight_model.name,
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                console.print(f"[red]Error in iteration {i + 1}[/red]")
                console.print(result.stderr)

            # Auto-trigger falsifier verification after each iteration
            console.print("[yellow]Running falsifier verification...[/yellow]")
            falsifier_task = (
                f"Falsify and validate the results from the latest iteration. "
                f"Check for: data leakage, statistical validity, confounders, "
                f"reproducibility issues. Original task: {tasks}"
            )
            falsifier_result = execute_agent_task(AgentType.FALSIFIER, falsifier_task)
            if falsifier_result.status == "success":
                console.print(
                    f"[green]Falsifier: {falsifier_result.output[:200]}[/green]"
                )
            else:
                console.print(
                    f"[yellow]Falsifier flagged issues: {falsifier_result.output[:200]}[/yellow]"
                )

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
    from core.session import list_sessions as _list_sessions

    sessions = _list_sessions()
    if not sessions:
        console.print("No sessions found")
        return

    for s in sessions:
        console.print(f"  {s.name} - {s.status} ({s.started[:10]})")


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
    action: str = typer.Argument(
        help="Action: search, log-decision, export, import, stats"
    ),
    query: str = typer.Argument(
        "", help="Search query or text (for search / log-decision)"
    ),
    top_k: int = typer.Option(5, help="Number of results (for search)"),
    file: Path = typer.Option(None, "--file", "-f", help="File path (for import)"),
):
    """Manage project knowledge: search, log decisions, export/import, stats."""
    if action == "search":
        if not query:
            console.print("[red]Provide a search query.[/red]")
            raise typer.Exit(1)
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

    elif action == "log-decision":
        if not query:
            console.print("[red]Provide decision text.[/red]")
            raise typer.Exit(1)
        from core.knowledge import log_decision

        # Split on " -- " to separate decision from rationale, or use full text
        if " -- " in query:
            decision, rationale = query.split(" -- ", 1)
        else:
            decision = query
            rationale = "Recorded via CLI"
        log_decision(decision, rationale)
        console.print(f"[green]Decision logged: {decision}[/green]")

    elif action == "export":
        from core.knowledge import export_knowledge
        from core.onboarding import load_settings

        settings = load_settings(Path.cwd())
        project_name = settings.get("project_name", Path.cwd().name)
        try:
            output = export_knowledge(project_name)
            console.print(f"[green]Knowledge exported to {output}[/green]")
        except FileNotFoundError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)

    elif action == "import":
        if file is None:
            console.print("[red]Provide --file/-f path for import.[/red]")
            raise typer.Exit(1)
        from core.knowledge import import_knowledge

        try:
            count = import_knowledge(file)
            console.print(f"[green]Imported {count} entries from {file}[/green]")
        except FileNotFoundError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)

    elif action == "stats":
        from core.knowledge import get_encyclopedia_stats

        stats = get_encyclopedia_stats()
        if stats:
            console.print("[bold]Encyclopedia stats:[/bold]")
            for section, count in stats.items():
                console.print(f"  {section}: {count} entries")
        else:
            console.print("[yellow]No encyclopedia found or empty.[/yellow]")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available: search, log-decision, export, import, stats")
        raise typer.Exit(1)


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
def auto(
    action: str = typer.Argument(help="Action: add-routine, list-routines, monitor"),
    name: str = typer.Option("", "--name", "-n", help="Routine name (for add-routine)"),
    description: str = typer.Option("", "--desc", "-d", help="Routine description"),
    schedule: str = typer.Option(
        "daily", "--schedule", "-s", help="Schedule: daily, hourly, weekly"
    ),
    command: str = typer.Option(
        "", "--command", "-c", help="Command to run (for add-routine)"
    ),
    topic: str = typer.Option(
        "", "--topic", "-t", help="Topic to monitor (for monitor)"
    ),
):
    """Manage autonomous routines: scheduled tasks and topic monitoring."""
    from core.autonomous import (
        ScheduledRoutine,
        add_routine,
        list_routines,
        monitor_topic,
    )

    if action == "add-routine":
        if not name:
            console.print("[red]Provide --name/-n for the routine.[/red]")
            raise typer.Exit(1)
        if not command:
            console.print("[red]Provide --command/-c for the routine.[/red]")
            raise typer.Exit(1)
        routine = ScheduledRoutine(
            name=name,
            description=description or name,
            schedule=schedule,
            command=command,
        )
        add_routine(routine)
        console.print(f"[green]Routine added: {name} ({schedule})[/green]")

    elif action == "list-routines":
        routines = list_routines()
        if routines:
            console.print("[bold]Scheduled routines:[/bold]")
            for r in routines:
                enabled = (
                    "[green]enabled[/green]" if r.enabled else "[dim]disabled[/dim]"
                )
                console.print(f"  {r.name} ({r.schedule}) {enabled} - {r.description}")
        else:
            console.print("No routines configured.")

    elif action == "monitor":
        if not topic:
            console.print("[red]Provide --topic/-t for monitoring.[/red]")
            raise typer.Exit(1)
        spec = monitor_topic(topic)
        console.print(
            f"[green]Monitoring '{topic}' via {', '.join(spec['sources'])}[/green]"
        )
        console.print(f"  Status: {spec['status']}")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available: add-routine, list-routines, monitor")
        raise typer.Exit(1)


@app.command()
def repro(
    action: str = typer.Argument(help="Action: log, list, show, hash"),
    run_id: str = typer.Option("", "--run-id", "-r", help="Run ID (for log/show)"),
    command_str: str = typer.Option(
        "", "--command", "-c", help="Command that was run (for log)"
    ),
    path: Path = typer.Option(None, "--path", "-p", help="Path to hash (for hash)"),
    notes: str = typer.Option("", "--notes", "-n", help="Notes for the run (for log)"),
):
    """Reproducibility tracking: log runs, list history, show details, hash datasets."""
    from core.reproducibility import (
        RunLog,
        compute_dataset_hash,
        list_runs,
        load_run,
        log_run,
    )

    if action == "log":
        if not run_id:
            run_id = datetime.now().strftime("run-%Y%m%d-%H%M%S")
        if not command_str:
            console.print("[red]Provide --command/-c for the run command.[/red]")
            raise typer.Exit(1)
        # Capture current git hash if available
        git_hash = ""
        try:
            proc = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True
            )
            if proc.returncode == 0:
                git_hash = proc.stdout.strip()
        except Exception:
            pass
        run = RunLog(
            run_id=run_id,
            command=command_str,
            git_hash=git_hash,
            notes=notes,
            status="completed",
        )
        saved = log_run(run)
        console.print(f"[green]Run logged: {run_id} -> {saved}[/green]")

    elif action == "list":
        runs = list_runs()
        if runs:
            console.print("[bold]Experiment runs:[/bold]")
            for r in runs:
                console.print(
                    f"  {r.run_id} [{r.status}] {r.command[:60]} ({r.started[:10]})"
                )
        else:
            console.print("No runs recorded yet.")

    elif action == "show":
        if not run_id:
            console.print("[red]Provide --run-id/-r to show.[/red]")
            raise typer.Exit(1)
        run = load_run(run_id)
        if run:
            console.print(f"[bold]Run: {run.run_id}[/bold]")
            console.print(f"  Command:  {run.command}")
            console.print(f"  Status:   {run.status}")
            console.print(f"  Started:  {run.started}")
            console.print(f"  Ended:    {run.ended or 'N/A'}")
            console.print(f"  Git hash: {run.git_hash or 'N/A'}")
            if run.parameters:
                console.print(f"  Params:   {json.dumps(run.parameters)}")
            if run.metrics:
                console.print(f"  Metrics:  {json.dumps(run.metrics)}")
            if run.artifacts:
                console.print(f"  Artifacts: {', '.join(run.artifacts)}")
            if run.notes:
                console.print(f"  Notes:    {run.notes}")
        else:
            console.print(f"[red]Run not found: {run_id}[/red]")

    elif action == "hash":
        if path is None:
            console.print("[red]Provide --path/-p to hash.[/red]")
            raise typer.Exit(1)
        if not path.exists():
            console.print(f"[red]Path not found: {path}[/red]")
            raise typer.Exit(1)
        digest = compute_dataset_hash(path)
        console.print(f"[bold]SHA-256:[/bold] {digest}")
        console.print(f"  Path: {path}")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available: log, list, show, hash")
        raise typer.Exit(1)


@app.command(name="mcp-search")
def mcp_search(
    need: str = typer.Argument(help="What you need (e.g. 'access PubMed papers')"),
    install: bool = typer.Option(
        False, "--install", "-i", help="Auto-install the match"
    ),
):
    """Search the MCP catalog for a server matching your need.

    Claude reads the full MCP catalog (1 300+ servers) and suggests the
    best match, its install command, and any API keys required.
    """
    from core.mcps import suggest_and_install_mcp

    suggest_and_install_mcp(
        need,
        auto_install=install,
        prompt_fn=lambda q, d: typer.prompt(q, default=d),
        print_fn=lambda msg: console.print(msg),
    )


@app.command()
def paper(
    action: str = typer.Argument(
        help="Action: build, update, modernize, check, adapt-style"
    ),
    reference: Path = typer.Option(
        None, "--reference", help="Path to reference paper for adapt-style"
    ),
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

    elif action == "adapt-style":
        console.print("[bold]Adapting paper style from reference...[/bold]")
        from core.style_transfer import rewrite_in_reference_style

        paper_tex = Path("paper/main.tex")
        if not paper_tex.exists():
            console.print("[red]paper/main.tex not found[/red]")
            raise typer.Exit(1)
        if reference is None:
            console.print("[red]--reference is required for adapt-style[/red]")
            raise typer.Exit(1)
        if not reference.exists():
            console.print(f"[red]Reference file not found: {reference}[/red]")
            raise typer.Exit(1)

        source_text = paper_tex.read_text()
        reference_text = reference.read_text()
        result = rewrite_in_reference_style(source_text, reference_text)

        console.print("\n[bold]Source style:[/bold]")
        sp = result["source_profile"]
        console.print(f"  Avg sentence length: {sp.avg_sentence_length} words")
        console.print(f"  Passive voice ratio: {sp.passive_voice_ratio}")
        console.print(f"  Hedging ratio: {sp.hedging_ratio}")
        console.print(f"  Vocabulary richness: {sp.vocabulary_richness}")
        console.print(f"  Tense: {sp.tense}")

        console.print("\n[bold]Target style:[/bold]")
        tp = result["target_profile"]
        console.print(f"  Avg sentence length: {tp.avg_sentence_length} words")
        console.print(f"  Passive voice ratio: {tp.passive_voice_ratio}")
        console.print(f"  Hedging ratio: {tp.hedging_ratio}")
        console.print(f"  Vocabulary richness: {tp.vocabulary_richness}")
        console.print(f"  Tense: {tp.tense}")

        if result.get("rewritten"):
            out_path = Path("paper/main_adapted.tex")
            out_path.write_text(result["rewritten"])
            console.print(f"\n[green]Adapted text written to {out_path}[/green]")
            if result["plagiarism_flags"]:
                console.print(
                    f"[yellow]Plagiarism flags: {len(result['plagiarism_flags'])}[/yellow]"
                )
                for flag in result["plagiarism_flags"]:
                    console.print(f"  - n-gram overlap: \"{flag['ngram']}\"")
            auto_commit("ricet paper: adapted style from reference")
        else:
            console.print(
                f"\n[yellow]Rewrite skipped: {result.get('error', 'unknown')}[/yellow]"
            )

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available: build, update, modernize, check, adapt-style")
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


@app.command()
def docs(
    force: bool = typer.Option(
        False, "--force", "-f", help="Run even if RICET_AUTO_DOCS is not set"
    ),
):
    """Auto-update project documentation from source code.

    Scans Python source directories, then:
    - Appends missing module stubs to docs/API.md
    - Adds missing CLI commands to README.md
    - Regenerates docs/MODULES.md index

    Enable automatic mode with: export RICET_AUTO_DOCS=true
    """
    from core.auto_docs import auto_update_docs

    console.print("[bold]Scanning project for documentation gaps...[/bold]")
    result = auto_update_docs(force=True if force else None)

    api = result.get("api_added", 0)
    cli = result.get("cli_added", 0)
    idx = result.get("modules_indexed", 0)

    if api or cli:
        console.print(f"[green]Updated docs:[/green]")
        if api:
            console.print(f"  API stubs added to docs/API.md: {api}")
        if cli:
            console.print(f"  CLI commands added to README.md: {cli}")
        if idx:
            console.print(f"  Module index updated: {idx} modules")
        auto_commit("ricet docs: auto-updated documentation")
    else:
        console.print("[dim]Documentation is up to date. No gaps found.[/dim]")
        if idx:
            console.print(f"  Module index refreshed: {idx} modules")


@app.command(name="two-repo")
def two_repo(
    action: str = typer.Argument(help="Action: init, status, promote, sync, diff"),
    files: str = typer.Option(
        "", "--files", "-f", help="Comma-separated file paths (for promote)"
    ),
    message: str = typer.Option(
        "Promote files", "--message", "-m", help="Commit message (for promote)"
    ),
    shared: str = typer.Option(
        "", "--shared", help="Comma-separated shared paths (for sync)"
    ),
):
    """Manage two-repo structure (experiments/ vs clean/)."""
    from core.two_repo import TwoRepoManager

    mgr = TwoRepoManager(Path.cwd())

    if action == "init":
        console.print("[bold]Initializing two-repo structure...[/bold]")
        result = mgr.init_two_repos()
        for name, ok in result.items():
            icon = "[green]ok[/green]" if ok else "[red]fail[/red]"
            console.print(f"  {name}: {icon}")
        auto_commit("ricet two-repo: initialized experiments/ and clean/")
        console.print("[green]Two-repo structure ready.[/green]")

    elif action == "status":
        st = mgr.get_status()
        for name, info in st.items():
            dirty = (
                "[yellow]dirty[/yellow]" if info["dirty"] else "[green]clean[/green]"
            )
            console.print(f"  {name}: branch={info['branch']} {dirty}")

    elif action == "promote":
        if not files:
            console.print(
                "[red]Provide --files/-f with comma-separated paths to promote.[/red]"
            )
            raise typer.Exit(1)
        file_list = [f.strip() for f in files.split(",") if f.strip()]
        console.print(f"[bold]Promoting {len(file_list)} file(s) to clean/...[/bold]")
        ok = mgr.promote_to_clean(file_list, message)
        if ok:
            auto_commit(f"ricet two-repo: promoted {len(file_list)} files")
            console.print("[green]Files promoted and committed in clean/.[/green]")
        else:
            console.print(
                "[red]Promote failed. Check that source files exist in experiments/.[/red]"
            )
            raise typer.Exit(1)

    elif action == "sync":
        shared_files = [s.strip() for s in shared.split(",") if s.strip()] or None
        console.print("[bold]Syncing shared files...[/bold]")
        ok = mgr.sync_shared(shared_files)
        if ok:
            auto_commit("ricet two-repo: synced shared files")
            console.print(
                "[green]Shared files synced from experiments/ to clean/.[/green]"
            )
        else:
            console.print("[red]Sync failed. Check that source paths exist.[/red]")
            raise typer.Exit(1)

    elif action == "diff":
        diff_output = mgr.diff_repos()
        if diff_output:
            console.print("[bold]Differences between experiments/ and clean/:[/bold]")
            console.print(diff_output)
        else:
            console.print("[green]No differences found.[/green]")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available: init, status, promote, sync, diff")
        raise typer.Exit(1)


@app.command()
def browse(
    url: str = typer.Argument(help="URL to fetch and extract text from"),
    screenshot: str = typer.Option(
        "", "--screenshot", "-s", help="Save screenshot to this path"
    ),
):
    """Fetch a URL and extract its text content (useful for literature review)."""
    from core.browser import BrowserSession

    session = BrowserSession()
    if not session.is_available():
        console.print(
            "[red]No browser backend available (need curl, wget, or Puppeteer).[/red]"
        )
        raise typer.Exit(1)

    console.print(f"[bold]Fetching:[/bold] {url}")
    try:
        text = session.extract_text(url)
        if text:
            console.print(text)
        else:
            console.print("[yellow]No text content extracted.[/yellow]")
    except Exception as exc:
        console.print(f"[red]Fetch failed: {exc}[/red]")
        raise typer.Exit(1)

    if screenshot:
        try:
            out_path = session.screenshot(url, Path(screenshot))
            console.print(f"[green]Screenshot saved to {out_path}[/green]")
        except Exception as exc:
            console.print(f"[yellow]Screenshot failed: {exc}[/yellow]")


@app.command()
def infra(
    action: str = typer.Argument(
        help="Action: check, docker-build, docker-run, cicd, secrets"
    ),
    tag: str = typer.Option(
        "", "--tag", "-t", help="Docker image tag (for docker-build/docker-run)"
    ),
    dockerfile: Path = typer.Option(
        Path("Dockerfile"), "--dockerfile", help="Dockerfile path"
    ),
    template: str = typer.Option(
        "python", "--template", help="CI/CD template (python, node)"
    ),
):
    """Manage infrastructure, Docker, CI/CD, and secrets."""
    from core.devops import (
        DockerManager,
        check_infrastructure,
        rotate_secrets,
        setup_ci_cd,
    )

    if action == "check":
        console.print("[bold]Infrastructure check:[/bold]")
        results = check_infrastructure()
        for name, info in results.items():
            if info["available"]:
                console.print(f"  {name}: [green]{info['version']}[/green]")
            else:
                console.print(f"  {name}: [red]not found[/red]")

    elif action == "docker-build":
        if not tag:
            console.print("[red]Provide --tag/-t for the Docker image.[/red]")
            raise typer.Exit(1)
        dm = DockerManager()
        if not dm.is_available():
            console.print("[red]Docker is not available.[/red]")
            raise typer.Exit(1)
        console.print(f"[bold]Building Docker image: {tag}[/bold]")
        ok = dm.build(tag, dockerfile)
        if ok:
            console.print(f"[green]Image {tag} built successfully.[/green]")
        else:
            console.print("[red]Docker build failed.[/red]")
            raise typer.Exit(1)

    elif action == "docker-run":
        if not tag:
            console.print("[red]Provide --tag/-t for the Docker image.[/red]")
            raise typer.Exit(1)
        dm = DockerManager()
        if not dm.is_available():
            console.print("[red]Docker is not available.[/red]")
            raise typer.Exit(1)
        console.print(f"[bold]Running container: {tag}[/bold]")
        container_id = dm.run(tag)
        if container_id:
            console.print(f"[green]Container started: {container_id[:12]}[/green]")
        else:
            console.print("[red]Docker run failed.[/red]")
            raise typer.Exit(1)

    elif action == "cicd":
        console.print(f"[bold]Setting up CI/CD ({template} template)...[/bold]")
        workflow_path = setup_ci_cd(Path.cwd(), template)
        auto_commit(f"ricet infra: created CI/CD workflow ({template})")
        console.print(f"[green]Workflow created: {workflow_path}[/green]")

    elif action == "secrets":
        console.print("[bold]Scanning for secrets to rotate...[/bold]")
        findings = rotate_secrets(Path.cwd())
        if findings:
            console.print(
                f"[yellow]Found {len(findings)} potential secret(s):[/yellow]"
            )
            for finding in findings:
                console.print(f"  - {finding}")
        else:
            console.print("[green]No exposed secrets found.[/green]")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available: check, docker-build, docker-run, cicd, secrets")
        raise typer.Exit(1)


@app.command()
def runbook(
    file: Path = typer.Argument(help="Path to a markdown runbook file"),
    execute: bool = typer.Option(
        False, "--execute", "-x", help="Actually execute code blocks (default: dry-run)"
    ),
):
    """Parse and optionally execute code blocks from a markdown runbook."""
    from core.markdown_commands import execute_runbook, parse_runbook

    if not file.exists():
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Parsing runbook:[/bold] {file}")
    steps = parse_runbook(file)

    if not steps:
        console.print("[yellow]No code blocks found in the runbook.[/yellow]")
        return

    console.print(f"Found {len(steps)} code block(s):")
    for i, step in enumerate(steps, 1):
        heading = step.get("heading", "(no heading)")
        lang = step.get("language", "?")
        console.print(f"  {i}. [{lang}] {heading}")

    if not execute:
        console.print("\n[dim]Dry-run mode. Use --execute/-x to run code blocks.[/dim]")

    results = execute_runbook(steps, dry_run=not execute)
    for i, r in enumerate(results, 1):
        heading = r.get("heading", "(no heading)")
        if r["skipped"]:
            console.print(f"  {i}. [dim]SKIPPED[/dim] {heading}")
        elif r["returncode"] == 0:
            console.print(f"  {i}. [green]OK[/green] {heading}")
            if r["output"]:
                console.print(f"     {r['output'][:200]}")
        else:
            console.print(f"  {i}. [red]FAIL (rc={r['returncode']})[/red] {heading}")
            if r["output"]:
                console.print(f"     {r['output'][:200]}")

    if execute:
        auto_commit(f"ricet runbook: executed {file.name}")


@app.command()
def cite(
    query: str = typer.Argument(help="Literature search query"),
    max_results: int = typer.Option(5, "--max", "-n", help="Max papers to cite"),
):
    """Search literature and add citations to references.bib."""
    from core.paper import search_and_cite

    console.print(f"[bold]Searching: {query}[/bold]")
    results = search_and_cite(query, max_results=max_results)
    if results:
        for r in results:
            console.print(f"  [green]+[/green] {r['key']}: {r.get('title', '')[:80]}")
        auto_commit(f"ricet cite: added {len(results)} references for '{query[:50]}'")
    else:
        console.print("[yellow]No results found (Claude may be unavailable).[/yellow]")


@app.command()
def discover(
    query: str = typer.Argument(help="Research topic to search on PaperBoat"),
    add_bib: bool = typer.Option(
        False, "--cite", help="Auto-add results to references.bib"
    ),
    max_results: int = typer.Option(5, "--max", "-n", help="Max papers to return"),
):
    """Search PaperBoat (paperboatch.com) for recent cross-discipline papers."""
    from core.paper import (
        add_citation,
        generate_citation_key,
        list_citations,
        search_paperboat,
    )

    console.print(f"[bold]Searching PaperBoat for: {query}[/bold]")
    papers = search_paperboat(query)

    if not papers:
        console.print("[yellow]No results found (Claude may be unavailable).[/yellow]")
        return

    for i, p in enumerate(papers[:max_results], 1):
        console.print(f"\n  [bold]{i}. {p.get('title', 'Untitled')}[/bold]")
        console.print(f"     Authors: {p.get('authors', 'Unknown')}")
        console.print(f"     Year: {p.get('year', '?')}")
        console.print(f"     Abstract: {p.get('abstract', '')[:200]}")
        if p.get("url"):
            console.print(f"     URL: {p['url']}")

    if add_bib:
        bib_file = Path("paper/references.bib")
        existing = list_citations(bib_file) if bib_file.exists() else []
        added = 0
        for p in papers[:max_results]:
            key = generate_citation_key(
                p.get("authors", "Unknown"),
                p.get("year", "2024"),
            )
            if key in existing:
                key = f"{key}b"
                if key in existing:
                    continue
            add_citation(
                key=key,
                entry_type="article",
                author=p.get("authors", ""),
                title=p.get("title", ""),
                year=p.get("year", ""),
                url=p.get("url", ""),
                bib_file=bib_file,
            )
            existing.append(key)
            added += 1
            console.print(f"  [green]+[/green] Added to bib: {key}")
        if added:
            auto_commit(
                f"ricet discover: added {added} PaperBoat references for '{query[:50]}'"
            )


@app.command(name="sync-learnings")
def sync_learnings(
    source_project: Path = typer.Argument(
        help="Path to the source project to transfer from"
    ),
):
    """Transfer encyclopedia entries and meta-rules from another project."""
    from core.knowledge import sync_learnings_to_project

    target = Path.cwd()

    if not source_project.exists():
        console.print(f"[red]Source project not found: {source_project}[/red]")
        raise typer.Exit(1)

    src_enc = source_project / "knowledge" / "ENCYCLOPEDIA.md"
    if not src_enc.exists():
        console.print(
            f"[yellow]No ENCYCLOPEDIA.md in source project: {source_project}[/yellow]"
        )

    console.print(f"[bold]Syncing learnings from: {source_project}[/bold]")
    result = sync_learnings_to_project(source_project, target)

    enc_count = result.get("encyclopedia_transferred", 0)
    rules_count = result.get("rules_transferred", 0)

    if enc_count or rules_count:
        console.print(f"  [green]Encyclopedia entries transferred: {enc_count}[/green]")
        console.print(f"  [green]Meta-rules transferred: {rules_count}[/green]")
        auto_commit(
            f"ricet sync-learnings: transferred {enc_count} entries, {rules_count} rules"
        )
    else:
        console.print(
            "[dim]No new entries to transfer (all duplicates or empty source).[/dim]"
        )


@app.command()
def fidelity():
    """Check whether current work aligns with GOAL.md."""
    from core.verification import check_goal_fidelity

    console.print("[bold]Checking goal fidelity...[/bold]")
    result = check_goal_fidelity(Path.cwd())

    if result.get("error"):
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(1)

    score = result.get("score", 0)

    # Color the score
    if score >= 70:
        console.print(f"\n[bold green]Fidelity Score: {score}/100[/bold green]")
    elif score >= 40:
        console.print(f"\n[bold yellow]Fidelity Score: {score}/100[/bold yellow]")
    else:
        console.print(f"\n[bold red]Fidelity Score: {score}/100[/bold red]")

    aligned = result.get("aligned_areas", [])
    if aligned:
        console.print("\n[bold]Aligned areas:[/bold]")
        for area in aligned:
            console.print(f"  [green]+ {area}[/green]")

    drift = result.get("drift_areas", [])
    if drift:
        console.print("\n[bold]Drift areas:[/bold]")
        for area in drift:
            console.print(f"  [red]- {area}[/red]")

    recs = result.get("recommendations", [])
    if recs:
        console.print("\n[bold]Recommendations:[/bold]")
        for i, rec in enumerate(recs, 1):
            console.print(f"  {i}. {rec}")


if __name__ == "__main__":
    app()
