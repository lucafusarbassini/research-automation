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
# tectonic is preferred (single binary, auto-downloads packages).
# lualatex + biber is the traditional alternative.
REQUIRED_LATEX_TOOLS = {
    "tectonic|lualatex": "LaTeX compiler (tectonic preferred, lualatex fallback)",
    "biber": "Bibliography processor (BibLaTeX backend)",
}

OPTIONAL_LATEX_TOOLS = {
    "make": "Build system (for Makefile-based compilation)",
    "gs": "Ghostscript (PDF compression via make small)",
    "latexdiff": "Revision diff generation",
}


def check_latex_dependencies(*, verbose: bool = False) -> tuple[bool, list[str]]:
    """Check that required LaTeX tools are installed.

    Tool keys may use ``|`` to specify alternatives (e.g. ``tectonic|lualatex``).

    Returns:
        Tuple of (all_required_present, list_of_error_messages).
    """
    errors: list[str] = []
    warnings: list[str] = []

    for tool_spec, description in REQUIRED_LATEX_TOOLS.items():
        alternatives = tool_spec.split("|")
        if not any(shutil.which(t) for t in alternatives):
            errors.append(f"  - {' or '.join(alternatives)}: {description}")

    if verbose:
        for tool_spec, description in OPTIONAL_LATEX_TOOLS.items():
            alternatives = tool_spec.split("|")
            if not any(shutil.which(t) for t in alternatives):
                warnings.append(f"  - {' or '.join(alternatives)}: {description}")

    messages: list[str] = []
    if errors:
        messages.append("Required LaTeX tools not found:\n" + "\n".join(errors))
        messages.append(
            "Install with: ricet init (auto-installs tectonic + biber)\n"
            "  Or manually: curl -sL https://drop-sh.fullyjustified.net | sh"
        )

    if verbose and warnings:
        messages.append("Optional tools not found (non-fatal):\n" + "\n".join(warnings))

    return len(errors) == 0, messages


PAPER_DIR = Path("paper")
FIGURES_DIR = Path("figures")
BIB_FILE = PAPER_DIR / "literature.bib"

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
    """Compile the LaTeX paper.

    Prefers tectonic (single command, auto-downloads packages).
    Falls back to ``make all`` if tectonic is unavailable.

    Returns:
        True if compilation succeeded.
    """
    deps_ok, dep_messages = check_latex_dependencies(verbose=True)
    if not deps_ok:
        for msg in dep_messages:
            logger.error(msg)
        return False

    main_tex = paper_dir / "main.tex"
    if not main_tex.exists():
        logger.error("main.tex not found in %s", paper_dir)
        return False

    # Prefer tectonic
    if shutil.which("tectonic"):
        try:
            subprocess.run(
                ["tectonic", "main.tex"],
                cwd=paper_dir,
                check=True,
                capture_output=True,
                text=True,
                timeout=600,
            )
            logger.info("Paper compiled successfully (tectonic)")
            return True
        except subprocess.CalledProcessError as e:
            logger.error("tectonic compilation failed:\n%s", e.stderr)
            return False
        except subprocess.TimeoutExpired:
            logger.error("tectonic compilation timed out")
            return False

    # Fallback: make
    if shutil.which("make") and (paper_dir / "Makefile").exists():
        try:
            subprocess.run(
                ["make", "main"],
                cwd=paper_dir,
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("Paper compiled successfully (make)")
            return True
        except subprocess.CalledProcessError as e:
            logger.error("make compilation failed:\n%s", e.stderr)
            return False

    logger.error("No compilation tool available (need tectonic or make + lualatex)")
    return False


def clean_paper(paper_dir: Path = PAPER_DIR) -> None:
    """Clean LaTeX build artifacts."""
    for pattern in ("*.aux", "*.bbl", "*.bcf", "*.blg", "*.log", "*.out",
                    "*.run.xml", "*.toc", "*.fls", "*.fdb_latexmk"):
        for f in paper_dir.glob(pattern):
            f.unlink(missing_ok=True)
    if shutil.which("make") and (paper_dir / "Makefile").exists():
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


def _extract_json_array(text: str) -> list | None:
    """Extract a JSON array from text that may contain prose preamble.

    Handles code fences, prose before/after JSON, and nested arrays.
    """
    import json as _json

    # 1. Try code fences first
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            cleaned = part.strip().removeprefix("json").strip()
            if cleaned.startswith("["):
                try:
                    return _json.loads(cleaned)
                except (ValueError, _json.JSONDecodeError):
                    continue

    # 2. Try the whole text as JSON
    stripped = text.strip()
    if stripped.startswith("["):
        try:
            return _json.loads(stripped)
        except (ValueError, _json.JSONDecodeError):
            pass

    # 3. Find the first '[' and try to parse from there
    idx = text.find("[")
    if idx >= 0:
        # Find the matching closing bracket
        bracket_depth = 0
        for i in range(idx, len(text)):
            if text[i] == "[":
                bracket_depth += 1
            elif text[i] == "]":
                bracket_depth -= 1
                if bracket_depth == 0:
                    candidate = text[idx : i + 1]
                    try:
                        return _json.loads(candidate)
                    except (ValueError, _json.JSONDecodeError):
                        pass
                    break

    return None


def generate_citation_key(author: str, year: str) -> str:
    """Generate a BibTeX citation key like 'Smith2024'."""
    # Take first author's last name, clean it, append year
    last = author.split(",")[0].split()[-1] if author else "Unknown"
    last = re.sub(r"[^a-zA-Z]", "", last)
    return f"{last}{year}"


def search_and_cite(
    query: str,
    bib_file: Path | None = None,
    *,
    max_results: int = 5,
    run_cmd=None,
) -> list[dict]:
    """Search literature using MCP paper-search tools and append to .bib.

    Instructs Claude to use its paper-search-mcp, arxiv-mcp-server, or
    scientific-papers-mcp tools to find REAL papers from arXiv, PubMed,
    Semantic Scholar, etc.  NEVER hallucates.

    Args:
        query: Search query (e.g., "transformer protein folding 2024").
        bib_file: Path to .bib file (default: paper/references.bib).
        max_results: Maximum papers to return.
        run_cmd: Optional callable for testing.

    Returns:
        List of dicts with keys: key, title, authors, year, doi.
    """
    from core.claude_helper import call_claude

    if bib_file is None:
        bib_file = Path("paper/literature.bib")

    prompt = (
        f'Find {max_results} real academic papers matching: "{query}"\n\n'
        "INSTRUCTIONS:\n"
        "1. Use WebSearch to search PubMed (pubmed.ncbi.nlm.nih.gov) for this query.\n"
        "   PubMed is the PRIMARY source — always search it first.\n"
        "2. Also search arXiv, Semantic Scholar, or Google Scholar if relevant.\n"
        "3. Use WebFetch on result pages to get paper details (DOI, authors, year).\n"
        "4. Return ONLY papers you actually found with real, verifiable DOIs.\n"
        "5. DO NOT invent, hallucinate, or guess any paper metadata.\n"
        "6. If no papers found, return: []\n\n"
        "Return a JSON array with fields:\n"
        '  {"title": "...", "authors": "LastName, First and ...", '
        '"year": "2024", "journal": "...", "doi": "10.xxxx/...", '
        '"entry_type": "article"}\n\n'
        "Reply with JSON array only."
    )

    raw = call_claude(prompt, model="sonnet", timeout=120, run_cmd=run_cmd)
    if raw is None:
        return []
    results = _extract_json_array(raw)
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
        existing = list_citations(bib_file) if bib_file.exists() else []
        if key in existing:
            key = f"{key}b"
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
            url=paper.get("url", ""),
            bib_file=bib_file,
        )
        added.append({"key": key, **paper})

    return added
