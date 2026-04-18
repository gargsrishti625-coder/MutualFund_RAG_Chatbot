"""
Phase 2.8 — Response Formatter

What this phase does:
  Takes the raw answer string from the LLM (Phase 2.7) and applies three
  post-processing steps before the response reaches the user:

    1. Enforce 3-sentence maximum — split on sentence boundaries and
       truncate. The LLM is instructed to stay within 3 sentences, but
       code enforcement is a reliable safety net for occasional slippage.

    2. Append exactly one citation link — the source_url from the
       highest-ranked retrieved chunk (carried in QueryContext from
       Phase 2.6). This is a hard requirement from the problem statement.

    3. Append a "Last updated" footer — the scraped_at date from the
       chunk metadata, formatted as "Last updated from sources: YYYY-MM-DD".
       This makes data freshness transparent to the user.

Why separate formatting from generation?
  The LLM's job is to produce a factual answer. Structural concerns like
  citation format and footer layout are deterministic and belong in code —
  not in the model's probabilistic output. This split also makes it easy
  to change the output format without touching the prompt.

Sentence splitting:
  Uses a regex that splits after . ! ? only when followed by whitespace
  and an uppercase letter. This avoids splitting on:
    - "0.77%"  (digit before period)
    - "e.g. "  (lowercase after period)
    - "₹1.25 lakh"  (digit or symbol after period)
  For the short, factual sentences this LLM produces, this is accurate
  enough without pulling in spaCy or NLTK.

Input:
  raw_answer : str          — LLM output from Phase 2.7
  context    : QueryContext — carries source_url and scraped_at

Output:
  FormattedResponse — dataclass with four fields:
    answer       : str  — truncated answer (≤3 sentences)
    source_url   : str  — citation link
    last_updated : str  — "YYYY-MM-DD" date string
    full_text    : str  — complete response ready to display in the UI

Example full_text:
  The expense ratio for HDFC Mid Cap Fund – Direct Growth is 0.77% per annum.
  This is the Total Expense Ratio (TER) as mandated by SEBI regulations.

  Source: https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth
  Last updated from sources: 2026-04-18
"""

from __future__ import annotations
import logging
import re
from dataclasses import dataclass

from query.retrieval.phase_2_6_context_builder import QueryContext

logger = logging.getLogger(__name__)

MAX_SENTENCES = 3


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------

@dataclass
class FormattedResponse:
    """
    The final response object returned to the UI.

    Attributes:
      answer       — the LLM answer, hard-capped at MAX_SENTENCES sentences
      source_url   — single citation URL (from the top-ranked retrieved chunk)
      last_updated — date the data was scraped, e.g. "2026-04-18"
      full_text    — answer + source line + last-updated line, ready for display
    """
    answer:       str
    source_url:   str
    last_updated: str
    full_text:    str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> list[str]:
    """
    Split text into sentences on [.!?] followed by whitespace + uppercase.

    This avoids false splits on:
      - Decimal numbers  : "0.77%", "₹1.25 lakh"
      - Abbreviations    : "e.g. this", "i.e. that"
      - Ellipsis         : "..."

    Returns a list of non-empty sentence strings.
    """
    # Split after sentence-ending punctuation only when followed by
    # whitespace and an uppercase letter or digit (start of a new sentence).
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z₹\d"])', text.strip())
    return [s.strip() for s in parts if s.strip()]


def _truncate_to_sentences(text: str, max_sentences: int) -> str:
    """
    Return text truncated to at most max_sentences sentences.
    If the text has fewer sentences, it is returned unchanged.
    """
    sentences = _split_sentences(text)
    kept = sentences[:max_sentences]
    # Ensure the last sentence ends with punctuation
    result = " ".join(kept)
    if result and result[-1] not in ".!?":
        result += "."
    return result


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------

def format_response(raw_answer: str, context: QueryContext) -> FormattedResponse:
    """
    Post-process the raw LLM answer into the final structured response.

    Steps:
      1. Truncate raw_answer to MAX_SENTENCES (3) sentences.
      2. Build full_text by appending the source URL and last-updated footer.
      3. Return a FormattedResponse with all fields populated.

    Args:
      raw_answer : The string returned by Phase 2.7 generate().
      context    : QueryContext from Phase 2.6 — provides source_url and
                   scraped_at.

    Returns:
      FormattedResponse ready to be rendered by the UI.
    """
    answer = _truncate_to_sentences(raw_answer.strip(), MAX_SENTENCES)

    last_updated = context.scraped_at   # already "YYYY-MM-DD" from Phase 2.6
    source_url   = context.source_url

    full_text = (
        f"{answer}\n\n"
        f"Source: {source_url}\n"
        f"Last updated from sources: {last_updated}"
    )

    logger.info(
        "Response formatted: %d sentences | source=%s | date=%s",
        len(_split_sentences(answer)),
        source_url,
        last_updated,
    )

    return FormattedResponse(
        answer=answer,
        source_url=source_url,
        last_updated=last_updated,
        full_text=full_text,
    )
