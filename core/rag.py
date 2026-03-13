"""Local RAG (Retrieval-Augmented Generation) search for the Encyclopedia.

Uses sentence-transformers (all-MiniLM-L6-v2) to embed encyclopedia entries
and find semantically similar passages for a query, even when keywords don't match.

The index is saved as a numpy .npz file next to the encyclopedia so it persists
across sessions and is rebuilt only when the encyclopedia changes.

Falls back gracefully to keyword search if sentence-transformers is not installed.

Install:
    uv pip install sentence-transformers
"""

import hashlib
import logging
import os
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "all-MiniLM-L6-v2"


class RAGHit(NamedTuple):
    score: float
    text: str
    line_no: int


def _model_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401

        return True
    except ImportError:
        return False


def _load_model(model_name: str = _DEFAULT_MODEL):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def _hash_file(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _index_path(encyclopedia_path: Path) -> Path:
    return encyclopedia_path.with_suffix(".vec.npz")


def _parse_entries(encyclopedia_path: Path) -> list[tuple[int, str]]:
    """Extract non-empty, non-header lines as (line_no, text) tuples."""
    entries = []
    for i, line in enumerate(encyclopedia_path.read_text(errors="replace").splitlines(), 1):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and len(stripped) > 20:
            entries.append((i, stripped.lstrip("-•* ")))
    return entries


def build_index(
    encyclopedia_path: Path,
    *,
    model_name: str = _DEFAULT_MODEL,
    force: bool = False,
) -> bool:
    """Build or refresh the semantic index for the encyclopedia.

    Args:
        encyclopedia_path: Path to ENCYCLOPEDIA.md.
        model_name: Sentence-transformers model to use.
        force: Rebuild even if index is up to date.

    Returns:
        True if index was built/refreshed, False if already current or unavailable.
    """
    import numpy as np

    if not encyclopedia_path.exists():
        return False
    if not _model_available():
        logger.warning("sentence-transformers not installed; run: uv pip install sentence-transformers")
        return False

    index_file = _index_path(encyclopedia_path)
    current_hash = _hash_file(encyclopedia_path)

    # Skip rebuild if index is already current
    if not force and index_file.exists():
        data = np.load(index_file, allow_pickle=True)
        if str(data.get("source_hash", "")) == current_hash:
            return False

    entries = _parse_entries(encyclopedia_path)
    if not entries:
        return False

    line_nos, texts = zip(*entries)
    model = _load_model(model_name)
    embeddings = model.encode(list(texts), show_progress_bar=False, normalize_embeddings=True)

    np.savez(
        index_file,
        embeddings=embeddings.astype("float32"),
        texts=np.array(texts, dtype=object),
        line_nos=np.array(line_nos, dtype=np.int32),
        source_hash=np.array(current_hash),
        model=np.array(model_name),
    )
    logger.info("Built RAG index: %d entries from %s", len(texts), encyclopedia_path)
    return True


def search(
    query: str,
    *,
    encyclopedia_path: Path | None = None,
    top_k: int = 5,
    model_name: str = _DEFAULT_MODEL,
    min_score: float = 0.30,
    auto_build: bool = True,
) -> list[RAGHit]:
    """Semantic search over the encyclopedia.

    Args:
        query: Free-text query.
        encyclopedia_path: Path to ENCYCLOPEDIA.md (auto-detected if None).
        top_k: Maximum results to return.
        model_name: Embedding model to use.
        min_score: Minimum cosine similarity (0-1) for a result to be included.
        auto_build: Rebuild index automatically if stale.

    Returns:
        List of RAGHit(score, text, line_no), highest score first.
        Empty list if sentence-transformers is unavailable.
    """
    import numpy as np

    if not _model_available():
        return []

    if encyclopedia_path is None:
        encyclopedia_path = Path("knowledge/ENCYCLOPEDIA.md")
    if not encyclopedia_path.exists():
        return []

    index_file = _index_path(encyclopedia_path)
    current_hash = _hash_file(encyclopedia_path)

    # Auto-refresh index if stale
    if auto_build:
        needs_build = not index_file.exists()
        if not needs_build and index_file.exists():
            data = np.load(index_file, allow_pickle=True)
            needs_build = str(data.get("source_hash", "")) != current_hash
        if needs_build:
            build_index(encyclopedia_path, model_name=model_name)

    if not index_file.exists():
        return []

    data = np.load(index_file, allow_pickle=True)
    embeddings = data["embeddings"]  # (N, D) float32
    texts = data["texts"]
    line_nos = data["line_nos"]

    model = _load_model(model_name)
    q_vec = model.encode([query], show_progress_bar=False, normalize_embeddings=True)[0]

    # Cosine similarity (embeddings are already normalised)
    scores = embeddings @ q_vec
    ranked = scores.argsort()[::-1]

    hits = []
    for idx in ranked:
        s = float(scores[idx])
        if s < min_score:
            break
        hits.append(RAGHit(score=s, text=str(texts[idx]), line_no=int(line_nos[idx])))
        if len(hits) >= top_k:
            break

    return hits


def index_stats(encyclopedia_path: Path | None = None) -> dict:
    """Return stats about the current index."""
    import numpy as np

    if encyclopedia_path is None:
        encyclopedia_path = Path("knowledge/ENCYCLOPEDIA.md")
    index_file = _index_path(encyclopedia_path)
    if not index_file.exists():
        return {"status": "no index"}

    data = np.load(index_file, allow_pickle=True)
    return {
        "entries": len(data["texts"]),
        "model": str(data.get("model", "unknown")),
        "index_file": str(index_file),
        "source_hash": str(data.get("source_hash", ""))[:8] + "...",
    }
