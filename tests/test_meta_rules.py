"""Tests for meta-rule capture."""

from pathlib import Path

from core.meta_rules import (
    append_to_cheatsheet,
    classify_rule_type,
    detect_operational_rule,
)


def test_detect_operational_rule_positive():
    assert detect_operational_rule("Always run tests before committing") is True
    assert detect_operational_rule("Never push directly to main") is True
    assert detect_operational_rule("Must use type hints") is True
    assert detect_operational_rule("Important: check for data leakage") is True


def test_detect_operational_rule_negative():
    assert detect_operational_rule("The model achieved 95% accuracy") is False
    assert detect_operational_rule("We used PyTorch for training") is False


def test_classify_rule_workflow():
    assert classify_rule_type("Always run tests before deploying") == "workflow"


def test_classify_rule_constraint():
    assert classify_rule_type("Must not exceed the maximum batch size limit") == "constraint"


def test_classify_rule_preference():
    assert classify_rule_type("Prefer using vectorized operations for better performance") == "preference"


def test_classify_rule_debug():
    assert classify_rule_type("When CUDA error occurs, check GPU memory first as a workaround") == "debug"


def test_classify_rule_general():
    assert classify_rule_type("something vague") == "general"


def test_append_to_cheatsheet_new_file(tmp_path: Path):
    cs = tmp_path / "CHEATSHEET.md"
    append_to_cheatsheet("Always test first", cheatsheet_path=cs)
    assert cs.exists()
    content = cs.read_text()
    assert "Always test first" in content
    assert "## Workflow" in content


def test_append_to_cheatsheet_existing(tmp_path: Path):
    cs = tmp_path / "CHEATSHEET.md"
    cs.write_text("# Operational Cheatsheet\n\n## Workflow\n\n## Constraints\n\n## General\n")
    append_to_cheatsheet("Must validate inputs", rule_type="constraint", cheatsheet_path=cs)
    content = cs.read_text()
    assert "Must validate inputs" in content


def test_append_to_cheatsheet_auto_classify(tmp_path: Path):
    cs = tmp_path / "CHEATSHEET.md"
    append_to_cheatsheet("Never commit secrets to git", cheatsheet_path=cs)
    content = cs.read_text()
    assert "Never commit secrets" in content
