"""
query/retrieval — Phases 2.4, 2.5, 2.6

The retrieval layer sits between the query classifier and the LLM.
It converts the user's question into a vector, finds the most relevant
chunks from ChromaDB Cloud, and assembles them into a prompt-ready
context block with exactly one citation URL.

  Phase 2.4 — Query Embedder   : text  → 384-dim vector (bge-small-en-v1.5)
  Phase 2.5 — Retriever        : vector → top-K RetrievedChunks (ChromaDB)
  Phase 2.6 — Context Builder  : chunks → QueryContext (text + source + date)
"""

from .phase_2_4_query_embedder import embed_query
from .phase_2_5_retriever import retrieve, RetrievedChunk
from .phase_2_6_context_builder import build_context, QueryContext, EmptyRetrievalError

__all__ = [
    "embed_query",
    "retrieve",
    "RetrievedChunk",
    "build_context",
    "QueryContext",
    "EmptyRetrievalError",
]
