"""
Phase 2.4 — Query Embedder

What this phase does:
  Converts the user's question into a 384-dimensional vector using the same
  BAAI/bge-small-en-v1.5 model that embedded all the chunks during ingestion
  (Phase 1.5). Both sides must use the identical model — if they differ, the
  vectors live in different spaces and similarity search breaks entirely.

Why fastembed instead of sentence-transformers on the backend?
  sentence-transformers loads PyTorch (~500 MB RAM). Render's free tier only
  provides 512 MB total — the process OOMs before serving any requests.
  fastembed uses the ONNX export of the same HuggingFace model, which runs
  in ~100 MB RAM and produces bit-identical vectors to sentence-transformers.
  The ingestion pipeline (GitHub Actions) still uses sentence-transformers —
  that's fine because GitHub Actions has ample RAM.

Why the BGE instruction prefix?
  BGE models are trained with an asymmetric setup:
    - Passages (chunks) are stored WITHOUT any prefix.
    - Queries are encoded WITH the prefix "Represent this sentence for
      searching relevant passages: " prepended.
  This asymmetry shifts the query vector toward the passage cluster in
  embedding space, measurably improving top-K recall.

Input:
  user_query : str  — the factual question from the user (already classified
                       as FACTUAL by Phase 2.2 before this is called)

Output:
  list[float] — 384-dimensional unit-length vector
"""

from __future__ import annotations
import logging

from fastembed import TextEmbedding

logger = logging.getLogger(__name__)

EMBEDDING_MODEL      = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIMENSIONS = 384

# Applied to queries only — NOT to stored chunks (asymmetric by design)
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# Module-level model cache — loaded once, reused for every query
_model: TextEmbedding | None = None


def _get_model() -> TextEmbedding:
    """
    Lazily load bge-small-en-v1.5 (ONNX) on first call;
    return cached instance on all subsequent calls.
    """
    global _model
    if _model is None:
        logger.info("Loading query embedding model: %s (fastembed/ONNX)", EMBEDDING_MODEL)
        _model = TextEmbedding(model_name=EMBEDDING_MODEL)
        logger.info("Query embedding model loaded (%d dims)", EMBEDDING_DIMENSIONS)
    return _model


def embed_query(user_query: str) -> list[float]:
    """
    Embed a single user query into a 384-dim unit-length vector.

    Args:
      user_query: The user's question, e.g. "What is the expense ratio of
                  HDFC Mid Cap Fund?"

    Returns:
      A list of 384 floats representing the query in embedding space.
    """
    model   = _get_model()
    prefixed = BGE_QUERY_PREFIX + user_query.strip()
    vectors  = list(model.embed([prefixed]))
    return vectors[0].tolist()
