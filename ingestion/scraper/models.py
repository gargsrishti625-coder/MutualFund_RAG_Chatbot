"""
Data models for scraped fund data.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FundFields:
    """All factual fields extracted from a single Groww fund page."""

    nav: str | None = None                  # e.g. "₹218.21"
    nav_date: str | None = None             # e.g. "17 Apr 2026"
    aum: str | None = None                  # e.g. "₹85,357.92 Cr"
    expense_ratio: str | None = None        # e.g. "0.77%"
    risk_rating: str | None = None          # e.g. "Very High Risk"
    fund_category: str | None = None        # e.g. "Equity > Mid Cap"
    min_sip: str | None = None              # e.g. "₹100"
    min_lumpsum: str | None = None          # e.g. "₹100"
    exit_load: str | None = None            # e.g. "1% if redeemed within 1 year"
    stcg_tax: str | None = None             # e.g. "20%"
    ltcg_tax: str | None = None             # e.g. "12.5% on gains above ₹1.25 lakh"
    stamp_duty: str | None = None           # e.g. "0.005%"
    benchmark: str | None = None            # e.g. "NIFTY Midcap 150 TRI"
    fund_managers: list[str] = field(default_factory=list)   # e.g. ["Chirag Setalvad (since Jan 2013)"]
    num_holdings: str | None = None         # e.g. "78"
    top_holdings: list[str] = field(default_factory=list)    # e.g. ["Max Financial Services 4.50%"]
    lock_in_period: str | None = None       # Populated for ELSS only — e.g. "3 years"
    elss_tax_benefit: str | None = None     # Populated for ELSS only


@dataclass
class ScrapedFund:
    """Complete output for one scraped fund page."""

    scheme_name: str
    category: str
    source_url: str
    scraped_at: str                    # ISO 8601 with IST offset, e.g. "2026-04-18T09:15:00+05:30"
    fields: FundFields
    scrape_method: str = "requests"    # "requests" or "playwright"
    error: str | None = None           # Non-None if scrape failed or was partial


@dataclass
class ScrapeRun:
    """Aggregated result for one full pipeline run across all funds."""

    run_at: str                                        # ISO 8601 timestamp
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    results: list[ScrapedFund] = field(default_factory=list)

    def add(self, result: ScrapedFund) -> None:
        self.results.append(result)
        self.total += 1
        if result.error:
            self.failed += 1
        else:
            self.succeeded += 1

    @property
    def successful_results(self) -> list[ScrapedFund]:
        return [r for r in self.results if r.error is None]
