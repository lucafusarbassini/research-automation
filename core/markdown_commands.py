"""Markdown-to-commands: parse markdown files into executable commands/tasks."""

import logging
import re
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Regex for fenced code blocks: ```lang\n...\n```
_CODE_BLOCK_RE = re.compile(
    r"^```(\w*)\s*\n(.*?)^```",
    re.MULTILINE | re.DOTALL,
)

# Regex for TODO checkbox items: - [x] or - [ ] with optional (**Pn**) priority
_TODO_RE = re.compile(
    r"^-\s+\[([ xX])\]\s+(?:\(\*\*(\w+)\*\*\)\s+)?(.+)$",
    re.MULTILINE,
)

# Regex for markdown headings (used for runbook step names)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_code_blocks(md_text: str) -> list[dict]:
    """Extract fenced code blocks with language from markdown text.

    Returns a list of dicts with keys: ``language``, ``code``, ``start``
    (character offset of the opening fence).
    """
    blocks: list[dict] = []
    for m in _CODE_BLOCK_RE.finditer(md_text):
        blocks.append(
            {
                "language": m.group(1) or "",
                "code": m.group(2).rstrip("\n"),
                "start": m.start(),
            }
        )
    return blocks


def parse_todo_to_tasks(md_path: Path) -> list[dict]:
    """Parse a TODO.md with checkbox items into task dicts.

    Each returned dict contains:
    * ``done``  – bool, whether the checkbox is checked
    * ``priority`` – str, e.g. ``"P0"`` (empty string if absent)
    * ``description`` – str, the task text
    """
    text = md_path.read_text()
    tasks: list[dict] = []
    for m in _TODO_RE.finditer(text):
        tasks.append(
            {
                "done": m.group(1).lower() == "x",
                "priority": m.group(2) or "",
                "description": m.group(3).strip(),
            }
        )
    return tasks


def parse_runbook(md_path: Path) -> list[dict]:
    """Parse a markdown runbook into executable steps.

    The runbook is expected to use headings for step names and fenced code
    blocks (with language hints) for the commands.  Each returned dict has:
    * ``heading`` – the most recent heading before the code block
    * ``language`` – the language hint of the fenced block
    * ``code`` – the raw code string
    """
    text = md_path.read_text()

    # Build a sorted list of (offset, heading_text) from headings
    headings: list[tuple[int, str]] = [
        (m.start(), m.group(2).strip()) for m in _HEADING_RE.finditer(text)
    ]

    blocks = extract_code_blocks(text)
    steps: list[dict] = []
    for block in blocks:
        # Find the nearest heading that precedes this code block
        heading = ""
        for h_offset, h_text in reversed(headings):
            if h_offset < block["start"]:
                heading = h_text
                break
        steps.append(
            {
                "heading": heading,
                "language": block["language"],
                "code": block["code"],
            }
        )
    return steps


def execute_runbook(
    steps: list[dict],
    dry_run: bool = True,
) -> list[dict]:
    """Execute parsed runbook steps.

    Parameters
    ----------
    steps:
        Output of :func:`parse_runbook`.
    dry_run:
        When ``True`` (the default), no commands are actually executed.

    Returns a list of result dicts with keys: ``heading``, ``language``,
    ``code``, ``skipped``, ``output``, ``returncode``.
    """
    results: list[dict] = []
    for step in steps:
        result: dict[str, Any] = {
            "heading": step.get("heading", ""),
            "language": step["language"],
            "code": step["code"],
            "skipped": dry_run,
            "output": "",
            "returncode": None,
        }
        if dry_run:
            logger.info("DRY-RUN skip: %s", step.get("heading", step["code"][:40]))
        elif step["language"] in ("bash", "sh", "shell", "zsh"):
            try:
                proc = subprocess.run(
                    step["code"],
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                result["output"] = proc.stdout.strip()
                result["returncode"] = proc.returncode
            except subprocess.TimeoutExpired:
                result["output"] = "TIMEOUT"
                result["returncode"] = -1
        elif step["language"] == "python":
            # For safety, python blocks are only exec'd in-process in non-dry mode
            try:
                local_ns: dict[str, Any] = {}
                exec(step["code"], {}, local_ns)  # noqa: S102
                result["output"] = str(local_ns) if local_ns else ""
                result["returncode"] = 0
            except Exception as exc:  # noqa: BLE001
                result["output"] = str(exc)
                result["returncode"] = 1
        else:
            result["output"] = f"unsupported language: {step['language']}"
            result["skipped"] = True

        results.append(result)
    return results


def update_todo_status(md_path: Path, task_idx: int, status: bool) -> None:
    """Check or uncheck a TODO checkbox item by its index (0-based).

    Rewrites the file in-place.
    """
    text = md_path.read_text()
    matches = list(_TODO_RE.finditer(text))
    if task_idx < 0 or task_idx >= len(matches):
        raise IndexError(
            f"task_idx {task_idx} out of range (found {len(matches)} tasks)"
        )

    m = matches[task_idx]
    mark = "x" if status else " "
    # Replace just the checkbox character (group 1)
    new_text = text[: m.start(1)] + mark + text[m.end(1) :]
    md_path.write_text(new_text)


def generate_task_file(tasks: list[dict], output: Path) -> Path:
    """Generate a structured TODO.md from a list of task dicts.

    Each task dict should have keys ``done``, ``priority``, ``description``.
    Returns the path written.
    """
    lines = ["# Tasks", ""]
    for t in tasks:
        check = "x" if t.get("done") else " "
        priority = t.get("priority", "")
        desc = t.get("description", "")
        if priority:
            lines.append(f"- [{check}] (**{priority}**) {desc}")
        else:
            lines.append(f"- [{check}] {desc}")
    lines.append("")  # trailing newline
    output.write_text("\n".join(lines))
    return output
