"""Adopt existing repositories as Ricet projects.

``adopt_repo`` takes a GitHub URL or local path, optionally forks it,
overlays the ricet workspace structure, and registers it as a project.
"""

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".ricet"


def adopt_repo(
    source: str,
    *,
    project_name: str | None = None,
    target_path: str | Path | None = None,
    fork: bool = True,
    run_cmd=None,
) -> Path:
    """Transform an existing repo into a Ricet project.

    Args:
        source: A GitHub URL or local directory path.
        project_name: Name for the project (derived from URL/path if None).
        target_path: Where to place the repo locally (defaults to cwd).
        fork: If True and *source* is a URL, fork via ``gh repo fork``.
        run_cmd: Optional ``callable(cmd_list, **kw) -> CompletedProcess``
                 override for testing.

    Returns:
        Path to the adopted project directory.
    """
    if run_cmd is None:

        def run_cmd(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                **kwargs,
            )

    is_url = (
        source.startswith("http://")
        or source.startswith("https://")
        or source.startswith("git@")
    )

    if project_name is None:
        # Derive from last path component
        project_name = source.rstrip("/").split("/")[-1]
        if project_name.endswith(".git"):
            project_name = project_name[:-4]

    if is_url:
        base = Path(target_path) if target_path else Path.cwd()
        project_dir = base / project_name

        if fork:
            r = run_cmd(
                [
                    "gh",
                    "repo",
                    "fork",
                    source,
                    "--clone",
                    "--clone-dir",
                    str(project_dir),
                ]
            )
            if r.returncode != 0:
                logger.warning(
                    "gh repo fork failed, falling back to git clone: %s",
                    r.stderr.strip(),
                )
                r = run_cmd(["git", "clone", source, str(project_dir)])
                if r.returncode != 0:
                    raise RuntimeError(f"git clone failed: {r.stderr.strip()}")
        else:
            r = run_cmd(["git", "clone", source, str(project_dir)])
            if r.returncode != 0:
                raise RuntimeError(f"git clone failed: {r.stderr.strip()}")
    else:
        project_dir = Path(source).resolve()
        if not project_dir.is_dir():
            raise FileNotFoundError(f"Source directory not found: {source}")

    # Overlay ricet structure
    _overlay_structure(project_dir)

    # Pre-fill GOAL.md from README
    _prefill_goal_from_readme(project_dir)

    # Register in ~/.ricet/projects.json
    _register_project(project_name, project_dir)

    # Auto-commit the scaffolding
    from core.auto_commit import auto_commit

    auto_commit(
        f"ricet adopt: scaffolded project {project_name}",
        cwd=project_dir,
        run_cmd=run_cmd,
    )

    return project_dir


def _overlay_structure(project_dir: Path) -> None:
    """Create ricet workspace dirs without overwriting existing files."""
    from core.onboarding import setup_workspace

    setup_workspace(project_dir)

    # Create knowledge dir
    knowledge_dir = project_dir / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    goal_file = knowledge_dir / "GOAL.md"
    if not goal_file.exists():
        goal_file.write_text(
            "# Project Goal\n\n"
            "<!-- Describe the research goal for this adopted project. -->\n\n"
        )

    # Create state files
    state_dir = project_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "sessions").mkdir(parents=True, exist_ok=True)

    todo = state_dir / "TODO.md"
    if not todo.exists():
        todo.write_text(
            "# TODO\n\n"
            "- [ ] Review existing codebase\n"
            "- [ ] Edit GOAL.md with research description\n"
            "- [ ] Run ricet start\n"
        )

    progress = state_dir / "PROGRESS.md"
    if not progress.exists():
        progress.write_text("# Progress\n\n")

    # Config
    config_dir = project_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    settings_file = config_dir / "settings.yml"
    if not settings_file.exists():
        import yaml

        settings_file.write_text(
            yaml.dump(
                {
                    "project": {"name": project_dir.name, "adopted": True},
                    "compute": {"type": "local-cpu"},
                    "notifications": {"enabled": False, "method": "none"},
                    "features": {"website": False, "mobile": False},
                },
                default_flow_style=False,
                sort_keys=False,
            )
        )

    # .gitattributes for union merge strategy
    gitattrs = project_dir / ".gitattributes"
    existing = gitattrs.read_text() if gitattrs.exists() else ""
    lines_to_add = []
    if "knowledge/ENCYCLOPEDIA.md" not in existing:
        lines_to_add.append("knowledge/ENCYCLOPEDIA.md merge=union")
    if "state/PROGRESS.md" not in existing:
        lines_to_add.append("state/PROGRESS.md merge=union")
    if lines_to_add:
        with open(gitattrs, "a") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write("\n".join(lines_to_add) + "\n")


def _prefill_goal_from_readme(project_dir: Path) -> None:
    """If a README exists, extract content into GOAL.md."""
    readme_candidates = ["README.md", "README.rst", "README.txt", "README"]
    readme_text = ""
    for name in readme_candidates:
        rp = project_dir / name
        if rp.exists():
            readme_text = rp.read_text(errors="replace")[:4000]
            break

    if not readme_text:
        return

    goal_file = project_dir / "knowledge" / "GOAL.md"
    if goal_file.exists():
        current = goal_file.read_text()
        # Only pre-fill if still has placeholder
        if "Describe the research goal" in current or len(current.strip()) < 50:
            goal_file.write_text(
                "# Project Goal\n\n"
                "<!-- Extracted from README -- edit to describe your research goal. -->\n\n"
                f"{readme_text}\n"
            )


def _register_project(name: str, path: Path) -> None:
    """Register project in ~/.ricet/projects.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    projects_file = CONFIG_DIR / "projects.json"

    projects: list[dict] = []
    if projects_file.exists():
        try:
            projects = json.loads(projects_file.read_text())
        except (json.JSONDecodeError, OSError):
            projects = []

    # Remove existing entry with same name
    projects = [p for p in projects if p.get("name") != name]

    # Deactivate all others
    for p in projects:
        p["active"] = False

    projects.append(
        {
            "name": name,
            "path": str(path),
            "active": True,
        }
    )

    projects_file.write_text(json.dumps(projects, indent=2))
