"""Paper pipeline: figure generation, citation management, and LaTeX compilation."""

import logging
import re
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PAPER_DIR = Path("paper")
FIGURES_DIR = Path("figures")
BIB_FILE = PAPER_DIR / "references.bib"

# Colorblind-safe palette
COLORS = {
    "blue": "#0077BB",
    "orange": "#EE7733",
    "green": "#009988",
    "red": "#CC3311",
    "purple": "#AA3377",
    "grey": "#BBBBBB",
}

# matplotlib rcParams for publication-quality figures
RC_PARAMS = {
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica"],
    "font.size": 10,
    "axes.labelsize": 10,
    "axes.titlesize": 11,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.figsize": (3.5, 2.5),
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.format": "pdf",
    "savefig.bbox": "tight",
    "axes.linewidth": 0.8,
    "lines.linewidth": 1.0,
    "axes.spines.top": False,
    "axes.spines.right": False,
}


def apply_rcparams() -> None:
    """Apply publication-quality matplotlib rcParams."""
    import matplotlib.pyplot as plt

    plt.rcParams.update(RC_PARAMS)


def add_citation(
    key: str,
    entry_type: str = "article",
    *,
    author: str,
    title: str,
    year: str,
    journal: str = "",
    doi: str = "",
    url: str = "",
    bib_file: Path = BIB_FILE,
) -> None:
    """Add a BibTeX citation to the references file.

    Args:
        key: Citation key (e.g., 'AuthorYear').
        entry_type: BibTeX entry type.
        author: Author string.
        title: Paper title.
        year: Publication year.
        journal: Journal name.
        doi: DOI string.
        url: URL string.
        bib_file: Path to .bib file.
    """
    bib_file.parent.mkdir(parents=True, exist_ok=True)

    # Check for duplicate key
    if bib_file.exists() and key in bib_file.read_text():
        logger.warning("Citation key '%s' already exists", key)
        return

    fields = [
        f"  author = {{{author}}}",
        f"  title = {{{title}}}",
        f"  year = {{{year}}}",
    ]
    if journal:
        fields.append(f"  journal = {{{journal}}}")
    if doi:
        fields.append(f"  doi = {{{doi}}}")
    if url:
        fields.append(f"  url = {{{url}}}")

    entry = f"\n@{entry_type}{{{key},\n" + ",\n".join(fields) + ",\n}\n"

    with open(bib_file, "a") as f:
        f.write(entry)

    logger.info("Added citation: %s", key)


def list_citations(bib_file: Path = BIB_FILE) -> list[str]:
    """List all citation keys in the bib file.

    Returns:
        List of citation keys.
    """
    if not bib_file.exists():
        return []

    content = bib_file.read_text()
    return re.findall(r"@\w+\{(\w+),", content)


def compile_paper(paper_dir: Path = PAPER_DIR) -> bool:
    """Compile the LaTeX paper using make.

    Returns:
        True if compilation succeeded.
    """
    makefile = paper_dir / "Makefile"
    if not makefile.exists():
        logger.error("Makefile not found in %s", paper_dir)
        return False

    try:
        subprocess.run(
            ["make", "all"],
            cwd=paper_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("Paper compiled successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Paper compilation failed:\n%s", e.stderr)
        return False


def clean_paper(paper_dir: Path = PAPER_DIR) -> None:
    """Clean LaTeX build artifacts."""
    subprocess.run(["make", "clean"], cwd=paper_dir, capture_output=True)


def check_figure_references(paper_dir: Path = PAPER_DIR) -> list[str]:
    """Check that all figures referenced in LaTeX exist on disk.

    Returns:
        List of missing figure paths.
    """
    main_tex = paper_dir / "main.tex"
    if not main_tex.exists():
        return []

    content = main_tex.read_text()
    referenced = re.findall(r"\\includegraphics(?:\[.*?\])?\{(.*?)\}", content)

    missing = []
    for fig_path in referenced:
        full_path = paper_dir / fig_path
        # Try with common extensions if no extension given
        if not full_path.suffix:
            candidates = [full_path.with_suffix(ext) for ext in [".pdf", ".png", ".jpg"]]
            if not any(c.exists() for c in candidates):
                missing.append(fig_path)
        elif not full_path.exists():
            missing.append(fig_path)

    return missing


def save_figure(
    fig,
    name: str,
    *,
    figures_dir: Path = FIGURES_DIR,
    fmt: str = "pdf",
) -> Path:
    """Save a matplotlib figure with publication settings.

    Args:
        fig: matplotlib Figure object.
        name: Figure name (without extension).
        figures_dir: Directory to save figures.
        fmt: Output format.

    Returns:
        Path to saved figure.
    """
    figures_dir.mkdir(parents=True, exist_ok=True)
    output_path = figures_dir / f"{name}.{fmt}"
    fig.savefig(output_path, bbox_inches="tight", pad_inches=0.02, dpi=300)
    logger.info("Saved figure: %s", output_path)
    return output_path
