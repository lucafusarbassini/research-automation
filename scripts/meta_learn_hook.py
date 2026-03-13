#!/usr/bin/env python3
"""UserPromptSubmit hook: capture explicit behavioral rules from user messages.

Called by Claude Code's UserPromptSubmit hook with the user's message in
the $PROMPT environment variable.

DESIGN: explicit-only capture. Rules are recorded ONLY when the user
deliberately signals them with a known magic prefix. All other matching
(broad regex over sentence content) proved too noisy.

Recognised prefixes (case-insensitive, at start of a line or sentence):
    remember:   <rule>
    rule:       <rule>
    add rule:   <rule>
    always:     <rule>
    never:      <rule>     ← only at sentence start, not mid-sentence
    from now on: <rule>

For ad-hoc rule management use:
    ricet memory add-rule "Your rule"
    ricet memory rules

Designed to be fast (<50ms), uses stdlib only.
"""

import os
import re
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
RULES_FILE = PROJECT_ROOT / "knowledge" / "RULES.md"

# Magic prefixes that signal deliberate rule capture
# Must appear at the start of a line or after sentence-ending punctuation
_PREFIX_RE = re.compile(
    r"(?:^|(?<=[.!?])\s+)"           # start of text or after sentence end
    r"(?:remember|rule|add rule|from now on|always remember)\s*:\s*"
    r"(.{10,150}?)(?=[.!?\n]|$)",    # capture the rule body (10-150 chars)
    re.IGNORECASE | re.MULTILINE,
)

MAX_RULE_LEN = 150


def _existing_rules(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip("- \n") for line in path.read_text().splitlines() if line.startswith("- ")}


def _append_rules(rules: list[str], path: Path) -> int:
    if not rules:
        return 0
    existing = _existing_rules(path)
    new_rules = [r.strip() for r in rules if r.strip() and r.strip() not in existing]
    if not new_rules:
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    if not path.exists():
        path.write_text(
            "# Behavioral Rules\n\n"
            "Fundamental principles from user corrections.\n"
            "Edit freely — loaded into every session.\n\n"
        )

    with path.open("a") as f:
        f.write(f"\n<!-- {today} -->\n")
        for rule in new_rules:
            rule_text = rule[:MAX_RULE_LEN]
            f.write(f"- {rule_text}\n")

    return len(new_rules)


def main() -> None:
    prompt = os.environ.get("PROMPT", "").strip()
    if not prompt:
        if not sys.stdin.isatty():
            prompt = sys.stdin.read().strip()
    if not prompt:
        return

    matches = _PREFIX_RE.findall(prompt)
    added = _append_rules(matches, RULES_FILE)

    if added and os.environ.get("RICET_META_DEBUG"):
        print(f"[meta-learn] captured {added} explicit rule(s)")


if __name__ == "__main__":
    main()
