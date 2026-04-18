"""
Phase 2.4 — Query Embedder

What this phase does:
  Converts the user's question into a 384-dimensional vector using the same
  BAAI/bge-small-en-v1.5 model that embedded all the chunks during ingestion
  (Phase 1.5). Both sides must use the identical model — if they differ, the
  vectors live in different spaces and similarity search breaks entirely.

Why the BGE instruction prefix?
  BGE models are trained with an asymmetric setup:
    - Passages (chunks) are stored WITHOUT any prefix.
    - Queries are encoded WITH the prefix "Represent this sentence for
      searching relevant passages: " prepended.
  This asymmetry shifts the query vector toward the passage cluster in
  embedding space, measurably improving top-K recall. It is documented in
  the BGE paper and the model card on HuggingFace.

Model caching:
  The SentenceTransformer is loaded once at module level on first use and
  reused for every subsequent query. Loading takes ~2 s on CPU; after that
  each encode() call completes in milliseconds.

Input:
  user_query : str  — the factual question from the user (already classified
                       as FACTUAL by Phase 2.2 before this is called)

Output:
  list[float] — 384-dimensional unit-length vector (normalize_embeddings=True
                 guarantees cosine similarity == dot product, matching how
                 ChromaDB is configured with hnsw:space: cosine)
"""

from __future__ import annotations
import logging

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

EMBEDDING_MODEL      = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIMENSIONS = 384

# Applied to queries only — NOT to stored chunks (asymmetric by design)
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# Module-level model cache — loaded once, reused for every query
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """
    Lazily load bge-small-en-v1.5 on first call; return cached instance
    on all subsequent calls.
    """
    global _model
    if _model is None:
        logger.info("Loading query embedding model: %s", EMBEDDING_MODEL)
        _model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info("Query embedding model loaded (%d dims)", EMBEDDING_DIMENSIONS)
    return _model


def embed_query(user_query: str) -> list[float]:
    """
    Embed a single user query into a 384-dim unit-length vector.

    Steps:
      1. Prepend the BGE query instruction prefix to the raw query string.
      2. Encode the prefixed string with normalize_embeddings=True so the
         vector has unit length — required for cosine distance in ChromaDB.
      3. Return as a plain Python list[float] (ChromaDB expects a list,
         not a numpy array).

    Args:
      user_query: The user's question, e.g. "What is the expense ratio of
                  HDFC Mid Cap Fund?"

    Returns:
      A list of 384 floats representing the query in embedding space.
    """
    model   = _get_model()
    prefixed = BGE_QUERY_PREFIX + user_query.strip()
    vector   = model.encode([prefixed], normalize_embeddings=True)
    return vector[0].tolist()
