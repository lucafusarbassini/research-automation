"""Auto-generate pytest tests for user project code using Claude."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_tests_for_file(
    source_file: Path,
    *,
    test_dir: Path | None = None,
    run_cmd=None,
) -> Path | None:
    """Auto-generate pytest tests for a Python source file using Claude.

    Reads the source, asks Claude to generate comprehensive tests,
    writes them to test_dir/test_<filename>.py.

    Args:
        source_file: Path to the Python source file.
        test_dir: Directory to write test files. Defaults to
                  ``source_file.parent.parent / "tests"``.
        run_cmd: Optional callable for testing (forwarded to call_claude).

    Returns:
        The path to the generated test file, or None on failure.
    """
    from core.claude_helper import call_claude

    if not source_file.exists():
        return None

    source_text = source_file.read_text()
    if not source_text.strip():
        return None

    if test_dir is None:
        test_dir = source_file.parent.parent / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)

    test_filename = f"test_{source_file.stem}.py"
    test_path = test_dir / test_filename

    prompt = (
        "Generate comprehensive pytest tests for the following Python module. "
        "Include: happy path tests, edge cases, error handling. "
        "Use unittest.mock for external dependencies. "
        "IMPORTANT: Output ONLY the Python code inside a single ```python code block. "
        "No explanation before or after the code block.\n\n"
        f"# File: {source_file.name}\n\n"
        f"{source_text[:8000]}"
    )

    result = call_claude(prompt, run_cmd=run_cmd, timeout=90)
    if result and result.strip():
        # Extract code from markdown fences if present
        text = result.strip()
        import re as _re

        # Try to extract fenced code block (```python ... ``` or ``` ... ```)
        fence_match = _re.search(
            r"```(?:python)?\s*\n(.*?)```", text, _re.DOTALL
        )
        if fence_match:
            text = fence_match.group(1).strip()
        elif text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        # If no import/def found, the output is likely explanation, not code
        if "import " not in text and "def test_" not in text:
            logger.warning("Claude output did not contain test code for %s", source_file.name)
            return None

        test_path.write_text(text)
        logger.info("Generated tests: %s", test_path)
        return test_path

    logger.warning("Claude did not return test code for %s", source_file.name)
    return None


def generate_tests_for_project(
    project_path: Path,
    *,
    run_cmd=None,
) -> list[Path]:
    """Auto-generate tests for all Python files in a ricet project's src/ directory.

    Scans ``project_path/src`` and ``project_path`` (root) for ``.py`` files,
    skipping private modules (``_*``) and existing test files (``test_*``).

    Args:
        project_path: Root of the user's ricet project.
        run_cmd: Optional callable for testing (forwarded to call_claude).

    Returns:
        List of paths to generated test files.
    """
    generated: list[Path] = []
    src_dirs = [project_path / "src", project_path]

    for src_dir in src_dirs:
        if not src_dir.is_dir():
            continue
        for py_file in sorted(src_dir.glob("*.py")):
            if py_file.name.startswith("_") or py_file.name.startswith("test_"):
                continue
            test_path = generate_tests_for_file(
                py_file,
                test_dir=project_path / "tests",
                run_cmd=run_cmd,
            )
            if test_path:
                generated.append(test_path)

    return generated
