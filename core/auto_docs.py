"""Auto-update project documentation when new code is developed.

Works on the *user's project* (the current working directory), not on ricet
itself.  Scans Python source directories for public API, then:

1. Appends missing module stubs to ``docs/API.md`` (or creates it).
2. Appends missing CLI commands to ``README.md``'s command table.
3. Updates a feature index in ``docs/MODULES.md``.

Called automatically after state-modifying CLI commands when
``RICET_AUTO_DOCS`` env is ``"true"`` (opt-in, default ``"false"``).
Can also be triggered manually via ``ricet docs``.
"""

import ast
import logging
import os
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_enabled() -> bool:
    return os.environ.get("RICET_AUTO_DOCS", "false").lower() in ("true", "1", "yes")


def _find_source_dirs(project_root: Path) -> list[Path]:
    """Heuristically find Python source directories in a project."""
    candidates = ["src", "lib", "core", "app", project_root.name]
    dirs = []
    for name in candidates:
        d = project_root / name
        if d.is_dir() and any(d.glob("*.py")):
            dirs.append(d)
    # Fallback: any top-level dir containing .py files (excluding tests, docs, etc.)
    if not dirs:
        skip = {
            "tests",
            "test",
            "docs",
            "scripts",
            ".git",
            "__pycache__",
            "node_modules",
            ".venv",
            "venv",
            "env",
        }
        for d in project_root.iterdir():
            if d.is_dir() and d.name not in skip and not d.name.startswith("."):
                if any(d.glob("*.py")):
                    dirs.append(d)
    return dirs


def _find_cli_file(project_root: Path) -> Path | None:
    """Find the main CLI entry point."""
    candidates = [
        project_root / "cli" / "main.py",
        project_root / "cli.py",
        project_root / "app" / "cli.py",
        project_root / "src" / "cli.py",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


# ---------------------------------------------------------------------------
# AST scanning
# ---------------------------------------------------------------------------


def scan_public_functions(module_path: Path) -> list[dict]:
    """Extract public function and class names from a Python module.

    Args:
        module_path: Path to a .py file.

    Returns:
        List of dicts with 'name', 'type' ('function' or 'class'), 'docstring',
        and 'args' (for functions).
    """
    if not module_path.exists():
        return []

    try:
        tree = ast.parse(module_path.read_text())
    except SyntaxError:
        return []

    results = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                args = _extract_args(node)
                results.append(
                    {
                        "name": node.name,
                        "type": "function",
                        "docstring": ast.get_docstring(node) or "",
                        "args": args,
                    }
                )
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                results.append(
                    {
                        "name": node.name,
                        "type": "class",
                        "docstring": ast.get_docstring(node) or "",
                        "args": "",
                    }
                )

    return results


def _extract_args(node: ast.FunctionDef) -> str:
    """Extract a simplified argument signature from a function node."""
    parts = []
    args = node.args
    defaults_offset = len(args.args) - len(args.defaults)
    for i, arg in enumerate(args.args):
        if arg.arg == "self":
            continue
        name = arg.arg
        annotation = ""
        if arg.annotation and isinstance(arg.annotation, ast.Name):
            annotation = f": {arg.annotation.id}"
        elif arg.annotation and isinstance(arg.annotation, ast.Constant):
            annotation = f": {arg.annotation.value}"
        default_idx = i - defaults_offset
        if default_idx >= 0 and default_idx < len(args.defaults):
            parts.append(f"{name}{annotation}=...")
        else:
            parts.append(f"{name}{annotation}")
    if args.vararg:
        parts.append(f"*{args.vararg.arg}")
    for kwarg in args.kwonlyargs:
        parts.append(f"{kwarg.arg}=...")
    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")
    return ", ".join(parts)


def scan_all_modules(source_dir: Path) -> dict[str, list[dict]]:
    """Scan a source directory for public API surface.

    Args:
        source_dir: Path to a Python source directory.

    Returns:
        Dict mapping module name to list of public items.
    """
    if not source_dir.is_dir():
        return {}

    modules = {}
    for py_file in sorted(source_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        module_name = py_file.stem
        items = scan_public_functions(py_file)
        if items:
            modules[module_name] = items

    return modules


# ---------------------------------------------------------------------------
# Gap detection
# ---------------------------------------------------------------------------


def check_api_coverage(
    api_doc: Path,
    source_dirs: list[Path],
) -> dict[str, list[dict]]:
    """Find modules missing from the API doc.

    Args:
        api_doc: Path to the API documentation file.
        source_dirs: Source directories to scan.

    Returns:
        Dict mapping ``"dir_name.module_name"`` to list of public items
        for modules not yet documented.
    """
    existing_text = api_doc.read_text().lower() if api_doc.exists() else ""
    missing = {}
    for src_dir in source_dirs:
        prefix = src_dir.name
        modules = scan_all_modules(src_dir)
        for mod_name, items in modules.items():
            qualified = f"{prefix}.{mod_name}"
            if qualified not in existing_text and f"`{mod_name}`" not in existing_text:
                missing[qualified] = items
    return missing


def check_cli_commands(
    readme: Path,
    cli_file: Path | None,
) -> list[str]:
    """Find CLI commands not mentioned in README.

    Args:
        readme: Path to README.md.
        cli_file: Path to the CLI entry point.

    Returns:
        List of command function names missing from README.
    """
    if not cli_file or not cli_file.exists() or not readme.exists():
        return []

    cli_text = cli_file.read_text()
    commands = re.findall(r"@app\.command\(\)\s*\ndef\s+(\w+)", cli_text)

    readme_lower = readme.read_text().lower()
    missing = []
    for cmd in commands:
        kebab = cmd.replace("_", "-")
        if kebab not in readme_lower and cmd not in readme_lower:
            missing.append(cmd)
    return missing


# ---------------------------------------------------------------------------
# Content generation
# ---------------------------------------------------------------------------


def generate_module_stub(qualified_name: str, items: list[dict]) -> str:
    """Generate a markdown section for a module.

    Args:
        qualified_name: e.g. ``"core.auto_commit"``.
        items: Public items from scan_public_functions.

    Returns:
        Markdown string ready to append to an API doc.
    """
    lines = [f"\n---\n\n## `{qualified_name}`\n"]
    for item in items:
        if item["type"] == "class":
            first_line = item["docstring"].split("\n")[0] if item["docstring"] else ""
            lines.append(f"\n### `{item['name']}`\n")
            if first_line:
                lines.append(f"\n{first_line}\n")
        else:
            sig = item.get("args", "...")
            first_line = item["docstring"].split("\n")[0] if item["docstring"] else ""
            lines.append(f"\n#### `{item['name']}({sig})`\n")
            if first_line:
                lines.append(f"\n{first_line}\n")
    return "\n".join(lines)


def generate_cli_row(cmd_name: str) -> str:
    """Generate a README table row for a CLI command."""
    kebab = cmd_name.replace("_", "-")
    return f"| `ricet {kebab}` | *TODO: add description* |"


def generate_module_index(all_modules: dict[str, list[dict]]) -> str:
    """Generate a modules index page listing all source modules.

    Args:
        all_modules: Dict of ``"dir.module"`` -> items.

    Returns:
        Full markdown page content.
    """
    lines = [
        "# Modules Index",
        "",
        f"*Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}.*",
        "",
        "| Module | Public Items | Description |",
        "|--------|-------------|-------------|",
    ]
    for qualified, items in sorted(all_modules.items()):
        count = len(items)
        # First docstring of the first item as a hint
        hint = ""
        for it in items:
            if it["docstring"]:
                hint = it["docstring"].split("\n")[0][:60]
                break
        lines.append(f"| `{qualified}` | {count} | {hint} |")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------


def update_api_doc(
    api_doc: Path,
    missing_modules: dict[str, list[dict]],
) -> int:
    """Append stubs for missing modules to the API doc.

    Creates the file if it doesn't exist.

    Args:
        api_doc: Path to the API documentation file.
        missing_modules: Dict from check_api_coverage.

    Returns:
        Number of modules appended.
    """
    if not missing_modules:
        return 0

    api_doc.parent.mkdir(parents=True, exist_ok=True)

    if not api_doc.exists():
        api_doc.write_text(
            "# API Reference\n\n"
            "*Auto-generated by ricet. Edit freely -- new modules are "
            "appended, existing sections are never overwritten.*\n"
        )

    content = api_doc.read_text()
    appended = 0
    for qualified, items in sorted(missing_modules.items()):
        stub = generate_module_stub(qualified, items)
        content += stub
        appended += 1
        logger.info("Appended API stub for %s", qualified)

    api_doc.write_text(content)
    return appended


def update_readme_commands(
    readme: Path,
    missing_commands: list[str],
) -> int:
    """Append missing CLI commands to the README command table.

    Looks for a markdown table containing ``ricet`` and appends rows.
    If no table is found, appends a new section.

    Args:
        readme: Path to README.md.
        missing_commands: List of command names.

    Returns:
        Number of commands added.
    """
    if not missing_commands or not readme.exists():
        return 0

    content = readme.read_text()

    # Find the last row of a table that mentions "ricet"
    table_pattern = r"(\|[^\n]*ricet[^\n]*\|[^\n]*\n)"
    matches = list(re.finditer(table_pattern, content, re.IGNORECASE))
    if matches:
        insert_pos = matches[-1].end()
        rows = "\n".join(generate_cli_row(cmd) for cmd in missing_commands)
        content = content[:insert_pos] + rows + "\n" + content[insert_pos:]
    else:
        # No table found -- append a section
        rows = "\n".join(generate_cli_row(cmd) for cmd in missing_commands)
        content += (
            "\n\n## CLI Commands\n\n"
            "| Command | Description |\n"
            "|---------|-------------|\n"
            f"{rows}\n"
        )

    readme.write_text(content)
    return len(missing_commands)


def update_module_index(
    index_path: Path,
    source_dirs: list[Path],
) -> int:
    """Regenerate the module index file.

    Args:
        index_path: Path to docs/MODULES.md.
        source_dirs: Source directories to scan.

    Returns:
        Total number of modules listed.
    """
    all_modules: dict[str, list[dict]] = {}
    for src_dir in source_dirs:
        prefix = src_dir.name
        for mod_name, items in scan_all_modules(src_dir).items():
            all_modules[f"{prefix}.{mod_name}"] = items

    if not all_modules:
        return 0

    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(generate_module_index(all_modules))
    logger.info("Updated module index at %s (%d modules)", index_path, len(all_modules))
    return len(all_modules)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def review_claude_md(project_path: Path, *, run_cmd=None) -> str | None:
    """Review and simplify the project's CLAUDE.md using Claude.

    Reads CLAUDE.md, asks Claude to trim redundancies and keep it
    under 200 lines while preserving essential agent instructions.
    Returns the simplified text, or None if Claude unavailable.
    """
    from core.claude_helper import call_claude

    claude_md = project_path / ".claude" / "CLAUDE.md"
    if not claude_md.exists():
        claude_md = project_path / "CLAUDE.md"
    if not claude_md.exists():
        return None

    text = claude_md.read_text()
    if len(text.splitlines()) <= 200:
        return None  # Already concise

    prompt = (
        "You are reviewing a CLAUDE.md agent configuration file. "
        "It has grown too large. Simplify it to under 200 lines while "
        "preserving all essential agent instructions, tool configurations, "
        "and workflow rules. Remove redundancies and verbose examples. "
        "Reply with ONLY the simplified CLAUDE.md content.\n\n"
        f"Current CLAUDE.md ({len(text.splitlines())} lines):\n{text}"
    )

    result = call_claude(prompt, run_cmd=run_cmd)
    if result and result.strip():
        return result.strip()
    return None


def auto_update_docs(
    *,
    project_root: Path | None = None,
    force: bool = False,
) -> dict:
    """Scan the project, find documentation gaps, and fill them.

    Works on the current working directory (the user's project).

    Args:
        project_root: Project root (defaults to cwd).
        force: If True, run even when RICET_AUTO_DOCS is not set.

    Returns:
        Dict with 'api_added', 'cli_added', 'modules_indexed' counts.
    """
    if not force and not _is_enabled():
        return {"api_added": 0, "cli_added": 0, "modules_indexed": 0}

    if project_root is None:
        project_root = Path.cwd()

    source_dirs = _find_source_dirs(project_root)
    if not source_dirs:
        return {"api_added": 0, "cli_added": 0, "modules_indexed": 0}

    api_doc = project_root / "docs" / "API.md"
    readme = project_root / "README.md"
    module_index = project_root / "docs" / "MODULES.md"
    cli_file = _find_cli_file(project_root)

    # 1. API doc stubs
    missing_api = check_api_coverage(api_doc, source_dirs)
    api_added = update_api_doc(api_doc, missing_api)

    # 2. README CLI commands
    missing_cli = check_cli_commands(readme, cli_file)
    cli_added = update_readme_commands(readme, missing_cli)

    # 3. Module index
    modules_indexed = update_module_index(module_index, source_dirs)

    if api_added or cli_added:
        logger.info(
            "Auto-docs: %d API stubs, %d CLI commands, %d modules indexed",
            api_added,
            cli_added,
            modules_indexed,
        )

    return {
        "api_added": api_added,
        "cli_added": cli_added,
        "modules_indexed": modules_indexed,
    }
