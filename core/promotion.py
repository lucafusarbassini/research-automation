"""Lab → Stable promotion with provenance tracking.

Promotes validated code from lab/ to stable/ with metadata recording
the source, git hash, validation status, and timestamp.
"""

import json
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _git_hash() -> str:
    """Get current git HEAD hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip()[:12] if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def promote_file(
    source: Path,
    *,
    force: bool = False,
    project_root: Path | None = None,
) -> dict:
    """Promote a file from lab/ to stable/.

    Args:
        source: Path to the file (e.g. lab/analysis.py)
        force: Skip falsification check
        project_root: Project root (auto-detected if None)

    Returns:
        dict with 'ok', 'dest', 'provenance', 'error' keys
    """
    source = Path(source)
    if not source.is_absolute():
        source = Path.cwd() / source

    if not source.exists():
        return {"ok": False, "error": f"File not found: {source}"}

    # Determine project root
    if project_root is None:
        project_root = Path.cwd()

    # Ensure source is under lab/
    try:
        rel = source.relative_to(project_root / "lab")
    except ValueError:
        return {"ok": False, "error": f"File must be under lab/. Got: {source}"}

    # Destination
    dest = project_root / "stable" / rel
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Falsification check (unless forced)
    if not force:
        check_result = _run_basic_validation(source)
        if not check_result["passed"]:
            return {
                "ok": False,
                "error": f"Validation failed: {check_result['reason']}. Use --force to override.",
            }

    # Copy file
    shutil.copy2(source, dest)

    # Write provenance
    provenance = {
        "source": str(source.relative_to(project_root)),
        "promoted_at": datetime.now().isoformat(),
        "git_hash": _git_hash(),
        "forced": force,
    }
    provenance_path = dest.with_suffix(dest.suffix + ".provenance.json")
    provenance_path.write_text(json.dumps(provenance, indent=2))

    # Auto-commit
    try:
        subprocess.run(
            ["git", "add", str(dest), str(provenance_path)],
            cwd=str(project_root), capture_output=True, timeout=10,
        )
        subprocess.run(
            ["git", "commit", "-m",
             f"promote: {rel} → stable/ (hash: {provenance['git_hash']})"],
            cwd=str(project_root), capture_output=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("Auto-commit failed: %s", exc)

    logger.info("Promoted %s → %s", source, dest)
    return {
        "ok": True,
        "dest": str(dest.relative_to(project_root)),
        "provenance": str(provenance_path.relative_to(project_root)),
    }


def _run_basic_validation(path: Path) -> dict:
    """Run basic validation checks on a file before promotion."""
    suffix = path.suffix

    if suffix == ".py":
        # Syntax check
        import ast
        try:
            ast.parse(path.read_text())
        except SyntaxError as e:
            return {"passed": False, "reason": f"Syntax error: {e}"}

        # Check for TODO/FIXME/HACK markers in comments (not docstrings)
        import re
        source = path.read_text()
        for i, line in enumerate(source.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#") and re.search(r"\b(TODO|FIXME|HACK)\b", stripped):
                return {"passed": False, "reason": f"Line {i}: contains TODO/FIXME/HACK marker"}

    # File must not be empty
    if path.stat().st_size == 0:
        return {"passed": False, "reason": "File is empty"}

    return {"passed": True, "reason": ""}
