"""Git introspection helpers for the ricet runtime.

Exposes :func:`get_git_info` which returns the current repo's short SHA,
branch name, and dirty flag, and :func:`get_version` which reads the
installed ``ricet`` package version (falling back to ``cli.main.__version__``
for dev installs — same pattern as ``core.updater``).

Results are cached at module import time so we don't shell out on every
``/status`` or ``/dashboard`` poll. Call :func:`refresh` after ``self-update``
(or to invalidate the cache in tests).
"""

from __future__ import annotations

import importlib.metadata
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Repo root detection
# ---------------------------------------------------------------------------

# ``core/git_info.py`` → repo root
_RICET_REPO_ROOT = Path(__file__).resolve().parent.parent


def get_repo_root() -> Path:
    """Return the ricet repo root (parent of ``core/``)."""
    return _RICET_REPO_ROOT


# ---------------------------------------------------------------------------
# Git info
# ---------------------------------------------------------------------------


def _run_git(args: list[str], cwd: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.debug("git %s failed: %s", " ".join(args), exc)
        return None
    if result.returncode != 0:
        logger.debug(
            "git %s rc=%d stderr=%s",
            " ".join(args), result.returncode, result.stderr.strip()[:200],
        )
        return None
    return result.stdout.strip()


def get_git_info(repo_path: Optional[Path] = None) -> Dict[str, Any]:
    """Return ``{"git_sha", "git_branch", "git_dirty"}`` for *repo_path*.

    Each value is ``None`` if git isn't available or the directory isn't a
    git checkout. Never raises — safe to call from request hot paths.
    """
    path = Path(repo_path) if repo_path else _RICET_REPO_ROOT
    sha = _run_git(["rev-parse", "--short", "HEAD"], path)
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], path)
    porcelain = _run_git(["status", "--porcelain"], path)
    dirty: Optional[bool]
    if porcelain is None:
        dirty = None
    else:
        dirty = bool(porcelain.strip())
    return {"git_sha": sha, "git_branch": branch, "git_dirty": dirty}


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------


def get_version() -> str:
    """Return the installed ricet version, falling back to the CLI constant."""
    try:
        return importlib.metadata.version("ricet")
    except importlib.metadata.PackageNotFoundError:
        try:
            from cli.main import __version__  # type: ignore[no-redef]
            return __version__
        except Exception:
            return "0.0.0"


# ---------------------------------------------------------------------------
# Cached bundle
# ---------------------------------------------------------------------------


def _compute_cached() -> Dict[str, Any]:
    info = get_git_info(_RICET_REPO_ROOT)
    info["version"] = get_version()
    return info


# Cache at import time so /status and /dashboard don't shell out per request.
_CACHED: Dict[str, Any] = _compute_cached()


def cached_info() -> Dict[str, Any]:
    """Return the cached ``{version, git_sha, git_branch, git_dirty}`` bundle."""
    return dict(_CACHED)


def refresh() -> Dict[str, Any]:
    """Recompute the cached bundle. Call after ``self-update``."""
    global _CACHED
    _CACHED = _compute_cached()
    return dict(_CACHED)
