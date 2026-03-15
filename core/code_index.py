"""Code indexing for RAG over external/legacy codebases.

Walks a directory, extracts function/class signatures and docstrings,
and writes a searchable markdown index. The index can be searched via
core.rag.search() (reuses the same sentence-transformers infrastructure).
"""

import ast
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SKIP_DIRS = {
    "__pycache__", ".git", ".hg", "node_modules", ".tox", ".mypy_cache",
    ".pytest_cache", "dist", "build", ".eggs", "venv", ".venv", "env",
}

_CODE_EXTENSIONS = {".py", ".r", ".R", ".jl", ".m", ".sh"}


def _extract_python_signatures(source: str, path: str) -> list[str]:
    """Extract function and class signatures from Python source."""
    entries = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [f"- **{path}**: (syntax error, could not parse)"]

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            args = ", ".join(a.arg for a in node.args.args)
            doc = ast.get_docstring(node) or ""
            doc_short = doc.split("\n")[0][:120] if doc else ""
            entry = f"  - `def {node.name}({args})` L{node.lineno}"
            if doc_short:
                entry += f" — {doc_short}"
            entries.append(entry)
        elif isinstance(node, ast.ClassDef):
            doc = ast.get_docstring(node) or ""
            doc_short = doc.split("\n")[0][:120] if doc else ""
            methods = [
                n.name for n in node.body
                if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
                and not n.name.startswith("_")
            ]
            entry = f"  - `class {node.name}` L{node.lineno}"
            if doc_short:
                entry += f" — {doc_short}"
            if methods:
                entry += f" | methods: {', '.join(methods[:8])}"
            entries.append(entry)

    return entries


def _extract_generic_signatures(source: str) -> list[str]:
    """Extract function-like patterns from non-Python files."""
    import re
    entries = []
    for i, line in enumerate(source.splitlines(), 1):
        line_stripped = line.strip()
        # R functions
        if re.match(r"^\w+\s*<-\s*function\s*\(", line_stripped):
            name = line_stripped.split("<-")[0].strip()
            entries.append(f"  - `{name}()` L{i}")
        # Julia functions
        elif re.match(r"^function\s+\w+", line_stripped):
            entries.append(f"  - `{line_stripped.split('(')[0]}()` L{i}")
        # Shell functions
        elif re.match(r"^\w+\s*\(\)\s*\{", line_stripped):
            name = line_stripped.split("(")[0].strip()
            entries.append(f"  - `{name}()` L{i}")
    return entries


def build_index(root: Path, output: Path | None = None) -> str:
    """Walk root directory, extract signatures, return markdown index.

    Args:
        root: Directory to index.
        output: If provided, write the index to this file.

    Returns:
        The markdown index as a string.
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Not a directory: {root}")

    lines = [
        f"# Code Index: {root.name}",
        f"",
        f"Source: `{root}`",
        f"",
    ]

    file_count = 0
    for path in sorted(root.rglob("*")):
        if any(skip in path.parts for skip in _SKIP_DIRS):
            continue
        if path.suffix not in _CODE_EXTENSIONS:
            continue
        if not path.is_file():
            continue

        rel = path.relative_to(root)
        try:
            source = path.read_text(errors="replace")
        except OSError:
            continue

        loc = sum(1 for line in source.splitlines() if line.strip())

        if path.suffix == ".py":
            sigs = _extract_python_signatures(source, str(rel))
        else:
            sigs = _extract_generic_signatures(source)

        lines.append(f"### {rel} ({loc} lines)")
        if sigs:
            lines.extend(sigs)
        else:
            # File-level summary for files with no extractable signatures
            first_doc = ""
            for line in source.splitlines()[:10]:
                stripped = line.strip().lstrip("#").lstrip("!").strip()
                if stripped and not stripped.startswith("import") and not stripped.startswith("from"):
                    first_doc = stripped[:120]
                    break
            if first_doc:
                lines.append(f"  - {first_doc}")
        lines.append("")
        file_count += 1

    lines.append(f"---\n{file_count} files indexed.")

    index_text = "\n".join(lines)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(index_text)
        logger.info("Code index written to %s (%d files)", output, file_count)

    return index_text
