"""
Phase 1.6 — Vector Store Builder

What this phase does:
  Takes all embedded chunks and persists them into a ChromaDB Cloud collection
  so the query pipeline can search them at runtime from anywhere.

Why ChromaDB Cloud instead of local?
  A local PersistentClient writes files to disk on whatever machine runs the
  pipeline. That machine (a GitHub Actions runner) is deleted after the job,
  so the files would have to be uploaded as an artifact and re-downloaded by
  the query service every time — fragile and slow.

  With ChromaDB Cloud (trychroma.com), the collection lives in a permanent
  hosted database. Both the ingestion pipeline (GitHub Actions) and the
  query pipeline (Streamlit app, wherever it runs) connect to the same
  collection using credentials — no file passing required.

Why drop-and-recreate instead of updating?
  With only 48 chunks and a full daily re-scrape, updating would require
  tracking which chunks changed — extra complexity with no benefit at this
  scale. Dropping and recreating is simpler and guarantees no stale data.

Input:
  list[EmbeddedChunk] — embedded chunks from Phase 1.5 (Embedder)

Output:
  Updated ChromaDB Cloud collection (persistent, accessible by query pipeline)

ChromaDB Cloud collection config (from ChunkingEmbeddingArchitecture.md):
  Collection name  : mutual_fund_faq
  Distance metric  : cosine similarity (hnsw:space = cosine)
  Index type       : HNSW (managed by ChromaDB Cloud)
  Host             : api.trychroma.com

Environment variables required (set locally and as GitHub Actions secrets):
  CHROMA_API_KEY   — API key from trychroma.com dashboard
  CHROMA_TENANT    — Tenant ID from trychroma.com dashboard
  CHROMA_DATABASE  — Database name created on trychroma.com

What gets stored per entry:
  id         : "chunk_0", "chunk_1", ...
  document   : raw chunk text
  embedding  : 384-dim float vector (bge-small-en-v1.5)
  metadata   : { source_url, scheme_name, fund_category,
                 passage_topic, scraped_at, chunk_index }
"""

from __future__ import annotations
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))   # ensures ingestion/ is on path

import chromadb

from phase_1_5_embedder import EmbeddedChunk

logger = logging.getLogger(__name__)

COLLECTION_NAME  = "mutual_fund_faq"
CHROMA_HOST      = "api.trychroma.com"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_client() -> chromadb.ClientAPI:
    """
    Return a ChromaDB CloudClient connected to ChromaDB Cloud (trychroma.com).

    Uses chromadb.CloudClient (introduced in chromadb 1.0.0) which targets the
    v2 API — the v1 API used by the old HttpClient is deprecated on trychroma.com.

    Reads credentials from environment variables at call time so the module
    can be imported safely even when the env vars aren't set yet (e.g.
    during unit tests that don't exercise the vector store).

    Raises KeyError with a clear message if any required env var is missing.
    """
    missing = [v for v in ("CHROMA_API_KEY", "CHROMA_TENANT", "CHROMA_DATABASE")
               if not os.environ.get(v)]
    if missing:
        raise KeyError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Set them locally or as GitHub Actions secrets."
        )

    return chromadb.CloudClient(
        tenant=os.environ["CHROMA_TENANT"],
        database=os.environ["CHROMA_DATABASE"],
        api_key=os.environ["CHROMA_API_KEY"],
    )


# ---------------------------------------------------------------------------
# Vector store builder
# ---------------------------------------------------------------------------

def drop_and_recreate_collection() -> None:
    """
    Delete the existing ChromaDB Cloud collection (if any) and create a fresh
    one with cosine similarity as the distance metric.

    Why cosine?
      Our embeddings are L2-normalised (normalize_embeddings=True in Phase 1.5),
      which means cosine similarity equals dot product — fast and accurate.

    The collection is configured via metadata={"hnsw:space": "cosine"} so
    ChromaDB's HNSW index uses cosine distance for all comparisons.
    """
    client = _get_client()

    # Delete the stale collection if it exists from a previous run
    try:
        client.delete_collection(COLLECTION_NAME)
        logger.info("  Dropped existing collection '%s' from ChromaDB Cloud", COLLECTION_NAME)
    except Exception:
        # Collection didn't exist yet — nothing to drop
        logger.info("  No existing collection to drop — creating fresh")

    client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info("  Created collection '%s' in ChromaDB Cloud (distance: cosine)", COLLECTION_NAME)


def insert_chunks(embedded_chunks: list[EmbeddedChunk]) -> None:
    """
    Insert all embedded chunks into the ChromaDB Cloud collection in a
    single batch.

    ChromaDB stores four parallel lists per entry:
      ids        — unique string IDs ("chunk_0", "chunk_1", ...)
      embeddings — the 384-dim float vectors
      documents  — the raw chunk text (returned at query time)
      metadatas  — dicts with source_url, scheme_name, scraped_at, etc.

    Sending all ~48 chunks in one .add() call is faster than looping
    because ChromaDB batches the HNSW index updates internally.
    """
    if not embedded_chunks:
        logger.warning("  insert_chunks called with empty list — nothing to insert")
        return

    client = _get_client()
    collection = client.get_collection(COLLECTION_NAME)

    ids        = [f"chunk_{i}" for i in range(len(embedded_chunks))]
    embeddings = [chunk.embedding for chunk in embedded_chunks]
    documents  = [chunk.text for chunk in embedded_chunks]
    metadatas  = [chunk.metadata for chunk in embedded_chunks]

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )
    logger.info(
        "  Inserted %d chunks into '%s' on ChromaDB Cloud",
        len(embedded_chunks), COLLECTION_NAME,
    )


def run_vector_store_builder(embedded_chunks: list[EmbeddedChunk]) -> None:
    """
    Phase 1.6 entry point — called by run_pipeline.py.

    Drops the old cloud collection, creates a fresh one, and inserts all
    chunks. After this function returns, the collection on trychroma.com
    is up to date and ready for the query pipeline.

    Raises on any ChromaDB error — the caller (run_pipeline.py) treats
    an exception here as a pipeline failure so GitHub Actions marks the
    job failed and the previous cloud collection remains intact.
    """
    logger.info(
        "Phase 1.6: Vector Store Builder — pushing %d chunks to ChromaDB Cloud",
        len(embedded_chunks),
    )
    drop_and_recreate_collection()
    insert_chunks(embedded_chunks)
    logger.info(
        "Phase 1.6: Collection '%s' updated on ChromaDB Cloud (%s)",
        COLLECTION_NAME, CHROMA_HOST,
    )


# ---------------------------------------------------------------------------
# Query-time retrieval (used by query/phase_2_5_retriever.py at runtime)
# ---------------------------------------------------------------------------

def get_collection() -> chromadb.Collection:
    """
    Return the live ChromaDB Cloud collection for query-time similarity search.
    Called by query/phase_2_5_retriever.py for every user question.

    The Streamlit app must also have CHROMA_API_KEY, CHROMA_TENANT, and
    CHROMA_DATABASE set in its environment (e.g. via .env locally, or
    platform secrets on Render / Streamlit Cloud).

    Raises KeyError if credentials are missing, or
    chromadb.errors.InvalidCollectionException if ingestion has never run.
    """
    client = _get_client()
    return client.get_collection(COLLECTION_NAME)
