"""Tests for voice prompting pipeline."""

from pathlib import Path

from core.voice import (
    detect_language,
    load_prompt_templates,
    structure_prompt,
    translate_to_english,
)


def test_detect_language_english():
    assert detect_language("This is a simple English sentence") == "en"


def test_detect_language_chinese():
    assert detect_language("这是一个中文句子测试文本") == "zh"


def test_detect_language_russian():
    assert detect_language("Это простое предложение на русском языке") == "ru"


def test_detect_language_arabic():
    assert detect_language("هذه جملة بسيطة باللغة العربية") == "ar"


def test_detect_language_empty():
    assert detect_language("") == "en"


def test_translate_english_passthrough():
    text = "This is already in English"
    assert translate_to_english(text) == text


def test_load_prompt_templates(tmp_path: Path):
    prompts_md = tmp_path / "PROMPTS.md"
    prompts_md.write_text("""# Prompts

### PROMPT: test-prompt
**Tags**: test, example, demo
**Use when**: Testing

```
Do the thing with [TOPIC].
Step 1: Analyze
Step 2: Execute
```
""")
    templates = load_prompt_templates(prompts_md)
    assert "test-prompt" in templates
    assert "test" in templates["test-prompt"]["tags"]
    assert "[TOPIC]" in templates["test-prompt"]["template"]


def test_load_prompt_templates_missing(tmp_path: Path):
    templates = load_prompt_templates(tmp_path / "nonexistent.md")
    assert templates == {}


def test_structure_prompt_with_match():
    templates = {
        "review-code": {
            "tags": ["review", "code", "quality"],
            "template": "Review the code: [CODE/FILE]\nCheck for bugs.",
        },
        "write-docs": {
            "tags": ["write", "docs", "documentation"],
            "template": "Write documentation for [TOPIC].",
        },
    }
    result = structure_prompt("review the code quality", templates=templates)
    assert "Review the code:" in result
    assert "Check for bugs" in result


def test_structure_prompt_no_match():
    templates = {
        "test": {"tags": ["xyz"], "template": "template"},
    }
    result = structure_prompt("something completely different", templates=templates)
    assert result == "something completely different"


def test_structure_prompt_no_templates():
    result = structure_prompt("just pass through", templates={})
    assert result == "just pass through"
