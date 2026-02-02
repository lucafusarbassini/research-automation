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


def record_audio(
    output_path: Path,
    *,
    duration: int = 30,
    sample_rate: int = 16000,
    run_cmd=None,
) -> bool:
    """Record audio from microphone using system tools.

    Tries in order: arecord (Linux ALSA), sox/rec, ffmpeg.
    Returns True if recording succeeded.
    """
    import shutil
    import subprocess

    _run = run_cmd or (
        lambda cmd: subprocess.run(cmd, capture_output=True, timeout=duration + 5)
    )

    # Try arecord (Linux ALSA)
    if shutil.which("arecord"):
        try:
            _run(
                [
                    "arecord",
                    "-d",
                    str(duration),
                    "-f",
                    "S16_LE",
                    "-r",
                    str(sample_rate),
                    "-c",
                    "1",
                    str(output_path),
                ]
            )
            return output_path.exists()
        except Exception:
            pass

    # Try sox/rec
    if shutil.which("rec"):
        try:
            _run(
                [
                    "rec",
                    str(output_path),
                    "rate",
                    str(sample_rate),
                    "channels",
                    "1",
                    "trim",
                    "0",
                    str(duration),
                ]
            )
            return output_path.exists()
        except Exception:
            pass

    # Try ffmpeg
    if shutil.which("ffmpeg"):
        try:
            _run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "pulse",
                    "-i",
                    "default",
                    "-t",
                    str(duration),
                    "-ar",
                    str(sample_rate),
                    "-ac",
                    "1",
                    str(output_path),
                ]
            )
            return output_path.exists()
        except Exception:
            pass

    logger.warning("No audio recording tool found (install arecord, sox, or ffmpeg)")
    return False


def transcribe_audio(audio_path: Path, *, run_cmd=None) -> str:
    """Transcribe audio file to text using whisper CLI or whisper Python library.

    Tries whisper CLI first, then Python library, then returns empty string.
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    import shutil
    import subprocess

    # Try whisper CLI
    if shutil.which("whisper"):
        try:
            subprocess.run(
                [
                    "whisper",
                    str(audio_path),
                    "--model",
                    "base",
                    "--output_format",
                    "txt",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            txt_file = audio_path.with_suffix(".txt")
            if txt_file.exists():
                text = txt_file.read_text().strip()
                logger.info("Transcribed %d characters via whisper CLI", len(text))
                return text
        except Exception:
            pass

    # Try whisper Python library
    try:
        import whisper

        model = whisper.load_model("base")
        result = model.transcribe(str(audio_path))
        text = result.get("text", "")
        logger.info("Transcribed %d characters from %s", len(text), audio_path.name)
        return text
    except ImportError:
        pass

    logger.warning("Whisper not available for transcription")
    return ""


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


def voice_prompt(*, duration: int = 30, run_cmd=None) -> str:
    """Record voice, transcribe, detect language, translate, structure as prompt.

    Full pipeline: record -> transcribe -> detect language -> translate -> structure.
    Returns the structured prompt ready for agent use.
    """
    import tempfile

    audio_path = Path(tempfile.mktemp(suffix=".wav"))

    if not record_audio(audio_path, duration=duration, run_cmd=run_cmd):
        return ""

    text = transcribe_audio(audio_path, run_cmd=run_cmd)
    if not text:
        return ""

    # Clean up audio file
    try:
        audio_path.unlink()
    except Exception:
        pass

    # Detect and translate
    lang = detect_language(text)
    if lang != "en":
        text = translate_to_english(text, source_lang=lang, run_cmd=run_cmd)

    # Structure the prompt
    prompts_path = Path("knowledge") / "PROMPTS.md"
    templates = load_prompt_templates(prompts_path)
    structured = structure_prompt(text, templates=templates)

    return structured
