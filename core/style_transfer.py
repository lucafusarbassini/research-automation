"""Paper style transfer: analyze style, generate transformation prompts, plagiarism checks."""

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class StyleProfile:
    avg_sentence_length: float = 0.0
    passive_voice_ratio: float = 0.0
    hedging_ratio: float = 0.0
    citation_density: float = 0.0
    vocabulary_richness: float = 0.0
    common_phrases: list[str] = field(default_factory=list)
    tense: str = "mixed"  # past, present, mixed

    def to_dict(self) -> dict:
        return {
            "avg_sentence_length": self.avg_sentence_length,
            "passive_voice_ratio": self.passive_voice_ratio,
            "hedging_ratio": self.hedging_ratio,
            "citation_density": self.citation_density,
            "vocabulary_richness": self.vocabulary_richness,
            "common_phrases": self.common_phrases,
            "tense": self.tense,
        }


_PASSIVE_MARKERS = re.compile(
    r"\b(is|are|was|were|been|being|be)\s+\w+ed\b", re.IGNORECASE
)
_HEDGING_WORDS = {
    "may", "might", "could", "possibly", "perhaps", "likely",
    "suggest", "suggests", "indicate", "indicates", "appear",
    "appears", "seem", "seems", "approximately", "roughly",
}
_CITATION_PATTERN = re.compile(r"\\cite\{|\\citep\{|\\citet\{|\[\d+\]|\(.*?\d{4}\)")


def analyze_paper_style(text: str) -> StyleProfile:
    """Analyze the writing style of a paper or text sample.

    Args:
        text: The paper text to analyze.

    Returns:
        StyleProfile with computed metrics.
    """
    profile = StyleProfile()

    if not text.strip():
        return profile

    # Sentence analysis
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if sentences:
        lengths = [len(s.split()) for s in sentences]
        profile.avg_sentence_length = round(sum(lengths) / len(lengths), 1)

    # Passive voice ratio
    total_sentences = len(sentences) if sentences else 1
    passive_count = len(_PASSIVE_MARKERS.findall(text))
    profile.passive_voice_ratio = round(passive_count / total_sentences, 2)

    # Hedging ratio
    words = text.lower().split()
    if words:
        hedging_count = sum(1 for w in words if w.strip(".,;:()") in _HEDGING_WORDS)
        profile.hedging_ratio = round(hedging_count / len(words), 3)

    # Citation density (per sentence)
    citation_count = len(_CITATION_PATTERN.findall(text))
    profile.citation_density = round(citation_count / total_sentences, 2)

    # Vocabulary richness (type-token ratio)
    if words:
        unique_words = set(w.lower().strip(".,;:()") for w in words)
        profile.vocabulary_richness = round(len(unique_words) / len(words), 2)

    # Common bigrams
    if len(words) > 1:
        bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)]
        common = Counter(bigrams).most_common(5)
        profile.common_phrases = [phrase for phrase, _ in common]

    # Tense detection
    past_markers = sum(1 for w in words if w.endswith("ed"))
    present_markers = sum(1 for w in words if w.endswith(("s", "es")) and len(w) > 3)
    if past_markers > present_markers * 1.5:
        profile.tense = "past"
    elif present_markers > past_markers * 1.5:
        profile.tense = "present"
    else:
        profile.tense = "mixed"

    return profile


def generate_transformation_prompt(
    source_profile: StyleProfile,
    target_profile: StyleProfile,
) -> str:
    """Generate a prompt to transform writing from source style to target style.

    Args:
        source_profile: Current writing style.
        target_profile: Desired writing style.

    Returns:
        Instruction prompt for style transformation.
    """
    instructions = ["Transform the following text to match the target writing style:"]

    # Sentence length
    if abs(source_profile.avg_sentence_length - target_profile.avg_sentence_length) > 3:
        if target_profile.avg_sentence_length > source_profile.avg_sentence_length:
            instructions.append("- Use longer, more complex sentences")
        else:
            instructions.append("- Use shorter, more concise sentences")

    # Voice
    if target_profile.passive_voice_ratio < source_profile.passive_voice_ratio - 0.1:
        instructions.append("- Prefer active voice over passive voice")
    elif target_profile.passive_voice_ratio > source_profile.passive_voice_ratio + 0.1:
        instructions.append("- Use more passive constructions where appropriate")

    # Hedging
    if target_profile.hedging_ratio > source_profile.hedging_ratio + 0.005:
        instructions.append("- Add more hedging language (may, might, suggests)")
    elif target_profile.hedging_ratio < source_profile.hedging_ratio - 0.005:
        instructions.append("- Be more assertive, reduce hedging words")

    # Tense
    if target_profile.tense != source_profile.tense:
        instructions.append(f"- Use {target_profile.tense} tense")

    if len(instructions) == 1:
        instructions.append("- The styles are similar; make minor refinements for consistency")

    return "\n".join(instructions)


def verify_no_plagiarism(
    new_text: str,
    reference_texts: list[str],
    *,
    threshold: int = 6,
) -> list[dict]:
    """Check for overlapping n-grams between new text and references.

    This is a simple n-gram overlap check, not a full plagiarism detector.

    Args:
        new_text: The text to check.
        reference_texts: List of reference texts to compare against.
        threshold: N-gram size to check (default 6 words).

    Returns:
        List of dicts with 'ngram', 'source_index' for flagged overlaps.
    """
    def _ngrams(text: str, n: int) -> set[str]:
        words = text.lower().split()
        return {" ".join(words[i:i+n]) for i in range(len(words) - n + 1)}

    new_ngrams = _ngrams(new_text, threshold)
    flags: list[dict] = []

    for idx, ref_text in enumerate(reference_texts):
        ref_ngrams = _ngrams(ref_text, threshold)
        overlap = new_ngrams & ref_ngrams
        for ngram in overlap:
            flags.append({"ngram": ngram, "source_index": idx})

    if flags:
        logger.warning("Found %d potential plagiarism matches", len(flags))
    return flags
