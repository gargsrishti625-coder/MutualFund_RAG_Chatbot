"""
Ingestion pipeline entry point.

Stages (called in order):
  Phase 1.3   — Scraper:      Fetch and parse 5 Groww fund pages  → data/raw/
  Phase 1.3.1 — Normalizer:   Clean and standardize field values   → data/normalized/
  Phase 1.4   — Chunker:      Convert into text passages + chunks
  Phase 1.5   — Embedder:     Embed chunks via sentence-transformers (bge-small-en-v1.5)
  Phase 1.6   — Vector Store: Push embedded chunks to ChromaDB Cloud

Folder responsibilities:
  data/raw/        — raw scraped JSON exactly as the scraper returned it
  data/normalized/ — same data after normalizer has cleaned all fields
  logs/            — pipeline run logs (.log files only, no data)
  vector_store/    — ChromaDB files (built in Phase 5)

This script is invoked directly by the GitHub Actions daily workflow:
  cd ingestion && python run_pipeline.py

Exit codes:
  0 — pipeline completed (all stages OK, or partial scrape with at least 1 success)
  1 — pipeline failed (all scrapes failed, or a downstream stage crashed)
"""

import logging
import sys
import json
import dataclasses
from pathlib import Path
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
load_dotenv()   # loads CHROMA_API_KEY, CHROMA_TENANT, CHROMA_DATABASE from .env

from scraper import run_scraper
from scraper.models import ScrapeRun, ScrapedFund, FundFields
from scraper.phase_1_3_1_normalizer import normalize
from phase_1_4_chunker import run_chunker
from phase_1_5_embedder import run_embedder
from phase_1_6_vector_store import run_vector_store_builder

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_ROOT       = Path(__file__).parent.parent
_LOG_DIR    = _ROOT / "logs"
_RAW_DIR    = _ROOT / "data" / "raw"
_NORM_DIR   = _ROOT / "data" / "normalized"

for _d in (_LOG_DIR, _RAW_DIR, _NORM_DIR):
    _d.mkdir(parents=True, exist_ok=True)

_IST = timezone(timedelta(hours=5, minutes=30))


# ---------------------------------------------------------------------------
# Logging — .log files only go into logs/
# ---------------------------------------------------------------------------

def _setup_logging() -> None:
    log_file = _LOG_DIR / f"ingestion_{datetime.now(_IST).strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


logger = logging.getLogger("pipeline")


# ---------------------------------------------------------------------------
# Shared helper — FundFields → plain dict for JSON serialisation
# ---------------------------------------------------------------------------

def _fields_to_dict(f: FundFields) -> dict:
    return dataclasses.asdict(f)


def _run_to_payload(run: ScrapeRun) -> dict:
    """Convert a ScrapeRun into a JSON-serialisable dict."""
    return {
        "run_at":    run.run_at,
        "total":     run.total,
        "succeeded": run.succeeded,
        "failed":    run.failed,
        "results": [
            {
                "scheme_name":   r.scheme_name,
                "category":      r.category,
                "source_url":    r.source_url,
                "scraped_at":    r.scraped_at,
                "scrape_method": r.scrape_method,
                "error":         r.error,
                "fields":        _fields_to_dict(r.fields),
            }
            for r in run.results
        ],
    }


def _write_json(path: Path, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info("Saved → %s", path.relative_to(_ROOT))


# ---------------------------------------------------------------------------
# Phase 1.3 — Save raw scrape output
# ---------------------------------------------------------------------------

def _save_raw(run: ScrapeRun) -> None:
    """
    Save the raw scraper output to data/raw/scrape_<date>.json.

    'Raw' means exactly what the HTML parser returned — no cleaning applied.
    This is your source of truth if you ever need to re-process the data
    without re-scraping the web.
    """
    date_str  = datetime.now(_IST).strftime("%Y%m%d")
    out_path  = _RAW_DIR / f"scrape_{date_str}.json"
    _write_json(out_path, _run_to_payload(run))


# ---------------------------------------------------------------------------
# Phase 1.3.1 — Normalise and save
# ---------------------------------------------------------------------------

def _build_normalized_run(raw_run: ScrapeRun) -> ScrapeRun:
    """
    Apply the normalizer to every successfully scraped fund.
    Returns a new ScrapeRun whose ScrapedFund.fields are all cleaned.
    Failed scrapes are carried over unchanged (fields are empty anyway).
    """
    normalized_run = ScrapeRun(run_at=raw_run.run_at)
    for result in raw_run.results:
        if result.error:
            normalized_run.add(result)          # pass through as-is
            continue
        try:
            clean_fields = normalize(result.fields)
            normalized_run.add(ScrapedFund(
                scheme_name=result.scheme_name,
                category=result.category,
                source_url=result.source_url,
                scraped_at=result.scraped_at,
                scrape_method=result.scrape_method,
                fields=clean_fields,
            ))
            logger.info("  ✓ Normalized: %s", result.scheme_name)
        except Exception as exc:
            logger.warning(
                "  ⚠ Normalization failed for %s: %s — using raw values",
                result.scheme_name, exc,
            )
            normalized_run.add(result)          # fall back to raw
    return normalized_run


def _save_normalized(run: ScrapeRun) -> None:
    """
    Save the normalized data to data/normalized/normalized_<date>.json.

    This is what the chunker (Phase 1.4) will read.
    Having it as a file means Phase 1.4 can be re-run without re-scraping.
    """
    date_str  = datetime.now(_IST).strftime("%Y%m%d")
    out_path  = _NORM_DIR / f"normalized_{date_str}.json"
    _write_json(out_path, _run_to_payload(run))




# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    _setup_logging()

    logger.info("╔══════════════════════════════════════════════════╗")
    logger.info("║        Mutual Fund FAQ — Ingestion Pipeline       ║")
    logger.info("╚══════════════════════════════════════════════════╝")

    # ── Phase 1.3: Scraper ───────────────────────────────────────────────
    logger.info("── Phase 1.3: Scraper ───────────────────────────")
    raw_run = run_scraper()
    _save_raw(raw_run)                          # → data/raw/scrape_<date>.json

    if raw_run.succeeded == 0:
        logger.error("All %d scrapes failed. Aborting pipeline.", raw_run.total)
        return 1
    if raw_run.failed > 0:
        logger.warning(
            "%d/%d scrapes failed — continuing with partial data.",
            raw_run.failed, raw_run.total,
        )

    # ── Phase 1.3.1: Normalizer ────────────────────────────────────────────
    logger.info("── Phase 1.3.1: Normalizer ────────────────────────")
    normalized_run = _build_normalized_run(raw_run)
    _save_normalized(normalized_run)            # → data/normalized/normalized_<date>.json

    # ── Phase 1.4: Chunker ───────────────────────────────────────────────
    logger.info("── Phase 1.4: Chunker ───────────────────────────")
    chunks = run_chunker(normalized_run)

    # ── Phase 1.5: Embedder ──────────────────────────────────────────────
    logger.info("── Phase 1.5: Embedder ──────────────────────────")
    embedded_chunks = run_embedder(chunks)

    # ── Phase 1.6: Vector Store (ChromaDB Cloud) ─────────────────────────
    logger.info("── Phase 1.6: Vector Store (ChromaDB Cloud) ─────")
    run_vector_store_builder(embedded_chunks)

    logger.info("Pipeline complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
