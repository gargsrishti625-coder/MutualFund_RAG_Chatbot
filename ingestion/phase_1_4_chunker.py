"""
Phase 1.4 — Text Chunker

What this phase does:
  Converts normalized FundFields data into plain-English text passages,
  then splits those passages into small chunks ready for embedding.

Why two steps (passages first, then chunks)?
  Groww pages have scattered fields (NAV here, fund manager there).
  If we chunked raw text directly, one chunk might be half about expense
  ratio and half about benchmark — confusing for retrieval.
  Pre-building topic-focused passages (one passage = one topic) ensures
  every chunk stays semantically tight.

Input:
  ScrapeRun — the normalized scrape run from Phase 1.3.1 (Normalizer)

Output:
  list[Chunk] — list of text chunks, each with metadata attached

Chunk metadata carried forward to the vector store:
  source_url    — citation link shown to the user in the final response
  scheme_name   — used for metadata filtering at query time
  fund_category — used for metadata filtering at query time
  passage_topic — semantic label (e.g. "expense_exit", "tax", "nav_aum")
  scraped_at    — used for the "Last updated" footer in responses
  chunk_index   — position within the parent passage

Chunking parameters (from ChunkingEmbeddingArchitecture.md):
  chunk_size    = 300 tokens
  chunk_overlap = 50 tokens
  splitter      = RecursiveCharacterTextSplitter
  min_chunk_size = 30 tokens (fragments below this are discarded)
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field

from langchain_text_splitters import RecursiveCharacterTextSplitter
import tiktoken

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))   # ensures ingestion/ is on path
from scraper.models import ScrapeRun, ScrapedFund, FundFields

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token counter — used by the splitter for accurate chunk sizing
# ---------------------------------------------------------------------------

_enc = tiktoken.get_encoding("cl100k_base")

def _token_len(text: str) -> int:
    return len(_enc.encode(text))


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    """A single text chunk ready to be embedded."""
    text: str
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Passage builders — one function per topic
# ---------------------------------------------------------------------------

def _passage_identity(fund: ScrapedFund) -> str:
    """
    Passage 1 — Fund identity.
    Answers: what is this fund, who runs it, where is the source?
    """
    return "\n".join([
        f"Scheme: {fund.scheme_name}",
        f"Category: {fund.category}",
        "AMC: HDFC Mutual Fund",
        f"Source: {fund.source_url}",
        f"Data as of: {fund.scraped_at[:10]}",
    ])


def _passage_nav_aum(fields: FundFields, scraped_at: str) -> str:
    """
    Passage 2 — NAV and fund size.
    Answers: what is the current NAV, how large is the fund?
    """
    nav_date = fields.nav_date or scraped_at[:10]
    nav      = fields.nav or "Not available"
    aum      = fields.aum or "Not available"
    return "\n".join([
        f"NAV (Net Asset Value): {nav} as of {nav_date}",
        f"AUM (Assets Under Management): {aum}",
    ])


def _passage_investment_requirements(fields: FundFields) -> str:
    """
    Passage 3 — Minimum investment amounts.
    Answers: how much do I need to start a SIP or lump sum?
    """
    min_sip     = fields.min_sip or "Not available"
    min_lumpsum = fields.min_lumpsum or "Not available"
    return "\n".join([
        f"Minimum SIP amount: {min_sip} per month",
        f"Minimum lump sum (one-time) investment: {min_lumpsum}",
    ])


def _passage_expense_exit(fields: FundFields) -> str:
    """
    Passage 4 — Expense ratio and exit load.
    Answers: what does the fund charge per year, what is the exit penalty?
    """
    expense_ratio = fields.expense_ratio or "Not available"
    exit_load     = fields.exit_load or "Not available"
    return "\n".join([
        f"Expense Ratio (Total Expense Ratio / TER): {expense_ratio} per annum",
        f"Exit Load: {exit_load}",
    ])


def _passage_risk_benchmark(fields: FundFields) -> str:
    """
    Passage 5 — Risk rating, category, and benchmark.
    Answers: how risky is this fund, what index does it track?
    """
    risk_rating   = fields.risk_rating or "Not available"
    fund_category = fields.fund_category or "Not available"
    benchmark     = fields.benchmark or "Not available"
    return "\n".join([
        f"Riskometer / Risk Rating: {risk_rating}",
        f"Fund Category: {fund_category}",
        f"Benchmark Index: {benchmark}",
    ])


def _passage_fund_managers(fields: FundFields) -> str:
    """
    Passage 6 — Fund manager(s).
    Answers: who manages this fund?
    """
    if not fields.fund_managers:
        return "Fund Manager: Not available"
    lines = []
    for i, manager in enumerate(fields.fund_managers):
        label = "Fund Manager" if i == 0 else "Co-Fund Manager"
        lines.append(f"{label}: {manager}")
    return "\n".join(lines)


def _passage_tax(fields: FundFields) -> str:
    """
    Passage 7 — STCG, LTCG, and stamp duty.
    Answers: what are the tax implications of investing in this fund?
    """
    lines = []
    if fields.stcg_tax:
        lines.append(
            f"Short Term Capital Gains (STCG): {fields.stcg_tax} tax applicable "
            "if redeemed before 1 year."
        )
    if fields.ltcg_tax:
        lines.append(
            f"Long Term Capital Gains (LTCG): {fields.ltcg_tax}, applicable after 1 year."
        )
    if fields.stamp_duty:
        lines.append(
            f"Stamp Duty: {fields.stamp_duty} of investment amount "
            "(effective July 1, 2020)."
        )
    return "\n".join(lines) if lines else "Tax information: Not available"


def _passage_holdings(fields: FundFields) -> str | None:
    """
    Passage 8 — Number of holdings and top stocks (optional).
    Only included when the scraper found holdings data.
    Answers: how many stocks does the fund hold, what are the top positions?
    """
    if not fields.num_holdings and not fields.top_holdings:
        return None
    lines = []
    if fields.num_holdings:
        lines.append(f"Number of holdings: {fields.num_holdings} stocks")
    for holding in fields.top_holdings[:5]:
        lines.append(f"Top holding: {holding}")
    return "\n".join(lines) if lines else None


def _passage_elss_lockin(fields: FundFields) -> str | None:
    """
    Passage 9 — Lock-in period and 80C benefit (ELSS funds only).
    Only called for HDFC ELSS Tax Saver.
    Answers: how long is my money locked in, what tax benefit do I get?
    """
    lines = []
    if fields.lock_in_period:
        lines.append(
            f"Lock-in Period: {fields.lock_in_period} from the date of each "
            "SIP instalment / lump sum investment."
        )
        lines.append(
            "This is mandated by SEBI for all ELSS (Equity Linked Savings Scheme) funds."
        )
    if fields.elss_tax_benefit:
        lines.append(f"Tax benefit: {fields.elss_tax_benefit}")
    return "\n".join(lines) if lines else None


# ---------------------------------------------------------------------------
# Passage assembler
# ---------------------------------------------------------------------------

def build_passages(fund: ScrapedFund) -> list[tuple[str, str]]:
    """
    Build all text passages for one fund.
    Returns list of (passage_text, passage_topic) tuples.

    Passages 1-7 are always produced.
    Passage 8 (holdings) is skipped if the scraper found no holdings data.
    Passage 9 (ELSS lock-in) is only added for ELSS category funds.
    """
    f = fund.fields
    passages: list[tuple[str, str]] = [
        (_passage_identity(fund),                    "identity"),
        (_passage_nav_aum(f, fund.scraped_at),       "nav_aum"),
        (_passage_investment_requirements(f),         "investment_requirements"),
        (_passage_expense_exit(f),                    "expense_exit"),
        (_passage_risk_benchmark(f),                  "risk_benchmark"),
        (_passage_fund_managers(f),                   "fund_managers"),
        (_passage_tax(f),                             "tax"),
    ]

    # Passage 8 — optional: only if holdings data was scraped
    holdings_text = _passage_holdings(f)
    if holdings_text:
        passages.append((holdings_text, "holdings"))

    # Passage 9 — ELSS lock-in: only for ELSS category funds
    if "ELSS" in fund.category.upper():
        elss_text = _passage_elss_lockin(f)
        if elss_text:
            passages.append((elss_text, "elss_lockin"))

    return passages


# ---------------------------------------------------------------------------
# Splitter
# ---------------------------------------------------------------------------

def chunk_passages(
    passages: list[tuple[str, str]],
    fund: ScrapedFund,
    chunk_size: int = 300,
    chunk_overlap: int = 50,
    min_chunk_size: int = 30,
) -> list[Chunk]:
    """
    Split passages into chunks using RecursiveCharacterTextSplitter.
    Attaches metadata to every chunk.

    Most passages are short enough to produce exactly one chunk each.
    The splitter is a safety net for longer passages (e.g. holdings with many entries).
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=_token_len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[Chunk] = []
    for passage_text, passage_topic in passages:
        sub_texts = splitter.split_text(passage_text)
        for i, text in enumerate(sub_texts):
            # Discard fragments below minimum chunk size
            if _token_len(text) < min_chunk_size:
                continue
            chunks.append(Chunk(
                text=text,
                metadata={
                    "source_url":    fund.source_url,
                    "scheme_name":   fund.scheme_name,
                    "fund_category": fund.category,
                    "passage_topic": passage_topic,
                    "scraped_at":    fund.scraped_at,
                    "chunk_index":   i,
                },
            ))
    return chunks


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_chunker(normalized_run: ScrapeRun) -> list[Chunk]:
    """
    Phase 1.4 entry point — called by run_pipeline.py.

    Processes all successfully scraped funds and returns a flat list of chunks
    ready to be passed to the Embedder (Phase 1.5).
    """
    all_chunks: list[Chunk] = []
    for fund in normalized_run.successful_results:
        passages = build_passages(fund)
        chunks   = chunk_passages(passages, fund)
        all_chunks.extend(chunks)
        logger.info(
            "  ✓ Chunked: %s — %d passages → %d chunks",
            fund.scheme_name, len(passages), len(chunks),
        )
    logger.info("  Total chunks across all funds: %d", len(all_chunks))
    return all_chunks
