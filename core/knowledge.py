"""Encyclopedia auto-update and knowledge management.

Handles persistent knowledge across sessions: learnings, decisions,
successful/failed approaches. When claude-flow is available, search_knowledge
uses HNSW vector memory for semantic search, and append_learning dual-writes
to both markdown and the vector index.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

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

    # Include user_id for collaborative tracking
    try:
        from core.collaboration import get_user_id

        user_id = get_user_id()
        formatted_entry = f"\n- [{timestamp}] ({user_id}) {entry}"
    except Exception:
        formatted_entry = f"\n- [{timestamp}] {entry}"

    # Find the section header and append after the comment line
    pattern = rf"(## {re.escape(section)}\n(?:<!--.*?-->\n)?)"
    match = re.search(pattern, content)
    if match:
        insert_pos = match.end()
        content = content[:insert_pos] + formatted_entry + content[insert_pos:]
        encyclopedia_path.write_text(content)
        logger.info("Added entry to '%s' section", section)

        # Dual-write to claude-flow HNSW vector memory
        try:
            bridge = _get_bridge()
            bridge.store_memory(
                entry,
                namespace="knowledge",
                metadata={"section": section, "timestamp": timestamp},
            )
        except ClaudeFlowUnavailable:
            pass
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
    """Search the encyclopedia, using semantic search when claude-flow is available.

    Tries HNSW vector memory first for semantic results, then merges with
    keyword matches from the markdown file.

    Args:
        query: Search query string.
        encyclopedia_path: Path to encyclopedia file.

    Returns:
        List of matching lines/entries.
    """
    results: list[str] = []

    # Try semantic search via claude-flow
    try:
        bridge = _get_bridge()
        cf_result = bridge.query_memory(query, top_k=10)
        for hit in cf_result.get("results", []):
            text = hit.get("text", "").strip()
            if text and text not in results:
                results.append(text)
    except ClaudeFlowUnavailable:
        pass

    # Always merge with keyword search from markdown
    if encyclopedia_path.exists():
        query_lower = query.lower()
        for line in encyclopedia_path.read_text().splitlines():
            stripped = line.strip()
            if query_lower in stripped.lower() and stripped not in results:
                results.append(stripped)

    # Cross-repo RAG: search linked repositories
    if query:
        try:
            from core.cross_repo import search_all_linked

            linked_results = search_all_linked(query)
            for hit in linked_results:
                text = hit.get("text", "").strip()
                source = hit.get("source", "linked")
                tagged = f"[{source}] {text}"
                if tagged not in results and text not in results:
                    results.append(tagged)
        except Exception:
            pass

    return results


def export_knowledge(
    project_name: str,
    *,
    encyclopedia_path: Path = ENCYCLOPEDIA_PATH,
    output_path: Path | None = None,
) -> Path:
    """Export project knowledge to a portable JSON format.

    Args:
        project_name: Name of the current project.
        encyclopedia_path: Path to the encyclopedia.
        output_path: Where to write the export. Auto-generated if None.

    Returns:
        Path to the exported file.
    """
    if not encyclopedia_path.exists():
        raise FileNotFoundError(f"Encyclopedia not found: {encyclopedia_path}")

    stats = get_encyclopedia_stats(encyclopedia_path)
    content = encyclopedia_path.read_text()
    entries = search_knowledge("", encyclopedia_path)  # Get all lines

    export_data = {
        "project": project_name,
        "exported": datetime.now().isoformat(),
        "stats": stats,
        "content": content,
    }

    if output_path is None:
        output_path = encyclopedia_path.parent / f"{project_name}_export.json"

    output_path.write_text(json.dumps(export_data, indent=2))
    logger.info("Exported knowledge to %s", output_path)
    return output_path


def import_knowledge(
    import_path: Path,
    *,
    encyclopedia_path: Path = ENCYCLOPEDIA_PATH,
    merge: bool = True,
) -> int:
    """Import knowledge from a previously exported file.

    Args:
        import_path: Path to the exported JSON file.
        encyclopedia_path: Path to the target encyclopedia.
        merge: If True, append entries. If False, replace.

    Returns:
        Number of entries imported.
    """
    if not import_path.exists():
        raise FileNotFoundError(f"Import file not found: {import_path}")

    data = json.loads(import_path.read_text())
    imported_content = data.get("content", "")

    if not imported_content:
        return 0

    if not merge or not encyclopedia_path.exists():
        encyclopedia_path.parent.mkdir(parents=True, exist_ok=True)
        encyclopedia_path.write_text(imported_content)
        logger.info("Replaced encyclopedia with imported content")
        return len(
            [l for l in imported_content.splitlines() if l.strip().startswith("- [")]
        )

    # Merge: extract entries from imported content and append
    existing = encyclopedia_path.read_text()
    count = 0
    for line in imported_content.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [") and stripped not in existing:
            # Find which section it belongs to by context
            append_learning(
                "Tricks", stripped.lstrip("- "), encyclopedia_path=encyclopedia_path
            )
            count += 1

    logger.info("Imported %d entries", count)
    return count


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
