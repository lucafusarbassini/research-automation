"""Voice prompting pipeline: transcription, language detection, prompt structuring."""

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Prompt templates indexed by tag
PROMPT_TEMPLATES: dict[str, dict] = {}


def load_prompt_templates(prompts_path: Path) -> dict[str, dict]:
    """Load prompt templates from a PROMPTS.md file.

    Args:
        prompts_path: Path to the PROMPTS.md file.

    Returns:
        Dict mapping template name to {tags, template} dicts.
    """
    if not prompts_path.exists():
        return {}

    content = prompts_path.read_text()
    templates = {}

    # Parse ### PROMPT: sections
    pattern = r"### PROMPT:\s*(\S+)\n\*\*Tags\*\*:\s*(.*?)\n.*?```\n(.*?)```"
    for match in re.finditer(pattern, content, re.DOTALL):
        name = match.group(1)
        tags = [t.strip() for t in match.group(2).split(",")]
        template = match.group(3).strip()
        templates[name] = {"tags": tags, "template": template}

    return templates


def transcribe_audio(audio_path: Path) -> str:
    """Transcribe an audio file using Whisper (requires whisper installed).

    Args:
        audio_path: Path to audio file.

    Returns:
        Transcribed text.

    Raises:
        ImportError: If whisper is not installed.
        FileNotFoundError: If audio file doesn't exist.
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    try:
        import whisper
    except ImportError:
        raise ImportError("whisper not installed. Run: pip install openai-whisper")

    model = whisper.load_model("base")
    result = model.transcribe(str(audio_path))
    text = result.get("text", "")
    logger.info("Transcribed %d characters from %s", len(text), audio_path.name)
    return text


def detect_language(text: str) -> str:
    """Detect the language of a text string.

    Simple heuristic based on character ranges. For production use,
    consider using langdetect or similar.

    Args:
        text: Input text.

    Returns:
        ISO 639-1 language code (e.g., 'en', 'es', 'zh').
    """
    if not text.strip():
        return "en"

    # Check for CJK characters
    cjk_count = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    if cjk_count > len(text) * 0.1:
        return "zh"

    # Check for Cyrillic
    cyrillic_count = sum(1 for c in text if "\u0400" <= c <= "\u04ff")
    if cyrillic_count > len(text) * 0.1:
        return "ru"

    # Check for Arabic
    arabic_count = sum(1 for c in text if "\u0600" <= c <= "\u06ff")
    if arabic_count > len(text) * 0.1:
        return "ar"

    # Check for common Spanish/French/German markers
    text_lower = text.lower()
    spanish_markers = ["el ", "la ", "de ", "que ", "los ", "las "]
    if sum(1 for m in spanish_markers if m in text_lower) >= 2:
        return "es"

    return "en"


def translate_to_english(text: str, source_lang: str = "", *, run_cmd=None) -> str:
    """Translate non-English text to English using Claude Haiku.

    If text is already English or Claude is unavailable, returns original text.
    """
    if not text.strip():
        return text

    # Detect language if not provided
    if not source_lang:
        source_lang = detect_language(text)

    if source_lang == "en":
        return text

    from core.claude_helper import call_claude

    prompt = (
        f"Translate the following {source_lang} text to English. "
        "Preserve technical terms and formatting. Reply with ONLY the translation.\n\n"
        f"{text}"
    )
    result = call_claude(prompt, run_cmd=run_cmd)
    if result and result.strip():
        return result.strip()

    logger.warning("Translation unavailable, returning original text.")
    return text


def structure_prompt(
    user_input: str,
    *,
    templates: dict[str, dict] | None = None,
) -> str:
    """Structure a natural language input into a formatted prompt using templates.

    Matches user input keywords against template tags to find the best template,
    then fills it in.

    Args:
        user_input: Raw user input (possibly from voice).
        templates: Loaded prompt templates. Uses global cache if None.

    Returns:
        Structured prompt string.
    """
    if templates is None:
        templates = PROMPT_TEMPLATES

    if not templates:
        return user_input

    # Score templates by tag overlap
    input_words = set(user_input.lower().split())
    best_name = None
    best_score = 0

    for name, info in templates.items():
        score = sum(1 for tag in info["tags"] if tag in input_words)
        if score > best_score:
            best_score = score
            best_name = name

    if best_name and best_score > 0:
        template = templates[best_name]["template"]
        # Replace placeholders with user input context
        structured = template.replace("[TOPIC]", user_input)
        structured = structured.replace("[DESCRIPTION]", user_input)
        structured = structured.replace("[CODE/FILE]", user_input)
        structured = structured.replace("[TEXT]", user_input)
        structured = structured.replace("[SECTION]", user_input)
        return structured

    return user_input
