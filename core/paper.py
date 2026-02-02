"""Paper pipeline: figure generation, citation management, and LaTeX compilation."""

import logging
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# LaTeX tools required for paper compilation
REQUIRED_LATEX_TOOLS = {
    "pdflatex": "LaTeX compiler (core)",
    "bibtex": "Bibliography processor",
    "make": "Build system",
}

OPTIONAL_LATEX_TOOLS = {
    "biber": "Modern bibliography processor (BibLaTeX)",
    "latexmk": "Automated LaTeX build tool",
    "dvips": "DVI to PostScript converter",
}


def check_latex_dependencies(*, verbose: bool = False) -> tuple[bool, list[str]]:
    """Check that required LaTeX tools are installed.

    Args:
        verbose: If True, also report optional missing tools.

    Returns:
        Tuple of (all_required_present, list_of_error_messages).
    """
    errors: list[str] = []
    warnings: list[str] = []
    system = platform.system()

    for tool, description in REQUIRED_LATEX_TOOLS.items():
        if shutil.which(tool) is None:
            errors.append(f"  - {tool}: {description}")

    if verbose:
        for tool, description in OPTIONAL_LATEX_TOOLS.items():
            if shutil.which(tool) is None:
                warnings.append(f"  - {tool}: {description}")

    messages: list[str] = []
    if errors:
        messages.append("Required LaTeX tools not found:\n" + "\n".join(errors))
        if system == "Linux":
            messages.append(
                "Install with:\n"
                "  sudo apt install texlive-full  # Debian/Ubuntu\n"
                "  sudo dnf install texlive-scheme-full  # Fedora\n"
                "  sudo pacman -S texlive  # Arch"
            )
        elif system == "Darwin":
            messages.append(
                "Install with:\n"
                "  brew install --cask mactex\n"
                "or download from https://tug.org/mactex/"
            )
        elif system == "Windows":
            messages.append(
                "Install MiKTeX from https://miktex.org/download\n"
                "or TeX Live from https://tug.org/texlive/"
            )

    if verbose and warnings:
        messages.append("Optional tools not found (non-fatal):\n" + "\n".join(warnings))

    return len(errors) == 0, messages


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

    Runs a pre-flight check for required LaTeX tools before attempting
    compilation.

    Returns:
        True if compilation succeeded.
    """
    # Pre-flight: check that LaTeX toolchain is available
    deps_ok, dep_messages = check_latex_dependencies(verbose=True)
    if not deps_ok:
        for msg in dep_messages:
            logger.error(msg)
        return False

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
            candidates = [
                full_path.with_suffix(ext) for ext in [".pdf", ".png", ".jpg"]
            ]
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


def generate_citation_key(author: str, year: str) -> str:
    """Generate a BibTeX citation key like 'Smith2024'."""
    # Take first author's last name, clean it, append year
    last = author.split(",")[0].split()[-1] if author else "Unknown"
    last = re.sub(r"[^a-zA-Z]", "", last)
    return f"{last}{year}"


def search_paperboat(query: str, *, run_cmd=None) -> list[dict]:
    """Search PaperBoat for recent cross-discipline papers.

    PaperBoat scans thousands of journals daily. This function uses
    Claude to query PaperBoat's public interface and extract results.
    Falls back to Gemini (which has native web access) when Claude
    cannot reach the web.

    Args:
        query: Research topic to search.
        run_cmd: Optional callable for testing.

    Returns:
        List of paper dicts with title, authors, year, abstract, url.
    """
    from core.claude_helper import call_with_web_fallback

    prompt = (
        "Search PaperBoat (https://paperboatch.com/) for recent academic papers "
        f'matching: "{query}"\n\n'
        "PaperBoat is a cross-discipline paper discovery service that updates daily. "
        "Return a JSON array of up to 5 papers with fields: "
        '{"title": "...", "authors": "...", "year": "...", "abstract": "1-2 sentences", '
        '"url": "https://..."}\n'
        "If you cannot access PaperBoat, use your knowledge of recent papers instead. "
        "Reply with JSON array only."
    )
    raw = call_with_web_fallback(prompt, run_cmd=run_cmd)
    if raw is None:
        return []
    # Parse JSON from raw response
    import json as _json

    text = raw
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            cleaned = part.strip().removeprefix("json").strip()
            if cleaned.startswith("["):
                text = cleaned
                break
    try:
        result = _json.loads(text)
    except (ValueError, _json.JSONDecodeError):
        return []
    if isinstance(result, list):
        return [p for p in result if isinstance(p, dict) and p.get("title")]
    return []


def search_and_cite(
    query: str,
    bib_file: Path | None = None,
    *,
    max_results: int = 5,
    run_cmd=None,
) -> list[dict]:
    """Search literature via Claude and append results to .bib file.

    Uses Claude to search PubMed/arXiv (via available MCPs or web knowledge),
    extract metadata, and format as BibTeX entries.  Falls back to Gemini
    (which has native web access) when Claude cannot reach the web.

    Args:
        query: Search query (e.g., "transformer protein folding 2024").
        bib_file: Path to .bib file (default: paper/references.bib).
        max_results: Maximum papers to return.
        run_cmd: Optional callable for testing.

    Returns:
        List of dicts with keys: key, title, authors, year, doi, bibtex.
    """
    from core.claude_helper import call_with_web_fallback

    if bib_file is None:
        bib_file = Path("paper/references.bib")

    prompt = (
        f"Search for {max_results} relevant academic papers matching this query:\n\n"
        f'  "{query}"\n\n'
        "For each paper, provide a JSON array of objects with these fields:\n"
        '  {"title": "...", "authors": "LastName, First and ...", '
        '"year": "2024", "journal": "...", "doi": "...", '
        '"entry_type": "article"}\n\n'
        "Focus on recent, highly-cited, peer-reviewed papers. "
        "Reply with the JSON array only, no markdown fences."
    )

    raw = call_with_web_fallback(prompt, run_cmd=run_cmd)
    if raw is None:
        results = None
    else:
        import json as _json

        text = raw
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                cleaned = part.strip().removeprefix("json").strip()
                if cleaned.startswith("["):
                    text = cleaned
                    break
        try:
            results = _json.loads(text)
        except (ValueError, _json.JSONDecodeError):
            results = None
    if not results or not isinstance(results, list):
        return []

    added = []
    for paper in results[:max_results]:
        if not isinstance(paper, dict) or not paper.get("title"):
            continue
        key = generate_citation_key(
            paper.get("authors", "Unknown"),
            paper.get("year", "2024"),
        )
        # Deduplicate: check if key already in bib
        existing = list_citations(bib_file) if bib_file.exists() else []
        if key in existing:
            key = f"{key}b"  # Simple dedup suffix
            if key in existing:
                continue

        add_citation(
            key=key,
            entry_type=paper.get("entry_type", "article"),
            author=paper.get("authors", ""),
            title=paper.get("title", ""),
            year=paper.get("year", ""),
            journal=paper.get("journal", ""),
            doi=paper.get("doi", ""),
            bib_file=bib_file,
        )
        added.append({"key": key, **paper})

    return added
