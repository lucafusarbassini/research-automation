"""Cascading ricet self-update system.

Checks PyPI (or GitHub) for newer ricet versions and offers to upgrade.
Designed to be called on session-start or periodically (e.g. weekly).

Safety rules:
  - NEVER overwrites user data (knowledge/, state/, paper/, secrets/).
  - Only upgrades the pip-installed package (core/, cli/, templates/).
  - Always asks the user before upgrading.
  - Records the installed version in state/.ricet-version for migration tracking.
"""

import importlib.metadata
import json
import logging
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# How often to check (avoid nagging on every message)
CHECK_INTERVAL = timedelta(days=7)
VERSION_STATE_FILE = "state/.ricet-version"
LAST_CHECK_FILE = "state/.ricet-update-check"


def get_installed_version() -> str:
    """Get the currently installed ricet version."""
    try:
        return importlib.metadata.version("ricet")
    except importlib.metadata.PackageNotFoundError:
        # Dev install or not pip-installed
        try:
            from cli.main import __version__
            return __version__
        except ImportError:
            return "0.0.0"


def get_latest_version(*, timeout: int = 10) -> Optional[str]:
    """Query PyPI for the latest ricet version.

    Returns None if the check fails (no network, not published, etc.).
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "index", "versions", "ricet"],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0 and "versions:" in result.stdout.lower():
            # pip index output: "ricet (0.4.0)\n  INSTALLED: 0.3.0\n  LATEST:    0.4.0"
            for line in result.stdout.splitlines():
                if "LATEST" in line.upper():
                    return line.split(":")[-1].strip()
            # Fallback: first line often has "ricet (X.Y.Z)"
            first_line = result.stdout.strip().splitlines()[0]
            if "(" in first_line and ")" in first_line:
                return first_line.split("(")[1].split(")")[0]
    except Exception as e:
        logger.debug("PyPI version check failed: %s", e)

    # Fallback: try pip install --dry-run
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--dry-run",
             "--no-deps", "ricet", "--upgrade"],
            capture_output=True, text=True, timeout=timeout,
        )
        for line in result.stdout.splitlines():
            if "Would install" in line and "ricet" in line:
                # "Would install ricet-0.4.0"
                for token in line.split():
                    if token.startswith("ricet-"):
                        return token.replace("ricet-", "")
    except Exception:
        pass

    return None


def _parse_version(v: str) -> tuple:
    """Parse version string to comparable tuple."""
    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(p)
    return tuple(parts)


def is_newer(latest: str, current: str) -> bool:
    """Check if latest version is newer than current."""
    try:
        return _parse_version(latest) > _parse_version(current)
    except Exception:
        return latest != current


def should_check_now() -> bool:
    """Return True if enough time has passed since last check."""
    check_file = Path(LAST_CHECK_FILE)
    if not check_file.exists():
        return True
    try:
        data = json.loads(check_file.read_text())
        last_check = datetime.fromisoformat(data["last_check"])
        return datetime.now() - last_check > CHECK_INTERVAL
    except Exception:
        return True


def record_check() -> None:
    """Record that we just performed an update check."""
    check_file = Path(LAST_CHECK_FILE)
    check_file.parent.mkdir(parents=True, exist_ok=True)
    check_file.write_text(json.dumps({
        "last_check": datetime.now().isoformat(),
        "version": get_installed_version(),
    }))


def record_version() -> None:
    """Write the current version to state/.ricet-version for migration tracking."""
    version_file = Path(VERSION_STATE_FILE)
    version_file.parent.mkdir(parents=True, exist_ok=True)
    version_file.write_text(json.dumps({
        "version": get_installed_version(),
        "installed_at": datetime.now().isoformat(),
    }))


def do_upgrade(*, use_uv: bool = False) -> bool:
    """Upgrade ricet via pip (or uv).

    Returns True if upgrade succeeded.
    """
    installer = "uv" if use_uv else "pip"
    try:
        if use_uv:
            cmd = ["uv", "pip", "install", "--upgrade", "ricet"]
        else:
            cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "ricet"]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            record_version()
            logger.info("ricet upgraded successfully via %s", installer)
            return True
        else:
            logger.error("Upgrade failed: %s", result.stderr[:500])
            return False
    except Exception as e:
        logger.error("Upgrade failed: %s", e)
        return False


def check_and_prompt(*, print_fn=None, confirm_fn=None) -> Optional[str]:
    """Check for updates and prompt the user if one is available.

    Args:
        print_fn: Function to display messages (default: print).
        confirm_fn: Function that returns True/False for user confirmation.
                    If None, just reports the update without upgrading.

    Returns:
        The new version string if an upgrade was performed, None otherwise.
    """
    if print_fn is None:
        print_fn = print

    if not should_check_now():
        return None

    current = get_installed_version()
    latest = get_latest_version()
    record_check()

    if latest is None:
        logger.debug("Could not determine latest ricet version")
        return None

    if not is_newer(latest, current):
        logger.debug("ricet %s is up to date", current)
        return None

    print_fn(f"  ricet update available: {current} -> {latest}")

    if confirm_fn is not None:
        if confirm_fn(f"Upgrade ricet to {latest}? [y/N] "):
            use_uv = bool(__import__("shutil").which("uv"))
            if do_upgrade(use_uv=use_uv):
                print_fn(f"  ricet upgraded to {latest}")
                print_fn("  Note: Restart your session to use the new version.")
                return latest
            else:
                print_fn("  Upgrade failed. You can try manually: pip install --upgrade ricet")
        else:
            print_fn("  Skipped. Run 'pip install --upgrade ricet' when ready.")
    else:
        print_fn("  Run 'pip install --upgrade ricet' to upgrade.")

    return None


# ---------------------------------------------------------------------------
# git-based self-update (for the hub dashboard + `ricet self-update` CLI)
# ---------------------------------------------------------------------------

EXPECTED_REMOTES = (
    "github.com/lucafusarbassini/research-automation",
    "github.com:lucafusarbassini/research-automation",
)


def _verify_remote(repo_path: Path) -> bool:
    """Security check: confirm ``origin`` points at the canonical GitHub repo.

    The self-update endpoint is protected by Bearer auth, but we additionally
    refuse to pull from a tampered-with remote (e.g. a malicious local clone
    pointed at an attacker URL). Returns True if the remote URL contains one
    of the EXPECTED_REMOTES fragments, False otherwise.
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(repo_path), capture_output=True, text=True, timeout=5,
        )
    except Exception as exc:
        logger.warning("remote verification failed: %s", exc)
        return False
    if result.returncode != 0:
        return False
    url = result.stdout.strip().lower()
    return any(frag in url for frag in EXPECTED_REMOTES)


def _current_branch(repo_path: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo_path), capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return "main"
    if result.returncode != 0:
        return "main"
    return result.stdout.strip() or "main"


def _current_sha(repo_path: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_path), capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def self_update(
    repo_path: Optional[Path] = None,
    *,
    reinstall: bool = True,
    verify_remote: bool = True,
) -> dict:
    """Pull latest commits, reinstall in editable mode, return a status dict.

    Does NOT restart the process — the caller is responsible for scheduling
    the restart *after* it has returned its HTTP response (see the
    ``/self-update`` endpoint in ``core.mobile``).

    Returns::

        {
            "ok": True,
            "status": "updated" | "up_to_date",
            "old_sha": "a1b2c3d",
            "new_sha": "e4f5g6h",
            "branch": "main",
        }

    or ``{"ok": False, "error": "..."}`` on failure.
    """
    if repo_path is None:
        # core/updater.py → parent.parent is the repo root
        repo_path = Path(__file__).resolve().parent.parent
    repo_path = Path(repo_path)

    if not (repo_path / ".git").exists():
        return {"ok": False, "error": "not_a_git_checkout", "repo": str(repo_path)}

    if verify_remote and not _verify_remote(repo_path):
        return {
            "ok": False,
            "error": "remote_mismatch",
            "detail": "origin does not point at github.com/lucafusarbassini/research-automation",
        }

    branch = _current_branch(repo_path)
    old_sha = _current_sha(repo_path)

    try:
        pull = subprocess.run(
            ["git", "-C", str(repo_path), "pull", "origin", branch],
            capture_output=True, text=True, timeout=120,
        )
    except Exception as exc:
        return {"ok": False, "error": f"git_pull_failed: {exc}"}
    if pull.returncode != 0:
        return {
            "ok": False,
            "error": "git_pull_failed",
            "detail": (pull.stderr or pull.stdout or "").strip()[:500],
        }

    new_sha = _current_sha(repo_path)
    status = "updated" if new_sha and new_sha != old_sha else "up_to_date"

    # Only reinstall if git actually fetched new commits
    if reinstall and status == "updated":
        installer = __import__("shutil").which("pipx")
        if installer:
            cmd = ["pipx", "install", "-e", str(repo_path), "--force"]
        else:
            cmd = [sys.executable, "-m", "pip", "install", "-e", str(repo_path), "--force-reinstall", "--no-deps"]
        try:
            reinstall_proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300,
            )
            if reinstall_proc.returncode != 0:
                return {
                    "ok": False,
                    "error": "reinstall_failed",
                    "detail": (reinstall_proc.stderr or "").strip()[:500],
                    "old_sha": old_sha,
                    "new_sha": new_sha,
                }
        except Exception as exc:
            return {
                "ok": False,
                "error": f"reinstall_exception: {exc}",
                "old_sha": old_sha,
                "new_sha": new_sha,
            }
        # Refresh cached git_info now that we're on a new SHA
        try:
            from core.git_info import refresh as _refresh_git_info
            _refresh_git_info()
        except Exception:
            pass

    return {
        "ok": True,
        "status": status,
        "old_sha": old_sha,
        "new_sha": new_sha,
        "branch": branch,
    }


def session_start_check(*, print_fn=None) -> None:
    """Lightweight check suitable for session-start hooks.

    Only checks once per CHECK_INTERVAL (default: 7 days).
    Reports the update but does not auto-install.
    """
    if print_fn is None:
        print_fn = print

    if not should_check_now():
        return

    current = get_installed_version()
    latest = get_latest_version(timeout=5)
    record_check()

    if latest and is_newer(latest, current):
        print_fn(f"  [ricet] Update available: {current} -> {latest}")
        print_fn("          Run: pip install --upgrade ricet")
