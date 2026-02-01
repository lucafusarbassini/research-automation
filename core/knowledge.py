"""Encyclopedia auto-update and knowledge management.

Handles persistent knowledge across sessions: learnings, decisions,
successful/failed approaches. Optionally integrates with ChromaDB
for semantic search over accumulated knowledge.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

ENCYCLOPEDIA_PATH = Path("knowledge/ENCYCLOPEDIA.md")
SHARED_KNOWLEDGE_PATH = Path("/shared/knowledge")


def append_learning(
    section: str,
    entry: str,
    encyclopedia_path: Path = ENCYCLOPEDIA_PATH,
) -> None:
    """Append a learning to the encyclopedia under the given section.

    Args:
        section: One of 'Tricks', 'Decisions', 'What Works', 'What Doesn\\'t Work'.
        entry: The text to append.
        encyclopedia_path: Path to the encyclopedia file.
    """
    if not encyclopedia_path.exists():
        logger.warning("Encyclopedia not found at %s", encyclopedia_path)
        return

    content = encyclopedia_path.read_text()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    formatted_entry = f"\n- [{timestamp}] {entry}"

    # Find the section header and append after the comment line
    pattern = rf"(## {re.escape(section)}\n(?:<!--.*?-->\n)?)"
    match = re.search(pattern, content)
    if match:
        insert_pos = match.end()
        content = content[:insert_pos] + formatted_entry + content[insert_pos:]
        encyclopedia_path.write_text(content)
        logger.info("Added entry to '%s' section", section)
    else:
        logger.warning("Section '%s' not found in encyclopedia", section)


def log_decision(decision: str, rationale: str) -> None:
    """Log a design decision with rationale."""
    entry = f"{decision} -- Rationale: {rationale}"
    append_learning("Decisions", entry)


def log_success(approach: str, context: str) -> None:
    """Log a successful approach."""
    entry = f"{approach} (context: {context})"
    append_learning("What Works", entry)


def log_failure(approach: str, reason: str) -> None:
    """Log a failed approach to avoid repeating it."""
    entry = f"{approach} -- Failed because: {reason}"
    append_learning("What Doesn't Work", entry)


def log_trick(trick: str) -> None:
    """Log a useful trick or tip discovered during work."""
    append_learning("Tricks", trick)


def sync_to_shared(
    project_name: str,
    encyclopedia_path: Path = ENCYCLOPEDIA_PATH,
    shared_path: Path = SHARED_KNOWLEDGE_PATH,
) -> None:
    """Sync project encyclopedia to shared cross-project knowledge store.

    Args:
        project_name: Name of the current project.
        encyclopedia_path: Path to project encyclopedia.
        shared_path: Path to shared knowledge directory.
    """
    if not shared_path.exists():
        shared_path.mkdir(parents=True, exist_ok=True)

    dest = shared_path / f"{project_name}.md"
    if encyclopedia_path.exists():
        dest.write_text(encyclopedia_path.read_text())
        logger.info("Synced encyclopedia to %s", dest)


def search_knowledge(
    query: str,
    encyclopedia_path: Path = ENCYCLOPEDIA_PATH,
) -> list[str]:
    """Simple keyword search over the encyclopedia.

    For semantic search, use the ChromaDB integration via the chroma-mcp.

    Args:
        query: Search query string.
        encyclopedia_path: Path to encyclopedia file.

    Returns:
        List of matching lines.
    """
    if not encyclopedia_path.exists():
        return []

    query_lower = query.lower()
    results = []
    for line in encyclopedia_path.read_text().splitlines():
        if query_lower in line.lower():
            results.append(line.strip())

    return results


def get_encyclopedia_stats(
    encyclopedia_path: Path = ENCYCLOPEDIA_PATH,
) -> dict:
    """Get statistics about the encyclopedia.

    Returns:
        Dict with counts per section.
    """
    if not encyclopedia_path.exists():
        return {}

    content = encyclopedia_path.read_text()
    sections = ["Tricks", "Decisions", "What Works", "What Doesn't Work"]
    stats = {}

    for section in sections:
        pattern = rf"## {re.escape(section)}\n(.*?)(?=\n## |\Z)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            entries = [
                line
                for line in match.group(1).strip().splitlines()
                if line.strip().startswith("- [")
            ]
            stats[section] = len(entries)
        else:
            stats[section] = 0

    return stats
