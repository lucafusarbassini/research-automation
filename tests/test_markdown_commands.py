"""Tests for markdown-to-commands module."""

from pathlib import Path

from core.markdown_commands import (
    execute_runbook,
    extract_code_blocks,
    generate_task_file,
    parse_runbook,
    parse_todo_to_tasks,
    update_todo_status,
)


# ---------------------------------------------------------------------------
# extract_code_blocks
# ---------------------------------------------------------------------------

def test_extract_code_blocks_basic():
    md = "# Title\n\n```python\nprint('hello')\n```\n"
    blocks = extract_code_blocks(md)
    assert len(blocks) == 1
    assert blocks[0]["language"] == "python"
    assert blocks[0]["code"] == "print('hello')"


def test_extract_code_blocks_multiple():
    md = (
        "```bash\necho hi\n```\n\nSome text\n\n"
        "```python\nx = 1\n```\n"
    )
    blocks = extract_code_blocks(md)
    assert len(blocks) == 2
    assert blocks[0]["language"] == "bash"
    assert blocks[1]["language"] == "python"


def test_extract_code_blocks_no_language():
    md = "```\nplain code\n```\n"
    blocks = extract_code_blocks(md)
    assert len(blocks) == 1
    assert blocks[0]["language"] == ""
    assert blocks[0]["code"] == "plain code"


# ---------------------------------------------------------------------------
# parse_todo_to_tasks
# ---------------------------------------------------------------------------

def test_parse_todo_to_tasks(tmp_path: Path):
    todo = tmp_path / "TODO.md"
    todo.write_text(
        "# Tasks\n\n"
        "- [x] (**P0**) Build parser\n"
        "- [ ] (**P1**) Write tests\n"
        "- [ ] Add docs\n"
    )
    tasks = parse_todo_to_tasks(todo)
    assert len(tasks) == 3
    assert tasks[0]["done"] is True
    assert tasks[0]["priority"] == "P0"
    assert tasks[0]["description"] == "Build parser"
    assert tasks[1]["done"] is False
    assert tasks[1]["priority"] == "P1"
    assert tasks[2]["priority"] == ""


def test_parse_todo_to_tasks_empty(tmp_path: Path):
    todo = tmp_path / "EMPTY.md"
    todo.write_text("# Nothing here\n\nJust prose.\n")
    tasks = parse_todo_to_tasks(todo)
    assert tasks == []


# ---------------------------------------------------------------------------
# parse_runbook / execute_runbook
# ---------------------------------------------------------------------------

def test_parse_runbook(tmp_path: Path):
    rb = tmp_path / "runbook.md"
    rb.write_text(
        "# Runbook\n\n"
        "## Step 1 — Setup\n\n"
        "```bash\necho setup\n```\n\n"
        "## Step 2 — Run\n\n"
        "```python\nprint('run')\n```\n"
    )
    steps = parse_runbook(rb)
    assert len(steps) == 2
    assert steps[0]["language"] == "bash"
    assert steps[0]["heading"] == "Step 1 — Setup"
    assert steps[1]["language"] == "python"


def test_execute_runbook_dry_run():
    steps = [
        {"language": "bash", "code": "echo hello", "heading": "greet"},
        {"language": "python", "code": "x = 1", "heading": "calc"},
    ]
    results = execute_runbook(steps, dry_run=True)
    assert len(results) == 2
    assert all(r["skipped"] is True for r in results)
    assert results[0]["code"] == "echo hello"


def test_execute_runbook_real_bash():
    steps = [{"language": "bash", "code": "echo ok", "heading": "test"}]
    results = execute_runbook(steps, dry_run=False)
    assert len(results) == 1
    assert results[0]["skipped"] is False
    assert "ok" in results[0]["output"]


# ---------------------------------------------------------------------------
# update_todo_status
# ---------------------------------------------------------------------------

def test_update_todo_status(tmp_path: Path):
    todo = tmp_path / "TODO.md"
    todo.write_text(
        "- [ ] First\n"
        "- [ ] Second\n"
        "- [x] Third\n"
    )
    update_todo_status(todo, 0, True)
    update_todo_status(todo, 2, False)
    text = todo.read_text()
    assert "- [x] First" in text
    assert "- [ ] Third" in text
    assert "- [ ] Second" in text  # unchanged


# ---------------------------------------------------------------------------
# generate_task_file
# ---------------------------------------------------------------------------

def test_generate_task_file(tmp_path: Path):
    tasks = [
        {"done": False, "priority": "P0", "description": "Build it"},
        {"done": True, "priority": "", "description": "Plan it"},
    ]
    out = generate_task_file(tasks, tmp_path / "out.md")
    assert out.exists()
    content = out.read_text()
    assert "- [ ] (**P0**) Build it" in content
    assert "- [x] Plan it" in content


def test_generate_task_file_empty(tmp_path: Path):
    out = generate_task_file([], tmp_path / "empty.md")
    content = out.read_text()
    assert "# Tasks" in content
