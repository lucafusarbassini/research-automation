"""Slide deck generation for ricet projects.

Manages the slides/ directory inside a ricet project:
- ``setup_slides()`` copies template files from the bundled templates
- ``create_slides()`` runs the slide-maker agent to generate ``make_slides.py``
- ``build_slides()`` runs the generated script to produce the ``.pptx``

Template files live in ``templates/slides/`` and are deployed into the
project's ``slides/`` directory, matching the sandbox deployment pattern.
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

TEMPLATE_SLIDES_DIR = Path(__file__).resolve().parent.parent / "templates" / "slides"

FILES_TO_COPY = [
    "slide_utils.py",
    "slides_task.md",
    "make_slides_example.py",
]


def get_slides_dir(project_path: Path) -> Path:
    """Return the slides/ directory inside the project."""
    return project_path / "slides"


def has_slides(project_path: Path) -> bool:
    """Return True if the project has slide infrastructure set up."""
    sdir = get_slides_dir(project_path)
    return (sdir / "slide_utils.py").exists() and (sdir / "slides_task.md").exists()


def setup_slides(
    project_path: Path,
    *,
    print_fn=print,
) -> bool:
    """Copy slide template files into the project's slides/ directory.

    Args:
        project_path: Root of the ricet project.
        print_fn: Callable for status messages.

    Returns:
        True if setup succeeded.
    """
    if not TEMPLATE_SLIDES_DIR.exists():
        logger.error("Slides templates not found at %s", TEMPLATE_SLIDES_DIR)
        return False

    dest = get_slides_dir(project_path)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "slides_output").mkdir(exist_ok=True)

    for fname in FILES_TO_COPY:
        src = TEMPLATE_SLIDES_DIR / fname
        if src.exists():
            shutil.copy2(src, dest / fname)
            print_fn(f"Copied {fname}")
        else:
            logger.warning("Template file missing: %s", src)

    print_fn(f"Slides infrastructure ready at {dest}")
    return True


def _write_task_file(
    project_path: Path,
    *,
    title: str,
    audience: str,
    duration: str,
    key_message: str,
    emphasis: list[str],
    skip: list[str],
    schematics_n: int = 4,
    schematics_descriptions: Optional[list[str]] = None,
    author: str = "",
    date: str = "",
    source_path: Optional[str] = None,
    source_url: Optional[str] = None,
) -> Path:
    """Write the slides_task.md file with the provided parameters.

    Returns the path to the written file.
    """
    lines = ["# Slide Deck Task\n", "## Source\n"]

    if source_path:
        lines.append(f"**Codebase path**: {source_path}\n")
    elif source_url:
        lines.append(f"**Website URL**: {source_url}\n")
    else:
        # Default: point to the project root
        lines.append(f"**Codebase path**: {project_path}\n")

    lines.append("\n## Presentation Context\n")
    lines.append(f"**Title**: {title}\n")
    lines.append(f"**Audience**: {audience}\n")
    lines.append(f"**Duration**: {duration}\n")
    lines.append(f"**Key message**: {key_message}\n")

    lines.append("\n## What to Emphasize\n")
    for i, point in enumerate(emphasis, 1):
        lines.append(f"{i}. {point}\n")

    lines.append("\n## What to Skip\n")
    for point in skip:
        lines.append(f"- {point}\n")
    if not skip:
        lines.append("- (nothing specific)\n")

    lines.append(f"\n## Schematics (N={schematics_n})\n")
    if schematics_descriptions:
        for i, desc in enumerate(schematics_descriptions, 1):
            lines.append(f"{i}. {desc}\n")
    else:
        for i in range(1, schematics_n + 1):
            lines.append(f"{i}. [Agent will decide based on project analysis]\n")

    lines.append("\n## Author & Date\n")
    lines.append(f"**Author**: {author or 'Research Team'}\n")
    lines.append(f"**Date**: {date or 'TBD'}\n")

    task_file = get_slides_dir(project_path) / "slides_task.md"
    task_file.write_text("".join(lines))
    return task_file


def _load_google_api_key(project_path: Path) -> Optional[str]:
    """Load GOOGLE_API_KEY from environment, project .env, or global credentials."""
    # 1. Already in environment
    key = os.environ.get("GOOGLE_API_KEY")
    if key:
        return key

    # 2. Project secrets/.env
    env_file = project_path / "secrets" / ".env"
    if not env_file.exists():
        env_file = project_path / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("GOOGLE_API_KEY="):
                val = line.partition("=")[2].strip().strip("'\"")
                if val:
                    return val

    # 3. Global credential store
    try:
        from core.credential_store import load_global_credentials

        creds = load_global_credentials()
        if "GOOGLE_API_KEY" in creds:
            return creds["GOOGLE_API_KEY"]
    except ImportError:
        pass

    return None


def create_slides(
    project_path: Path,
    *,
    title: str,
    audience: str = "Technical peers",
    duration: str = "15 minutes",
    key_message: str = "",
    emphasis: Optional[list[str]] = None,
    skip: Optional[list[str]] = None,
    schematics_n: int = 4,
    author: str = "",
    source_path: Optional[str] = None,
    source_url: Optional[str] = None,
    dangerously_skip_permissions: bool = False,
) -> Path:
    """Run the slide-maker agent to generate make_slides.py.

    Writes ``slides_task.md`` with the given parameters, then invokes the
    slide-maker agent (via claude-flow or direct Claude CLI) to analyze the
    project and write the slide generation script.

    Args:
        project_path: Root of the ricet project.
        title: Presentation title.
        audience: Target audience description.
        duration: Presentation duration.
        key_message: The one thing the audience should remember.
        emphasis: Points to emphasize (3-5 items).
        skip: Things to skip.
        schematics_n: Number of schematics to generate.
        author: Author name.
        source_path: Codebase path to analyze (defaults to project root).
        source_url: Website URL to analyze (alternative to source_path).
        dangerously_skip_permissions: Skip permission checks (overnight mode).

    Returns:
        Path to the generated ``make_slides.py``.
    """
    if not has_slides(project_path):
        setup_slides(project_path)

    _write_task_file(
        project_path,
        title=title,
        audience=audience,
        duration=duration,
        key_message=key_message,
        emphasis=emphasis or [],
        skip=skip or [],
        schematics_n=schematics_n,
        author=author,
        source_path=source_path,
        source_url=source_url,
    )

    # Run the slide-maker agent
    from core.agents import AgentType, execute_agent_task

    task_desc = (
        f"Read slides/slides_task.md and analyze the project to create a presentation. "
        f"Title: {title}. Audience: {audience}. Duration: {duration}. "
        f"Write slides/make_slides.py that generates {schematics_n} schematics "
        f"and builds a complete .pptx deck."
    )

    result = execute_agent_task(
        AgentType.SLIDE_MAKER,
        task_desc,
        dangerously_skip_permissions=dangerously_skip_permissions,
    )

    make_slides_path = get_slides_dir(project_path) / "make_slides.py"

    if result.status in ("success", "completed"):
        logger.info("Slide-maker agent completed: %s", result.status)
    else:
        logger.warning("Slide-maker agent status: %s", result.status)

    return make_slides_path


def build_slides(project_path: Path) -> Path:
    """Run make_slides.py to generate the .pptx presentation.

    Ensures GOOGLE_API_KEY is available (env → project .env → global creds),
    then runs the script in the slides/ directory.

    Args:
        project_path: Root of the ricet project.

    Returns:
        Path to the generated presentation.pptx.

    Raises:
        FileNotFoundError: If make_slides.py doesn't exist.
        RuntimeError: If the build fails.
    """
    slides_dir = get_slides_dir(project_path)
    make_slides = slides_dir / "make_slides.py"

    if not make_slides.exists():
        raise FileNotFoundError(
            f"No make_slides.py found at {make_slides}. "
            f"Run 'ricet slides create' first."
        )

    # Set up GOOGLE_API_KEY in environment for the subprocess
    env = os.environ.copy()
    api_key = _load_google_api_key(project_path)
    if api_key:
        env["GOOGLE_API_KEY"] = api_key
    else:
        logger.warning(
            "GOOGLE_API_KEY not found. Schematics will fail but deck structure "
            "will still be generated."
        )

    try:
        proc = subprocess.run(
            ["python3", str(make_slides)],
            cwd=str(slides_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Slide build timed out after 5 minutes.")

    if proc.returncode != 0:
        raise RuntimeError(
            f"Slide build failed (exit {proc.returncode}):\n{proc.stderr}"
        )

    output_pptx = slides_dir / "slides_output" / "presentation.pptx"
    if not output_pptx.exists():
        # Check if the script saved elsewhere
        for pptx in slides_dir.rglob("*.pptx"):
            output_pptx = pptx
            break

    return output_pptx
