"""
Phase 1.5 — Chunk Embedder

What this phase does:
  Converts each text chunk into a 384-dimensional float vector using
  the BAAI/bge-small-en-v1.5 model via sentence-transformers. These vectors
  are what makes semantic search possible — similar meaning = similar vector.

Why vectors?
  Computers can't understand text directly. Converting text to numbers
  (vectors) lets us measure how similar two pieces of text are by
  computing the distance between their vectors. A query like
  "what is the expense ratio?" will produce a vector very close to
  the chunk "Expense Ratio (TER): 0.77% per annum" — even though
  the words don't match exactly.

Why bge-small-en-v1.5?
  - Runs locally on the GitHub Actions runner — no API key, no cost
  - Trained specifically for retrieval tasks (BGE = BAAI General Embedding)
  - 384 dimensions are compact and fast to search at this corpus size (~48 chunks)
  - normalize_embeddings=True makes cosine similarity equal to dot product,
    which ChromaDB handles correctly with hnsw:space: cosine

Input:
  list[Chunk] — chunks produced by Phase 1.4 (Chunker)

Output:
  list[EmbeddedChunk] — same chunks, each now carrying a 384-dim vector

Embedding model (from ChunkingEmbeddingArchitecture.md):
  Model      : BAAI/bge-small-en-v1.5 (sentence-transformers)
  Dimensions : 384
  Batching   : all chunks encoded in a single local call
  Cost       : $0 — local inference, no external API
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))   # ensures ingestion/ is on path

from sentence_transformers import SentenceTransformer
from phase_1_4_chunker import Chunk

logger = logging.getLogger(__name__)

EMBEDDING_MODEL      = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIMENSIONS = 384

# Module-level model instance — loaded once on first call, reused for all chunks
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """
    Lazily load the SentenceTransformer model on first call.
    Subsequent calls return the cached instance — model loading takes ~2s
    and should only happen once per pipeline run.
    """
    global _model
    if _model is None:
        logger.info("  Loading embedding model: %s", EMBEDDING_MODEL)
        _model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info("  Model loaded — output dimensions: %d", EMBEDDING_DIMENSIONS)
    return _model


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------

@dataclass
class EmbeddedChunk:
    """A chunk that has been converted into a vector."""
    text: str
    embedding: list[float]                   # 384 floats
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Embedder
# ---------------------------------------------------------------------------

def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Encode a list of text strings into 384-dim vectors using bge-small-en-v1.5.
    Returns one vector per input text.

    All texts are encoded in a single local call (no network required).
    normalize_embeddings=True ensures vectors are unit-length so cosine
    similarity equals dot product — required for ChromaDB's hnsw:space: cosine.
    """
    model = _get_model()
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embeddings.tolist()


def run_embedder(chunks: list[Chunk]) -> list[EmbeddedChunk]:
    """
    Phase 1.5 entry point — called by run_pipeline.py.

    Embeds all chunks in a single batched call and returns EmbeddedChunk
    list ready for the Vector Store Builder (Phase 1.6).
    """
    if not chunks:
        logger.warning("  run_embedder called with empty chunk list")
        return []

    logger.info("  Embedding %d chunks with %s ...", len(chunks), EMBEDDING_MODEL)
    texts   = [chunk.text for chunk in chunks]
    vectors = embed_texts(texts)

    embedded = [
        EmbeddedChunk(
            text=chunk.text,
            embedding=vector,
            metadata=chunk.metadata,
        )
        for chunk, vector in zip(chunks, vectors)
    ]
    logger.info("  ✓ Produced %d embedded chunks (%d dims each)", len(embedded), EMBEDDING_DIMENSIONS)
    return embedded
