"""Plot gallery: scan, organize, and display figures by run."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

FIGURES_DIR = Path("figures")

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf", ".svg", ".eps"}


@dataclass
class FigureEntry:
    path: Path
    name: str
    format: str
    size_kb: float
    run_id: str = ""


def scan_figures(
    figures_dir: Path = FIGURES_DIR,
) -> list[FigureEntry]:
    """Scan a directory for figure files.

    Args:
        figures_dir: Directory to scan.

    Returns:
        List of FigureEntry objects sorted by modification time.
    """
    if not figures_dir.exists():
        return []

    entries = []
    for item in sorted(figures_dir.rglob("*"), key=lambda p: p.stat().st_mtime):
        if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS:
            # Try to extract run_id from parent directory name
            run_id = ""
            if item.parent != figures_dir:
                run_id = item.parent.name

            entries.append(
                FigureEntry(
                    path=item,
                    name=item.stem,
                    format=item.suffix.lstrip("."),
                    size_kb=round(item.stat().st_size / 1024, 1),
                    run_id=run_id,
                )
            )

    return entries


def organize_by_run(figures: list[FigureEntry]) -> dict[str, list[FigureEntry]]:
    """Group figures by their run ID.

    Args:
        figures: List of FigureEntry objects.

    Returns:
        Dict mapping run_id -> list of figures. Unassociated figures use key "".
    """
    by_run: dict[str, list[FigureEntry]] = {}
    for fig in figures:
        key = fig.run_id or "(no run)"
        by_run.setdefault(key, []).append(fig)
    return by_run


def display_gallery(
    figures_dir: Path = FIGURES_DIR,
) -> str:
    """Generate a text-based gallery summary.

    Args:
        figures_dir: Directory to scan.

    Returns:
        Formatted gallery text.
    """
    figures = scan_figures(figures_dir)
    if not figures:
        return "No figures found."

    by_run = organize_by_run(figures)
    lines = [f"Figure Gallery ({len(figures)} total)", "=" * 40]

    for run_id, figs in sorted(by_run.items()):
        lines.append(f"\n  Run: {run_id}")
        for fig in figs:
            lines.append(f"    {fig.name}.{fig.format} ({fig.size_kb} KB)")

    return "\n".join(lines)
