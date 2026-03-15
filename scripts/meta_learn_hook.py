#!/usr/bin/env python3
"""UserPromptSubmit hook: Claude-intelligence-driven knowledge extraction.

Called by Claude Code's UserPromptSubmit hook with the user's message in
the $PROMPT environment variable.

DESIGN: semantic extraction via Claude (Haiku — fast + cheap). Claude reads
the full user message and decides:
  - What is worth preserving (most messages: nothing)
  - Where it goes:
      RULES.md        — behavioral instructions for the AI assistant
      ENCYCLOPEDIA.md — domain insights, research knowledge, technique notes
      DECISION_LOG.md — project-level architectural / methodological choices

Falls back silently if the API is unavailable. Never blocks the session.
"""

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
RULES_FILE = PROJECT_ROOT / "knowledge" / "RULES.md"
ENCYCLOPEDIA_FILE = PROJECT_ROOT / "knowledge" / "ENCYCLOPEDIA.md"
DECISION_LOG_FILE = PROJECT_ROOT / "knowledge" / "DECISION_LOG.md"

_EXTRACTION_PROMPT = """\
You are a knowledge extraction agent for a research automation system called ricet.

A user sent the following message to an AI coding assistant. Extract anything genuinely \
worth preserving in long-term memory. Most messages contain nothing — return [] in that case.

Classify each extracted item into one of three types:

"rule"     — A behavioral instruction for the AI: how to behave, what to avoid, \
coding style, workflow preferences, corrections to past mistakes.

"insight"  — A domain fact, research finding, scientific technique, or piece of \
knowledge about the field (not about the AI's behavior).

"decision" — A project-level choice made for THIS project: architectural, \
methodological, or strategic. Must have clear rationale.

Return a JSON array. Each element: \
{"type": "rule"|"insight"|"decision", "content": "<distilled one-sentence summary>", \
"rationale": "<required for decisions; brief for others if helpful>"}

Be very conservative. Do NOT capture:
- Frustration or venting that doesn't encode a clear rule
- Questions or requests
- Status updates, check-ins, or task instructions
- Anything derivable by reading the code
- Transient debugging details
- Text the user is quoting from elsewhere

USER MESSAGE:
{message}"""


def _load_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    try:
        from dotenv import load_dotenv
        for candidate in [Path.cwd() / ".env", PROJECT_ROOT / ".env"]:
            if candidate.exists():
                load_dotenv(candidate, override=False)
                break
        key = os.environ.get("ANTHROPIC_API_KEY", "")
    except ImportError:
        pass
    return key


def _call_claude(message: str) -> list[dict]:
    """Call Claude Haiku for semantic extraction. Returns [] on any failure."""
    try:
        import anthropic
    except ImportError:
        return []

    api_key = _load_api_key()
    if not api_key:
        return []

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": _EXTRACTION_PROMPT.format(message=message[:4000])}],
        )
        text = msg.content[0].text if msg.content else "[]"
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return []


# ── writers ──────────────────────────────────────────────────────────────────

def _existing_bullets(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip("- \n") for line in path.read_text().splitlines() if line.startswith("- ")}


def _is_low_quality(content: str) -> bool:
    """Reject garbled, noisy, or trivially short content."""
    content = content.strip()
    if len(content) < 15:
        return True
    # Excessive punctuation (frustration/venting that slipped through)
    punct_count = sum(1 for c in content if c in "!?.")
    if punct_count > 5:
        return True
    # Raw multi-line user text (numbered lists, multiple newlines)
    if "\n\n" in content:
        return True
    if re.match(r"^\d+\)", content):
        return True
    # Auto-commit noise
    if "auto-commit:" in content or "state-modifying CLI" in content:
        return True
    # Session lifecycle noise
    if re.match(r"^session (started|ended):", content):
        return True
    return False


def _fuzzy_exists(content: str, existing: set[str]) -> bool:
    """Check if content's first 30 chars match any existing entry."""
    prefix = content[:30].lower()
    return any(e[:30].lower() == prefix for e in existing if len(e) >= 10)


def _append_rule(content: str) -> bool:
    content = content.strip()
    if not content or _is_low_quality(content):
        return False
    existing = _existing_bullets(RULES_FILE)
    if content in existing or _fuzzy_exists(content, existing):
        return False
    RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not RULES_FILE.exists():
        RULES_FILE.write_text(
            "# Behavioral Rules\n\n"
            "Behavioral principles captured from user corrections.\n"
            "Edit freely — loaded into every session.\n\n"
        )
    with RULES_FILE.open("a") as f:
        f.write(f"\n<!-- {date.today().isoformat()} -->\n- {content}\n")
    return True


def _append_insight(content: str) -> bool:
    content = content.strip()
    if not content or _is_low_quality(content):
        return False
    if ENCYCLOPEDIA_FILE.exists():
        text = ENCYCLOPEDIA_FILE.read_text()
        if content[:50] in text:
            return False
        existing = _existing_bullets(ENCYCLOPEDIA_FILE)
        if _fuzzy_exists(content, existing):
            return False
    ENCYCLOPEDIA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not ENCYCLOPEDIA_FILE.exists():
        ENCYCLOPEDIA_FILE.write_text("# Encyclopedia\n\nAccumulated domain knowledge.\n\n")
    with ENCYCLOPEDIA_FILE.open("a") as f:
        f.write(f"\n<!-- {date.today().isoformat()} -->\n- {content}\n")
    return True


def _append_decision(content: str, rationale: str) -> bool:
    content = content.strip()
    if not content or _is_low_quality(content):
        return False
    if DECISION_LOG_FILE.exists():
        text = DECISION_LOG_FILE.read_text()
        if content[:50] in text:
            return False
    DECISION_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not DECISION_LOG_FILE.exists():
        DECISION_LOG_FILE.write_text(
            "# Decision Log\n\n"
            "Chronological log of key project decisions.\n"
            "Updated automatically by the meta-learn hook — edit freely.\n\n"
            "---\n\n"
        )
    with DECISION_LOG_FILE.open("a") as f:
        f.write(f"## {date.today().isoformat()} — {content}\n")
        if rationale:
            f.write(f"**Rationale**: {rationale.strip()}\n")
        f.write("\n")
    return True


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    prompt_text = os.environ.get("PROMPT", "").strip()
    if not prompt_text and not sys.stdin.isatty():
        prompt_text = sys.stdin.read().strip()
    if not prompt_text or len(prompt_text) < 15:
        return

    items = _call_claude(prompt_text)
    if not items:
        return

    added = {"rule": 0, "insight": 0, "decision": 0}
    for item in items:
        t = item.get("type", "")
        content = item.get("content", "")
        rationale = item.get("rationale", "")
        if t == "rule" and _append_rule(content):
            added["rule"] += 1
        elif t == "insight" and _append_insight(content):
            added["insight"] += 1
        elif t == "decision" and _append_decision(content, rationale):
            added["decision"] += 1

    if os.environ.get("RICET_META_DEBUG") and any(added.values()):
        total = sum(added.values())
        print(
            f"[meta-learn] +{total} item(s): "
            f"rules={added['rule']} insights={added['insight']} decisions={added['decision']}"
        )


if __name__ == "__main__":
    main()
