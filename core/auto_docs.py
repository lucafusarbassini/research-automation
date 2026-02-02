"""Auto-update documentation when new features are developed.

Scans core/ for public functions and classes, then updates:
- docs/site/api.md  (API reference)
- docs/site/features.md  (feature list index)
- README.md  (CLI commands table)

Called automatically by ricet after major operations when
RICET_AUTO_DOCS is set to "true" (default: "false").
"""

import ast
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

CORE_DIR = Path("core")
DOCS_API = Path("docs/site/api.md")
README = Path("README.md")


def _is_enabled() -> bool:
    return os.environ.get("RICET_AUTO_DOCS", "false").lower() in ("true", "1", "yes")


def scan_public_functions(module_path: Path) -> list[dict]:
    """Extract public function and class names from a Python module.

    Args:
        module_path: Path to a .py file.

    Returns:
        List of dicts with 'name', 'type' ('function' or 'class'), and 'docstring'.
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
                results.append(
                    {
                        "name": node.name,
                        "type": "function",
                        "docstring": ast.get_docstring(node) or "",
                    }
                )
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                results.append(
                    {
                        "name": node.name,
                        "type": "class",
                        "docstring": ast.get_docstring(node) or "",
                    }
                )

    return results


def scan_all_modules(core_dir: Path = CORE_DIR) -> dict[str, list[dict]]:
    """Scan all core modules for public API surface.

    Args:
        core_dir: Path to the core/ directory.

    Returns:
        Dict mapping module name (e.g. 'agents') to list of public items.
    """
    if not core_dir.is_dir():
        return {}

    modules = {}
    for py_file in sorted(core_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        module_name = py_file.stem
        items = scan_public_functions(py_file)
        if items:
            modules[module_name] = items

    return modules


def check_api_coverage(
    docs_api: Path = DOCS_API,
    core_dir: Path = CORE_DIR,
) -> list[str]:
    """Check which core modules are missing from the API docs.

    Args:
        docs_api: Path to api.md.
        core_dir: Path to core/ directory.

    Returns:
        List of module names not mentioned in api.md.
    """
    modules = scan_all_modules(core_dir)
    if not docs_api.exists():
        return list(modules.keys())

    api_text = docs_api.read_text().lower()
    missing = []
    for name in modules:
        # Check if module is referenced as core.name or core_name
        if f"core.{name}" not in api_text and f"`{name}`" not in api_text:
            missing.append(name)

    return missing


def check_cli_commands(
    readme: Path = README,
    cli_main: Path = Path("cli/main.py"),
) -> list[str]:
    """Check which CLI commands are missing from README.

    Args:
        readme: Path to README.md.
        cli_main: Path to cli/main.py.

    Returns:
        List of command names not mentioned in README.
    """
    if not cli_main.exists() or not readme.exists():
        return []

    # Extract @app.command() decorated function names
    cli_text = cli_main.read_text()
    commands = re.findall(r"@app\.command\(\)\s*\ndef\s+(\w+)", cli_text)

    readme_text = readme.read_text().lower()
    missing = []
    for cmd in commands:
        # Convert underscore names to kebab-case for CLI
        cli_name = cmd.replace("_", "-")
        if (
            f"ricet {cli_name}" not in readme_text
            and f"ricet{cli_name}" not in readme_text
        ):
            # Also check original name
            if f"ricet {cmd}" not in readme_text:
                missing.append(cmd)

    return missing


def generate_module_stub(module_name: str, items: list[dict]) -> str:
    """Generate a markdown stub for a module's API docs.

    Args:
        module_name: Module name (e.g. 'auto_commit').
        items: List of public items from scan_public_functions.

    Returns:
        Markdown string for the module section.
    """
    lines = [f"\n\n## `core.{module_name}`\n"]

    for item in items:
        if item["type"] == "class":
            lines.append(f"\n### `{item['name']}`\n")
        else:
            first_line = item["docstring"].split("\n")[0] if item["docstring"] else ""
            lines.append(f"\n#### `{item['name']}(...)`\n")
            if first_line:
                lines.append(f"\n{first_line}\n")

    return "\n".join(lines)


def auto_update_docs(
    *,
    core_dir: Path = CORE_DIR,
    docs_api: Path = DOCS_API,
    readme: Path = README,
    force: bool = False,
) -> dict[str, list[str]]:
    """Check for documentation gaps and report them.

    This function scans the codebase and identifies what needs updating.
    It returns the gaps rather than auto-writing, so a human or Claude
    session can review and fill them properly.

    Args:
        core_dir: Path to core/ directory.
        docs_api: Path to api.md.
        readme: Path to README.md.
        force: If True, run even when RICET_AUTO_DOCS is not set.

    Returns:
        Dict with 'missing_api_modules' and 'missing_cli_commands' lists.
    """
    if not force and not _is_enabled():
        return {"missing_api_modules": [], "missing_cli_commands": []}

    missing_api = check_api_coverage(docs_api, core_dir)
    missing_cli = check_cli_commands(readme)

    if missing_api:
        logger.info("Modules missing from API docs: %s", ", ".join(missing_api))
    if missing_cli:
        logger.info("CLI commands missing from README: %s", ", ".join(missing_cli))

    return {
        "missing_api_modules": missing_api,
        "missing_cli_commands": missing_cli,
    }
