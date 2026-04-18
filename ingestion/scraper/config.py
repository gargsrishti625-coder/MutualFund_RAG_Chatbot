"""
Scraper configuration — loads fund list from config/funds.json.

Why a JSON file instead of hardcoding here?
  The fund list is a business decision ("which funds do we track?"), not code.
  Storing it in config/funds.json means anyone can add or remove a fund by
  editing one JSON file — no Python knowledge needed, no risk of syntax errors.

To add a new fund:
  Edit config/funds.json and add an entry:
    { "scheme_name": "...", "category": "...", "url": "https://groww.in/..." }
  Then re-run the pipeline (or wait for the 9:15 AM scheduled run).
"""

import json
from dataclasses import dataclass
from pathlib import Path

# config/funds.json is two levels up from this file (ingestion/scraper/config.py)
_FUNDS_FILE = Path(__file__).parent.parent.parent / "config" / "funds.json"


@dataclass(frozen=True)
class FundConfig:
    scheme_name: str
    category: str
    url: str


def _load_fund_configs() -> list[FundConfig]:
    if not _FUNDS_FILE.exists():
        raise FileNotFoundError(
            f"Fund config file not found: {_FUNDS_FILE}\n"
            "Expected config/funds.json at the project root."
        )
    with open(_FUNDS_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    return [
        FundConfig(
            scheme_name=entry["scheme_name"],
            category=entry["category"],
            url=entry["url"],
        )
        for entry in raw
    ]


# Loaded once at import time — same behaviour as before, but source is the JSON file
FUND_CONFIGS: list[FundConfig] = _load_fund_configs()


# ---------------------------------------------------------------------------
# Scraper settings (these stay in code — they are system config, not business config)
# ---------------------------------------------------------------------------

# Keywords in page text that indicate performance/return sections — excluded from corpus
EXCLUDED_SECTION_KEYWORDS: list[str] = [
    "1 year return",
    "3 year return",
    "5 year return",
    "10 year return",
    "annualised return",
    "annualized return",
    "cagr",
    "absolute return",
    "trailing return",
    "peer comparison",
    "similar funds",
    "return calculator",
    "sip calculator",
    "lumpsum calculator",
]

REQUEST_TIMEOUT: int = 15
SCRAPE_DELAY_SECONDS: float = 2.0

REQUEST_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
