"""Security utilities: repo root enforcement, secret scanning, immutable file protection.

When claude-flow is available, scan_for_secrets merges bridge results with local regex scan.
enforce_repo_root and protect_immutable_files are kept as-is.
"""

import logging
import re
import subprocess
from pathlib import Path

from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

logger = logging.getLogger(__name__)

# Patterns that indicate secrets
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"]?[\w\-]{20,}"),
    re.compile(r"(?i)(secret|password|passwd|token)\s*[:=]\s*['\"]?[\w\-]{8,}"),
    re.compile(r"(?i)aws[_-]?(access[_-]?key|secret)\s*[:=]\s*['\"]?[\w\-/+=]{16,}"),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),  # OpenAI-style
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),  # GitHub PAT
    re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
]

# Files that should never be modified by automation
DEFAULT_IMMUTABLE = [
    ".env",
    ".env.local",
    "secrets/*",
    "*.pem",
    "*.key",
]


def enforce_repo_root() -> Path:
    """Ensure we are inside a git repository and return its root.

    Returns:
        The absolute path to the repository root.

    Raises:
        RuntimeError: If not inside a git repo.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise RuntimeError("Not inside a git repository. Run from a project directory.")


def scan_for_secrets(
    path: Path,
    *,
    extra_patterns: list[re.Pattern] | None = None,
) -> list[dict]:
    """Scan files for potential secrets.

    Args:
        path: File or directory to scan.
        extra_patterns: Additional regex patterns to check.

    Returns:
        List of dicts with 'file', 'line', and 'pattern' keys.
    """
    patterns = SECRET_PATTERNS + (extra_patterns or [])
    findings: list[dict] = []

    files = [path] if path.is_file() else _collect_scannable_files(path)

    for file_path in files:
        try:
            content = file_path.read_text(errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue

        for i, line in enumerate(content.splitlines(), 1):
            for pattern in patterns:
                if pattern.search(line):
                    findings.append({
                        "file": str(file_path),
                        "line": i,
                        "pattern": pattern.pattern[:60],
                    })
                    break  # One finding per line

    # Merge claude-flow security scan results if available
    try:
        bridge = _get_bridge()
        cf_result = bridge.scan_security(str(path))
        cf_findings = cf_result.get("findings", [])
        seen = {(f["file"], f["line"]) for f in findings}
        for cf in cf_findings:
            key = (cf.get("file", ""), cf.get("line", 0))
            if key not in seen:
                findings.append({
                    "file": cf.get("file", ""),
                    "line": cf.get("line", 0),
                    "pattern": cf.get("pattern", "claude-flow"),
                })
    except ClaudeFlowUnavailable:
        pass

    if findings:
        logger.warning("Found %d potential secret(s)", len(findings))
    return findings


def protect_immutable_files(
    files_to_check: list[Path],
    *,
    immutable: list[str] | None = None,
) -> list[Path]:
    """Check if any files in the list are immutable/protected.

    Args:
        files_to_check: Files that are about to be modified.
        immutable: Glob patterns for immutable files. Uses DEFAULT_IMMUTABLE if None.

    Returns:
        List of protected files that should NOT be modified.
    """
    protected_patterns = immutable or DEFAULT_IMMUTABLE
    blocked: list[Path] = []

    for file_path in files_to_check:
        for pattern in protected_patterns:
            if file_path.match(pattern):
                blocked.append(file_path)
                logger.warning("Blocked modification of protected file: %s", file_path)
                break

    return blocked


def _collect_scannable_files(directory: Path, max_files: int = 500) -> list[Path]:
    """Collect files suitable for scanning, skipping binaries and large files."""
    scannable = []
    skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv"}
    text_suffixes = {
        ".py", ".yml", ".yaml", ".json", ".toml", ".cfg", ".ini",
        ".sh", ".bash", ".env", ".txt", ".md", ".tex", ".bib",
        ".js", ".ts", ".r", ".R",
    }

    for item in directory.rglob("*"):
        if any(part in skip_dirs for part in item.parts):
            continue
        if item.is_file() and item.suffix in text_suffixes and item.stat().st_size < 1_000_000:
            scannable.append(item)
            if len(scannable) >= max_files:
                break

    return scannable
