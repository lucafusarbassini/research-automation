"""Paper style transfer: Claude-intelligence-driven style analysis and rewriting.

The core idea: rather than measuring surface proxies (passive ratio, word endings),
pass the raw texts to Claude and let it identify the deep stylistic dimensions that
matter — vocabulary register, conceptual framing, sentence rhythm, hedging density,
domain terminology, narrative sequentiality, etc.

Requires the anthropic Python SDK (pip install anthropic / uv pip install anthropic).
Works even inside a Claude Code session (uses SDK directly, not CLI subprocess).
"""

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_CITATION_PATTERN = re.compile(r"\\cite\{|\\citep\{|\\citet\{|\[\d+\]|\(.*?\d{4}\)")


def _call_claude_api(prompt: str, *, model: str = "claude-sonnet-4-6", max_tokens: int = 4096) -> str | None:
    """Call Claude via the anthropic SDK (works inside Claude Code sessions)."""
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic SDK not installed: uv pip install anthropic")
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        # Try loading from .env
        try:
            from dotenv import load_dotenv
            for candidate in [Path.cwd() / ".env", Path(__file__).parent.parent / ".env"]:
                if candidate.exists():
                    load_dotenv(candidate, override=False)
                    break
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        except ImportError:
            pass

    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set")
        return None

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text if msg.content else None


def analyze_paper_style(text: str, *, reference_label: str = "this text") -> dict:
    """Analyze the writing style of a paper using Claude's full intelligence.

    Returns a rich style profile dict with qualitative + quantitative dimensions.
    Falls back to basic surface metrics if Claude is unavailable.

    Args:
        text: The paper text to analyze (excerpt or full text).
        reference_label: Human-readable label for logging.

    Returns:
        Dict with style dimensions understood by generate_transformation_prompt().
    """
    if not text.strip():
        return {}

    prompt = (
        "You are a scientific writing analyst. Analyze the writing style of the following text "
        "and return a structured JSON object describing its style across these dimensions:\n\n"
        "1. tense: dominant tense (\"past\", \"present\", \"mixed\" — be precise, e.g. methods/results "
        "in past, interpretations in present counts as \"mixed\")\n"
        "2. voice: \"active\", \"passive\", or \"mixed\" with approximate ratio\n"
        "3. sentence_rhythm: \"short_punchy\", \"long_complex\", \"varied\"\n"
        "4. hedging_level: \"low\", \"medium\", \"high\" — how often uncertainty is expressed\n"
        "5. vocabulary_register: \"technical_specialist\", \"technical_broad\", \"accessible\"\n"
        "6. narrative_style: brief description of how arguments are structured and connected\n"
        "7. domain_markers: list of 5-10 characteristic domain-specific terms or phrases\n"
        "8. framing_approach: how results/contributions are positioned (humble, assertive, etc.)\n"
        "9. citation_style: \"dense\", \"moderate\", \"sparse\"\n"
        "10. distinctive_patterns: list of 3-5 specific stylistic habits (e.g. 'uses colons to introduce evidence', "
        "'opens paragraphs with broad claim then narrows')\n\n"
        "Return ONLY valid JSON. No commentary before or after.\n\n"
        f"--- TEXT ---\n{text[:8000]}\n--- END ---"
    )

    raw = _call_claude_api(prompt, max_tokens=1000)

    if raw:
        import json
        # Extract JSON from response
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

    # Fallback: minimal surface metrics
    logger.info("Claude unavailable for style analysis; using surface metrics")
    return _surface_metrics(text)


def _surface_metrics(text: str) -> dict:
    """Minimal surface-level style metrics as fallback."""
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    words = text.lower().split()
    passive_count = len(re.findall(r"\b(is|are|was|were|been|being|be)\s+\w+ed\b", text, re.IGNORECASE))
    hedging = {"may", "might", "could", "possibly", "perhaps", "likely", "suggest", "suggests",
               "indicate", "indicates", "appear", "appears", "seem", "seems"}
    hedging_count = sum(1 for w in words if w.strip(".,;:()") in hedging)
    past_markers = sum(1 for w in words if w.endswith("ed"))
    pres_markers = sum(1 for w in words if w.endswith(("s", "es")) and len(w) > 3)
    tense = "past" if past_markers > pres_markers * 1.5 else ("present" if pres_markers > past_markers * 1.5 else "mixed")
    n = len(sentences) or 1
    return {
        "tense": tense,
        "voice": f"passive_ratio={passive_count / n:.2f}",
        "hedging_level": "high" if hedging_count / (len(words) or 1) > 0.02 else "low",
        "avg_sentence_length": round(sum(len(s.split()) for s in sentences) / n, 1),
        "_source": "surface_metrics_fallback",
    }


def generate_transformation_prompt(source_profile: dict, target_profile: dict) -> str:
    """Generate a detailed Claude prompt for style transformation.

    Args:
        source_profile: Style profile of the text to rewrite.
        target_profile: Style profile of the reference text.

    Returns:
        Instruction string for Claude to transform source → target style.
    """
    import json

    instructions = [
        "Rewrite the text below to match the TARGET writing style while preserving all scientific content.\n",
        f"TARGET STYLE PROFILE:\n{json.dumps(target_profile, indent=2)}\n",
        f"SOURCE STYLE (for contrast):\n{json.dumps(source_profile, indent=2)}\n",
        "TRANSFORMATION RULES:",
        "- Match the target tense conventions exactly",
        "- Match the target voice (active/passive balance)",
        "- Adopt the target sentence rhythm and complexity",
        "- Use vocabulary at the target register and domain level",
        "- Replicate the target narrative/framing approach",
        "- Mirror the hedging level and assertion style",
        "- Do NOT copy phrases verbatim from the reference — transfer style only",
        "- Preserve all scientific claims, data, and citations exactly",
        "- Return ONLY the rewritten text, no commentary",
    ]

    # Add specific guidance where profiles differ on key dimensions
    if source_profile.get("tense") != target_profile.get("tense"):
        instructions.append(f"- IMPORTANT: change tense from '{source_profile.get('tense')}' to '{target_profile.get('tense')}'")
    if source_profile.get("hedging_level") != target_profile.get("hedging_level"):
        instructions.append(f"- Adjust hedging: {source_profile.get('hedging_level')} → {target_profile.get('hedging_level')}")

    return "\n".join(instructions)


def verify_no_plagiarism(new_text: str, reference_texts: list[str], *, threshold: int = 6) -> list[dict]:
    """Check for n-gram overlap between new text and references."""
    def _ngrams(text: str, n: int) -> set[str]:
        words = text.lower().split()
        return {" ".join(words[i: i + n]) for i in range(len(words) - n + 1)}

    new_ngrams = _ngrams(new_text, threshold)
    flags: list[dict] = []
    for idx, ref_text in enumerate(reference_texts):
        for ngram in new_ngrams & _ngrams(ref_text, threshold):
            flags.append({"ngram": ngram, "source_index": idx})

    if flags:
        logger.warning("Found %d potential plagiarism matches", len(flags))
    return flags


def rewrite_in_reference_style(
    source_text: str,
    reference_text: str,
    *,
    verify: bool = True,
    run_cmd=None,  # kept for API compatibility
) -> dict:
    """Rewrite source_text in the style of reference_text using Claude.

    Uses Claude's full intelligence to analyze both texts and produce
    a style-matched rewrite. Works even inside Claude Code sessions
    (uses anthropic SDK directly, not CLI subprocess).

    Returns dict with keys: rewritten, source_profile, target_profile,
    transformation_prompt, plagiarism_flags, error (if any).
    """
    source_profile = analyze_paper_style(source_text, reference_label="source")
    target_profile = analyze_paper_style(reference_text, reference_label="reference")
    transformation_prompt = generate_transformation_prompt(source_profile, target_profile)

    full_prompt = (
        f"{transformation_prompt}\n\n"
        f"--- TEXT TO REWRITE ---\n{source_text}\n--- END ---"
    )

    rewritten = _call_claude_api(full_prompt, max_tokens=8192)

    # Fallback to CLI if SDK unavailable
    if rewritten is None and run_cmd is None:
        try:
            from core.claude_helper import call_claude
            rewritten = call_claude(full_prompt)
        except Exception:
            pass

    result: dict = {
        "source_profile": source_profile,
        "target_profile": target_profile,
        "transformation_prompt": transformation_prompt,
        "plagiarism_flags": [],
    }

    if rewritten is None:
        result["rewritten"] = None
        result["error"] = "Claude unavailable (set ANTHROPIC_API_KEY or run from terminal)"
        return result

    result["rewritten"] = rewritten

    if verify:
        result["plagiarism_flags"] = verify_no_plagiarism(rewritten, [reference_text])

    return result
