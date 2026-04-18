"""
Scraping service — fetches each Groww fund page and extracts raw structured data.

Flow per URL:
  1. Try requests (fast, lightweight)
  2. If content looks incomplete (JS-gated), fall back to Playwright headless Chromium
  3. Parse HTML with parser.py
  4. Return ScrapedFund dataclass with RAW field values (no normalization here)

Normalization is intentionally NOT done here.
run_pipeline.py calls the normalizer as a separate step after scraping,
so that raw data can be saved to data/raw/ before any cleaning is applied.

All 5 fund pages are scraped sequentially with a configurable delay between
requests to avoid rate limiting.
"""

import logging
import time
from datetime import datetime, timezone, timedelta

import requests

from .config import (
    FUND_CONFIGS,
    FundConfig,
    SCRAPE_DELAY_SECONDS,
    REQUEST_TIMEOUT,
    REQUEST_HEADERS,
)
from .models import FundFields, ScrapedFund, ScrapeRun
from .phase_1_3_parser import parse_fund_page

logger = logging.getLogger(__name__)

# IST offset
_IST = timezone(timedelta(hours=5, minutes=30))

# Minimum character count to consider an HTTP response usable
# (Groww React pages return a tiny shell if JS hasn't run)
_MIN_USEFUL_HTML_LENGTH = 5_000

# Keywords that must appear somewhere in the HTML for it to be considered
# a properly rendered fund page
_CONTENT_MARKERS = [
    "expense ratio",
    "exit load",
    "fund manager",
    "NAV",
]


def _ist_now() -> str:
    """Return current time as ISO 8601 string in IST."""
    return datetime.now(_IST).isoformat()


def _html_looks_complete(html: str) -> bool:
    """
    Heuristic: does the page HTML look like a fully rendered fund page,
    or just a bare React shell?
    """
    if len(html) < _MIN_USEFUL_HTML_LENGTH:
        return False
    html_lower = html.lower()
    matched = sum(1 for marker in _CONTENT_MARKERS if marker.lower() in html_lower)
    return matched >= 2


def _fetch_with_requests(url: str) -> str | None:
    """
    Attempt to fetch page HTML using requests.
    Returns HTML string, or None on failure.
    """
    try:
        response = requests.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        logger.warning("requests fetch failed for %s: %s", url, exc)
        return None


def _fetch_with_playwright(url: str) -> str | None:
    """
    Fetch a JS-rendered page using Playwright headless Chromium.
    Returns full page HTML after JS execution, or None on failure.

    Playwright is imported lazily so the scraper still works in
    environments where it is not installed (requests-only path).
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        logger.error(
            "playwright is not installed. Run: pip install playwright && playwright install chromium"
        )
        return None

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=REQUEST_HEADERS["User-Agent"],
                locale="en-IN",
            )
            page = context.new_page()

            # Block images, fonts, and media to speed up load
            page.route(
                "**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,mp4,mp3}",
                lambda route: route.abort(),
            )

            page.goto(url, wait_until="networkidle", timeout=30_000)

            # Wait for a key element that signals fund data has loaded
            try:
                page.wait_for_selector(
                    "text=Expense Ratio",
                    timeout=10_000,
                )
            except PWTimeout:
                logger.warning("Timed out waiting for fund content on %s", url)

            html = page.content()
            browser.close()
            return html

    except Exception as exc:
        logger.error("playwright fetch failed for %s: %s", url, exc)
        return None


def _scrape_one(config: FundConfig) -> ScrapedFund:
    """
    Scrape a single fund page. Tries requests first; falls back to Playwright
    if the HTML looks like an unrendered React shell.
    """
    logger.info("Scraping: %s", config.url)
    scraped_at = _ist_now()
    scrape_method = "requests"
    html: str | None = None

    # --- Step 1: Try requests ---
    html = _fetch_with_requests(config.url)

    if html and _html_looks_complete(html):
        logger.info("  ✓ requests fetch sufficient for %s", config.scheme_name)
    else:
        # --- Step 2: Fall back to Playwright ---
        logger.info(
            "  ↳ requests HTML incomplete (%d chars), trying Playwright…",
            len(html) if html else 0,
        )
        scrape_method = "playwright"
        html = _fetch_with_playwright(config.url)

        if not html or not _html_looks_complete(html):
            logger.error("  ✗ Both fetch methods failed for %s", config.scheme_name)
            return ScrapedFund(
                scheme_name=config.scheme_name,
                category=config.category,
                source_url=config.url,
                scraped_at=scraped_at,
                fields=FundFields(),
                scrape_method=scrape_method,
                error=f"Failed to retrieve usable HTML from {config.url}",
            )

        logger.info("  ✓ Playwright fetch succeeded for %s", config.scheme_name)

    # --- Step 3: Parse HTML ---
    is_elss = config.category == "ELSS"
    try:
        fields = parse_fund_page(html, is_elss=is_elss)
    except Exception as exc:
        logger.error("  ✗ Parsing failed for %s: %s", config.scheme_name, exc)
        return ScrapedFund(
            scheme_name=config.scheme_name,
            category=config.category,
            source_url=config.url,
            scraped_at=scraped_at,
            fields=FundFields(),
            scrape_method=scrape_method,
            error=f"HTML parsing error: {exc}",
        )

    logger.info("  ✓ Parsed successfully (raw): %s", config.scheme_name)

    return ScrapedFund(
        scheme_name=config.scheme_name,
        category=config.category,
        source_url=config.url,
        scraped_at=scraped_at,
        fields=fields,
        scrape_method=scrape_method,
    )


def run_scraper() -> ScrapeRun:
    """
    Scrape all 5 HDFC fund pages sequentially.
    Returns a ScrapeRun with results for all funds.
    """
    run = ScrapeRun(run_at=_ist_now())
    total = len(FUND_CONFIGS)

    logger.info("=" * 60)
    logger.info("Starting scrape run — %d funds to process", total)
    logger.info("=" * 60)

    for i, config in enumerate(FUND_CONFIGS):
        result = _scrape_one(config)
        run.add(result)

        # Delay between requests (skip after the last one)
        if i < total - 1:
            logger.debug("Sleeping %.1fs before next request…", SCRAPE_DELAY_SECONDS)
            time.sleep(SCRAPE_DELAY_SECONDS)

    logger.info("=" * 60)
    logger.info(
        "Scrape run complete — %d/%d succeeded, %d failed",
        run.succeeded,
        run.total,
        run.failed,
    )
    if run.failed > 0:
        for r in run.results:
            if r.error:
                logger.warning("  FAILED: %s — %s", r.scheme_name, r.error)
    logger.info("=" * 60)

    return run
