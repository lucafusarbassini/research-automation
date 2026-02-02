"""Encyclopedia auto-update and knowledge management.

Handles persistent knowledge across sessions: learnings, decisions,
successful/failed approaches. When claude-flow is available, search_knowledge
uses HNSW vector memory for semantic search, and append_learning dual-writes
to both markdown and the vector index.

Section matching is fuzzy and case-insensitive: aliases like "tips" resolve to
"Tricks", "failures" resolves to "What Doesn't Work", etc.  If a section
doesn't exist in the file it is created dynamically at the end.
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

# ---------------------------------------------------------------------------
# Section type definitions with canonical names and aliases
# ---------------------------------------------------------------------------

# Canonical section type -> (canonical header name, set of lowercase aliases)
SECTION_TYPES: dict[str, tuple[str, set[str]]] = {
    "tricks": (
        "Tricks",
        {
            "tricks",
            "tips",
            "useful tips",
            "tips and tricks",
            "hints",
        },
    ),
    "decisions": (
        "Decisions",
        {
            "decisions",
            "design decisions",
            "choices",
            "rationale",
            "design choices",
        },
    ),
    "what_works": (
        "What Works",
        {
            "what works",
            "successes",
            "working approaches",
            "good results",
            "successful approaches",
        },
    ),
    "what_doesnt_work": (
        "What Doesn't Work",
        {
            "what doesn't work",
            "what doesnt work",
            "what doesn\u2019t work",
            "failures",
            "failed approaches",
            "what failed",
            "pitfalls",
        },
    ),
}


def _normalize(name: str) -> str:
    """Lowercase, strip, collapse whitespace, remove trailing punctuation."""
    name = name.strip().lower()
    name = re.sub(r"\s+", " ", name)
    name = name.rstrip(":")
    return name


def _resolve_section_type(name: str) -> str | None:
    """Return the canonical section-type key for *name*, or ``None``.

    Tries, in order:
    1. Exact alias match (case-insensitive).
    2. Substring / containment match (alias contained in name or vice-versa).
    """
    norm = _normalize(name)
    # 1. Exact alias hit
    for key, (_canon, aliases) in SECTION_TYPES.items():
        if norm in aliases or norm == _normalize(_canon):
            return key
    # 2. Fuzzy containment
    for key, (_canon, aliases) in SECTION_TYPES.items():
        for alias in aliases:
            if alias in norm or norm in alias:
                return key
    return None


def discover_sections(content: str) -> dict[str, str]:
    """Scan *content* for ``## <name>`` headers and return ``{lowercase_name: original_name}``.

    This allows the system to discover section names that may have drifted
    from the canonical names without breaking.
    """
    sections: dict[str, str] = {}
    for m in re.finditer(r"^## (.+)$", content, re.MULTILINE):
        header = m.group(1).strip()
        sections[_normalize(header)] = header
    return sections


def find_section(content: str, section_type: str) -> str | None:
    """Find the actual ``## <header>`` name present in *content* that matches *section_type*.

    *section_type* can be a canonical key (``"tricks"``), a canonical header
    (``"Tricks"``), or any known alias (``"tips and tricks"``).

    Returns the **exact header text** as it appears in the file, or ``None``
    if no matching header exists.
    """
    discovered = discover_sections(content)

    # Resolve the requested name to a canonical type key
    type_key = _resolve_section_type(section_type)

    if type_key is not None:
        _canon, aliases = SECTION_TYPES[type_key]
        # Check discovered headers against the canonical name + aliases
        for norm_header, orig_header in discovered.items():
            if norm_header == _normalize(_canon):
                return orig_header
            if norm_header in aliases:
                return orig_header
            # Also try containment for drifted names
            for alias in aliases:
                if alias in norm_header or norm_header in alias:
                    return orig_header

    # Fallback: try direct normalized match against discovered headers
    norm_requested = _normalize(section_type)
    if norm_requested in discovered:
        return discovered[norm_requested]

    return None


def _default_comment_for_type(type_key: str) -> str:
    """Return the default HTML comment for a canonical section type."""
    comments = {
        "tricks": "<!-- Learnings get appended here -->",
        "decisions": "<!-- Design decisions get logged here -->",
        "what_works": "<!-- Successful approaches -->",
        "what_doesnt_work": "<!-- Failed approaches (to avoid repeating) -->",
    }
    return comments.get(type_key, "")


def _ensure_section(content: str, section_type: str) -> tuple[str, str]:
    """Ensure *content* contains a header matching *section_type*.

    Returns ``(possibly_updated_content, actual_header_name)``.
    If the section didn't exist, it is appended at the end of the file.
    """
    header = find_section(content, section_type)
    if header is not None:
        return content, header

    # Section missing -- create it
    type_key = _resolve_section_type(section_type)
    if type_key is not None:
        canon_name = SECTION_TYPES[type_key][0]
        comment = _default_comment_for_type(type_key)
    else:
        # Completely unknown section -- use the provided name capitalised
        canon_name = section_type.strip().title()
        comment = ""

    new_section = f"\n\n## {canon_name}\n"
    if comment:
        new_section += f"{comment}\n"
    content = content.rstrip("\n") + new_section
    logger.info("Created missing section '%s' in encyclopedia", canon_name)
    return content, canon_name


def append_learning(
    section: str,
    entry: str,
    encyclopedia_path: Path = ENCYCLOPEDIA_PATH,
) -> None:
    """Append a learning to the encyclopedia under the given section.

    *section* is matched fuzzily: ``"tips"``, ``"Tricks"``, ``"tips and tricks"``
    all resolve to the Tricks section.  If the section doesn't exist yet it is
    created dynamically.

    Args:
        section: Section name, alias, or canonical type key.
        entry: The text to append.
        encyclopedia_path: Path to the encyclopedia file.
    """
    if not encyclopedia_path.exists():
        encyclopedia_path.parent.mkdir(parents=True, exist_ok=True)
        encyclopedia_path.write_text(
            "# Encyclopedia\n\n## Tricks\n\n## Decisions\n\n"
            "## What Works\n\n## What Fails\n"
        )
        logger.info("Created encyclopedia at %s", encyclopedia_path)

    content = encyclopedia_path.read_text()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Include user_id for collaborative tracking
    try:
        from core.collaboration import get_user_id

        user_id = get_user_id()
        formatted_entry = f"\n- [{timestamp}] ({user_id}) {entry}"
    except Exception:
        formatted_entry = f"\n- [{timestamp}] {entry}"

    # Ensure the target section exists (creates it if missing)
    content, actual_header = _ensure_section(content, section)

    # Find the section header and append after the comment line
    pattern = rf"(## {re.escape(actual_header)}\n(?:<!--.*?-->\n)?)"
    match = re.search(pattern, content)
    if match:
        insert_pos = match.end()
        content = content[:insert_pos] + formatted_entry + content[insert_pos:]
        encyclopedia_path.write_text(content)
        logger.info("Added entry to '%s' section", actual_header)

        # Dual-write to claude-flow HNSW vector memory
        try:
            bridge = _get_bridge()
            bridge.store_memory(
                entry,
                namespace="knowledge",
                metadata={"section": actual_header, "timestamp": timestamp},
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


def sync_learnings_to_project(source_project: Path, target_project: Path) -> dict:
    """Transfer encyclopedia entries and meta-rules from source to target project.

    Reads source project's knowledge/ENCYCLOPEDIA.md and knowledge/CHEATSHEET.md,
    deduplicates against target's existing entries, and appends new ones.

    Returns dict with counts: {"encyclopedia_transferred": int, "rules_transferred": int}
    """
    result = {"encyclopedia_transferred": 0, "rules_transferred": 0}

    # --- Encyclopedia transfer ---
    src_enc = source_project / "knowledge" / "ENCYCLOPEDIA.md"
    tgt_enc = target_project / "knowledge" / "ENCYCLOPEDIA.md"

    if src_enc.exists():
        src_content = src_enc.read_text()
        tgt_content = tgt_enc.read_text() if tgt_enc.exists() else ""

        # Split source into entries by "## " section headers
        # Extract individual bullet entries (lines starting with "- [")
        src_entries = [
            line.strip()
            for line in src_content.splitlines()
            if line.strip().startswith("- [")
        ]
        tgt_lines_set = set(tgt_content.splitlines())

        new_entries = []
        for entry in src_entries:
            # Check for duplicate by exact match or matching content after timestamp
            if entry not in tgt_lines_set and entry.strip() not in tgt_content:
                new_entries.append(entry)

        if new_entries and tgt_enc.exists():
            # Append new entries to the "Tricks" section (general catch-all)
            for entry in new_entries:
                append_learning(
                    "Tricks",
                    entry.lstrip("- ").lstrip(),
                    encyclopedia_path=tgt_enc,
                )
            result["encyclopedia_transferred"] = len(new_entries)

    # --- Cheatsheet / meta-rules transfer ---
    src_cheat = source_project / "knowledge" / "CHEATSHEET.md"
    tgt_cheat = target_project / "knowledge" / "CHEATSHEET.md"

    if src_cheat.exists():
        src_rules = src_cheat.read_text()
        tgt_rules = tgt_cheat.read_text() if tgt_cheat.exists() else ""

        # Split rules by "---" separators or "## " headers
        import re as _re

        src_blocks = _re.split(r"\n---\n|\n## ", src_rules)
        tgt_blocks_text = tgt_rules

        new_rules = []
        for block in src_blocks:
            block = block.strip()
            if not block:
                continue
            # Use the first line as the dedup key
            first_line = block.splitlines()[0].strip() if block.splitlines() else ""
            if first_line and first_line not in tgt_blocks_text:
                new_rules.append(block)

        if new_rules:
            tgt_cheat.parent.mkdir(parents=True, exist_ok=True)
            with open(tgt_cheat, "a") as f:
                for rule in new_rules:
                    f.write(f"\n---\n{rule}\n")
            result["rules_transferred"] = len(new_rules)

    return result


def get_encyclopedia_stats(
    encyclopedia_path: Path = ENCYCLOPEDIA_PATH,
) -> dict:
    """Get statistics about the encyclopedia.

    Uses fuzzy matching to find sections, so files with drifted header names
    still report correctly.

    Returns:
        Dict with counts per canonical section name.
    """
    if not encyclopedia_path.exists():
        return {}

    content = encyclopedia_path.read_text()
    canonical_sections = ["Tricks", "Decisions", "What Works", "What Doesn't Work"]
    stats = {}

    for section in canonical_sections:
        actual_header = find_section(content, section)
        if actual_header is None:
            stats[section] = 0
            continue
        pattern = rf"## {re.escape(actual_header)}\n(.*?)(?=\n## |\Z)"
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
