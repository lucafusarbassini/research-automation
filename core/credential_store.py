"""Global credential store for sharing secrets across ricet projects.

Credentials are stored in ``~/.ricet/credentials.env`` (chmod 600) using
simple KEY=VALUE format.  Project-level secrets always take precedence.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

GLOBAL_CREDS_DIR = Path.home() / ".ricet"
GLOBAL_CREDS_FILE = GLOBAL_CREDS_DIR / "credentials.env"


def load_global_credentials() -> dict[str, str]:
    """Load credentials from the global store.

    Returns an empty dict if the file doesn't exist.
    """
    if not GLOBAL_CREDS_FILE.exists():
        return {}

    creds: dict[str, str] = {}
    for line in GLOBAL_CREDS_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and value:
                creds[key] = value
    return creds


def save_global_credentials(creds: dict[str, str]) -> Path:
    """Save credentials to the global store (chmod 600).

    Only non-empty values are persisted.  Existing keys not present in
    *creds* are preserved.
    """
    GLOBAL_CREDS_DIR.mkdir(parents=True, exist_ok=True)

    # Merge with existing
    existing = load_global_credentials()
    existing.update({k: v for k, v in creds.items() if v})

    lines = ["# ricet global credentials — auto-generated, chmod 600\n"]
    for key, value in sorted(existing.items()):
        lines.append(f"{key}={value}\n")

    GLOBAL_CREDS_FILE.write_text("".join(lines))
    os.chmod(GLOBAL_CREDS_FILE, 0o600)
    logger.info("Saved %d credentials to %s", len(existing), GLOBAL_CREDS_FILE)
    return GLOBAL_CREDS_FILE


def merge_credentials(
    global_creds: dict[str, str],
    project_creds: dict[str, str],
) -> dict[str, str]:
    """Merge global and project credentials. Project values win."""
    merged = dict(global_creds)
    merged.update({k: v for k, v in project_creds.items() if v})
    return merged


def mask_value(value: str) -> str:
    """Return a masked version of a credential value for display."""
    if len(value) <= 4:
        return "****"
    return value[:2] + "*" * (len(value) - 4) + value[-2:]
