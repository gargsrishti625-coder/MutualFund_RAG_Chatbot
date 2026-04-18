"""
Phase 2.6 — Context Builder & Source Tracker

What this phase does:
  Takes the ranked list of RetrievedChunks from Phase 2.5 and produces
  a single QueryContext object containing:
    - context_text : all unique chunk texts joined into one block, ready
                     to be inserted into the LLM prompt
    - source_url   : the citation link for the response (exactly one URL,
                     taken from the highest-ranked chunk)
    - scraped_at   : the "Last updated" date shown in every response footer
                     (taken from the highest-ranked chunk's metadata)

Why deduplicate?
  The chunker in Phase 1.4 uses chunk_overlap=50 tokens so that context
  is not lost at chunk boundaries. This means adjacent chunks share ~50
  tokens of text. Without deduplication, the same sentence can appear
  twice in the LLM prompt — wasting tokens and potentially confusing the
  model into repeating itself.

Deduplication strategy:
  For each candidate chunk (in order of relevance, most relevant first):
    1. Take the first OVERLAP_CHECK_LEN characters of the chunk text.
    2. Check whether that prefix already appears verbatim in the
       accumulated context string.
    3. If yes → skip the chunk (it is the overlapping tail of a chunk
       already added).
    4. If no  → append the full chunk text to the context.

  This is O(n × m) where n = number of chunks and m = total context length.
  At TOP_K=4 and ~300-token chunks, this is negligible.

Why exactly one citation URL?
  The problem statement requires a single source link per response.
  We use the URL from chunk[0] — the closest match to the query — as it
  is the most authoritative source for the answer given.

Input:
  list[RetrievedChunk]  — ranked chunks from Phase 2.5, most relevant first.
                          May be empty if no chunks passed the distance
                          threshold — caller must handle EmptyRetrievalError.

Output:
  QueryContext  — assembled context + best source URL + data date
"""

from __future__ import annotations
import logging
from dataclasses import dataclass

from .phase_2_5_retriever import RetrievedChunk

logger = logging.getLogger(__name__)

# Number of leading characters used to detect overlap between adjacent chunks.
# 50 tokens ≈ 200–250 characters for typical English prose; 150 chars gives a
# reliable overlap signal without being too strict.
OVERLAP_CHECK_LEN = 150


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class EmptyRetrievalError(ValueError):
    """
    Raised when build_context() receives an empty chunk list.

    This happens when Phase 2.5 found no chunks within the similarity
    threshold — meaning the query has no relevant information in the corpus.
    The caller (pipeline.py) should catch this and return a
    "I don't have that information" response instead of calling the LLM.
    """


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------

@dataclass
class QueryContext:
    """
    The assembled context block passed to the LLM (Phase 2.7).

    Attributes:
      context_text  — unique chunk texts joined with double newlines,
                      ready to be inserted into the LLM system prompt
      source_url    — citation URL from the highest-ranked chunk;
                      shown as the one source link in every response
      scraped_at    — ISO date string (YYYY-MM-DD) from the chunk metadata;
                      shown in the "Last updated from sources: <date>" footer
    """
    context_text: str
    source_url:   str
    scraped_at:   str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_near_duplicate(candidate: str, accumulated: str) -> bool:
    """
    Return True if the candidate chunk is a near-duplicate of content
    already in the accumulated context.

    Detection method:
      Take the first OVERLAP_CHECK_LEN characters of the candidate.
      If that prefix appears verbatim anywhere in the accumulated string,
      the candidate is the overlapping continuation of an already-added
      chunk and should be skipped.

    This catches the specific overlap pattern produced by
    RecursiveCharacterTextSplitter(chunk_overlap=50): the last ~50 tokens
    of chunk N appear as the first ~50 tokens of chunk N+1.
    """
    if not accumulated:
        return False
    prefix = candidate[:OVERLAP_CHECK_LEN].strip()
    return bool(prefix) and prefix in accumulated


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def build_context(chunks: list[RetrievedChunk]) -> QueryContext:
    """
    Assemble deduplicated chunk texts into a QueryContext.

    Steps:
      1. Validate the input list is not empty.
      2. Extract source_url and scraped_at from chunk[0] (highest-ranked).
      3. Iterate through chunks in relevance order, skipping near-duplicates.
      4. Join the unique texts with double newlines into context_text.
      5. Return the QueryContext.

    Args:
      chunks: RetrievedChunks from Phase 2.5, sorted by distance ascending
              (most relevant first). Must not be empty.

    Returns:
      QueryContext with deduplicated context text, one source URL, and date.

    Raises:
      EmptyRetrievalError if chunks is empty — signals that the query had
      no relevant matches in the corpus.
    """
    if not chunks:
        raise EmptyRetrievalError(
            "No chunks retrieved — query has no relevant matches in the corpus. "
            "Respond with 'I don't have that information' instead of calling the LLM."
        )

    # Source URL and date always come from the highest-ranked chunk (index 0)
    best      = chunks[0]
    source_url = best.metadata.get("source_url", "")
    scraped_at = best.metadata.get("scraped_at", "")[:10]   # keep YYYY-MM-DD only

    # Deduplicate and collect unique chunk texts
    unique_texts: list[str] = []
    accumulated  = ""

    for chunk in chunks:
        if _is_near_duplicate(chunk.text, accumulated):
            logger.debug(
                "Deduped overlapping chunk (passage_topic=%s, chunk_index=%s)",
                chunk.metadata.get("passage_topic", "?"),
                chunk.metadata.get("chunk_index", "?"),
            )
            continue
        unique_texts.append(chunk.text)
        accumulated += "\n\n" + chunk.text

    context_text = "\n\n".join(unique_texts)

    logger.info(
        "Context built: %d unique chunks from %d retrieved | source=%s | date=%s",
        len(unique_texts), len(chunks), source_url, scraped_at,
    )

    return QueryContext(
        context_text=context_text,
        source_url=source_url,
        scraped_at=scraped_at,
    )
