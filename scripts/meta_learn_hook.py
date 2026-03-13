#!/usr/bin/env python3
"""UserPromptSubmit hook: extract behavioral rules from user messages.

Called by Claude Code's UserPromptSubmit hook with the user's message in
the $PROMPT environment variable. Detects corrections and rules, then
appends them to knowledge/RULES.md for persistence across sessions.

Designed to be fast (<100ms), uses stdlib only.
"""

import os
import re
import sys
from datetime import date
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
RULES_FILE = PROJECT_ROOT / "knowledge" / "RULES.md"

# ── Detection patterns ────────────────────────────────────────────────────────

# Sentences that are almost certainly correction/preference signals
CORRECTION_PATTERNS = [
    # Explicit negation rules
    r"\b(don'?t|never|stop|avoid|no more)\b.{3,60}",
    # Affirmative rules
    r"\b(always|must|should|make sure|remember to|from now on|going forward)\b.{3,60}",
    # Explicit rule declarations
    r"\b(the rule is|important:|note:|rule:)\b.{3,60}",
    # "X is not Y" corrections
    r"\b\w[\w\s]{0,20}\b is (not|wrong|incorrect|false|bad)\b.{0,40}",
    # Disagreement openers
    r"^(no[,.]|that'?s (not|wrong)|incorrect|wrong)[,\s].{5,80}",
    # "please don't / please always"
    r"\bplease (don'?t|never|always|stop)\b.{3,60}",
    # Try-except / coding style corrections
    r"\btry.?except\b.{3,60}",
]

COMPILED = [re.compile(p, re.IGNORECASE) for p in CORRECTION_PATTERNS]

# Things that look like rules but are too generic to log
NOISE_PATTERNS = [
    r"^(yes|ok|okay|sure|got it|thanks|thank you|great|good|done)[.!?]?$",
    r"^\d+[\).]",  # numbered list items by themselves
    r"^http",
]
NOISE = [re.compile(p, re.IGNORECASE) for p in NOISE_PATTERNS]

# Max length of a logged rule (keeps RULES.md tidy)
MAX_RULE_LEN = 120


def _split_sentences(text: str) -> list[str]:
    """Rough sentence splitter: split on '. ', '! ', '? ', newlines."""
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def _is_rule(sentence: str) -> bool:
    if len(sentence) < 8 or len(sentence) > 300:
        return False
    if any(n.search(sentence) for n in NOISE):
        return False
    return any(p.search(sentence) for p in COMPILED)


def _normalise(sentence: str) -> str:
    """Trim to MAX_RULE_LEN, strip trailing punctuation clutter."""
    s = sentence.strip()
    if len(s) > MAX_RULE_LEN:
        s = s[:MAX_RULE_LEN].rsplit(" ", 1)[0] + "…"
    return s


def _existing_rules(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip("- \n") for line in path.read_text().splitlines() if line.startswith("- ")}


def _append_rules(rules: list[str], path: Path) -> int:
    """Append new (non-duplicate) rules. Returns count added."""
    if not rules:
        return 0

    existing = _existing_rules(path)
    new_rules = [r for r in rules if r not in existing]
    if not new_rules:
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    if not path.exists():
        path.write_text(
            "# Behavioral Rules\n\n"
            "Automatically captured from user corrections during Claude Code sessions.\n"
            "Edit or delete entries freely — this file is loaded into every session.\n\n"
        )

    with path.open("a") as f:
        f.write(f"\n<!-- {today} -->\n")
        for rule in new_rules:
            f.write(f"- {rule}\n")

    return len(new_rules)


def main() -> None:
    prompt = os.environ.get("PROMPT", "").strip()
    if not prompt:
        # Also accept stdin (for manual testing)
        if not sys.stdin.isatty():
            prompt = sys.stdin.read().strip()
    if not prompt:
        return

    sentences = _split_sentences(prompt)
    rules = [_normalise(s) for s in sentences if _is_rule(s)]

    added = _append_rules(rules, RULES_FILE)
    if added:
        # Silent success — Claude Code hook output is shown to user
        # Only print if run directly for debugging
        if os.environ.get("RICET_META_DEBUG"):
            print(f"[meta-learn] captured {added} rule(s)")


if __name__ == "__main__":
    main()
