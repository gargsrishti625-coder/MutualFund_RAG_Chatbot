"""
Phase 2.5 — Vector Store Retriever

What this phase does:
  Takes the 384-dim query vector from Phase 2.4 and performs approximate
  nearest-neighbour (ANN) search against the ChromaDB Cloud collection that
  was built by the ingestion pipeline (Phase 1.6). Returns the top-K chunks
  most semantically similar to the query, filtered by a distance threshold.

How the similarity search works:
  ChromaDB's HNSW index computes cosine distance between the query vector
  and every stored chunk vector. Because all vectors are L2-normalised
  (normalize_embeddings=True in both Phase 1.5 and Phase 2.4), cosine
  distance equals 1 − dot_product, ranging from 0 (identical) to 2
  (completely opposite).

  A distance of 0.5 corresponds to cosine_similarity = 0.5, which means
  the chunk is at least moderately on-topic. Anything beyond that threshold
  is discarded — it would only dilute the LLM prompt with noise.

Optional scheme_name filter:
  If the query is about a specific fund (e.g. "HDFC Mid Cap"), the classifier
  can pass the exact scheme_name string. ChromaDB applies this as a metadata
  pre-filter so only that fund's chunks are even considered for similarity
  ranking — improving precision and reducing irrelevant results.

Collection caching:
  _get_collection() fetches the ChromaDB collection object once and caches
  it at module level. The collection object is a lightweight client-side
  handle — re-fetching it on every query would add unnecessary round-trips
  to trychroma.com.

Input:
  query_embedding : list[float]  — 384-dim vector from Phase 2.4
  scheme_name     : str | None   — optional metadata filter

Output:
  list[RetrievedChunk] — up to TOP_K chunks, sorted by distance ascending
                         (most similar first), with chunks beyond
                         SIMILARITY_THRESHOLD excluded
"""

from __future__ import annotations
import logging
import os
import sys
from dataclasses import dataclass

# ── Path setup ────────────────────────────────────────────────────────────────
# Add the project root (two levels up from this file) to sys.path so that
# `import ingestion` resolves when the app is run from any working directory.
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from ingestion.phase_1_6_vector_store import get_collection

logger = logging.getLogger(__name__)

TOP_K                = 4
SIMILARITY_THRESHOLD = 0.5   # cosine distance; lower = more similar


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------

@dataclass
class RetrievedChunk:
    """
    A single chunk returned from ChromaDB, enriched with its distance score.

    Attributes:
      text      — the raw chunk text, passed verbatim to the Context Builder
      metadata  — dict with source_url, scheme_name, fund_category,
                  passage_topic, scraped_at, chunk_index
      distance  — cosine distance from the query vector (0 = identical,
                  1 = orthogonal, 2 = opposite); lower is more relevant
    """
    text:     str
    metadata: dict
    distance: float


# ---------------------------------------------------------------------------
# Collection cache
# ---------------------------------------------------------------------------

_collection = None   # cached ChromaDB collection handle


def _get_collection():
    """
    Return the cached ChromaDB collection, fetching it on first call.
    Subsequent calls return the same object without a network round-trip.
    """
    global _collection
    if _collection is None:
        logger.info("Connecting to ChromaDB Cloud collection ...")
        _collection = get_collection()
        logger.info("Connected to ChromaDB collection: mutual_fund_faq")
    return _collection


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------

def retrieve(
    query_embedding: list[float],
    scheme_name: str | None = None,
) -> list[RetrievedChunk]:
    """
    Search ChromaDB Cloud for the top-K chunks most similar to the query.

    Args:
      query_embedding : 384-dim unit-length vector produced by Phase 2.4.
      scheme_name     : If the query mentions a specific fund (e.g.
                        "HDFC Mid Cap Fund – Direct Growth"), pass the exact
                        scheme_name string to restrict the search to that
                        fund's chunks only. Pass None to search all funds.

    Returns:
      A list of RetrievedChunk objects sorted by distance ascending
      (most relevant first). Any chunk whose cosine distance exceeds
      SIMILARITY_THRESHOLD (0.5) is dropped — it is considered too
      weakly related to be useful context for the LLM.

      Returns an empty list if no chunks pass the threshold.
    """
    collection = _get_collection()

    # Build optional metadata pre-filter
    where = {"scheme_name": scheme_name} if scheme_name else None

    # Query ChromaDB — returns parallel lists: documents, metadatas, distances
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=TOP_K,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    # Build RetrievedChunk list, dropping anything beyond the threshold
    chunks: list[RetrievedChunk] = []
    for text, metadata, distance in zip(documents, metadatas, distances):
        if distance <= SIMILARITY_THRESHOLD:
            chunks.append(RetrievedChunk(
                text=text,
                metadata=metadata,
                distance=distance,
            ))
        else:
            logger.debug(
                "Dropped chunk (distance %.3f > threshold %.1f): %s...",
                distance, SIMILARITY_THRESHOLD, text[:60],
            )

    logger.info(
        "Retrieved %d/%d chunks within threshold (scheme_filter=%s)",
        len(chunks), len(documents), scheme_name or "none",
    )
    return chunks
