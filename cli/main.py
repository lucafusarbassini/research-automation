#!/usr/bin/env python3
"""ricet CLI - Scientific research automation powered by Claude Code."""

import json
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

import typer
from rich.console import Console

from core.auto_commit import auto_commit
from core.latex_scaffold import scaffold_from_config
from core.onboarding import (
    OnboardingAnswers,
    auto_install_claude_flow,
    check_and_install_packages,
    collect_answers,
    collect_credentials,
    create_github_repo,
    detect_system_for_init,
    ensure_package,
    generate_goal_folders,
    generate_goal_milestones,
    generate_goal_todos,
    infer_packages_from_goal,
    install_inferred_packages,
    load_settings,
    print_folder_map,
    setup_docker_for_overnight,
    setup_workspace,
    validate_goal_content,
    write_env_example,
    write_env_file,
    write_goal_file,
    write_settings,
)

__version__ = "0.3.0"


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
    # Lightweight update check (runs at most once per week)
    try:
        from core.updater import session_start_check
        session_start_check()
    except Exception:
        pass


TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
DEFAULTS_DIR = Path(__file__).parent.parent / "defaults"
CONFIG_DIR = Path.home() / ".ricet"
SETUP_SCRIPT = Path(__file__).parent.parent / "scripts" / "setup_claude_flow.sh"


_TUNNEL_LOG = Path("/tmp/ricet-tunnel.log")


def _launch_tunnel_background(console: Console) -> None:
    """Kill stale tunnels, start server + cloudflared inline, show URL + QR.

    Starts the mobile server (daemon thread) and cloudflared directly — no
    intermediate subprocess.  Cloudflared runs with ``start_new_session=True``
    so it survives after the parent process exits.  A tiny keepalive server is
    also forked so the mobile API stays up.
    """
    import os
    import re
    import sys
    import time

    port = 8777

    # 1. Kill ALL old tunnel/server processes
    subprocess.run(f"fuser -k {port}/tcp", shell=True, capture_output=True)
    subprocess.run(
        "pkill -f 'cloudflared tunnel --url'", shell=True, capture_output=True
    )
    time.sleep(1)

    # 2. Start mobile server directly (daemon thread — stays alive as long as
    #    this process or the forked keepalive lives).
    try:
        from core.mobile import MobileServer

        srv = MobileServer()
        info = srv.serve(host="127.0.0.1", port=port, tls=False)
        console.print(f"  [dim]{info}[/dim]")
    except OSError as exc:
        if "Address already in use" in str(exc):
            subprocess.run(f"fuser -k {port}/tcp", shell=True, capture_output=True)
            time.sleep(0.5)
            try:
                from core.mobile import MobileServer

                srv = MobileServer()
                info = srv.serve(host="127.0.0.1", port=port, tls=False)
                console.print(f"  [dim]{info}[/dim]")
            except Exception as exc2:
                console.print(f"  [red]Server failed: {exc2}[/red]")
                return
        else:
            console.print(f"  [red]Server failed: {exc}[/red]")
            return
    except Exception as exc:
        console.print(f"  [red]Server failed: {exc}[/red]")
        return

    # 3. Start cloudflared directly — read URL from its stderr
    from core.mobile import _ensure_cloudflared

    try:
        cf_bin = _ensure_cloudflared()
    except Exception as exc:
        console.print(f"  [red]cloudflared not available: {exc}[/red]")
        return

    cf_proc = subprocess.Popen(
        [str(cf_bin), "tunnel", "--url", f"http://localhost:{port}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )

    # 4. Parse URL directly from cloudflared stderr (up to 30s)
    import select

    url_re = re.compile(r"(https://[a-z0-9-]+\.trycloudflare\.com)")
    tunnel_url = ""
    deadline = time.monotonic() + 30
    console.print("  [dim]Waiting for tunnel URL...[/dim]")
    collected: list[str] = []
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        ready, _, _ = select.select([cf_proc.stderr], [], [], min(remaining, 1.0))
        if ready:
            line = cf_proc.stderr.readline()
            if not line:
                break
            collected.append(line.strip())
            m = url_re.search(line)
            if m:
                tunnel_url = m.group(1)
                break

    if tunnel_url:
        console.print(f"\n  [bold green]Public URL (open on your phone):[/bold green]")
        console.print(f"  {tunnel_url}")
        try:
            from core.mobile import generate_qr_terminal

            qr = generate_qr_terminal(tunnel_url)
            if qr:
                console.print(f"\n{qr}")
        except Exception:
            pass
        # Detach cloudflared stderr so it doesn't block
        try:
            cf_proc.stderr.close()
        except Exception:
            pass
        console.print(
            f"  [dim]Tunnel PID {cf_proc.pid} | Server on :{port}[/dim]"
        )
        # Fork a keepalive process that holds the server alive
        _fork_server_keepalive(port, cf_proc.pid)
    else:
        console.print("  [red]Could not get tunnel URL after 30s.[/red]")
        for line in collected[-5:]:
            console.print(f"  [dim]{line}[/dim]")
        cf_proc.terminate()
        console.print("  [dim]Run 'ricet mobile tunnel' manually.[/dim]")


def _fork_server_keepalive(port: int, cf_pid: int) -> None:
    """Fork a tiny background process that keeps the mobile server alive.

    The server runs in a daemon thread of the parent — it dies when the parent
    exits.  This fork keeps a minimal Python process alive (with its own server
    instance) so the tunnel has something to connect to.  It also watches for
    cloudflared death and exits if that happens.
    """
    import os
    import sys

    pid = os.fork()
    if pid != 0:
        # Parent: continue normally (will exit after init/start finishes)
        return

    # --- Child process (daemon) ---
    os.setsid()  # new session
    # Close inherited stdio
    devnull = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull, 0)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)
    os.close(devnull)

    try:
        from core.mobile import MobileServer
        import time

        srv = MobileServer()
        srv.serve(host="127.0.0.1", port=port, tls=False)
    except Exception:
        pass  # port may still be held by parent briefly; that's OK

    # Stay alive, watching for cloudflared
    import time
    import signal

    while True:
        try:
            os.kill(cf_pid, 0)  # check if cloudflared is alive
        except OSError:
            break  # cloudflared died, exit
        time.sleep(10)


@app.command()
def init(
    project_name: str,
    path: Path = typer.Option(Path.cwd(), help="Where to create project"),
    skip_repo: bool = typer.Option(False, help="Skip GitHub repo creation"),
    no_env: bool = typer.Option(
        False, "--no-env", help="Skip conda/mamba environment creation"
    ),
    update: bool = typer.Option(
        False, "--update", help="Update an existing project (re-enter credentials, refresh templates)"
    ),
):
    """Initialize a new research project with full onboarding.

    Use --update to refresh an existing project: re-enter credentials,
    update templates and sandbox infrastructure, without recreating the
    project from scratch.
    """
    project_path = path / project_name

    if update:
        if not project_path.exists():
            console.print(f"[red]Error: {project_path} does not exist. Cannot --update.[/red]")
            raise typer.Exit(1)
        _init_update(project_path, project_name, skip_repo=skip_repo)
        return

    if project_path.exists():
        console.print(f"[red]Error: {project_path} already exists[/red]")
        console.print(
            "[dim]To update an existing project, use: "
            f"ricet init {project_name} --update[/dim]"
        )
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

    # --- Step 1b: Auto-install system dependencies ---
    console.print("\n[bold cyan]Step 1b: Checking & installing system dependencies...[/bold cyan]")
    try:
        from core.onboarding import auto_install_system_deps

        dep_results = auto_install_system_deps(
            print_fn=lambda msg: console.print(f"[dim]{msg}[/dim]")
        )
        installed = sum(1 for v in dep_results.values() if v)
        total = len(dep_results)
        console.print(f"  [green]{installed}/{total} system dependencies ready[/green]")
    except Exception as exc:
        console.print(f"  [yellow]System dependency check skipped: {exc}[/yellow]")

    # --- Step 2b: Ensure Claude auth ---
    console.print("\n[bold cyan]Step 2b: Checking Claude authentication...[/bold cyan]")
    try:
        auth_result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if auth_result.returncode == 0:
            console.print("  [green]Claude CLI available[/green]")
            console.print("  [dim]If not yet logged in, run: claude auth login[/dim]")
        else:
            console.print(
                "  [yellow]Claude CLI not responding. Run: claude auth login[/yellow]"
            )
    except FileNotFoundError:
        console.print(
            "  [yellow]Claude CLI not found. Install: https://docs.anthropic.com/en/docs/claude-code[/yellow]"
        )
    except subprocess.TimeoutExpired:
        console.print("  [yellow]Claude CLI timed out[/yellow]")

    # --- Step 2c: Install cloudflared for tunnel access ---
    console.print("\n[bold cyan]Step 2c: Setting up cloudflared...[/bold cyan]")
    try:
        from core.mobile import _ensure_cloudflared

        cf_path = _ensure_cloudflared()
        _cf_ver = subprocess.run(
            [str(cf_path), "--version"],
            capture_output=True, text=True, timeout=10,
        )
        console.print(
            f"  [green]cloudflared ready: {_cf_ver.stdout.strip()}[/green]"
        )
    except Exception as cf_exc:
        console.print(
            f"  [yellow]cloudflared not installed: {cf_exc}[/yellow]"
        )
        console.print(
            "  [dim]Tunnel access will not work. "
            "Install manually: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/[/dim]"
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

    def _cred_prompt(prompt, default=""):
        """Credential prompt that accepts empty Enter as skip."""
        raw = input(f"{prompt}: ")
        return raw if raw else default

    credentials = collect_credentials(
        answers,
        prompt_fn=_cred_prompt,
        print_fn=lambda msg: console.print(f"[dim]{msg}[/dim]"),
    )
    if credentials:
        console.print(f"  [green]{len(credentials)} credential(s) collected[/green]")
        # Offer to save globally
        try:
            save_resp = _prompt("Save credentials globally for future projects? (yes/no)", "yes")
            if save_resp.lower() in ("yes", "y", "true", "1"):
                from core.credential_store import save_global_credentials

                save_global_credentials(credentials)
                console.print(
                    "  [green]Credentials saved to ~/.ricet/credentials.env[/green]"
                )
        except (EOFError, KeyboardInterrupt):
            pass
    else:
        console.print(
            "  [dim]No credentials entered (can be added later in secrets/.env)[/dim]"
        )

    # --- Step 3c: Detailed project description (BEFORE project creation) ---
    # The goal drives environment packages, folder structure, TODOs, and LaTeX.
    console.print("\n[bold cyan]Step 3c: Project description[/bold cyan]")
    console.print(
        "  [dim]Describe your project in detail. This drives package selection,\n"
        "  folder structure, agent behavior, and paper scaffold. Be thorough\n"
        "  (research question, methodology, expected outcomes, constraints).\n"
        "  Type your description, then press Enter twice (empty line) to finish.[/dim]"
    )
    console.print()
    goal_lines: list[str] = []
    try:
        while True:
            line = input("  > ")
            if line == "" and goal_lines and goal_lines[-1] == "":
                goal_lines.pop()  # remove trailing blank
                break
            goal_lines.append(line)
    except EOFError:
        pass  # piped input ends here

    user_goal = "\n".join(goal_lines).strip()
    if not user_goal:
        user_goal = f"Research project: {project_name}"
        console.print(f"  [dim]Using default: {user_goal}[/dim]")
    else:
        console.print(
            f"  [green]Goal captured ({len(user_goal)} chars, "
            f"{len(user_goal.split())} words)[/green]"
        )

    # Store the detailed goal in answers so downstream steps use it
    answers.goal = user_goal

    # --- Step 4: Create project structure ---
    console.print("\n[bold cyan]Step 4: Creating project...[/bold cyan]")

    # Copy templates
    if TEMPLATE_DIR.exists():
        shutil.copytree(TEMPLATE_DIR, project_path)
    else:
        project_path.mkdir(parents=True)

    # Deploy research skills (slash commands)
    skills_src = TEMPLATE_DIR / ".claude" / "skills"
    skills_dst = project_path / ".claude" / "skills"
    if skills_src.exists():
        skills_dst.mkdir(parents=True, exist_ok=True)
        for f in skills_src.iterdir():
            if f.is_file():
                shutil.copy2(f, skills_dst / f.name)

    # Deploy behavioral rules from defaults/ into project knowledge/
    _defaults_to_deploy = ["LEGISLATION.md", "PHILOSOPHY.md"]
    knowledge_dst = project_path / "knowledge"
    knowledge_dst.mkdir(parents=True, exist_ok=True)
    for fname in _defaults_to_deploy:
        src = DEFAULTS_DIR / fname
        dst = knowledge_dst / fname
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)

    # Deploy knowledge templates (RULES, ENCYCLOPEDIA, DECISION_LOG, CONSTRAINTS)
    knowledge_tpl_src = TEMPLATE_DIR / "knowledge"
    if knowledge_tpl_src.exists():
        for f in knowledge_tpl_src.iterdir():
            if f.is_file():
                dst = knowledge_dst / f.name
                if not dst.exists():
                    shutil.copy2(f, dst)

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
        install_packages_in_env,
        populate_encyclopedia_env,
        sanitize_env_name,
        write_environment_yml,
    )

    env_info: dict = {}
    if no_env:
        console.print("  [dim]Skipping environment creation (--no-env)[/dim]")
    else:
        env_info = create_project_env(project_name, project_path)
        console.print(
            f"  [green]Python environment: {env_info['type']} ({env_info['name']})[/green]"
        )

        # Infer packages from the project goal and install into the env
        _goal_for_pkgs = answers.goal if answers.goal else ""
        _inferred_pkgs: list[str] = []
        if _goal_for_pkgs and system_info["conda"]:
            _inferred_pkgs = infer_packages_from_goal(_goal_for_pkgs)
            if _inferred_pkgs:
                console.print(
                    f"  [cyan]Inferred packages: {', '.join(_inferred_pkgs)}[/cyan]"
                )
                _installed, _pkg_failed = install_packages_in_env(
                    env_info["name"], _inferred_pkgs
                )
                if _installed:
                    console.print(
                        f"  [green]Installed into env: {', '.join(_installed)}[/green]"
                    )
                if _pkg_failed:
                    console.print(
                        f"  [yellow]Failed to install: {', '.join(_pkg_failed)}[/yellow]"
                    )

        # Write environment.yml
        _env_name = sanitize_env_name(project_name)
        write_environment_yml(
            project_path,
            _env_name,
            packages=_inferred_pkgs if _inferred_pkgs else None,
        )
        console.print("  [green]Wrote environment.yml[/green]")

        # Print activation command
        if env_info.get("type") in ("conda", "mamba"):
            console.print(
                f"  [bold]Activate with:[/bold] conda activate {env_info['name']}"
            )

    # Store env info in settings
    settings_path = project_path / "config" / "settings.yml"
    if settings_path.exists():
        import yaml

        _settings = yaml.safe_load(settings_path.read_text()) or {}
        if env_info:
            _settings["environment"] = env_info
        settings_path.write_text(
            yaml.dump(_settings, default_flow_style=False, sort_keys=False)
        )

    # Populate encyclopedia with environment details
    sys_info_obj = discover_system()
    if env_info:
        populate_encyclopedia_env(project_path, env_info, sys_info_obj)

    # Create state directories
    (project_path / "state" / "sessions").mkdir(parents=True, exist_ok=True)

    # Write GOAL.md with user's detailed description BEFORE generating TODOs/folders
    goal_file = project_path / "knowledge" / "GOAL.md"
    if goal_file.exists():
        goal_content = goal_file.read_text()
        for placeholder in (
            "<!-- User provides during init -->",
            "<!-- WRITE YOUR PROJECT DESCRIPTION HERE -->",
        ):
            if placeholder in goal_content:
                goal_content = goal_content.replace(placeholder, user_goal)
        goal_file.write_text(goal_content)
    else:
        goal_file.parent.mkdir(parents=True, exist_ok=True)
        goal_file.write_text(f"# Project Goal\n\n## Description\n\n{user_goal}\n")

    # Generate goal-aware TODO items and project-specific folders
    _goal_text = user_goal

    # Goal-aware TODO: ask Claude for specific actionable items
    todo_items = generate_goal_todos(_goal_text)
    todo_content = "# TODO\n\n" + todo_items
    (project_path / "state" / "TODO.md").write_text(todo_content)

    # Goal-aware folders: ask Claude for project-specific directories
    extra_folders = generate_goal_folders(_goal_text)
    for folder_name in extra_folders:
        folder_path = project_path / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)
        gitkeep = folder_path / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.write_text("")
    if extra_folders:
        console.print(
            f"  [green]Created {len(extra_folders)} goal-specific "
            f"folder(s): {', '.join(extra_folders)}[/green]"
        )

    (project_path / "state" / "PROGRESS.md").write_text("# Progress\n\n")

    # --- Adaptive LaTeX scaffold generation ---
    console.print("\n[bold cyan]Generating adaptive LaTeX scaffold...[/bold cyan]")
    latex_files = scaffold_from_config(
        project_path,
        paper_type=answers.paper_type,
        project_type=answers.project_type,
        goal_text=_goal_text,
        overwrite=True,  # Replace static template copies with adaptive versions
    )
    if latex_files:
        from core.latex_scaffold import detect_domain

        _domain = detect_domain(_goal_text, answers.project_type)
        console.print(
            f"  [green]Paper type: {answers.paper_type}, " f"domain: {_domain}[/green]"
        )
        console.print(
            f"  [green]Generated {len(latex_files)} LaTeX file(s): "
            f"{', '.join(latex_files.keys())}[/green]"
        )
    else:
        console.print("  [dim]LaTeX scaffold: paper/ already populated[/dim]")

    # (GOAL.md already written above, before TODO/folder generation)

    # --- Step 5: GitHub repo creation ---
    repo_url = ""
    _gh_pat = credentials.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")
    if not skip_repo:
        console.print("\n[bold cyan]Step 5: GitHub repository[/bold cyan]")
        create_repo = _prompt("Create a GitHub repo for this project? (yes/no)", "yes")
        if create_repo.lower() in ("yes", "y"):
            private = _prompt("Private repo? (yes/no)", "yes")
            is_private = private.lower() in ("yes", "y")
            console.print(f"  Creating {'private' if is_private else 'public'} repo...")
            repo_url = create_github_repo(
                project_name, private=is_private, github_token=_gh_pat
            )
            if repo_url:
                answers.github_repo = repo_url
                console.print(f"  [green]Repo created: {repo_url}[/green]")
                # Update settings with repo URL
                write_settings(project_path, answers)
                # Set repo description and topics from GOAL.md
                _configure_github_repo_from_goal(project_path, project_name, repo_url)
            else:
                console.print(
                    "  [yellow]Could not create repo. You can create it later:[/yellow]"
                )
                console.print("  [dim]  1. gh auth login[/dim]")
                console.print(f"  [dim]  2. gh repo create {project_name} --private[/dim]")
                console.print(
                    "  [dim]  (The project will continue without a remote repo)[/dim]"
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

    # --- Register in global project registry ---
    try:
        from core.multi_project import ProjectRegistry

        registry = ProjectRegistry()
        registry.register_project(project_name, str(project_path.resolve()))
        console.print("  [green]Registered in global project registry[/green]")
    except Exception as exc:
        logger.debug("Could not register project: %s", exc)

    # --- Step 7: Docker + sandbox setup for overnight mode ---
    console.print(
        "\n[bold cyan]Step 7: Setting up Docker sandbox for overnight mode...[/bold cyan]"
    )
    docker_result = setup_docker_for_overnight(
        project_path,
        print_fn=lambda msg: console.print(f"[dim]{msg}[/dim]"),
    )

    # Deploy sandbox infrastructure regardless of Docker availability
    # (the shell scripts and Dockerfiles are always useful to have)
    from core.sandbox import setup_sandbox

    sandbox_ok = setup_sandbox(
        project_path,
        print_fn=lambda msg: console.print(f"  [dim]{msg}[/dim]"),
    )
    if sandbox_ok:
        console.print(
            "  [green]Sandbox infrastructure deployed (sandbox/)[/green]"
        )

    if docker_result.get("test_passed"):
        console.print(
            "  [green]Docker is ready - overnight mode fully configured[/green]"
        )
    elif docker_result.get("skipped"):
        console.print(
            "  [dim]Docker not available (not required for project init).[/dim]"
        )
        console.print(
            "  [dim]You'll need Docker when running: ricet overnight[/dim]"
        )
    else:
        console.print(
            "  [yellow]Docker setup incomplete. "
            "You can retry later when needed for overnight mode.[/yellow]"
        )

    # --- Step 8: Register MCP servers in .claude/settings.json ---
    console.print(
        "\n[bold cyan]Step 8: Registering MCP servers...[/bold cyan]"
    )
    try:
        from core.mcps import install_priority_mcps

        mcp_results = install_priority_mcps(project_path=project_path)
        mcp_ok = sum(1 for v in mcp_results.values() if v)
        mcp_total = len(mcp_results)
        if mcp_total > 0:
            console.print(
                f"  [green]{mcp_ok}/{mcp_total} MCP servers registered[/green]"
            )
            for name, ok in mcp_results.items():
                status = "[green]OK[/green]" if ok else "[yellow]SKIP[/yellow]"
                console.print(f"    {status} {name}")
        else:
            console.print("  [dim]No priority MCPs configured[/dim]")
    except Exception as exc:
        console.print(f"  [yellow]MCP installation skipped: {exc}[/yellow]")

    # --- Step 9: Mobile access setup (named tunnel or quick tunnel) ---
    console.print("\n[bold cyan]Step 9: Setting up mobile access...[/bold cyan]")
    if answers.tunnel_domain:
        console.print(f"  Setting up named Cloudflare tunnel → {answers.tunnel_domain}")
        from core.onboarding import setup_named_tunnel, write_mobile_env
        tunnel_result = setup_named_tunnel(
            answers.tunnel_domain,
            print_fn=lambda s: console.print(f"  {s}"),
        )
        if tunnel_result["ok"]:
            console.print(f"  [green]Permanent URL: {tunnel_result['url']}[/green]")
            write_mobile_env(project_path, answers)
            console.print(f"  Run: [bold]ricet mobile tunnel[/bold] to activate")
        else:
            console.print(f"  [yellow]Named tunnel setup failed: {tunnel_result['error']}[/yellow]")
            console.print("  Falling back to quick tunnel mode.")
            _launch_tunnel_background(console)
    else:
        _launch_tunnel_background(console)
    if answers.screen_session:
        from core.onboarding import write_mobile_env
        write_mobile_env(project_path, answers)

    # --- Step 10: Install gstack startup workflow skills ---
    console.print("\n[bold cyan]Step 10: Installing gstack startup skills...[/bold cyan]")
    if _GSTACK_DIR.exists():
        _gv = (_GSTACK_DIR / "VERSION").read_text().strip() if (_GSTACK_DIR / "VERSION").exists() else "?"
        console.print(f"  [green]gstack v{_gv} already installed[/green]")
    else:
        import shutil as _sh_gstack
        import subprocess as _sp_gstack
        _has_bun_init = _sh_gstack.which("bun") is not None
        _skip = not _has_bun_init
        console.print(f"  Cloning gstack{'  (--skip-browser: bun not found)' if _skip else ''}...")
        _gstack_ok = _sp_gstack.run(
            ["git", "clone", _GSTACK_REPO, str(_GSTACK_DIR)],
            capture_output=True,
        ).returncode == 0
        if _gstack_ok:
            _skills_dir_init = Path.home() / ".claude" / "skills"
            _skills_dir_init.mkdir(parents=True, exist_ok=True)
            if not _skip:
                _sp_gstack.run(["bash", "./setup"], cwd=str(_GSTACK_DIR), capture_output=True)
            else:
                # Symlink non-browser skills manually
                for _sk in _GSTACK_ALL_SKILLS:
                    if _sk in _GSTACK_BROWSER_SKILLS:
                        continue
                    _sk_dir = _GSTACK_DIR / _sk
                    if not _sk_dir.is_dir():
                        continue
                    _link = _skills_dir_init / _sk
                    if not _link.exists() and not _link.is_symlink():
                        _link.symlink_to(f"gstack/{_sk}")
            _gv = (_GSTACK_DIR / "VERSION").read_text().strip() if (_GSTACK_DIR / "VERSION").exists() else "?"
            _installed = [s for s in _GSTACK_ALL_SKILLS if (_skills_dir_init / s).exists()]
            console.print(f"  [green]gstack v{_gv} installed: {', '.join('/' + s for s in _installed)}[/green]")
        else:
            console.print("  [yellow]gstack clone failed (network issue?). Run later: ricet gstack install[/yellow]")

    # --- Done ---
    console.print(f"\n[bold green]Project ready![/bold green]")
    console.print("")

    # Print folder map
    for line in print_folder_map(project_path):
        console.print(f"  {line}")
    console.print("")

    console.print("[bold]Next steps:[/bold]")
    console.print(f"  cd {project_name}")
    console.print("  ricet start          # Launch interactive research session")
    console.print("  ricet overnight      # Run autonomous overnight mode (Docker)")
    console.print("  ricet status         # Check project status")
    console.print("  ricet --help         # See all commands")
    if docker_result.get("test_passed"):
        console.print(
            "\n  [green]Docker is ready - overnight runs will be safely "
            "isolated in a container.[/green]"
        )
    else:
        console.print(
            "\n  [yellow]Install Docker to enable safe overnight mode: "
            "https://docs.docker.com/get-docker/[/yellow]"
        )

    # --- Background & remote access guide ---
    console.print("")
    console.print("[bold cyan]Running ricet in the background[/bold cyan]")
    console.print("")
    console.print("  To run overnight sessions that survive disconnects:")
    console.print("")
    console.print(f"    1. Start a screen session:    [bold]screen -S {project_name}[/bold]")
    console.print(f"    2. Enter your project:        [bold]cd {project_name}[/bold]")
    console.print("    3. Launch Claude:              [bold]claude[/bold]")
    console.print("    4. Ask Claude to run overnight:")
    console.print("       [dim]> run ricet overnight --iterations 30[/dim]")
    console.print("    5. Detach from screen:         [bold]Ctrl+A, then D[/bold]")
    console.print("")
    console.print("  To reattach later:")
    console.print(f"    [bold]screen -r {project_name}[/bold]")
    console.print("")
    console.print(
        "  [bold green]Control Claude from your phone:[/bold green] After launching\n"
        "  a Claude session in screen, run [bold]ricet mobile[/bold] in another terminal.\n"
        "  It creates a Tailscale tunnel with a QR code you can scan."
    )
    console.print("")
    console.print(
        "  [bold yellow]Reminder:[/bold yellow] Install [bold]Tailscale[/bold] on your phone\n"
        "  (iOS: App Store, Android: Play Store) and sign in with the same\n"
        "  account as this machine. Keep the app toggled ON when using mobile access."
    )

    # Record installed version for future migration tracking
    try:
        from core.updater import record_version
        record_version()
    except Exception:
        pass


def _init_update(
    project_path: Path,
    project_name: str,
    *,
    skip_repo: bool = False,
) -> None:
    """Update an existing ricet project without recreating from scratch.

    Re-enters credentials, refreshes templates and sandbox infrastructure,
    and optionally reconfigures the GitHub repo.
    """
    console.print(f"[bold]Updating project: {project_name}[/bold]")
    console.print(f"[dim]Path: {project_path}[/dim]\n")

    # --- Load existing settings ---
    settings_file = project_path / "config" / "settings.yml"
    existing_settings = {}
    if settings_file.exists():
        import yaml

        existing_settings = yaml.safe_load(settings_file.read_text()) or {}
        console.print(f"  [green]Loaded existing settings[/green]")

    # --- Re-collect credentials ---
    console.print("\n[bold cyan]Credentials update[/bold cyan]")
    console.print("  [dim]Press Enter to keep existing values, or type new ones.[/dim]")

    # Load existing credentials
    env_file = project_path / "secrets" / ".env"
    existing_creds: dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                existing_creds[key.strip()] = val.strip()

    # Show which credentials exist and let user update
    updated_creds: dict[str, str] = dict(existing_creds)
    cred_keys = [
        ("ANTHROPIC_API_KEY", "Anthropic API key"),
        ("GITHUB_PERSONAL_ACCESS_TOKEN", "GitHub Personal Access Token"),
        ("OPENAI_API_KEY", "OpenAI API key (optional)"),
        ("HUGGINGFACE_TOKEN", "HuggingFace token (optional)"),
        ("WANDB_API_KEY", "Weights & Biases key (optional)"),
    ]

    for key, label in cred_keys:
        existing = existing_creds.get(key, "")
        if existing:
            masked = existing[:4] + "..." + existing[-4:] if len(existing) > 8 else "****"
            new_val = input(f"  {label} [{masked}]: ")
        else:
            new_val = input(f"  {label} [not set]: ")

        if new_val.strip():
            updated_creds[key] = new_val.strip()

    # Write updated credentials
    if updated_creds:
        (project_path / "secrets").mkdir(exist_ok=True)
        write_env_file(project_path, updated_creds)
        n_updated = sum(
            1 for k in updated_creds
            if updated_creds[k] != existing_creds.get(k, "")
        )
        console.print(f"  [green]{n_updated} credential(s) updated[/green]")

    # --- Refresh sandbox infrastructure ---
    console.print("\n[bold cyan]Refreshing sandbox infrastructure...[/bold cyan]")
    from core.sandbox import setup_sandbox

    sandbox_ok = setup_sandbox(
        project_path,
        print_fn=lambda msg: console.print(f"  [dim]{msg}[/dim]"),
    )
    if sandbox_ok:
        console.print("  [green]Sandbox infrastructure updated[/green]")

    # --- Refresh research skills ---
    skills_src = TEMPLATE_DIR / ".claude" / "skills"
    skills_dst = project_path / ".claude" / "skills"
    if skills_src.exists():
        skills_dst.mkdir(parents=True, exist_ok=True)
        updated_skills = 0
        for f in skills_src.iterdir():
            if f.is_file():
                dst_file = skills_dst / f.name
                if not dst_file.exists() or f.stat().st_mtime > dst_file.stat().st_mtime:
                    shutil.copy2(f, dst_file)
                    updated_skills += 1
        console.print(f"  [green]{updated_skills} skill template(s) refreshed[/green]")

    # --- Refresh behavioral rules from defaults/ ---
    _defaults_to_deploy = ["LEGISLATION.md", "PHILOSOPHY.md"]
    knowledge_dst = project_path / "knowledge"
    knowledge_dst.mkdir(parents=True, exist_ok=True)
    updated_defaults = 0
    for fname in _defaults_to_deploy:
        src = DEFAULTS_DIR / fname
        dst = knowledge_dst / fname
        if src.exists():
            if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
                shutil.copy2(src, dst)
                updated_defaults += 1
    if updated_defaults:
        console.print(f"  [green]{updated_defaults} behavioral rule file(s) refreshed[/green]")

    # --- Ensure state files exist ---
    state_dir = project_path / "state"
    state_dir.mkdir(exist_ok=True)
    state_templates = Path(__file__).parent.parent / "templates" / "state"
    for state_file in ("SYSTEM.md",):
        dst = state_dir / state_file
        src = state_templates / state_file
        if not dst.exists() and src.exists():
            shutil.copy2(src, dst)
            console.print(f"  [dim]Created state/{state_file}[/dim]")

    # --- Ensure required directories ---
    for dirname in ("experiments", "reports/figures", "backups"):
        (project_path / dirname).mkdir(parents=True, exist_ok=True)

    # --- GitHub repo (optional) ---
    if not skip_repo:
        console.print("\n[bold cyan]GitHub configuration[/bold cyan]")
        existing_repo = existing_settings.get("github_repo", "")
        if existing_repo:
            console.print(f"  [dim]Current repo: {existing_repo}[/dim]")
        reconfigure = input("  Reconfigure GitHub repo? (y/N): ").strip().lower()
        if reconfigure in ("y", "yes"):
            _gh_pat = updated_creds.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")
            repo_url = create_github_repo(
                project_name, private=True, github_token=_gh_pat
            )
            if repo_url:
                console.print(f"  [green]Repo: {repo_url}[/green]")

    # --- Docker check ---
    console.print("\n[bold cyan]Docker check...[/bold cyan]")
    docker_result = setup_docker_for_overnight(
        project_path,
        print_fn=lambda msg: console.print(f"  [dim]{msg}[/dim]"),
    )
    if docker_result.get("test_passed"):
        console.print("  [green]Docker ready[/green]")
    elif docker_result.get("skipped"):
        console.print("  [dim]Docker not available (optional)[/dim]")
    else:
        console.print("  [yellow]Docker setup incomplete[/yellow]")

    # --- Start mobile access with cloudflared tunnel ---
    console.print("\n[bold cyan]Starting mobile access...[/bold cyan]")
    _launch_tunnel_background(console)

    # --- Done ---
    console.print(f"\n[bold green]Project updated![/bold green]")
    console.print(f"  cd {project_path}")
    console.print("  ricet start          # Resume interactive session")
    console.print("  ricet overnight      # Launch overnight mode")


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

    from core.session import create_session, update_session

    session = create_session(session_name)
    session.uuid = session_uuid
    update_session(session)

    # Load project settings
    settings = load_settings(Path.cwd())

    # Load and merge global credentials into environment
    try:
        from core.credential_store import load_global_credentials, merge_credentials

        global_creds = load_global_credentials()
        if global_creds:
            # Load project-level secrets
            env_file = Path.cwd() / "secrets" / ".env"
            project_creds: dict[str, str] = {}
            if env_file.exists():
                for line in env_file.read_text().splitlines():
                    line = line.strip()
                    if line and "=" in line and not line.startswith("#"):
                        k, _, v = line.partition("=")
                        if k.strip() and v.strip():
                            project_creds[k.strip()] = v.strip()
            merged = merge_credentials(global_creds, project_creds)
            for k, v in merged.items():
                os.environ.setdefault(k, v)
            console.print(
                f"[dim]Loaded {len(merged)} credential(s) (global + project)[/dim]"
            )
    except Exception:
        pass

    # Always start mobile server + tunnel as background process
    console.print("\n[bold cyan]Starting mobile access...[/bold cyan]")
    _launch_tunnel_background(console)

    # Show dashboard URL
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

    # --- End-of-session review report ---
    from core.session import close_session, generate_review_report

    console.print("\n[bold]Generating session review report...[/bold]")
    try:
        report_path = generate_review_report(session)
        console.print(f"[green]Review report saved: {report_path}[/green]")
    except Exception as exc:
        console.print(f"[yellow]Could not generate review report: {exc}[/yellow]")

    close_session(session)
    auto_commit(f"ricet start: end session {session_name}")


def _derive_project_name(project_path: Path) -> str:
    """Derive a project name from GOAL.md header or directory name."""
    import re
    goal_file = project_path / "knowledge" / "GOAL.md"
    if goal_file.exists():
        for line in goal_file.read_text().splitlines()[:5]:
            line = line.strip()
            if line.startswith("#"):
                name = re.sub(r"[^a-zA-Z0-9_-]", "-", line.lstrip("# ").strip())
                name = re.sub(r"-+", "-", name).strip("-")[:40]
                if name:
                    return name.lower()
    return project_path.name.lower()


def _project_port(project_name: str, base_port: int = 8777) -> int:
    """Derive a unique port from project name (8777-8877 range)."""
    h = sum(ord(c) for c in project_name)
    return base_port + (h % 100)


@app.command()
def up(
    screen_name: str = typer.Option("", "--screen", "-s", help="Screen session name (default: project name)"),
    port: int = typer.Option(0, "--port", "-p", help="Mobile server port (default: auto from project name)"),
    no_docker: bool = typer.Option(
        False,
        "--no-docker",
        help=(
            "Skip Docker sandbox. Claude will run directly on the host with "
            "--dangerously-skip-permissions. Use only if Docker is unavailable."
        ),
    ),
    no_mobile: bool = typer.Option(False, "--no-mobile", help="Skip mobile server + Tailscale"),
    no_remote: bool = typer.Option(False, "--no-remote", help="Skip /remote-control auto-injection"),
    timeout_hours: int = typer.Option(24, "--timeout", "-t", help="Sandbox watchdog timeout (hours)"),
):
    """Launch a persistent Claude session with sandbox, screen, and all input channels.

    Sets up:
    1. Docker sandbox with --dangerouslySkipPermissions (safe isolation)
    2. GNU Screen session (survives disconnects)
    3. Mobile dashboard + Tailscale (voice + text from phone)
    4. Claude /remote-control (QR code for Claude app on phone)

    Three ways to interact with the running Claude:
    - CLI:       screen -r <screen-name>
    - Phone app: scan the /remote-control QR code
    - Dashboard: open the Tailscale URL in phone browser (voice + text)

    Multiple projects can run simultaneously — each gets its own screen,
    container, and port derived from the project name.
    """
    import os
    import signal
    import sys
    import time

    project_path = Path.cwd()

    # --- 0. Project identity ---
    project_name = _derive_project_name(project_path)
    if not screen_name:
        screen_name = project_name
    if port == 0:
        port = _project_port(project_name)
    container_name = f"ricet-{project_name}"

    console.print(f"[bold]Project:[/bold] {project_name}")
    console.print(f"[bold]Screen:[/bold]  {screen_name}  |  [bold]Port:[/bold] {port}  |  [bold]Container:[/bold] {container_name}")

    # Register project in global registry
    try:
        from core.multi_project import register_project as _reg_proj
        _reg_proj(project_name, project_path)
    except Exception as exc:
        console.print(f"[dim]Could not register project: {exc}[/dim]")

    # --- 1. Docker sandbox setup ---
    if not no_docker:
        from core.devops import ensure_docker_ready
        from core.sandbox import (
            _set_env_var,
            get_sandbox_dir,
            is_sandbox_running,
            sandbox_exists,
            setup_sandbox,
            start_sandbox,
        )

        docker_status = ensure_docker_ready()
        _docker_usable = (
            docker_status["docker_installed"]
            and docker_status["daemon_running"]
        )

        # Try sg docker if needed (same logic as overnight)
        if _docker_usable:
            try:
                subprocess.run(
                    ["docker", "info"], capture_output=True, text=True, timeout=10
                ).check_returncode()
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                try:
                    subprocess.run(
                        ["sg", "docker", "-c", "docker info"],
                        capture_output=True, text=True, timeout=10,
                    ).check_returncode()
                    # Re-exec under docker group
                    console.print("[dim]Re-executing under docker group...[/dim]")
                    os.execvp("sg", ["sg", "docker", "-c", " ".join(sys.argv)])
                except Exception:
                    _docker_usable = False

        if not _docker_usable:
            if not docker_status["docker_installed"]:
                console.print(
                    "[red]Docker is not installed.[/red]\n"
                    "Install: https://docs.docker.com/get-docker/\n"
                    "Or use --no-docker (not recommended)."
                )
            elif not docker_status["daemon_running"]:
                console.print(
                    "[red]Docker daemon is not running.[/red]\n"
                    "Start: [bold]sudo systemctl start docker[/bold]\n"
                    "Or use --no-docker."
                )
            else:
                console.print(
                    "[red]Cannot access Docker.[/red]\n"
                    "Fix: [bold]sudo usermod -aG docker $USER[/bold] then re-login.\n"
                    "Or use --no-docker."
                )
            raise typer.Exit(1)

        # Set up sandbox infrastructure (always refresh critical files)
        if not sandbox_exists(project_path):
            console.print("[bold cyan]Setting up sandbox infrastructure...[/bold cyan]")
            if not setup_sandbox(project_path, print_fn=lambda m: console.print(f"  {m}")):
                console.print("[red]Failed to set up sandbox.[/red]")
                raise typer.Exit(1)
        else:
            # Refresh entrypoint/compose from templates (may have been updated)
            import shutil as _shutil
            _tmpl = Path(__file__).parent.parent / "templates" / "sandbox"
            _sdir = get_sandbox_dir(project_path)
            for _f in ("sandbox-entrypoint.sh", "docker-compose.sandbox.yml"):
                _src = _tmpl / _f
                if _src.exists():
                    _shutil.copy2(_src, _sdir / _f)
            # Ensure WORKSPACE_PATH is set for bind mount
            workspace_dir = project_path / "sandbox" / "workspace"
            workspace_dir.mkdir(parents=True, exist_ok=True)
            _set_env_var(_sdir / ".env", "WORKSPACE_PATH", str(workspace_dir.resolve()))

        # Set project-specific container name and host UID/GID in sandbox .env
        sandbox_env = get_sandbox_dir(project_path) / ".env"
        _set_env_var(sandbox_env, "CONTAINER_NAME", container_name)
        _set_env_var(sandbox_env, "HOST_UID", str(os.getuid()))
        _set_env_var(sandbox_env, "HOST_GID", str(os.getgid()))
        # Auto-detect system resources for container limits
        import multiprocessing
        _ncpu = multiprocessing.cpu_count()
        _set_env_var(sandbox_env, "SANDBOX_CPUS", str(_ncpu))
        try:
            _mem_gb = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // (1024 ** 3)
            _set_env_var(sandbox_env, "SANDBOX_MEMORY", f"{max(_mem_gb - 2, 2)}G")
        except Exception:
            _set_env_var(sandbox_env, "SANDBOX_MEMORY", "8G")

        # Start container
        if not is_sandbox_running(project_path):
            console.print("[bold cyan]Starting sandbox container...[/bold cyan]")
            if not start_sandbox(
                project_path,
                timeout_hours=timeout_hours,
                print_fn=lambda m: console.print(f"  {m}"),
            ):
                console.print("[red]Failed to start sandbox.[/red]")
                raise typer.Exit(1)
        else:
            console.print("[dim]Sandbox container already running.[/dim]")

        # Wait for container to be fully ready (entrypoint copies creds, etc.)
        console.print("[dim]Waiting for container to be ready...[/dim]")
        for _wait_i in range(15):
            _ready = subprocess.run(
                ["docker", "exec", container_name, "test", "-f", "/home/agent/.claude/.credentials.json"],
                capture_output=True,
            ).returncode == 0
            if _ready:
                break
            time.sleep(1)

        # Detect user-switch tool inside container (gosu on Debian, su-exec on Alpine)
        _has_gosu = subprocess.run(
            ["docker", "exec", container_name, "which", "gosu"],
            capture_output=True,
        ).returncode == 0
        _run_as = "gosu agent" if _has_gosu else "su-exec agent"

        # Verify Claude CLI works inside the container
        console.print("[dim]Verifying Claude auth inside sandbox...[/dim]")
        _auth_ok = False
        _auth_check = subprocess.run(
            ["docker", "exec", container_name, "bash", "-c",
             f"{_run_as} claude --version"],
            capture_output=True, text=True, timeout=15,
        )
        if _auth_check.returncode != 0:
            console.print("[yellow]Claude CLI check failed inside container.[/yellow]")
            console.print(f"  [bold]Run this to login, then ricet up again:[/bold]")
            console.print(f"  docker exec -it {container_name} {_run_as} claude auth login")
            console.print("")
            console.print("[dim]Starting screen anyway — you can login from inside.[/dim]")
        else:
            _auth_ok = True
            console.print(f"  [green]Claude CLI OK: {_auth_check.stdout.strip()}[/green]")

        # The claude command to run inside the container
        # Use --continue to resume the most recent session on restart
        claude_cmd = (
            f"docker exec -it {container_name} {_run_as} "
            f"claude --dangerously-skip-permissions --model opus --continue"
        )
    else:
        console.print(
            "[yellow]Running WITHOUT Docker sandbox. "
            "Claude will have full host access.[/yellow]"
        )
        claude_cmd = "claude --dangerously-skip-permissions --model opus --continue"

    # --- 2. Screen session ---
    existing = subprocess.run(
        ["screen", "-ls"], capture_output=True, text=True
    )
    import re
    if re.search(rf'\d+\.{re.escape(screen_name)}\s', existing.stdout):
        console.print(f"[yellow]Screen session '{screen_name}' already exists.[/yellow]")
        console.print(f"  Attach: [bold]screen -r {screen_name}[/bold]")
        console.print(f"  Kill first: [bold]screen -S {screen_name} -X quit[/bold]")
        # Start mobile server for existing session if needed
        if not no_mobile:
            console.print(f"\n[bold cyan]Starting mobile server for existing session...[/bold cyan]")
            _start_mobile_for_up(console, screen_name, port)
        return

    console.print(f"[bold cyan]Creating screen session '{screen_name}'...[/bold cyan]")

    # Create detached screen running Claude (loop keeps screen alive on exit/crash)
    if not no_docker:
        # For docker: check container is running before exec, restart if needed
        _inner_script = (
            f'while true; do '
            f'if ! docker inspect --format="{{{{.State.Running}}}}" {container_name} 2>/dev/null | grep -q true; then '
            f'echo "Container not running. Restarting..."; '
            f'docker start {container_name} 2>/dev/null || true; sleep 5; continue; fi; '
            f'{claude_cmd}; '
            f'echo ""; echo "=== Claude exited. Restarting in 5s (Ctrl+C to stop) ==="; '
            f'sleep 5; done'
        )
    else:
        _inner_script = (
            f'while true; do {claude_cmd}; '
            f'echo ""; echo "=== Claude exited. Restarting in 5s (Ctrl+C to stop) ==="; '
            f'sleep 5; done'
        )
    screen_cmd = [
        "screen", "-dmS", screen_name,
        "bash", "-c", _inner_script,
    ]
    result = subprocess.run(screen_cmd)
    if result.returncode != 0:
        console.print("[red]Failed to create screen session.[/red]")
        raise typer.Exit(1)

    # Verify screen started
    time.sleep(2)
    verify = subprocess.run(["screen", "-ls"], capture_output=True, text=True)
    if screen_name not in verify.stdout:
        console.print("[red]Screen session did not start.[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Screen session '{screen_name}' started with Claude.[/green]")

    # --- 3. Mobile server + Tailscale ---
    if not no_mobile:
        _start_mobile_for_up(console, screen_name, port)

    # --- 4. Remote control ---
    # Track whether auth was OK (set by docker path above; always True for no-docker)
    _auth_ok = locals().get("_auth_ok", True)
    if not no_remote and _auth_ok:
        console.print("[dim]Waiting for Claude to initialize before injecting /remote-control (30s)...[/dim]")
        time.sleep(30)
        rc_result = subprocess.run(
            ["screen", "-S", screen_name, "-X", "stuff", "/remote-control\r"],
            capture_output=True,
        )
        if rc_result.returncode == 0:
            console.print("[green]/remote-control injected — attach to screen to see QR code.[/green]")
        else:
            console.print("[yellow]Could not inject /remote-control. Do it manually after attaching.[/yellow]")
    elif not _auth_ok:
        console.print("[yellow]Skipping /remote-control injection — Claude auth not verified.[/yellow]")
        console.print("  After logging in, type /remote-control manually in the Claude session.")

    # --- 5. VS Code hint ---
    workspace_dir = project_path / "sandbox" / "workspace"
    if workspace_dir.exists() and not no_docker:
        console.print(f"\n[bold]VS Code workspace:[/bold] {workspace_dir}")
        console.print(f"  Open this folder in VS Code to see sandbox files in real time.")

    # --- Summary ---
    console.print(f"\n[bold green]ricet is up![/bold green]")

    if not _auth_ok and not no_docker:
        console.print(f"\n[bold yellow]First-time setup (once per container rebuild):[/bold yellow]")
        console.print(f"  1. [bold]screen -r {screen_name}[/bold]")
        console.print(f"  2. If Claude shows a login prompt, run:")
        console.print(f"     [bold]docker exec -it {container_name} {_run_as} claude auth login[/bold]")
        console.print(f"     Then exit the container shell and the screen session will auto-restart Claude.")
        console.print(f"  3. Once Claude is running, type [bold]/remote-control[/bold] to get the QR code")
        console.print(f"  4. Detach from screen: [bold]Ctrl+A[/bold] then [bold]D[/bold]")

    console.print(f"\n[bold]Three ways to interact:[/bold]")
    console.print(f"  1. CLI:        [bold]screen -r {screen_name}[/bold]")
    console.print(f"  2. Phone app:  Attach to screen, type [bold]/remote-control[/bold], scan QR")
    console.print(f"  3. Dashboard:  Open Tailscale URL on phone (Voice + Tasks)")
    if not no_docker:
        console.print(f"\n[bold]Sandbox:[/bold]")
        console.print(f"  ricet sandbox status    # Container status")
        console.print(f"  ricet sandbox logs      # Claude output")
        console.print(f"  VS Code: open sandbox/workspace/")
    console.print(f"\n[bold]To stop:[/bold]  ricet down")


@app.command()
def down(
    screen_name: str = typer.Option("", "--screen", "-s", help="Screen session name (default: project name)"),
    port: int = typer.Option(0, "--port", "-p", help="Mobile server port (default: auto)"),
    keep_sandbox: bool = typer.Option(False, "--keep-sandbox", help="Don't stop the sandbox container"),
):
    """Stop a running ricet session (screen + mobile + sandbox)."""
    import os as _os
    import signal as _sig

    project_name = _derive_project_name(Path.cwd())
    if not screen_name:
        screen_name = project_name
    if port == 0:
        port = _project_port(project_name)

    # Kill mobile keepalive process
    pid_file = Path.home() / ".ricet" / "mobile_keepalive.pid"
    if pid_file.exists():
        try:
            keepalive_pid = int(pid_file.read_text().strip())
            _os.kill(keepalive_pid, _sig.SIGTERM)
            pid_file.unlink(missing_ok=True)
            console.print(f"  [dim]Mobile keepalive (PID {keepalive_pid}) stopped.[/dim]")
        except (ProcessLookupError, ValueError):
            pid_file.unlink(missing_ok=True)
        except Exception:
            pass

    # Stop mobile server
    console.print("[bold]Stopping mobile server...[/bold]")
    subprocess.run(f"fuser -k {port}/tcp", shell=True, capture_output=True)
    console.print("  [green]Mobile server stopped.[/green]")

    # Stop tailscale serve — try turning off the specific HTTPS port,
    # then fall back to full reset if only one project is served.
    ts_current = subprocess.run(
        ["tailscale", "serve", "status"], capture_output=True, text=True
    )
    proxy_count = ts_current.stdout.count("proxy ")
    if proxy_count <= 1:
        # Only this project — full reset is safe
        subprocess.run(["tailscale", "serve", "reset"], capture_output=True)
    else:
        # Multiple projects — try to remove just this one's path
        subprocess.run(
            ["tailscale", "serve", "--set-path", f"/{screen_name}", "off"],
            capture_output=True,
        )
    console.print(f"  [dim]Tailscale serve for '{screen_name}' cleared.[/dim]")

    # Kill screen session
    result = subprocess.run(
        ["screen", "-S", screen_name, "-X", "quit"],
        capture_output=True,
    )
    if result.returncode == 0:
        console.print(f"  [green]Screen session '{screen_name}' terminated.[/green]")
    else:
        console.print(f"  [dim]Screen session '{screen_name}' was not running.[/dim]")

    # Stop sandbox
    if not keep_sandbox:
        from core.sandbox import is_sandbox_running, stop_sandbox
        project_path = Path.cwd()
        if is_sandbox_running(project_path):
            console.print("[bold]Stopping sandbox container...[/bold]")
            stop_sandbox(project_path, print_fn=lambda m: console.print(f"  {m}"))
        else:
            console.print("  [dim]Sandbox was not running.[/dim]")

    console.print("[green]ricet is down.[/green]")


def _start_mobile_for_up(console: Console, screen_name: str, port: int) -> None:
    """Start mobile server + Tailscale serve for ricet up.

    Launches `ricet mobile serve` as a detached background process so it
    survives after the parent exits. No fork tricks needed.
    """
    import os as _os
    import shutil
    import time

    # Kill stale processes on the port
    subprocess.run(f"fuser -k {port}/tcp", shell=True, capture_output=True)
    time.sleep(0.5)

    # Launch mobile server as a detached subprocess
    ricet_bin = shutil.which("ricet")
    if not ricet_bin:
        console.print("  [red]ricet not found in PATH[/red]")
        return

    log_file = Path.home() / ".ricet" / "mobile.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_fd = open(log_file, "a")

    env = dict(_os.environ)
    env["RICET_SCREEN_SESSION"] = screen_name

    mobile_proc = subprocess.Popen(
        [ricet_bin, "mobile", "serve", "--port", str(port), "--host", "127.0.0.1", "--no-tls"],
        stdout=log_fd,
        stderr=log_fd,
        start_new_session=True,
        env=env,
    )

    # Write PID for ricet down
    pid_file = Path.home() / ".ricet" / "mobile_keepalive.pid"
    pid_file.write_text(str(mobile_proc.pid) + "\n")

    # Wait for server to be ready
    for _ in range(20):
        time.sleep(0.5)
        try:
            import socket
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                break
        except (ConnectionRefusedError, OSError):
            continue

    # Verify screen injection works before declaring ready
    _screen_ok = subprocess.run(
        ["screen", "-S", screen_name, "-X", "stuff", ""],
        capture_output=True, timeout=3,
    ).returncode == 0
    if not _screen_ok:
        console.print(f"  [yellow]Screen session '{screen_name}' not reachable for injection.[/yellow]")

    console.print(f"  [green]Mobile server started (PID {mobile_proc.pid}, port {port})[/green]")
    console.print(f"  [dim]Log: {log_file}[/dim]")

    # Start tailscale serve
    from core.mobile import get_tailscale_address
    ts_ip = get_tailscale_address()

    if ts_ip:
        console.print("[bold cyan]Starting Tailscale serve...[/bold cyan]")
        # Check current serve config to decide root vs path mapping
        ts_current = subprocess.run(
            ["tailscale", "serve", "status"], capture_output=True, text=True
        )
        # If root "/" is mapped to a DIFFERENT port, use --set-path for this project
        root_mapped_to_other = (
            "/ proxy" in ts_current.stdout
            and f"127.0.0.1:{port}" not in ts_current.stdout
        )

        if root_mapped_to_other:
            # Another project owns "/". Map this one to a subpath.
            ts_serve_cmd = [
                "tailscale", "serve", "--bg",
                "--set-path", f"/{screen_name}",
                f"http://127.0.0.1:{port}",
            ]
            path_prefix = f"/{screen_name}"
        else:
            # No other project, or same port — take the root
            ts_serve_cmd = ["tailscale", "serve", "--bg", str(port)]
            path_prefix = ""

        ts_result = subprocess.run(ts_serve_cmd, capture_output=True, text=True)
        if ts_result.returncode != 0:
            console.print(f"  [yellow]tailscale serve failed: {ts_result.stderr.strip()}[/yellow]")
            console.print("  [yellow]Hint: sudo tailscale set --operator=$USER[/yellow]")
            return

        # Get the serve URL
        ts_status = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True, text=True,
        )
        try:
            ts_data = json.loads(ts_status.stdout)
            ts_hostname = ts_data.get("Self", {}).get("DNSName", "").rstrip(".")
            public_url = f"https://{ts_hostname}{path_prefix}"
        except Exception:
            public_url = "https://<tailscale-hostname>"

        console.print(f"  [bold green]Dashboard: {public_url}[/bold green]")

        # Save URL
        try:
            url_file = Path.home() / ".ricet" / "tunnel_url"
            url_file.parent.mkdir(parents=True, exist_ok=True)
            url_file.write_text(public_url + "\n")
        except Exception:
            pass

        # QR code
        try:
            from core.mobile import generate_qr_terminal
            qr = generate_qr_terminal(public_url)
            if qr:
                console.print(f"\n{qr}")
        except Exception:
            pass
    else:
        console.print("  [yellow]Tailscale not available. Mobile dashboard is local only.[/yellow]")
        console.print(f"  [dim]http://localhost:{port}[/dim]")

    # No keepalive fork needed — mobile server runs as a detached subprocess


@app.command()
def overnight(
    task_file: Path = typer.Option(Path("state/TODO.md"), help="Task file to execute"),
    iterations: int = typer.Option(20, help="Max iterations"),
    timeout_min: int = typer.Option(60, "--timeout", "-t", help="Timeout per iteration in minutes"),
    no_docker: bool = typer.Option(
        False,
        "--no-docker",
        help=(
            "ADVANCED USERS ONLY: Skip Docker isolation. "
            "Overnight mode runs with elevated permissions and can execute "
            "arbitrary commands on your system. Without Docker, there is NO "
            "sandbox protecting your files, network, or system configuration. "
            "Only use this if you fully understand the risks."
        ),
    ),
    hours: int = typer.Option(10, "--hours", help="Sandbox watchdog timeout in hours"),
):
    """Run overnight autonomous mode (requires Docker for safety).

    Overnight mode runs unattended with --dangerously-skip-permissions, which
    means Claude can execute any command without confirmation. Docker provides
    a safety sandbox so that these commands cannot damage your host system.

    The sandbox uses an isolated Docker container with:
    - Read-only project mount (agent works on a copy)
    - Per-iteration timeout (kills stuck iterations)
    - Watchdog timer (auto-shutdown after N hours)
    - Auto-commit after every iteration (nothing is lost)
    - Patch-based extraction (review changes before applying)

    Docker is REQUIRED by default. If you are an advanced user who understands
    the risks, you may pass --no-docker to bypass this requirement.
    """
    from core.sandbox import (
        is_sandbox_running,
        launch_overnight_loop,
        sandbox_exists,
        setup_sandbox,
        start_sandbox,
    )

    # Detect whether we are already running inside the sandbox container
    _inside_container = (
        Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()
    )

    if not no_docker and not _inside_container:
        # Docker is required - use the sandbox infrastructure
        from core.devops import ensure_docker_ready

        docker_status = ensure_docker_ready()

        _docker_usable = (
            docker_status["docker_installed"]
            and docker_status["daemon_running"]
        )
        # Quick permission check — can we actually talk to Docker?
        if _docker_usable:
            import subprocess as _sp

            _perm = _sp.run(
                ["docker", "info"], capture_output=True, text=True, timeout=10
            )
            if _perm.returncode != 0:
                # Try switching to the docker group (doesn't need sudo)
                console.print(
                    "[yellow]Docker socket permission denied. "
                    "Trying newgrp docker...[/yellow]"
                )
                _retry = _sp.run(
                    ["sg", "docker", "-c", "docker info"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if _retry.returncode == 0:
                    # sg docker works — re-exec ourselves under the docker group
                    import os, sys

                    console.print(
                        "[green]Docker group available. Re-launching...[/green]"
                    )
                    os.execvp(
                        "sg",
                        ["sg", "docker", "-c", " ".join(sys.argv)],
                    )
                _docker_usable = False

        if not _docker_usable:
            if not docker_status["docker_installed"]:
                console.print(
                    "[red]Docker is not installed.[/red]\n"
                    "Install Docker: https://docs.docker.com/get-docker/\n"
                )
            elif not docker_status["daemon_running"]:
                console.print(
                    "[red]Docker daemon is not running.[/red]\n"
                    "Start it with: [bold]sudo systemctl start docker[/bold]\n"
                )
            else:
                console.print(
                    "[red]Docker socket permission denied.[/red]\n"
                    "Your user is not in the 'docker' group. Ask an admin:\n"
                    "  [bold]sudo usermod -aG docker $USER[/bold]\n"
                    "Then log out and back in (or run [bold]newgrp docker[/bold]).\n"
                    "Or run with [bold]--no-docker[/bold] "
                    "(NOT recommended — no sandbox isolation).\n"
                )
            raise typer.Exit(1)

        project_path = Path.cwd().resolve()

        # Set up sandbox infrastructure if not already present
        if not sandbox_exists(project_path):
            console.print("[yellow]Setting up sandbox infrastructure...[/yellow]")
            if not setup_sandbox(
                project_path,
                print_fn=lambda msg: console.print(f"  [dim]{msg}[/dim]"),
            ):
                console.print("[red]Failed to set up sandbox.[/red]")
                raise typer.Exit(1)
            console.print("[green]Sandbox infrastructure ready.[/green]")

        # Start sandbox if not running
        if not is_sandbox_running(project_path):
            console.print("[bold]Starting sandbox container...[/bold]")
            if not start_sandbox(
                project_path,
                timeout_hours=hours,
                print_fn=lambda msg: console.print(f"  {msg}"),
            ):
                console.print("[red]Failed to start sandbox.[/red]")
                raise typer.Exit(1)

        # Launch the overnight loop inside the sandbox
        console.print(
            f"\n[bold]Launching overnight loop: {iterations} iterations, "
            f"{timeout_min}m per iteration, {hours}h watchdog[/bold]"
        )
        if not launch_overnight_loop(
            project_path,
            iterations=iterations,
            timeout_min=timeout_min,
            print_fn=lambda msg: console.print(f"  {msg}"),
        ):
            console.print("[red]Failed to launch overnight loop.[/red]")
            raise typer.Exit(1)

        console.print("\n[bold green]Overnight mode running in sandbox.[/bold green]")
        console.print("")
        console.print("[bold]Monitor:[/bold]")
        console.print("  ricet sandbox logs           # Recent output")
        console.print("  ricet sandbox status         # Container status")
        console.print("  ricet sandbox backup         # Sync results to host")
        console.print("")
        console.print("[bold]When done:[/bold]")
        console.print("  ricet sandbox extract        # Get work as patch")
        console.print("  ricet sandbox extract --apply # Extract and apply patch")
        console.print("  ricet sandbox stop           # Stop the container")
        return

    if no_docker and not _inside_container:
        # Only ask confirmation if the user explicitly passed --no-docker,
        # not if we auto-fell-back from Docker being unusable.
        import sys as _sys
        if "--no-docker" in _sys.argv:
            console.print(
                "[bold yellow]WARNING: Running overnight mode WITHOUT Docker "
                "isolation.[/bold yellow]\n"
                "[yellow]Claude will have unrestricted access to your host system.\n"
                "This includes the ability to read/write/delete ANY file, install "
                "software, and make network requests without sandboxing.[/yellow]\n"
            )
            confirm = typer.confirm(
                "Are you sure you want to proceed without Docker?", default=False
            )
            if not confirm:
                console.print(
                    "Aborted. Run without --no-docker to use Docker (recommended)."
                )
                raise typer.Exit(0)

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
            # Re-read constraints to check for drift
            constraints_file = Path("knowledge/CONSTRAINTS.md")
            if constraints_file.exists():
                constraints_text = constraints_file.read_text().strip()
                if constraints_text:
                    # Prepend constraints to the task for this iteration
                    enriched_tasks = f"CONSTRAINTS (must respect):\n{constraints_text[:1000]}\n\n{tasks}"
                    swarm_tasks = [{"type": "coder", "task": enriched_tasks}]

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

        # Run daily maintenance pass at the end of overnight
        from core.autonomous import run_maintenance

        console.print("\n[bold]Running maintenance pass...[/bold]")
        maint_results = run_maintenance(Path.cwd())
        for mname, mok in maint_results.items():
            tag = "[green]OK[/green]" if mok else "[red]FAIL[/red]"
            console.print(f"  {mname}: {tag}")
        auto_commit("ricet overnight: post-run maintenance")

        # --- End-of-overnight review report ---
        from core.session import generate_review_report

        console.print("\n[bold]Generating session review report...[/bold]")
        try:
            report_path = generate_review_report()
            console.print(f"[green]Review report saved: {report_path}[/green]")
        except Exception as exc:
            console.print(f"[yellow]Could not generate review report: {exc}[/yellow]")
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
        # Re-read constraints to check for drift
        constraints_file = Path("knowledge/CONSTRAINTS.md")
        if constraints_file.exists():
            constraints_text = constraints_file.read_text().strip()
            if constraints_text:
                enriched_tasks = f"CONSTRAINTS (must respect):\n{constraints_text[:1000]}\n\n{enriched_tasks}"

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
            # Re-read constraints to check for drift
            constraints_file = Path("knowledge/CONSTRAINTS.md")
            if constraints_file.exists():
                constraints_text = constraints_file.read_text().strip()
                if constraints_text:
                    # Prepend constraints to the task for this iteration
                    enriched_tasks = f"CONSTRAINTS (must respect):\n{constraints_text[:1000]}\n\n{tasks}"

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

    # Run daily maintenance pass at the end of overnight
    from core.autonomous import run_maintenance

    console.print("\n[bold]Running maintenance pass...[/bold]")
    maint_results = run_maintenance(Path.cwd())
    for mname, mok in maint_results.items():
        tag = "[green]OK[/green]" if mok else "[red]FAIL[/red]"
        console.print(f"  {mname}: {tag}")
    auto_commit("ricet overnight: post-run maintenance")

    # --- End-of-overnight review report ---
    from core.session import generate_review_report

    console.print("\n[bold]Generating session review report...[/bold]")
    try:
        report_path = generate_review_report()
        console.print(f"[green]Review report saved: {report_path}[/green]")
    except Exception as exc:
        console.print(f"[yellow]Could not generate review report: {exc}[/yellow]")


# ---------------------------------------------------------------------------
# Sandbox subcommands
# ---------------------------------------------------------------------------

sandbox_app = typer.Typer(help="Manage the overnight sandbox container.")
app.add_typer(sandbox_app, name="sandbox")


@sandbox_app.command("setup")
def sandbox_setup_cmd(
    dind: bool = typer.Option(False, "--dind", help="Use Docker-in-Docker variant"),
):
    """Set up sandbox infrastructure in the current project."""
    from core.sandbox import setup_sandbox

    project_path = Path.cwd().resolve()
    ok = setup_sandbox(
        project_path,
        dind=dind,
        print_fn=lambda msg: console.print(f"  {msg}"),
    )
    if ok:
        console.print("[green]Sandbox infrastructure ready.[/green]")
        console.print("")
        console.print("[bold]Next steps:[/bold]")
        console.print("  ricet sandbox start          # Build and start container")
        console.print("  ricet overnight              # Launch overnight loop")
    else:
        console.print("[red]Sandbox setup failed.[/red]")
        raise typer.Exit(1)


@sandbox_app.command("start")
def sandbox_start_cmd(
    hours: int = typer.Option(10, "--hours", "-h", help="Watchdog timeout in hours"),
):
    """Build and start the sandbox container."""
    from core.sandbox import start_sandbox

    project_path = Path.cwd().resolve()
    ok = start_sandbox(
        project_path,
        timeout_hours=hours,
        print_fn=lambda msg: console.print(f"  {msg}"),
    )
    if ok:
        console.print("[green]Sandbox started.[/green]")
        console.print("")
        console.print("[bold]Commands:[/bold]")
        console.print("  ricet overnight              # Launch overnight loop")
        console.print("  ricet sandbox logs           # Watch output")
        console.print("  ricet sandbox status         # Check status")
        console.print("  ricet sandbox stop           # Stop the container")
    else:
        console.print("[red]Failed to start sandbox.[/red]")
        raise typer.Exit(1)


@sandbox_app.command("stop")
def sandbox_stop_cmd():
    """Stop the sandbox container."""
    from core.sandbox import stop_sandbox

    project_path = Path.cwd().resolve()
    ok = stop_sandbox(
        project_path,
        print_fn=lambda msg: console.print(f"  {msg}"),
    )
    if not ok:
        console.print("[red]Failed to stop sandbox.[/red]")
        raise typer.Exit(1)
    console.print("")
    console.print("[dim]To extract work before cleanup: ricet sandbox extract[/dim]")
    console.print(
        "[dim]To remove persistent volumes: ricet sandbox destroy[/dim]"
    )


@sandbox_app.command("status")
def sandbox_status_cmd():
    """Show sandbox status."""
    from core.sandbox import sandbox_status

    project_path = Path.cwd().resolve()
    st = sandbox_status(project_path)

    if not st["setup"]:
        console.print("[yellow]Sandbox not set up. Run: ricet sandbox setup[/yellow]")
        return

    console.print(f"[bold]Container:[/bold] {st['container_name']}")
    if st["running"]:
        console.print(f"[bold]Status:[/bold] [green]Running[/green] ({st['uptime']})")
        if st["last_commit"]:
            console.print(f"[bold]Last commit:[/bold] {st['last_commit']}")
    else:
        console.print("[bold]Status:[/bold] [dim]Stopped[/dim]")


@sandbox_app.command("logs")
def sandbox_logs_cmd(
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow output (live)"),
):
    """Show sandbox Claude output logs."""
    from core.sandbox import _load_sandbox_env, is_sandbox_running, watch_sandbox_logs

    project_path = Path.cwd().resolve()

    if not is_sandbox_running(project_path):
        console.print("[yellow]Sandbox is not running.[/yellow]")
        raise typer.Exit(1)

    if follow:
        # Use docker exec tail -f directly for live following
        from core.devops import run_docker

        env = _load_sandbox_env(project_path)
        container_name = env["CONTAINER_NAME"]
        try:
            run_docker(
                [
                    "docker", "exec", container_name,
                    "tail", "-f", "/agent-logs/claude-output.log",
                ],
                timeout=None,
            )
        except KeyboardInterrupt:
            pass
    else:
        output = watch_sandbox_logs(project_path, lines=lines)
        console.print(output)


@sandbox_app.command("extract")
def sandbox_extract_cmd(
    apply: bool = typer.Option(False, "--apply", help="Apply patch to project after extraction"),
):
    """Extract work from sandbox as a git patch."""
    from core.sandbox import extract_work

    project_path = Path.cwd().resolve()
    patch = extract_work(
        project_path,
        apply_patch=apply,
        print_fn=lambda msg: console.print(f"  {msg}"),
    )
    if patch:
        console.print(f"\n[green]Patch saved: {patch}[/green]")
    else:
        console.print("[dim]No changes to extract.[/dim]")


@sandbox_app.command("backup")
def sandbox_backup_cmd(
    interval: int = typer.Option(0, "--interval", "-i", help="Continuous mode: minutes between backups (0 = single backup)"),
):
    """Sync sandbox state files and results to host.

    Without --interval, runs a single backup. With --interval N, runs
    continuously every N minutes (Ctrl+C to stop).
    """
    from core.sandbox import run_backup, start_auto_backup

    project_path = Path.cwd().resolve()

    if interval > 0:
        start_auto_backup(
            project_path,
            interval_min=interval,
            print_fn=lambda msg: console.print(f"  {msg}"),
        )
    else:
        ok = run_backup(
            project_path,
            print_fn=lambda msg: console.print(f"  {msg}"),
        )
        if ok:
            console.print("[green]Backup complete.[/green]")
        else:
            console.print("[yellow]Backup failed.[/yellow]")


@sandbox_app.command("destroy")
def sandbox_destroy_cmd():
    """Stop sandbox and remove all persistent volumes.

    WARNING: This destroys ALL workspace data inside the sandbox.
    Make sure to extract work first with 'ricet sandbox extract'.
    """
    from core.sandbox import destroy_sandbox

    console.print("[bold red]WARNING: This will destroy all sandbox data![/bold red]")
    console.print("Run 'ricet sandbox extract' first to save your work.")
    confirm = typer.confirm("Proceed?", default=False)
    if not confirm:
        console.print("Aborted.")
        raise typer.Exit(0)

    project_path = Path.cwd().resolve()
    ok = destroy_sandbox(
        project_path,
        print_fn=lambda msg: console.print(f"  {msg}"),
    )
    if not ok:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Slides subcommands
# ---------------------------------------------------------------------------

slides_app = typer.Typer(help="Generate presentation slide decks.")
app.add_typer(slides_app, name="slides")


@slides_app.command("setup")
def slides_setup_cmd():
    """Set up slide-making infrastructure in the current project."""
    from core.slides import setup_slides

    project_path = Path.cwd().resolve()
    ok = setup_slides(
        project_path,
        print_fn=lambda msg: console.print(f"  {msg}"),
    )
    if ok:
        console.print("[green]Slides infrastructure ready.[/green]")
        console.print("")
        console.print("[bold]Next steps:[/bold]")
        console.print("  ricet slides create          # Generate slide deck via agent")
        console.print("  ricet slides build           # Build the .pptx presentation")
    else:
        console.print("[red]Slides setup failed.[/red]")
        raise typer.Exit(1)


@slides_app.command("create")
def slides_create_cmd(
    title: str = typer.Option(..., "--title", "-t", prompt="Presentation title"),
    audience: str = typer.Option(
        "Technical peers", "--audience", "-a", prompt="Target audience"
    ),
    duration: str = typer.Option(
        "15 minutes", "--duration", "-d", prompt="Duration"
    ),
    key_message: str = typer.Option(
        "", "--key-message", "-k", prompt="Key message (one thing to remember)"
    ),
    schematics: int = typer.Option(4, "--schematics", "-n", help="Number of schematics"),
    author: str = typer.Option("", "--author", prompt="Author"),
    source: str = typer.Option("", "--source", "-s", help="Codebase path or URL to analyze"),
    dangerously_skip_permissions: bool = typer.Option(
        False, "--dangerously-skip-permissions", hidden=True
    ),
):
    """Run the slide-maker agent to generate a presentation script.

    The agent analyzes your project and writes make_slides.py with all slide
    content and schematic prompts. Run 'ricet slides build' afterwards to
    generate the .pptx.
    """
    from core.slides import create_slides

    project_path = Path.cwd().resolve()

    # Collect emphasis points
    console.print("\n[bold]What to emphasize[/bold] (enter points, empty line to finish):")
    emphasis: list[str] = []
    while True:
        point = typer.prompt(f"  {len(emphasis) + 1}", default="", show_default=False)
        if not point:
            break
        emphasis.append(point)

    # Determine source type
    source_path = None
    source_url = None
    if source:
        if source.startswith("http://") or source.startswith("https://"):
            source_url = source
        else:
            source_path = source

    console.print(f"\n[bold cyan]Generating slide deck: {title}[/bold cyan]")
    console.print(f"  Audience: {audience}  |  Duration: {duration}")
    console.print(f"  Schematics: {schematics}  |  Author: {author}")
    console.print("")

    make_slides = create_slides(
        project_path,
        title=title,
        audience=audience,
        duration=duration,
        key_message=key_message,
        emphasis=emphasis,
        schematics_n=schematics,
        author=author,
        source_path=source_path,
        source_url=source_url,
        dangerously_skip_permissions=dangerously_skip_permissions,
    )

    if make_slides.exists():
        console.print(f"\n[green]Generated: {make_slides}[/green]")
        console.print("")
        console.print("[bold]Next:[/bold]")
        console.print("  ricet slides build           # Build the .pptx")
    else:
        console.print("[yellow]Agent finished but make_slides.py not found.[/yellow]")
        console.print("Check the slides/ directory and agent output.")


@slides_app.command("build")
def slides_build_cmd():
    """Build the .pptx presentation from make_slides.py.

    Runs the generated script to produce schematics (via Nano Banana Pro)
    and the final PowerPoint deck.
    """
    from core.slides import build_slides, has_slides

    project_path = Path.cwd().resolve()

    if not has_slides(project_path):
        console.print("[yellow]No slides infrastructure. Run: ricet slides setup[/yellow]")
        raise typer.Exit(1)

    console.print("[bold cyan]Building slide deck...[/bold cyan]")

    try:
        output = build_slides(project_path)
        if output.exists():
            size_kb = output.stat().st_size / 1024
            console.print(f"\n[green]Presentation ready: {output} ({size_kb:.0f} KB)[/green]")
        else:
            console.print(f"\n[yellow]Build completed but .pptx not found at {output}[/yellow]")
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except RuntimeError as e:
        console.print(f"[red]Build failed:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def dashboard(
    live: bool = typer.Option(False, "--live", "-l", help="Live-updating mode"),
    interval: float = typer.Option(5.0, "--interval", "-i", help="Refresh interval (seconds)"),
):
    """Show the Rich TUI dashboard with project status panels."""
    from cli.dashboard import live_dashboard, show_dashboard

    if live:
        live_dashboard(refresh_interval=interval)
    else:
        show_dashboard()


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
def resume(
    session_name: str = typer.Argument(help="Name of the session to resume"),
):
    """Resume a previously started session."""
    import uuid as _uuid

    from core.session import list_sessions as _list_sessions
    from core.session import load_session, update_session

    session = load_session(session_name)
    if session is None:
        console.print(f"[red]Session '{session_name}' not found.[/red]")
        available = _list_sessions()
        if available:
            console.print("[bold]Available sessions:[/bold]")
            for s in available:
                console.print(f"  {s.name} - {s.status} ({s.started[:10]})")
        else:
            console.print("No sessions exist yet. Use 'ricet start' to create one.")
        raise typer.Exit(code=1)

    # Use stored UUID or generate a new one
    session_uuid = session.uuid if session.uuid else str(_uuid.uuid4())
    if not session.uuid:
        session.uuid = session_uuid
        update_session(session)

    # Mark session as active again
    session.status = "active"
    update_session(session)

    console.print(
        f"[green]Resuming session: {session.name} ({session_uuid[:8]}...)[/green]"
    )
    subprocess.run(["claude", "--session-id", session_uuid])


@app.command()
def agents():
    """Show swarm agent status."""
    from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

    # --- 1. Agent Definitions (from .claude/agents/*.md) ---
    source_root = Path(__file__).resolve().parent.parent
    agents_dir = source_root / ".claude" / "agents"
    templates_agents_dir = source_root / "templates" / ".claude" / "agents"
    definition_names: list[str] = []
    for search_dir in (agents_dir, templates_agents_dir):
        if search_dir.is_dir():
            definition_names = sorted(
                p.stem for p in search_dir.glob("*.md") if p.is_file()
            )
            break

    if definition_names:
        console.print(f"[bold]Agent Definitions ({len(definition_names)}):[/bold]")
        console.print(f"  {', '.join(definition_names)}")
    else:
        console.print("[dim]No agent definitions found[/dim]")

    console.print()

    # --- 2. Running Agents (from store.json + claude-flow CLI fallback) ---
    running_agents: list[dict] = []

    # 2a. Read .claude-flow/agents/store.json
    # Look in cwd first (the user's project), then fall back to source tree.
    cwd_store = Path.cwd() / ".claude-flow" / "agents" / "store.json"
    src_store = source_root / ".claude-flow" / "agents" / "store.json"
    store_path = cwd_store if cwd_store.is_file() else src_store
    if store_path.is_file():
        try:
            store_data = json.loads(store_path.read_text())
            # The top-level key is "agents" (dict of agentId -> info).
            agents_map = store_data.get("agents") or store_data
            # If agents_map is a list (unlikely but defensive), convert.
            if isinstance(agents_map, list):
                agents_map = {
                    a.get("agentId", f"agent-{i}"): a for i, a in enumerate(agents_map)
                }
            if isinstance(agents_map, dict):
                # Skip non-agent top-level keys like "version"
                for _aid, info in agents_map.items():
                    if not isinstance(info, dict):
                        continue
                    running_agents.append(
                        {
                            "id": info.get("agentId", _aid),
                            "type": info.get("agentType", "unknown"),
                            "status": info.get("status", "unknown"),
                            "model": info.get("model", ""),
                            "created": info.get("createdAt", ""),
                        }
                    )
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug("Could not read store.json: %s", exc)

    # 2b. If store.json yielded nothing, try claude-flow CLI
    if not running_agents:
        try:
            proc = subprocess.run(
                [
                    "npx",
                    "@claude-flow/cli@latest",
                    "agent",
                    "list",
                    "--json",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                try:
                    cli_data = json.loads(proc.stdout)
                    agents_list = (
                        cli_data
                        if isinstance(cli_data, list)
                        else cli_data.get("agents", [])
                    )
                    for info in agents_list:
                        if isinstance(info, dict):
                            running_agents.append(
                                {
                                    "id": info.get("agentId", info.get("name", "?")),
                                    "type": info.get("agentType", "unknown"),
                                    "status": info.get("status", "unknown"),
                                    "model": info.get("model", ""),
                                    "created": info.get("createdAt", ""),
                                }
                            )
                except json.JSONDecodeError:
                    # Plain-text output; show as-is
                    console.print("[bold]Running Agents (via claude-flow):[/bold]")
                    console.print(f"  {proc.stdout.strip()}")
                    return
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            logger.debug("claude-flow agent list failed: %s", exc)

    # --- 3. Display running agents ---
    if running_agents:
        console.print(
            f"[bold]Running Agents via claude-flow ({len(running_agents)}):[/bold]"
        )
        for ag in running_agents:
            model_part = f" \\[{ag['model']}]" if ag.get("model") else ""
            console.print(f"  {ag['id']} ({ag['type']}) - {ag['status']}{model_part}")
    else:
        # Last resort: project-internal agent tracker
        try:
            bridge = _get_bridge()
            console.print(f"[dim]claude-flow {bridge.get_version()} connected[/dim]")
        except ClaudeFlowUnavailable:
            pass

        from core.agents import get_active_agents_status

        active = get_active_agents_status()
        if active:
            console.print("[bold]Running Agents:[/bold]")
            for a in active:
                console.print(f"  [{a['agent']}] {a['description']}")
        else:
            console.print("  No running agents")


@app.command()
def memory(
    action: str = typer.Argument(
        help="Action: search, log-decision, export, import, stats, rules, add-rule"
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

        # Resolve encyclopedia path against active project
        _enc = Path("knowledge/ENCYCLOPEDIA.md")
        try:
            from core.project_registry import ProjectRegistry

            _preg = ProjectRegistry()
            _aproj = _preg.get_active_project()
            if _aproj and _aproj.get("path"):
                _enc = Path(_aproj["path"]) / "knowledge" / "ENCYCLOPEDIA.md"
        except Exception:
            pass

        # Try HNSW search via claude-flow only if it's already running (no auto-start)
        hits = []
        try:
            from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

            bridge = _get_bridge()
            result = bridge.query_memory(query, top_k=top_k)
            hits = result.get("results", [])
            if hits:
                console.print(f"[bold]Memory results ({len(hits)}) [HNSW]:[/bold]")
                for hit in hits:
                    score = hit.get("score", "?")
                    text = hit.get("text", "")[:120]
                    console.print(f"  [{score:.2f}] {text}")
        except Exception:
            pass  # claude-flow not running or disabled — fall through to keyword search

        # RAG semantic search (sentence-transformers, optional)
        rag_hits = []
        try:
            from core.rag import search as rag_search

            rag_hits = rag_search(query, encyclopedia_path=_enc, top_k=top_k)
            if rag_hits:
                console.print(f"[bold]Semantic matches ({len(rag_hits)}) [RAG]:[/bold]")
                for h in rag_hits:
                    console.print(f"  [{h.score:.2f}] {h.text[:120]}")
        except Exception:
            pass  # sentence-transformers not installed — install with: uv pip install sentence-transformers

        # Always merge with keyword search from encyclopedia
        from core.knowledge import search_knowledge

        kw_results = search_knowledge(query, encyclopedia_path=_enc)
        # Deduplicate against HNSW and RAG hits
        shown = {h.get("text", "") for h in hits} | {h.text for h in rag_hits}
        kw_only = [r for r in kw_results if r not in shown]

        if kw_only:
            if hits or rag_hits:
                console.print(f"[bold]Keyword matches ({len(kw_only)}):[/bold]")
            for r in kw_only[:top_k]:
                console.print(f"  {r}")

        if not hits and not rag_hits and not kw_only:
            if not _enc.exists():
                console.print(
                    f"[dim]Encyclopedia not found at {_enc}.\n"
                    f"  Log findings with: ricet memory log-decision \"Your insight\"[/dim]"
                )
            else:
                console.print(f"[dim]No matches for '{query}'.[/dim]")
                console.print(
                    "[dim]  Log new findings: ricet memory log-decision \"Your insight\"[/dim]"
                )

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

    elif action == "build-index":
        # Build / refresh RAG semantic index for the encyclopedia
        from core.rag import _model_available, build_index, index_stats

        if not _model_available():
            console.print(
                "[yellow]sentence-transformers not installed.[/yellow]\n"
                "  Install with: [bold]uv pip install sentence-transformers[/bold]"
            )
            raise typer.Exit(1)
        _enc = Path("knowledge/ENCYCLOPEDIA.md")
        rebuilt = build_index(_enc, force=("--force" in (query or "")))
        stats = index_stats(_enc)
        if rebuilt:
            console.print(f"[green]RAG index built: {stats['entries']} entries[/green]")
        else:
            console.print(f"[dim]RAG index already up to date ({stats['entries']} entries).[/dim]")

    elif action == "rules":
        # Show / manage knowledge/RULES.md
        rules_file = Path("knowledge/RULES.md")
        if not rules_file.exists():
            console.print("[yellow]No RULES.md yet. Rules are captured automatically from your corrections.[/yellow]")
        else:
            lines = [l for l in rules_file.read_text().splitlines() if l.startswith("- ")]
            console.print(f"[bold]Behavioral rules ({len(lines)}):[/bold]")
            for line in lines:
                console.print(f"  {line}")
            console.print(f"\n[dim]Edit directly: {rules_file}[/dim]")

    elif action == "add-rule":
        if not query:
            console.print("[red]Provide rule text.[/red]")
            raise typer.Exit(1)
        rules_file = Path("knowledge/RULES.md")
        rules_file.parent.mkdir(parents=True, exist_ok=True)
        if not rules_file.exists():
            rules_file.write_text(
                "# Behavioral Rules\n\nAutomatically captured from user corrections.\n\n"
            )
        existing = {l.strip("- \n") for l in rules_file.read_text().splitlines() if l.startswith("- ")}
        if query in existing:
            console.print("[yellow]Rule already exists.[/yellow]")
        else:
            with rules_file.open("a") as f:
                f.write(f"- {query}\n")
            console.print(f"[green]Rule added: {query}[/green]")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available: search, log-decision, export, import, stats, rules, add-rule")
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
def maintain():
    """Run daily maintenance pass (tests, docs, fidelity, verification)."""
    from core.autonomous import run_maintenance

    project_path = Path.cwd()
    console.print("[bold]Running daily maintenance pass...[/bold]")
    results = run_maintenance(project_path)

    all_ok = True
    for name, success in results.items():
        if success:
            console.print(f"  [green]{name}: passed[/green]")
        else:
            console.print(f"  [red]{name}: failed[/red]")
            all_ok = False

    if all_ok:
        console.print("[bold green]All maintenance tasks passed.[/bold green]")
    else:
        console.print(
            "[bold yellow]Some maintenance tasks failed. Review output above.[/bold yellow]"
        )

    auto_commit("ricet maintain: daily maintenance pass")


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


@app.command(name="enable-ruflo")
def enable_ruflo():
    """Enable the claude-flow (ruflo) MCP server for complex multi-agent tasks.

    \b
    WARNING: claude-flow loads 200+ tools into every message context, which
    significantly increases token consumption. Only enable it for tasks that
    genuinely need swarm coordination or HNSW vector memory. Disable it again
    with 'ricet disable-ruflo' when done.

    Useful for: overnight swarm runs, cross-session HNSW memory, agent spawning.
    Not needed for: normal research sessions, paper writing, single-agent tasks.
    """
    import json

    mcp_file = Path(".mcp.json")
    if not mcp_file.exists():
        console.print("[red].mcp.json not found in current directory[/red]")
        raise typer.Exit(1)

    config = json.loads(mcp_file.read_text())
    cf = config.get("mcpServers", {}).get("claude-flow", {})
    if not cf:
        console.print("[red]claude-flow not found in .mcp.json[/red]")
        raise typer.Exit(1)

    cf.pop("disabled", None)
    mcp_file.write_text(json.dumps(config, indent=2) + "\n")
    console.print("[green]claude-flow (ruflo) enabled.[/green]")
    console.print(
        "[yellow]⚠ This loads 200+ tools per message — token usage will increase substantially.[/yellow]"
    )
    console.print("[dim]Restart Claude Code for the change to take effect.[/dim]")
    console.print("[dim]Run 'ricet disable-ruflo' when done with complex tasks.[/dim]")


@app.command(name="disable-ruflo")
def disable_ruflo():
    """Disable the claude-flow (ruflo) MCP server to reduce token consumption."""
    import json

    mcp_file = Path(".mcp.json")
    if not mcp_file.exists():
        console.print("[red].mcp.json not found in current directory[/red]")
        raise typer.Exit(1)

    config = json.loads(mcp_file.read_text())
    cf = config.get("mcpServers", {}).get("claude-flow", {})
    if not cf:
        console.print("[red]claude-flow not found in .mcp.json[/red]")
        raise typer.Exit(1)

    cf["disabled"] = True
    mcp_file.write_text(json.dumps(config, indent=2) + "\n")
    console.print("[green]claude-flow (ruflo) disabled.[/green]")
    console.print("[dim]Restart Claude Code for the change to take effect.[/dim]")


@app.command(name="mcp-search")
def mcp_search(
    need: str = typer.Argument(help="What you need (e.g. 'access PubMed papers')"),
    install: bool = typer.Option(
        False, "--install", "-i", help="Auto-install the match"
    ),
):
    """Search the MCP catalog for a server matching your need.

    Claude reads the full MCP catalog (1 300+ servers) and suggests the
    best match, its install command, and any credentials required.
    """
    from core.mcps import suggest_and_install_mcp

    suggest_and_install_mcp(
        need,
        auto_install=install,
        prompt_fn=lambda q, d: typer.prompt(q, default=d),
        print_fn=lambda msg: console.print(msg),
    )


@app.command(name="mcp-create")
def mcp_create(
    name: str = typer.Argument(help="MCP server name"),
    description: str = typer.Option("", "--desc", "-d", help="What the MCP does"),
    tools: str = typer.Option("", "--tools", "-t", help="Comma-separated tool names"),
    output: Path = typer.Option(None, "--output", "-o", help="Output directory"),
):
    """Generate a new MCP server from scratch using Claude."""
    from core.mcps import create_mcp_scaffold

    tool_list = [t.strip() for t in tools.split(",") if t.strip()] if tools else []
    if not tool_list:
        console.print(
            "[yellow]No tools specified. Use --tools 'search,fetch,parse'[/yellow]"
        )
        raise typer.Exit(1)

    console.print(f"[bold]Generating MCP server: {name}[/bold]")
    if description:
        console.print(f"  Description: {description}")
    console.print(f"  Tools: {', '.join(tool_list)}")

    result = create_mcp_scaffold(name, description, tool_list, output_dir=output)
    if result:
        console.print(f"[green]MCP scaffold created at: {result}[/green]")
        console.print("  Next steps:")
        console.print(f"    cd {result}")
        console.print("    npm install")
        console.print("    npm run build")
    else:
        console.print(
            "[red]Failed to generate MCP scaffold (Claude unavailable?).[/red]"
        )
        raise typer.Exit(1)


@app.command(name="zapier")
def zapier_cmd(
    action: str = typer.Argument(help="Action: setup"),
    api_key: str = typer.Option("", "--key", "-k", help="Zapier NLA API key"),
):
    """Zapier integration commands."""
    from core.mcps import setup_zapier_mcp

    if action == "setup":
        console.print("[bold]Setting up Zapier MCP integration...[/bold]")
        success = setup_zapier_mcp(api_key=api_key)
        if success:
            console.print("[green]Zapier MCP configured successfully.[/green]")
            console.print("  Zapier zaps are now available as MCP tools.")
        else:
            console.print(
                "[red]Failed to configure Zapier MCP.[/red]\n"
                "  Ensure ZAPIER_NLA_API_KEY is set or pass --key."
            )
            raise typer.Exit(1)
    else:
        console.print(f"[red]Unknown action: {action}. Use 'setup'.[/red]")
        raise typer.Exit(1)


@app.command()
def paper(
    action: str = typer.Argument(
        help="Action: build, update, modernize, check, adapt-style"
    ),
    reference: Path = typer.Option(
        None, "--reference", help="Path to reference paper (style donor) for adapt-style"
    ),
    source: Path = typer.Option(
        None, "--source", "-s",
        help="Path to source text/tex to rewrite for adapt-style (default: paper/main.tex)",
    ),
):
    """Paper pipeline commands."""
    from core.paper import check_figure_references, clean_paper, compile_paper

    if action == "build":
        from core.paper import check_latex_dependencies

        console.print("[bold]Checking LaTeX dependencies...[/bold]")
        deps_ok, dep_messages = check_latex_dependencies(verbose=True)
        if not deps_ok:
            for msg in dep_messages:
                console.print(f"[red]{msg}[/red]")
            raise typer.Exit(1)
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

        # Resolve source file: --source flag, or default to paper/main.tex
        source_file = source if source else Path("paper/main.tex")
        if not source_file.exists():
            console.print(
                f"[red]Source file not found: {source_file}\n"
                "  Pass --source /path/to/file.txt to specify a different source.[/red]"
            )
            raise typer.Exit(1)
        if reference is None:
            console.print("[red]--reference is required for adapt-style[/red]")
            raise typer.Exit(1)
        if not reference.exists():
            console.print(f"[red]Reference file not found: {reference}[/red]")
            raise typer.Exit(1)

        source_text = source_file.read_text(errors="replace")

        # Handle PDF references: extract text with pdftotext or fallback
        if reference.suffix.lower() == ".pdf":
            import shutil
            import subprocess as _sp

            if shutil.which("pdftotext"):
                try:
                    proc = _sp.run(
                        ["pdftotext", "-layout", str(reference), "-"],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    if proc.returncode == 0 and proc.stdout.strip():
                        reference_text = proc.stdout
                    else:
                        console.print(
                            "[red]pdftotext failed. Install poppler-utils: "
                            "mamba install -c conda-forge poppler[/red]"
                        )
                        raise typer.Exit(1)
                except _sp.TimeoutExpired:
                    console.print("[red]PDF extraction timed out[/red]")
                    raise typer.Exit(1)
            else:
                console.print(
                    "[red]PDF reference requires pdftotext. Install with:[/red]\n"
                    "  mamba install -c conda-forge poppler  # recommended\n"
                    "  brew install poppler                  # macOS"
                )
                raise typer.Exit(1)
        else:
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
            out_path = source_file.with_stem(source_file.stem + "_adapted")
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
    action: str = typer.Argument(
        "tunnel",
        help="Action: tunnel (default), serve, stop, pair, connect-info, tokens, cert-regen, status"
    ),
    port: int = typer.Option(8777, "--port", "-p", help="Server port"),
    host: str = typer.Option("0.0.0.0", "--host", help="Bind address"),
    no_tls: bool = typer.Option(False, "--no-tls", help="Disable TLS"),
    label: str = typer.Option("", "--label", "-l", help="Token label (for pair)"),
    cf: bool = typer.Option(False, "--cf", help="Force Cloudflare quick tunnel (skip Tailscale)"),
):
    """Manage mobile companion server for secure on-the-go monitoring."""
    try:
        from core.mobile import mobile_server
    except ImportError:
        console.print(
            "[red]core.mobile not available. Install mobile dependencies first.[/red]"
        )
        raise typer.Exit(1)

    tls = not no_tls

    if action in ("serve", "start"):
        console.print("[bold]Starting mobile server...[/bold]")
        try:
            try:
                info = mobile_server.serve(host=host, port=port, tls=tls)
            except OSError as exc:
                if "Address already in use" in str(exc):
                    console.print(
                        f"[yellow]Port {port} already in use — "
                        f"stopping old server...[/yellow]"
                    )
                    import subprocess as _sp

                    _sp.run(
                        f"fuser -k {port}/tcp",
                        shell=True,
                        capture_output=True,
                    )
                    import time as _tw

                    _tw.sleep(0.5)
                    info = mobile_server.serve(host=host, port=port, tls=tls)
                else:
                    raise
            console.print(f"[green]{info}[/green]")
            scheme = "https" if tls else "http"
            console.print(f"\n[bold]Local/tunnel access (no auth needed):[/bold]")
            console.print(f"  {scheme}://localhost:{port}")
            console.print(f"\n[bold]SSH tunnel from another machine:[/bold]")
            console.print(
                f"  ssh -L {port}:localhost:{port} "
                f"$(whoami)@$(hostname -I 2>/dev/null | awk '{{print $1}}')"
            )
            console.print(f"\n[bold]Mobile phone access:[/bold]")
            console.print(
                f"  Option 1 (recommended): ricet mobile tunnel"
            )
            console.print(
                f"    Creates a public URL via Cloudflare — works through firewalls"
            )
            console.print(
                f"  Option 2: ricet mobile pair  (same network only)"
            )
            if tls:
                console.print(
                    f"\n[dim]Tip: If browser rejects the self-signed cert, "
                    f"restart with --no-tls[/dim]"
                )
            console.print("\n[dim]Press Ctrl+C to stop the server.[/dim]")
            # Block the main thread so the daemon server thread stays alive.
            import signal

            try:
                signal.pause()
            except AttributeError:
                import time

                while True:
                    time.sleep(3600)
        except KeyboardInterrupt:
            mobile_server.stop()
            console.print("\n[green]Mobile server stopped.[/green]")
        except Exception as exc:
            console.print(f"[red]Failed to start server: {exc}[/red]")
            raise typer.Exit(1)
    elif action == "stop":
        console.print("[bold]Stopping mobile server...[/bold]")
        mobile_server.stop()
        console.print("[green]Mobile server stopped.[/green]")
    elif action in ("pair", "url"):
        output = mobile_server.pair(label=label, host=host, port=port, tls=tls)
        console.print(output)
    elif action == "connect-info":
        info = mobile_server.connect_info(host=host, port=port)
        console.print(info)
    elif action == "tokens":
        token_list = mobile_server.tokens()
        if not token_list:
            console.print("[dim]No active tokens.[/dim]")
        else:
            for t in token_list:
                console.print(
                    f"  {t['hash_prefix']}  "
                    f"[dim]{t.get('created', '')}[/dim]  "
                    f"{t.get('label', '')}"
                )
    elif action == "cert-regen":
        try:
            info = mobile_server.cert_regen()
            console.print(f"[green]{info}[/green]")
        except Exception as exc:
            console.print(f"[red]Failed: {exc}[/red]")
            raise typer.Exit(1)
    elif action == "tunnel":
        # Auto-detect access mode (priority: Tailscale serve > named CF tunnel > quick CF tunnel)
        # Use --cf to force Cloudflare quick tunnel regardless of Tailscale availability.
        from core.mobile import get_tailscale_address
        _ts_ip = "" if cf else get_tailscale_address()
        _cf_config = Path.home() / ".cloudflared" / "config.yml"
        _named = _cf_config.exists()

        # Auto-detect screen session for task injection
        import subprocess as _sp_screen
        import os as _os_screen
        _screen_name = _os_screen.environ.get("RICET_SCREEN_SESSION", "")
        if not _screen_name:
            _screen_out = _sp_screen.run(
                ["screen", "-ls"], capture_output=True, text=True,
            )
            import re as _re_screen
            _screen_matches = _re_screen.findall(r'\d+\.(\S+)', _screen_out.stdout)
            # Prefer "research" session, fall back to first available
            if "research" in _screen_matches:
                _screen_name = "research"
            elif _screen_matches:
                _screen_name = _screen_matches[0]
        if _screen_name:
            console.print(f"[dim]Screen session: {_screen_name} (tasks will be injected)[/dim]")

        # Start mobile server on localhost (tailscale serve or CF tunnel will proxy to it)
        try:
            info = mobile_server.serve(host="127.0.0.1", port=port, tls=False, screen_session=_screen_name)
            console.print(f"[green]{info}[/green]")
        except OSError as exc:
            if "Address already in use" in str(exc):
                console.print(f"[yellow]Port {port} in use — stopping old server...[/yellow]")
                import subprocess as _sp
                _sp.run(f"fuser -k {port}/tcp", shell=True, capture_output=True)
                import time as _tw
                _tw.sleep(0.5)
                try:
                    info = mobile_server.serve(host="127.0.0.1", port=port, tls=False)
                    console.print(f"[green]{info}[/green]")
                except Exception as exc2:
                    console.print(f"[red]Still failed: {exc2}[/red]")
                    raise typer.Exit(1)
            else:
                console.print(f"[red]Failed to start server: {exc}[/red]")
                raise typer.Exit(1)
        except Exception as exc:
            console.print(f"[red]Failed to start server: {exc}[/red]")
            raise typer.Exit(1)

        from core.mobile import parse_tunnel_url, start_tunnel, generate_qr_terminal
        import shutil as _sh2

        if _ts_ip:
            # Tailscale serve: daemon proxies localhost:port → tailnet HTTPS
            # This works on any machine regardless of rp_filter/routing quirks.
            console.print(f"[bold]Starting Tailscale serve → tailnet HTTPS...[/bold]")
            import subprocess as _sp3
            _ts_result = _sp3.run(
                ["tailscale", "serve", "--bg", str(port)],
                capture_output=True, text=True,
            )
            if _ts_result.returncode != 0:
                console.print(f"[yellow]tailscale serve failed: {_ts_result.stderr.strip()}[/yellow]")
                console.print("[yellow]Hint: run 'sudo tailscale set --operator=$USER' once to avoid sudo[/yellow]")
                mobile_server.stop()
                raise typer.Exit(1)
            # Get the serve URL from tailscale status
            _ts_status = _sp3.run(
                ["tailscale", "status", "--json"],
                capture_output=True, text=True,
            )
            import json as _json
            try:
                _ts_data = _json.loads(_ts_status.stdout)
                _ts_hostname = _ts_data.get("Self", {}).get("DNSName", "").rstrip(".")
                public_url = f"https://{_ts_hostname}"
            except Exception:
                public_url = f"https://<tailscale-hostname>"
            proc = None
        else:
            console.print("[dim]Setting up cloudflared tunnel...[/dim]")
            _cf_bin = _sh2.which("cloudflared") or str(Path.home() / ".local" / "bin" / "cloudflared")
            if _named and Path(_cf_bin).exists():
                # Named tunnel: persistent URL
                import subprocess as _sp2
                proc = _sp2.Popen(
                    [_cf_bin, "tunnel", "run"],
                    stdout=_sp2.PIPE, stderr=_sp2.PIPE, text=True,
                )
                public_url = f"https://{_domain}"
                console.print(f"[dim]Named tunnel process started (PID {proc.pid})[/dim]")
            else:
                # Quick tunnel: ephemeral URL
                proc = start_tunnel(port=port)
                public_url = parse_tunnel_url(proc)
                if not public_url:
                    console.print("[red]Could not start tunnel. Check network connectivity.[/red]")
                    mobile_server.stop()
                    raise typer.Exit(1)

        console.print(f"\n[bold green]Public URL (open on your phone):[/bold green]")
        console.print(f"  {public_url}")
        qr = generate_qr_terminal(public_url)
        if qr:
            console.print(f"\n{qr}")
        # Persist URL to disk so other processes / Slack notifications can read it
        try:
            url_file = Path.home() / ".ricet" / "tunnel_url"
            url_file.parent.mkdir(parents=True, exist_ok=True)
            url_file.write_text(public_url + "\n")
            console.print(f"[dim]URL saved to {url_file}[/dim]")
        except Exception:
            pass
        console.print("[dim]Press Ctrl+C to stop.[/dim]")
        import signal

        try:
            signal.pause()
        except AttributeError:
            import time as _t

            while True:
                _t.sleep(3600)
        except KeyboardInterrupt:
            if proc is not None:
                proc.terminate()
            mobile_server.stop()
            console.print("\n[green]Server stopped.[/green]")
    elif action == "status":
        st = mobile_server.status()
        running = "[green]running[/green]" if st["running"] else "[dim]stopped[/dim]"
        tls_s = "[green]enabled[/green]" if st["tls"] else "[dim]disabled[/dim]"
        console.print(f"Server: {running}  Port: {st['port']}  TLS: {tls_s}")
        url_file = Path.home() / ".ricet" / "tunnel_url"
        if url_file.exists():
            console.print(f"Last tunnel URL: {url_file.read_text().strip()}")
    elif action == "persist":
        # Install a systemd user service so the server+tunnel auto-starts on login.
        import shutil as _sh
        import subprocess as _sp
        ricet_bin = _sh.which("ricet")
        if not ricet_bin:
            console.print("[red]'ricet' not found in PATH — install it first (pip install -e .)[/red]")
            raise typer.Exit(1)
        log_file = Path.home() / ".ricet" / "mobile.log"
        service_dir = Path.home() / ".config" / "systemd" / "user"
        service_dir.mkdir(parents=True, exist_ok=True)
        service_file = service_dir / "ricet-mobile.service"
        screen_env = f"Environment=RICET_SCREEN_SESSION=ricet\n"
        service_content = (
            "[Unit]\n"
            "Description=ricet mobile server + Cloudflare tunnel\n"
            "After=network-online.target\n"
            "Wants=network-online.target\n\n"
            "[Service]\n"
            "Type=simple\n"
            f"ExecStart={ricet_bin} mobile tunnel --no-tls --port {port}\n"
            "Restart=on-failure\n"
            "RestartSec=15\n"
            f"{screen_env}"
            f"StandardOutput=append:{log_file}\n"
            f"StandardError=append:{log_file}\n\n"
            "[Install]\n"
            "WantedBy=default.target\n"
        )
        service_file.write_text(service_content)
        console.print(f"[green]Service file written:[/green] {service_file}")
        try:
            _sp.run(["systemctl", "--user", "daemon-reload"], check=True, capture_output=True)
            _sp.run(["systemctl", "--user", "enable", "--now", "ricet-mobile"], check=True, capture_output=True)
            console.print("[green]Service enabled and started.[/green]")
        except Exception as exc:
            console.print(f"[yellow]systemctl failed ({exc}) — start manually:[/yellow]")
            console.print(f"  systemctl --user daemon-reload")
            console.print(f"  systemctl --user enable --now ricet-mobile")
        console.print(f"\nLogs:   tail -f {log_file}")
        console.print("Status: systemctl --user status ricet-mobile")
        console.print("Stop:   systemctl --user stop ricet-mobile")
        console.print(
            "\n[dim]Edit RICET_SCREEN_SESSION in the service file to match your "
            "screen session name for live voice injection.[/dim]"
        )
        console.print(f"  {service_file}")
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print(
            "Available: serve, stop, pair, tunnel, connect-info, tokens, cert-regen, status, persist"
        )
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
        url = site_manager.preview()
        console.print(f"[green]Preview running at {url}[/green]")
        console.print("[dim]Press Ctrl+C to stop.[/dim]")
        import signal

        try:
            signal.pause()
        except AttributeError:
            import time

            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            console.print("\n[green]Preview server stopped.[/green]")
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available: init, build, deploy, preview")
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
        method = claims[0].get("method", "") if claims else ""
        if method == "claude-verification":
            console.print(f"\n[bold]Claude verified {len(claims)} claim(s):[/bold]")
            for c in claims:
                conf_label = c.get("status", "low")
                color = {"high": "green", "medium": "yellow", "low": "red"}.get(
                    conf_label, "dim"
                )
                console.print(f"  [{color}][{conf_label}][/{color}] {c['claim']}")
                if c.get("reasoning"):
                    console.print(f"        [dim]{c['reasoning']}[/dim]")
                if c.get("needs_citation"):
                    console.print("        [yellow]^ needs citation[/yellow]")
        else:
            console.print(
                f"\n[bold]Extracted {len(claims)} claim(s) for review:[/bold]"
            )
            for c in claims:
                conf = f"{c['confidence']:.0%}"
                console.print(f"  [{conf}] {c['claim']}")
            console.print(
                "\n[dim]Claims extracted via Claude-powered verification. "
                "Cross-check with primary sources for critical results.[/dim]"
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
    if result.get("success"):
        console.print("[green]Issue resolved after auto-debug.[/green]")
        if result.get("fix_applied"):
            console.print(f"[bold]Fix applied:[/bold]\n{result.get('fix_applied')}")
    else:
        console.print("[yellow]Auto-debug could not fully resolve the issue.[/yellow]")
        if result.get("original_error"):
            console.print(f"[bold]Error:[/bold]\n{result.get('original_error')}")
        if result.get("fix_applied"):
            console.print(f"[bold]Attempted fix:[/bold]\n{result.get('fix_applied')}")


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

        # Also read mobile/voice inputs from state/TODO.md
        todo_path = Path("state/TODO.md")
        mobile_pending: list[str] = []
        mobile_done: list[str] = []
        if todo_path.exists():
            for line in todo_path.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith("- [ ]") and (
                    "[mobile" in stripped or "[voice" in stripped
                ):
                    mobile_pending.append(stripped)
                elif stripped.startswith("- [x]") and (
                    "[mobile" in stripped or "[voice" in stripped
                ):
                    mobile_done.append(stripped)

        total_queued = st["queued"] + len(mobile_pending)
        total_done = st["completed"] + len(mobile_done)

        console.print("[bold]Queue Status[/bold]")
        console.print(f"  Queued:    {total_queued}")
        console.print(f"  Running:   {st['running']}")
        console.print(f"  Completed: {total_done}")
        console.print(f"  Memory:    {st['memory_entries']} entries")
        if mobile_pending:
            console.print(
                f"\n[bold]Pending Mobile/Voice Inputs ({len(mobile_pending)}):[/bold]"
            )
            for item in mobile_pending:
                console.print(f"  {item}")
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
    branch: str = typer.Option(
        None,
        "--branch",
        "-b",
        help="Branch name for this user (auto-derived from git email if omitted)",
    ),
):
    """Adopt an existing repository as a Ricet project.

    Creates a personal branch for this user so multiple collaborators can work
    on the same repo independently. Use ``ricet morning-sync`` to merge all
    user branches into main.
    """
    from core.adopt import adopt_repo

    console.print(f"[bold]Adopting: {source}[/bold]")
    try:
        project_dir = adopt_repo(
            source,
            project_name=name,
            target_path=path,
            fork=not no_fork,
            branch=branch,
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


@app.command(name="morning-sync")
def morning_sync(
    main_branch: str = typer.Option("main", "--main", help="Integration branch name"),
    no_push: bool = typer.Option(False, "--no-push", help="Merge locally but don't push"),
):
    """Merge all user-* branches into main (run every morning).

    Pulls the latest from each collaborator's personal branch and fast-forwards
    or merges it into the main branch. Conflicts are reported and skipped.
    """
    from core.collaboration import morning_sync as _morning_sync

    console.print(f"[bold]Morning sync → {main_branch}[/bold]")
    results = _morning_sync(main_branch=main_branch, push=not no_push)
    if not results:
        console.print("[dim]No user branches found to merge.[/dim]")
        return
    for branch_name, status in results.items():
        if status == "merged":
            console.print(f"  [green]✓ {branch_name}[/green]")
        elif status == "conflict":
            console.print(f"  [red]✗ {branch_name} — conflict (skipped)[/red]")
        else:
            console.print(f"  [yellow]~ {branch_name}: {status}[/yellow]")
    merged = sum(1 for s in results.values() if s == "merged")
    console.print(f"[bold]Done: {merged}/{len(results)} branches merged.[/bold]")


@app.command()
def sync(
    push: bool = typer.Option(True, "--push/--no-push", help="Push after pull"),
):
    """Pull & rebase the current branch, then push. Safe daily workflow command."""
    from core.collaboration import sync_before_start

    console.print("[bold]Syncing current branch...[/bold]")
    ok = sync_before_start()
    if ok:
        console.print("[green]Up to date.[/green]")
        if push:
            import subprocess

            r = subprocess.run(
                ["git", "push"],
                capture_output=True,
                text=True,
                cwd=str(Path.cwd()),
            )
            if r.returncode == 0:
                console.print("[green]Pushed.[/green]")
            elif "Everything up-to-date" in r.stderr or "Everything up-to-date" in r.stdout:
                console.print("[dim]Nothing to push.[/dim]")
            else:
                console.print(f"[yellow]Push skipped: {r.stderr.strip()}[/yellow]")
    else:
        console.print("[red]Sync failed (conflict or no remote). Resolve manually.[/red]")
        raise typer.Exit(1)


@app.command()
def chub(
    action: str = typer.Argument(help="Action: search, get, annotate, feedback"),
    query_or_id: str = typer.Argument(help="Search query or doc ID"),
    extra: str = typer.Argument(None, help="Extra argument (note text, up/down)"),
    lang: str = typer.Option("py", "--lang", "-l", help="Language variant: py or js"),
    full: bool = typer.Option(False, "--full", help="Fetch full doc (not just summary)"),
):
    """Query context-hub for versioned API documentation.

    \b
    Examples:
      ricet chub search openai                # find available docs
      ricet chub get openai --lang py         # fetch Python API docs
      ricet chub get openai --full            # fetch complete reference
      ricet chub annotate openai "use v2 API" # add a local note
      ricet chub feedback openai up           # rate docs as helpful
    """
    import shutil
    import subprocess

    chub_bin = shutil.which("chub")
    if not chub_bin:
        console.print(
            "[red]chub not found. Run [bold]ricet init[/bold] to install it, "
            "or: npm install -g @aisuite/chub[/red]"
        )
        raise typer.Exit(1)

    cmd = ["chub", action, query_or_id]
    if action == "get":
        cmd += ["--lang", lang]
        if full:
            cmd += ["--full"]
    if extra:
        cmd.append(extra)

    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


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


@app.command(name="test-gen")
def test_gen(
    file: str = typer.Option(
        "", "--file", "-f", help="Specific file to generate tests for"
    ),
):
    """Auto-generate pytest tests for project code."""
    from core.auto_test import generate_tests_for_file, generate_tests_for_project

    if file:
        source = Path(file)
        if not source.exists():
            console.print(f"[red]File not found: {source}[/red]")
            raise typer.Exit(1)
        console.print(f"[bold]Generating tests for: {source}[/bold]")
        test_path = generate_tests_for_file(source)
        if test_path:
            console.print(f"[green]Tests written to: {test_path}[/green]")
            auto_commit(f"ricet test-gen: generated tests for {source.name}")
        else:
            console.print(
                "[yellow]Could not generate tests (Claude may be unavailable).[/yellow]"
            )
    else:
        project_path = Path.cwd()
        console.print(f"[bold]Generating tests for project: {project_path.name}[/bold]")
        generated = generate_tests_for_project(project_path)
        if generated:
            console.print(f"[green]Generated {len(generated)} test file(s):[/green]")
            for tp in generated:
                console.print(f"  {tp}")
            auto_commit(f"ricet test-gen: generated {len(generated)} test files")
        else:
            console.print(
                "[yellow]No test files generated. Check that .py files exist in src/ or project root.[/yellow]"
            )


@app.command()
def package(
    action: str = typer.Argument(help="Action: init, build, publish, publish-test"),
):
    """Prepare and publish your project as a pip package.

    \b
    ricet package init          # scaffold pyproject.toml
    ricet package build         # build sdist + wheel with uv
    ricet package publish       # upload to PyPI (needs PYPI_TOKEN in .env)
    ricet package publish-test  # upload to TestPyPI first (safer)
    """
    if action == "init":
        _package_init()
    elif action == "build":
        _package_build()
    elif action == "publish":
        _package_publish(test=False)
    elif action == "publish-test":
        _package_publish(test=True)
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available: init, build, publish, publish-test")
        raise typer.Exit(1)


def _package_init() -> None:
    """Generate a minimal pyproject.toml for the user's project."""
    from core.claude_helper import call_claude

    project_path = Path.cwd()
    pyproject = project_path / "pyproject.toml"
    if pyproject.exists():
        console.print(
            "[yellow]pyproject.toml already exists. Overwrite? (yes/no)[/yellow]"
        )
        confirm = typer.prompt("Overwrite?", default="no")
        if confirm.lower() not in ("yes", "y"):
            console.print("[dim]Aborted.[/dim]")
            return

    # Gather info
    project_name = typer.prompt("Package name", default=project_path.name)
    author = typer.prompt("Author name", default="")

    # Try to read GOAL.md for description
    description = ""
    goal_file = project_path / "knowledge" / "GOAL.md"
    if goal_file.exists():
        goal_text = goal_file.read_text()
        # Ask Claude to summarize into a one-liner
        summary = call_claude(
            "Summarize this research project description into a single "
            "sentence suitable for a Python package description (max 100 chars). "
            "Reply with just the sentence, no quotes.\n\n"
            f"{goal_text[:2000]}"
        )
        if summary:
            description = summary.strip().strip('"').strip("'")[:100]

    if not description:
        description = typer.prompt(
            "One-line description", default=f"{project_name} package"
        )

    content = f"""[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{project_name}"
version = "0.1.0"
description = "{description}"
requires-python = ">=3.11"
"""
    if author:
        content += f"""authors = [
    {{name = "{author}"}},
]
"""

    content += """
[project.scripts]
# Uncomment and edit to add a CLI entry point:
# my-tool = "src.main:main"
"""

    pyproject.write_text(content)
    console.print(f"[green]pyproject.toml created at {pyproject}[/green]")
    auto_commit(f"ricet package init: created pyproject.toml for {project_name}")


def _package_build() -> None:
    """Build the package using python -m build."""
    from core.onboarding import ensure_package as _ensure_pkg

    project_path = Path.cwd()
    pyproject = project_path / "pyproject.toml"
    if not pyproject.exists():
        console.print(
            "[red]No pyproject.toml found. Run 'ricet package init' first.[/red]"
        )
        raise typer.Exit(1)

    # Ensure build tool is available
    _ensure_pkg("build")

    console.print("[bold]Building package...[/bold]")
    result = subprocess.run(
        ["python", "-m", "build"],
        cwd=str(project_path),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        console.print("[green]Package built successfully.[/green]")
        dist_dir = project_path / "dist"
        if dist_dir.exists():
            for f in sorted(dist_dir.iterdir()):
                console.print(f"  {f.name}")
        auto_commit("ricet package build: built distribution")
    else:
        console.print("[red]Build failed:[/red]")
        console.print(result.stderr[-500:] if result.stderr else result.stdout[-500:])
        raise typer.Exit(1)


def _package_publish(test: bool = False) -> None:
    """Publish the package to PyPI using uv publish (falls back to twine)."""
    import os
    import shutil

    try:
        from dotenv import load_dotenv
        for env_cand in [Path.cwd() / ".env", Path.cwd() / "secrets" / ".env"]:
            if env_cand.exists():
                load_dotenv(env_cand, override=False)
                break
    except ImportError:
        pass

    project_path = Path.cwd()
    dist_dir = project_path / "dist"

    if not dist_dir.exists() or not list(dist_dir.iterdir()):
        console.print(
            "[red]No dist/ directory found. Run 'ricet package build' first.[/red]"
        )
        raise typer.Exit(1)

    token = os.getenv("PYPI_TOKEN", "")
    if not token:
        console.print(
            "[red]PYPI_TOKEN not set. Add to .env: PYPI_TOKEN=pypi-...[/red]"
        )
        console.print("[dim]Get token: https://pypi.org/manage/account/token/[/dim]")
        raise typer.Exit(1)

    registry = "https://test.pypi.org/legacy/" if test else "https://upload.pypi.org/legacy/"
    label = "TestPyPI" if test else "PyPI"

    console.print(f"[bold]Publishing to {label}...[/bold]")

    # Prefer uv publish (fast, no extra dependency)
    if shutil.which("uv"):
        env = {**os.environ, "UV_PUBLISH_TOKEN": token}
        cmd = ["uv", "publish", "--index-url", registry]
        if test:
            cmd += ["--trusted-publishing", "never"]
        result = subprocess.run(cmd, cwd=str(project_path), capture_output=True, text=True, env=env)
    else:
        # Fallback: twine
        subprocess.run(
            ["pip", "install", "-q", "twine"], capture_output=True
        )
        result = subprocess.run(
            ["python", "-m", "twine", "upload", "--repository-url", registry, "dist/*"],
            cwd=str(project_path), capture_output=True, text=True,
            env={**os.environ, "TWINE_USERNAME": "__token__", "TWINE_PASSWORD": token},
        )

    if result.returncode == 0:
        console.print(f"[green]Package published to {label} successfully.[/green]")
        if not test:
            auto_commit(f"ricet package publish: published to {label}")
    else:
        console.print(f"[red]Publish to {label} failed:[/red]")
        out = result.stderr or result.stdout
        console.print(out[-600:] if out else "(no output)")
        raise typer.Exit(1)


@app.command()
def zenodo(
    action: str = typer.Argument(help="Action: deposit, upload, publish, list, status"),
    deposition_id: str = typer.Option(None, "--id", "-i", help="Deposition ID"),
    files: str = typer.Option("", "--files", "-f", help="Comma-separated file paths to upload"),
    upload_type: str = typer.Option("software", "--type", "-t",
                                     help="Upload type: software, dataset, publication"),
    sandbox: bool = typer.Option(False, "--sandbox", help="Use sandbox.zenodo.org for testing"),
):
    """Publish software, datasets, and papers to Zenodo with a permanent DOI.

    \b
    Workflow:
      ricet zenodo deposit          # create draft from project metadata
      ricet zenodo upload --id 123 --files paper/main.pdf,dist/pkg.tar.gz
      ricet zenodo publish --id 123 # → get DOI
      ricet zenodo list             # list all depositions
      ricet zenodo status --id 123  # check status

    \b
    Set in .env:
      ZENODO_TOKEN=your-token       # from zenodo.org/account/settings/applications
      ZENODO_SANDBOX_TOKEN=token    # for testing on sandbox.zenodo.org
    """
    from core.zenodo import (
        create_deposition,
        deposit_from_project,
        get_deposition,
        list_depositions,
        publish_deposition,
        upload_file,
    )

    env_label = "[sandbox]" if sandbox else ""

    if action == "deposit":
        console.print(f"[bold]Creating Zenodo deposition {env_label}...[/bold]")
        file_list = [f.strip() for f in files.split(",") if f.strip()] or None
        dep = deposit_from_project(
            Path.cwd(), files=file_list, sandbox=sandbox, upload_type=upload_type
        )
        dep_id = dep["id"]
        html = dep.get("links", {}).get("html", f"https://zenodo.org/deposit/{dep_id}")
        console.print(f"[green]Deposition created: ID {dep_id}[/green]")
        console.print(f"  URL: {html}")
        console.print(f"  Status: {dep.get('state', 'draft')}")
        console.print("")
        console.print(f"  Next: ricet zenodo upload --id {dep_id} --files your_file.pdf")
        console.print(f"  Then: ricet zenodo publish --id {dep_id}")

    elif action == "upload":
        if not deposition_id:
            console.print("[red]--id is required for upload[/red]")
            raise typer.Exit(1)
        file_list = [f.strip() for f in files.split(",") if f.strip()]
        if not file_list:
            console.print("[red]--files is required for upload[/red]")
            raise typer.Exit(1)
        for f in file_list:
            fp = Path(f)
            if not fp.exists():
                console.print(f"[red]File not found: {f}[/red]")
                continue
            console.print(f"  Uploading {fp.name}...")
            result = upload_file(deposition_id, fp, sandbox=sandbox)
            console.print(f"  [green]✓ {fp.name} ({result.get('size', '?')} bytes)[/green]")

    elif action == "publish":
        if not deposition_id:
            console.print("[red]--id is required for publish[/red]")
            raise typer.Exit(1)
        console.print(f"[bold]Publishing deposition {deposition_id} {env_label}...[/bold]")
        result = publish_deposition(deposition_id, sandbox=sandbox)
        doi = result.get("doi", "")
        doi_url = result.get("doi_url", "")
        console.print(f"[green]Published![/green]")
        console.print(f"  DOI: {doi}")
        console.print(f"  URL: {doi_url or result.get('links', {}).get('record', '')}")
        auto_commit(f"ricet zenodo: published deposition {deposition_id} — DOI {doi}")

    elif action == "list":
        console.print(f"[bold]Zenodo depositions {env_label}:[/bold]")
        deps = list_depositions(sandbox=sandbox)
        if not deps:
            console.print("  No depositions found.")
        for d in deps:
            state = d.get("state", "?")
            title = d.get("title", "(no title)")
            doi = d.get("doi", "")
            color = "green" if state == "done" else "yellow"
            console.print(f"  [{color}]{d['id']}[/{color}] [{state}] {title}" + (f" — {doi}" if doi else ""))

    elif action == "status":
        if not deposition_id:
            console.print("[red]--id is required for status[/red]")
            raise typer.Exit(1)
        dep = get_deposition(deposition_id, sandbox=sandbox)
        console.print(f"[bold]Deposition {deposition_id}:[/bold]")
        console.print(f"  Title:  {dep.get('title', '?')}")
        console.print(f"  State:  {dep.get('state', '?')}")
        console.print(f"  DOI:    {dep.get('doi', 'not yet assigned')}")
        console.print(f"  Files:  {len(dep.get('files', []))}")
        for f in dep.get("files", []):
            console.print(f"    - {f.get('filename', '?')} ({f.get('filesize', '?')} bytes)")
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available: deposit, upload, publish, list, status")
        raise typer.Exit(1)


@app.command()
def audit():
    """Audit project code for half-baked features and stubs."""
    from core.doability import audit_feature_completeness

    project_path = Path.cwd()
    console.print("[bold]Auditing project for half-baked features...[/bold]")

    # Phase 1: fast heuristic scan
    heuristic_issues = audit_feature_completeness(project_path)

    # Phase 2: Claude deep audit (reads code, finds logic issues)
    console.print("[dim]Running Claude deep audit...[/dim]")
    from core.verification import fresh_agent_audit

    claude_result = fresh_agent_audit(project_path)
    claude_issues = claude_result.get("issues", [])

    # Merge results
    all_issues: list[dict] = []
    for issue in heuristic_issues:
        all_issues.append(issue)
    for issue in claude_issues:
        all_issues.append(
            {
                "file": issue.get("category", "general"),
                "line": 0,
                "issue": f"[{issue.get('severity', '?')}] {issue.get('description', '')}",
            }
        )

    score = claude_result.get("score", "?")
    console.print(f"\n[bold]Quality Score: {score}/10[/bold]")

    strengths = claude_result.get("strengths", [])
    if strengths:
        console.print("\n[bold]Strengths:[/bold]")
        for s in strengths:
            console.print(f"  [green]+ {s}[/green]")

    if all_issues:
        console.print(
            f"\n[bold yellow]Found {len(all_issues)} issue(s):[/bold yellow]"
        )
        for issue in all_issues:
            console.print(
                f"  [dim]{issue['file']}:{issue['line']}[/dim] {issue['issue']}"
            )
    else:
        console.print("[green]No half-baked features detected.[/green]")


@app.command(name="fresh-audit")
def fresh_audit():
    """Run a fresh-eyes audit of the project using Claude with no context."""
    from core.verification import fresh_agent_audit

    project_path = Path.cwd()
    console.print("[bold]Running fresh-agent audit (no prior context)...[/bold]")
    result = fresh_agent_audit(project_path)

    score = result.get("score", 0)
    if score >= 7:
        console.print(f"\n[bold green]Quality Score: {score}/10[/bold green]")
    elif score >= 4:
        console.print(f"\n[bold yellow]Quality Score: {score}/10[/bold yellow]")
    else:
        console.print(f"\n[bold red]Quality Score: {score}/10[/bold red]")

    strengths = result.get("strengths", [])
    if strengths:
        console.print("\n[bold]Strengths:[/bold]")
        for s in strengths:
            console.print(f"  [green]+ {s}[/green]")

    issues = result.get("issues", [])
    if issues:
        console.print("\n[bold]Issues:[/bold]")
        for issue in issues:
            severity = issue.get("severity", "medium")
            category = issue.get("category", "general")
            desc = issue.get("description", "")
            color = {"high": "red", "medium": "yellow", "low": "dim"}.get(
                severity, "white"
            )
            console.print(f"  [{color}][{severity}] {category}: {desc}[/{color}]")


@app.command(name="review-claude-md")
def review_claude_md_cmd():
    """Review and simplify the project's CLAUDE.md."""
    from core.auto_docs import review_claude_md

    project_path = Path.cwd()
    console.print("[bold]Reviewing CLAUDE.md...[/bold]")
    simplified = review_claude_md(project_path)

    if simplified is None:
        console.print(
            "[dim]CLAUDE.md not found or Claude unavailable.[/dim]"
        )
        return

    console.print(f"[green]Simplified to {len(simplified.splitlines())} lines.[/green]")
    console.print("\n[bold]Preview (first 20 lines):[/bold]")
    for line in simplified.splitlines()[:20]:
        console.print(f"  {line}")

    save = typer.prompt("\nSave simplified CLAUDE.md? (yes/no)", default="no")
    if save.lower() in ("yes", "y"):
        claude_md = project_path / ".claude" / "CLAUDE.md"
        if not claude_md.exists():
            claude_md = project_path / "CLAUDE.md"
        if claude_md.exists():
            claude_md.write_text(simplified)
            console.print(f"[green]Saved to {claude_md}[/green]")
            auto_commit("ricet review-claude-md: simplified CLAUDE.md")
        else:
            console.print("[red]Could not find CLAUDE.md to save.[/red]")
    else:
        console.print("[dim]Not saved.[/dim]")


@app.command()
def voice(
    duration: int = typer.Option(
        30, "--duration", "-t", help="Recording duration in seconds"
    ),
):
    """Record a voice prompt, transcribe, and execute."""
    from core.voice import voice_prompt

    console.print(f"[bold]Recording for {duration}s... Speak now.[/bold]")
    prompt = voice_prompt(duration=duration)
    if prompt:
        console.print(f"\n[green]Transcribed prompt:[/green]\n{prompt}")
    else:
        console.print("[red]No audio captured or transcription failed.[/red]")
        console.print("")
        console.print("[bold]Possible causes:[/bold]")
        console.print(
            "  1. No microphone on this machine (common on remote servers)"
        )
        console.print("  2. Whisper not installed: pip install openai-whisper")
        console.print(
            "  3. No recorder: mamba install -c conda-forge alsa-utils (Linux)"
        )
        console.print("")
        console.print("[bold]Alternatives for remote servers:[/bold]")
        console.print(
            "  - Use the Voice tab in the mobile PWA: ricet mobile start --no-tls"
        )
        console.print(
            "  - Record on your local machine, then transcribe:"
        )
        console.print(
            "    scp recording.wav server:~/recording.wav"
        )
        console.print(
            '    python -c "import whisper; m=whisper.load_model(\'base\'); '
            'print(m.transcribe(\'recording.wav\')[\'text\'])"'
        )


# ---------------------------------------------------------------------------
# Code RAG – index and search external/legacy codebases
# ---------------------------------------------------------------------------


@app.command(name="index-code")
def index_code(
    path: str = typer.Argument(help="Directory to index"),
    output: str = typer.Option(
        "state/code_index.md", "--output", "-o",
        help="Output file for the index",
    ),
):
    """Index a codebase for RAG search (functions, classes, signatures)."""
    from core.code_index import build_index

    root = Path(path).resolve()
    out = Path(output)
    if not out.is_absolute():
        out = Path.cwd() / out

    index_text = build_index(root, output=out)
    n_files = index_text.count("###")
    console.print(f"[green]Indexed {n_files} files → {out}[/green]")
    console.print(f"Search with: [bold]ricet search-code \"your query\"[/bold]")


@app.command(name="search-code")
def search_code(
    query: str = typer.Argument(help="Search query"),
    index: str = typer.Option(
        "state/code_index.md", "--index", "-i",
        help="Code index file to search",
    ),
    top_k: int = typer.Option(5, "--top", "-k", help="Number of results"),
):
    """Search indexed code via semantic similarity."""
    index_path = Path(index)
    if not index_path.is_absolute():
        index_path = Path.cwd() / index_path
    if not index_path.exists():
        console.print(f"[red]Index not found: {index_path}[/red]")
        console.print("Run first: [bold]ricet index-code <path>[/bold]")
        raise typer.Exit(1)

    from core.rag import search
    results = search(query, encyclopedia_path=str(index_path), top_k=top_k)
    if not results:
        console.print("[dim]No results found.[/dim]")
        return
    console.print(f"[bold]Top {len(results)} results for:[/bold] {query}\n")
    for i, (text, score) in enumerate(results, 1):
        console.print(f"  {i}. [cyan]{score:.3f}[/cyan] {text.strip()[:120]}")


# ---------------------------------------------------------------------------
# Lab/Stable promotion – chaos → validated
# ---------------------------------------------------------------------------


@app.command()
def promote(
    path: str = typer.Argument(help="File to promote (e.g. lab/analysis.py)"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip falsification check"),
):
    """Promote a lab/ file to stable/ after validation."""
    from core.promotion import promote_file
    result = promote_file(Path(path), force=force)
    if result["ok"]:
        console.print(f"[green]Promoted → {result['dest']}[/green]")
        if result.get("provenance"):
            console.print(f"  Provenance: {result['provenance']}")
    else:
        console.print(f"[red]Promotion failed: {result['error']}[/red]")


# ---------------------------------------------------------------------------
# Feature requests – for ricet's own development
# ---------------------------------------------------------------------------

_FEATURE_REQUESTS_FILE = Path(__file__).parent.parent / "state" / "feature_requests.md"


@app.command(name="feature-request")
def feature_request(
    description: str = typer.Argument(help="Description of the feature request"),
    source: str = typer.Option("cli", "--source", "-s", help="Source: cli, github, mobile"),
):
    """Log a feature request for ricet development."""
    from datetime import datetime
    _FEATURE_REQUESTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not _FEATURE_REQUESTS_FILE.exists():
        _FEATURE_REQUESTS_FILE.write_text(
            "# Feature Requests\n\n"
            "Accumulated feature requests for ricet development.\n\n"
            "| Date | Source | Description | Status |\n"
            "|------|--------|-------------|--------|\n"
        )
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    desc_escaped = description.replace("|", "\\|")
    with _FEATURE_REQUESTS_FILE.open("a") as f:
        f.write(f"| {ts} | {source} | {desc_escaped} | pending |\n")
    console.print(f"[green]Feature request logged.[/green]")
    console.print(f"  View: [bold]cat {_FEATURE_REQUESTS_FILE}[/bold]")
    console.print(f"  Implement: [bold]ricet implement-features[/bold]")


@app.command(name="implement-features")
def implement_features(
    max_parallel: int = typer.Option(3, "--parallel", "-p", help="Max parallel agents"),
):
    """Review pending feature requests and implement selected ones in parallel worktrees."""
    if not _FEATURE_REQUESTS_FILE.exists():
        console.print("[dim]No feature requests found.[/dim]")
        raise typer.Exit(0)

    lines = _FEATURE_REQUESTS_FILE.read_text().splitlines()
    pending = []
    for i, line in enumerate(lines):
        if "| pending |" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 5:
                pending.append({"index": i, "date": parts[1], "source": parts[2], "desc": parts[3]})

    if not pending:
        console.print("[dim]No pending feature requests.[/dim]")
        raise typer.Exit(0)

    console.print(f"[bold]Pending feature requests ({len(pending)}):[/bold]\n")
    for j, item in enumerate(pending, 1):
        console.print(f"  {j}. [{item['date']}] ({item['source']}) {item['desc']}")

    console.print(f"\n[bold]Select features to implement (comma-separated numbers, or 'all'):[/bold]")
    import sys
    selection = input("> ").strip()
    if not selection:
        console.print("[dim]No selection made.[/dim]")
        return

    if selection.lower() == "all":
        selected = pending
    else:
        indices = []
        for s in selection.split(","):
            s = s.strip()
            if s.isdigit() and 1 <= int(s) <= len(pending):
                indices.append(int(s) - 1)
        selected = [pending[i] for i in indices]

    if not selected:
        console.print("[dim]No valid features selected.[/dim]")
        return

    console.print(f"\n[bold]Implementing {len(selected)} feature(s)...[/bold]")

    import subprocess as sp
    from core.git_worktrees import create_worktree, remove_worktree

    results = []
    for item in selected[:max_parallel]:
        branch_name = "feature/" + item["desc"][:40].lower().replace(" ", "-").replace("/", "-")
        branch_name = "".join(c for c in branch_name if c.isalnum() or c in "-_/")
        console.print(f"\n  [cyan]→ {branch_name}[/cyan]: {item['desc']}")

        wt = create_worktree(branch_name)
        if not wt:
            console.print(f"    [red]Failed to create worktree[/red]")
            results.append({"desc": item["desc"], "ok": False, "error": "worktree failed"})
            continue

        console.print(f"    Worktree: {wt}")
        console.print(f"    [yellow]Spawning agent...[/yellow]")

        # Spawn claude in the worktree to implement the feature
        proc = sp.run(
            ["claude", "-p", f"Implement this feature request for ricet: {item['desc']}. "
             "Read CLAUDE.md first. Make minimal, focused changes. Commit when done."],
            cwd=str(wt),
            capture_output=True,
            text=True,
            timeout=600,
        )

        ok = proc.returncode == 0
        results.append({"desc": item["desc"], "ok": ok, "branch": branch_name})
        if ok:
            console.print(f"    [green]Done[/green]")
        else:
            console.print(f"    [red]Agent failed (exit {proc.returncode})[/red]")

    console.print(f"\n[bold]Results:[/bold]")
    for r in results:
        status = "[green]OK[/green]" if r["ok"] else "[red]FAIL[/red]"
        console.print(f"  {status} {r['desc']}")
        if r.get("branch"):
            console.print(f"        Branch: {r['branch']}")


# ---------------------------------------------------------------------------
# gstack – startup workflow skills (global install)
# ---------------------------------------------------------------------------

_GSTACK_DIR = Path.home() / ".claude" / "skills" / "gstack"
_GSTACK_REPO = "https://github.com/garrytan/gstack.git"
_GSTACK_ALL_SKILLS = [
    "plan-ceo-review", "plan-eng-review", "review", "ship",
    "browse", "qa", "setup-browser-cookies", "retro",
]
_GSTACK_BROWSER_SKILLS = {"browse", "qa", "setup-browser-cookies"}


@app.command(name="gstack")
def gstack_cmd(
    action: str = typer.Argument(
        "status",
        help="Action: install, update, status",
    ),
    skip_browser: bool = typer.Option(
        False, "--skip-browser",
        help="Install Markdown-only skills without bun/browser binary",
    ),
):
    """Manage gstack startup workflow skills (global install)."""
    import shutil
    import subprocess as sp

    skills_dir = Path.home() / ".claude" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    def _has_bun() -> bool:
        return shutil.which("bun") is not None

    def _symlink_skills(browser: bool = True):
        """Create skill symlinks in ~/.claude/skills/."""
        for skill in _GSTACK_ALL_SKILLS:
            if not browser and skill in _GSTACK_BROWSER_SKILLS:
                continue
            skill_dir = _GSTACK_DIR / skill
            if not skill_dir.is_dir():
                continue
            link = skills_dir / skill
            if link.exists() or link.is_symlink():
                link.unlink()
            link.symlink_to(f"gstack/{skill}")

    if action == "install":
        if _GSTACK_DIR.exists():
            console.print("[yellow]gstack already installed.[/yellow] Use: ricet gstack update")
            raise typer.Exit(0)

        has_bun = _has_bun()
        if not has_bun and not skip_browser:
            console.print("[yellow]bun not found.[/yellow] /browse and /qa need bun to compile the browser binary.")
            console.print("  Install bun:  curl -fsSL https://bun.sh/install | bash")
            console.print("  Or run:       ricet gstack install --skip-browser")
            console.print("                (installs 5 Markdown-only skills without the browser)")
            raise typer.Exit(1)

        console.print("[bold]Cloning gstack...[/bold]")
        sp.run(["git", "clone", _GSTACK_REPO, str(_GSTACK_DIR)], check=True)

        if not skip_browser and has_bun:
            console.print("[bold]Running gstack setup (building browser binary)...[/bold]")
            sp.run(["bash", "./setup"], cwd=str(_GSTACK_DIR), check=True)
        else:
            console.print("[bold]Symlinking Markdown-only skills (skipping browser)...[/bold]")
            _symlink_skills(browser=False)

        # Also symlink gstack-upgrade
        upgrade_link = skills_dir / "gstack-upgrade"
        if not upgrade_link.exists():
            upgrade_src = _GSTACK_DIR / "gstack-upgrade"
            if upgrade_src.exists():
                upgrade_link.symlink_to("gstack/gstack-upgrade")

        version_file = _GSTACK_DIR / "VERSION"
        version = version_file.read_text().strip() if version_file.exists() else "unknown"
        console.print(f"\n[green]gstack v{version} installed.[/green]")
        installed = [s for s in _GSTACK_ALL_SKILLS if (skills_dir / s).exists()]
        console.print(f"Skills: {', '.join('/' + s for s in installed)}")

    elif action == "update":
        if not _GSTACK_DIR.exists():
            console.print("[red]gstack not installed.[/red] Run: ricet gstack install")
            raise typer.Exit(1)

        old_ver = ""
        version_file = _GSTACK_DIR / "VERSION"
        if version_file.exists():
            old_ver = version_file.read_text().strip()

        console.print("[bold]Updating gstack...[/bold]")
        sp.run(["git", "pull", "origin", "main"], cwd=str(_GSTACK_DIR), check=True)

        if _has_bun() and (_GSTACK_DIR / "setup").exists():
            sp.run(["bash", "./setup"], cwd=str(_GSTACK_DIR), check=True)
        else:
            _symlink_skills(browser=False)

        new_ver = version_file.read_text().strip() if version_file.exists() else "unknown"
        if old_ver and old_ver != new_ver:
            console.print(f"[green]Updated: v{old_ver} → v{new_ver}[/green]")
        else:
            console.print(f"[green]gstack v{new_ver} up to date.[/green]")

    elif action == "status":
        if not _GSTACK_DIR.exists():
            console.print("[dim]gstack not installed.[/dim] Run: ricet gstack install")
            raise typer.Exit(0)

        version_file = _GSTACK_DIR / "VERSION"
        version = version_file.read_text().strip() if version_file.exists() else "unknown"
        console.print(f"[bold]gstack v{version}[/bold]")

        has_bun = _has_bun()
        browse_bin = _GSTACK_DIR / "browse" / "dist" / "browse"
        console.print(f"  bun:            {'installed' if has_bun else 'not found'}")
        console.print(f"  browser binary: {'built' if browse_bin.exists() else 'not built'}")
        console.print(f"  location:       {_GSTACK_DIR}")
        console.print()

        for skill in _GSTACK_ALL_SKILLS:
            link = skills_dir / skill
            active = link.exists() or link.is_symlink()
            icon = "[green]active[/green]" if active else "[dim]not linked[/dim]"
            console.print(f"  /{skill:.<28s} {icon}")
    else:
        console.print(f"[red]Unknown action: {action}[/red]. Use: install, update, status")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
