"""
Phase 3.2 — Query Classifier

What this phase does:
  Examines the user query and routes it into one of three tracks before
  any retrieval or generation happens. This is the gatekeeper that ensures
  advisory and performance queries never reach the LLM with a factual prompt.

The three tracks:
  FACTUAL      — answer using the vector store + LLM
                 e.g. "What is the expense ratio of HDFC Mid Cap?"

  ADVISORY     — refuse immediately with a polite educational link
                 e.g. "Should I invest in this fund?"
                 e.g. "Which fund is better for me?"

  PERFORMANCE  — redirect to the Groww source URL; don't answer
                 e.g. "What is the 3-year return of HDFC Mid Cap?"
                 e.g. "How has HDFC Equity Fund performed?"

Why classify before retrieval?
  Embedding a query and searching ChromaDB takes ~200ms and a network
  round-trip. Advisory and performance queries have known-bad answers —
  there is no point retrieving chunks for "Should I invest?" The classifier
  blocks them instantly with zero retrieval cost.

Why a two-layer approach?
  Layer 1 (keyword rules) — zero latency, zero cost, handles 95% of cases.
  Layer 2 (LLM zero-shot) — reserved for genuinely ambiguous edge cases
  where keyword matching is insufficient (not yet implemented; falls back
  to FACTUAL so the LLM system prompt acts as a second safety net).

Fund name extraction (extract_scheme_name):
  Also exported from this module. Identifies which of the 5 HDFC funds
  the user is asking about. Used by the pipeline to add a metadata filter
  to the ChromaDB query so only that fund's chunks are retrieved.

Input:
  user_query : str — sanitized query text (PII already removed by Phase 3.1)

Output:
  QueryType — FACTUAL, ADVISORY, or PERFORMANCE
  (extract_scheme_name also returns str | None)
"""

from __future__ import annotations
import re
import logging
from enum import Enum

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Query type enum
# ---------------------------------------------------------------------------

class QueryType(Enum):
    FACTUAL     = "factual"      # → retrieve and answer
    ADVISORY    = "advisory"     # → refuse with educational link
    PERFORMANCE = "performance"  # → redirect to fund source URL


# ---------------------------------------------------------------------------
# Keyword lists
# ---------------------------------------------------------------------------

# Any of these → ADVISORY (investment advice / recommendation request)
ADVISORY_KEYWORDS: list[str] = [
    "should i invest",
    "should i buy",
    "should i put",
    "is it good",
    "is it worth",
    "is this a good",
    "good time to invest",
    "worth investing",
    "better fund",
    "best fund",
    "which fund",
    "which is better",
    "recommend",
    "recommendation",
    "advice",
    "advise",
    "suggest",
    "suggestion",
    "compare",
    " vs ",
    "versus",
    "should i switch",
    "should i redeem",
]

# Any of these → PERFORMANCE (historical returns / performance data)
PERFORMANCE_KEYWORDS: list[str] = [
    "return",
    "returns",
    "performance",
    "cagr",
    "annualized",
    "annualised",
    "how has",
    "how did",
    "how much did",
    "1 year return",
    "3 year return",
    "5 year return",
    "10 year return",
    "1yr",
    "3yr",
    "5yr",
    "past performance",
    "historical return",
    "historic return",
    "year to date",
    "ytd",
    "absolute return",
]


# ---------------------------------------------------------------------------
# Fund name → scheme name map (for extract_scheme_name)
# ---------------------------------------------------------------------------

# Maps query keywords to the exact scheme_name stored in ChromaDB metadata.
# Keys are lowercase; matched via substring search in order.
_SCHEME_MAP: list[tuple[str, str]] = [
    ("mid cap",    "HDFC Mid Cap Fund – Direct Growth"),
    ("midcap",     "HDFC Mid Cap Fund – Direct Growth"),
    ("elss",       "HDFC ELSS Tax Saver Fund – Direct Growth"),
    ("tax saver",  "HDFC ELSS Tax Saver Fund – Direct Growth"),
    ("focused",    "HDFC Focused Fund – Direct Growth"),
    ("large cap",  "HDFC Large Cap Fund – Direct Growth"),
    ("largecap",   "HDFC Large Cap Fund – Direct Growth"),
    ("equity",     "HDFC Equity Fund – Direct Growth"),
]


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

def classify(user_query: str) -> QueryType:
    """
    Classify user_query into FACTUAL, ADVISORY, or PERFORMANCE.

    Algorithm (Layer 1 — keyword rules):
      1. Normalise query to lowercase.
      2. Check ADVISORY keywords — if any match, return ADVISORY immediately.
         Advisory queries take priority over performance (a query like
         "Which fund has better returns?" is advisory, not just performance).
      3. Check PERFORMANCE keywords — if any match, return PERFORMANCE.
      4. Default to FACTUAL — the LLM system prompt is a second safety net
         for edge cases that slip through keyword matching.

    Args:
      user_query: Sanitized query string (PII already stripped by Phase 3.1).

    Returns:
      QueryType enum value.
    """
    lower = user_query.lower().strip()

    for kw in ADVISORY_KEYWORDS:
        if kw in lower:
            logger.info("Classified as ADVISORY (matched: '%s')", kw)
            return QueryType.ADVISORY

    for kw in PERFORMANCE_KEYWORDS:
        if kw in lower:
            logger.info("Classified as PERFORMANCE (matched: '%s')", kw)
            return QueryType.PERFORMANCE

    logger.info("Classified as FACTUAL (no advisory/performance keywords)")
    return QueryType.FACTUAL


# ---------------------------------------------------------------------------
# Fund name extractor
# ---------------------------------------------------------------------------

def extract_scheme_name(user_query: str) -> str | None:
    """
    Identify which of the 5 HDFC funds the query is about.

    Scans the query for fund name keywords and returns the exact
    scheme_name string used as a metadata key in ChromaDB.

    Used by the pipeline to narrow retrieval to only the matching
    fund's chunks — improving precision when the user asks about
    a specific fund.

    Returns None if no specific fund is identified (retrieval will
    then search all 5 funds).

    Args:
      user_query: Raw or sanitized query string.

    Returns:
      Exact scheme_name str (e.g. "HDFC Mid Cap Fund – Direct Growth")
      or None if the query doesn't mention a specific fund.
    """
    lower = user_query.lower()
    for keyword, scheme_name in _SCHEME_MAP:
        if keyword in lower:
            logger.info("Fund identified: %s", scheme_name)
            return scheme_name
    return None
