"""Meta-rule capture: detect operational rules, classify, and append to cheatsheet."""

import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

CHEATSHEET_PATH = Path("knowledge/CHEATSHEET.md")

RULE_TYPES = {
    "workflow": ["always", "never", "before", "after", "first", "then", "step"],
    "constraint": [
        "must",
        "shall",
        "required",
        "forbidden",
        "limit",
        "maximum",
        "minimum",
    ],
    "preference": ["prefer", "recommend", "better", "best", "avoid", "default"],
    "debug": ["when.*error", "if.*fails", "workaround", "fix", "gotcha", "caveat"],
}


def detect_operational_rule(text: str) -> bool:
    """Detect if a text snippet contains an operational rule.

    Args:
        text: Text to analyze.

    Returns:
        True if the text appears to be an operational rule.
    """
    text_lower = text.lower().strip()

    # Must have imperative or prescriptive tone
    imperative_markers = [
        "always",
        "never",
        "must",
        "should",
        "do not",
        "don't",
        "make sure",
        "remember to",
        "important:",
        "note:",
        "rule:",
        "tip:",
        "trick:",
    ]

    return any(marker in text_lower for marker in imperative_markers)


def classify_rule_type(text: str) -> str:
    """Classify a rule into a category.

    Args:
        text: Rule text.

    Returns:
        One of 'workflow', 'constraint', 'preference', 'debug', or 'general'.
    """
    text_lower = text.lower()

    scores = {}
    for rule_type, patterns in RULE_TYPES.items():
        score = sum(1 for p in patterns if re.search(p, text_lower))
        if score > 0:
            scores[rule_type] = score

    if not scores:
        return "general"
    return max(scores, key=scores.get)


def append_to_cheatsheet(
    rule: str,
    *,
    rule_type: str = "",
    cheatsheet_path: Path = CHEATSHEET_PATH,
) -> None:
    """Append a rule to the cheatsheet file.

    Args:
        rule: The rule text to append.
        rule_type: Category (auto-detected if empty).
        cheatsheet_path: Path to the cheatsheet file.
    """
    if not rule_type:
        rule_type = classify_rule_type(rule)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not cheatsheet_path.exists():
        cheatsheet_path.parent.mkdir(parents=True, exist_ok=True)
        cheatsheet_path.write_text(
            "# Operational Cheatsheet\n\n"
            "## Workflow\n\n## Constraints\n\n## Preferences\n\n## Debug Tips\n\n## General\n"
        )

    content = cheatsheet_path.read_text()

    # Map rule_type to section header
    section_map = {
        "workflow": "## Workflow",
        "constraint": "## Constraints",
        "preference": "## Preferences",
        "debug": "## Debug Tips",
        "general": "## General",
    }

    section_header = section_map.get(rule_type, "## General")
    entry = f"\n- [{timestamp}] {rule}"

    # Find section and append
    idx = content.find(section_header)
    if idx >= 0:
        insert_pos = idx + len(section_header)
        content = content[:insert_pos] + entry + content[insert_pos:]
    else:
        content += f"\n{section_header}{entry}\n"

    cheatsheet_path.write_text(content)
    logger.info("Added %s rule to cheatsheet", rule_type)
