"""
HTML parser — extracts fund fields from a Groww fund page.

Strategy:
  All extractors operate directly on the raw HTML string using targeted
  regular expressions rather than BeautifulSoup sibling-walking.

  Why regex over BS4 sibling-walking?
    The previous approach used _find_value_near_label() which searched for
    a label text node and walked to its next sibling. On Groww pages the
    label "NAV" also appears inside the site navigation bar, whose next
    sibling is the entire page content — producing thousands of characters
    of garbage instead of "₹220.06".

    Regex on known HTML patterns is faster and unambiguous:
      'Fund size (AUM)</div><div class="bodyXLargeHeavy...">₹85,357.92 Cr</div>'
    There is no ambiguity about which occurrence is the right one.

  BS4 is still used at the top of parse_fund_page() to strip <script>,
  <style>, and <noscript> tags before the regex pass, so embedded
  JavaScript code cannot produce false-positive matches.

Public API (unchanged):
  parse_fund_page(html: str, is_elss: bool = False) -> FundFields
"""

import re
import logging
from bs4 import BeautifulSoup

from .models import FundFields

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HTML pre-processing
# ---------------------------------------------------------------------------

def _strip_noise_tags(html: str) -> str:
    """
    Remove <script>, <style>, <noscript>, <meta>, and <link> tags so that
    regex extractors never accidentally match text inside them.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "meta", "link"]):
        tag.decompose()
    return str(soup)


# ---------------------------------------------------------------------------
# Field extractors  (all take the cleaned html string)
# ---------------------------------------------------------------------------

def _extract_nav(html: str) -> tuple[str | None, str | None]:
    """
    NAV value and date from the fund header card.

    HTML pattern (static, confirmed across all 5 funds):
      NAV: 17 Apr &#x27;26</div>
      <div class="bodyXLargeHeavy contentPrimary valign-wrapper">₹220.06</div>

    The apostrophe in the year is HTML-encoded as &#x27;
    """
    m = re.search(
        r"NAV:\s*([^<]+?)</div>\s*<div[^>]*bodyXLargeHeavy[^>]*>(₹[\d,.]+)</div>",
        html,
    )
    if m:
        nav_date  = m.group(1).replace("&#x27;", "'").strip()
        nav_value = m.group(2).strip()
        return nav_value, nav_date
    return None, None


def _extract_aum(html: str) -> str | None:
    """
    Fund size (AUM) from the header card.
    Pattern: Fund size (AUM)</div><div class="bodyXLargeHeavy...">₹85,357.92 Cr</div>
    """
    m = re.search(
        r"Fund size \(AUM\)</div><div[^>]*bodyXLargeHeavy[^>]*>(₹[\d,.\s]+Cr)</div>",
        html,
    )
    return m.group(1).strip() if m else None


def _extract_expense_ratio(html: str) -> str | None:
    """
    Expense ratio from the header card.
    The label 'Expense ratio' is followed by an SVG info icon; the value
    appears in the next bodyXLargeHeavy div after the icon block.
    Pattern (abbreviated): Expense ratio<div...><svg...></svg></div></div>
                           <div class="bodyXLargeHeavy contentPrimary...">0.77%</div>
    """
    m = re.search(
        r"Expense ratio.{50,1500}?<div[^>]*bodyXLargeHeavy contentPrimary[^>]*>([\d.]+%)</div>",
        html,
        re.DOTALL,
    )
    return m.group(1).strip() if m else None


def _extract_risk_rating(html: str) -> str | None:
    """
    SEBI riskometer label from the fund header pill/badge.
    Pattern: <span class="bodySmallHeavy">Very High Risk</span>
    """
    m = re.search(r'<span class="bodySmallHeavy">([^<]*Risk[^<]*)</span>', html)
    return m.group(1).strip() if m else None


def _extract_min_sip(html: str) -> str | None:
    """
    Minimum SIP amount from the header card.
    Pattern: Min. for SIP</div><div class="bodyXLargeHeavy...">₹100</div>
    """
    m = re.search(
        r"Min\. for SIP</div><div[^>]*bodyXLargeHeavy[^>]*>(₹[\d,.]+)</div>",
        html,
    )
    return m.group(1).strip() if m else None


def _extract_min_lumpsum(html: str) -> str | None:
    """
    Minimum lump sum from the 'Minimum investments' section.
    Pattern: Min. for 1st investment</div><div class="bodyBaseHeavy">₹100</div>
    """
    m = re.search(
        r"Min\. for 1st investment</div><div[^>]*bodyBaseHeavy[^>]*>(₹[\d,.]+)</div>",
        html,
    )
    return m.group(1).strip() if m else None


def _extract_exit_load(html: str) -> str | None:
    """
    Exit load sentence from the exit load section.
    Pattern: Exit load of 1% if redeemed within 1 year.</div>
    """
    m = re.search(r"Exit load of ([^<.]+)\.", html, re.IGNORECASE)
    if m:
        return f"Exit load of {m.group(1).strip()}"
    return None


def _extract_benchmark(html: str) -> str | None:
    """
    Benchmark index name from the fund benchmark row.
    Pattern: Fund benchmark</span><span class="bodyLargeHeavy">NIFTY...</span>
    """
    m = re.search(
        r"Fund benchmark</span><span[^>]*bodyLargeHeavy[^>]*>([^<]+)</span>",
        html,
    )
    return m.group(1).strip() if m else None


def _extract_fund_category(html: str) -> str | None:
    """
    Fund category from the category/breadcrumb pill.
    Pattern: 'Equity Flexi Cap' or 'Mid Cap' appearing near the rating badge.
    We look for the known SEBI category strings adjacent to the risk badge.
    """
    # SEBI equity category patterns present on Groww pages
    category_pattern = re.compile(
        r"(Equity\s+(?:Flexi Cap|Mid Cap|Large Cap|Small Cap|ELSS|"
        r"Focused|Multi Cap|Large and Mid Cap|Dividend Yield|Value|"
        r"Contra|Sectoral[^<]*?|Thematic[^<]*?)|"
        r"Debt\s+[A-Za-z &]+|"
        r"Hybrid\s+[A-Za-z &]+|"
        r"(?:Mid|Large|Small) Cap Fund)",
        re.IGNORECASE,
    )
    m = category_pattern.search(html)
    return m.group(1).strip() if m else None


def _extract_tax(html: str) -> tuple[str | None, str | None, str | None]:
    """
    STCG rate, LTCG rate, and stamp duty from the tax section.

    STCG pattern  : "Returns are taxed at 20%, if you redeem before one year."
    LTCG pattern  : "pay LTCG tax of 12.5% on returns of Rs 1.25 lakh+"
    Stamp duty    : "Stamp duty on investment: <!-- -->0.005%"
    """
    # STCG
    stcg = None
    m = re.search(
        r"taxed at\s+([\d.]+%)[^<]*?(?:before one year|within one year)",
        html, re.IGNORECASE,
    )
    if m:
        stcg = m.group(1)

    # LTCG
    ltcg = None
    m = re.search(r"pay LTCG tax of\s+([\d.]+%)", html)
    if m:
        ltcg = f"{m.group(1)} on gains above ₹1.25 lakh after 1 year"

    # Stamp duty
    stamp = None
    m = re.search(
        r"Stamp duty on investment:(?:\s*<!--\s*-->)?\s*([\d.]+%)",
        html,
    )
    if m:
        stamp = m.group(1)

    return stcg, ltcg, stamp


def _extract_fund_managers(html: str) -> list[str]:
    """
    Fund manager names and tenure from the Fund Management section.

    HTML pattern per manager (two consecutive divs):
      <div class="...fundManagement_personName...">Chirag Setalvad</div>
      <div class="contentSecondary bodyLarge">Jan 2013<span ...> - Present</span>

    Returns list of "Name (since <date>)" strings, max 4 managers.
    """
    pattern = re.compile(
        r'fundManagement_personName[^>]+>([^<]+)</div>'
        r'.*?'
        r'contentSecondary bodyLarge">([^<]+)<span',
        re.DOTALL,
    )
    managers = []
    for m in pattern.finditer(html):
        name  = m.group(1).strip()
        since = m.group(2).strip()
        managers.append(f"{name} (since {since})")
        if len(managers) >= 4:
            break
    return managers


def _extract_holdings(html: str) -> tuple[str | None, list[str]]:
    """
    Number of holdings (from the Holdings heading) and top-5 stock names
    with weights (from the holdings table rows).

    Holdings count pattern : Holdings (<!-- -->78
    Top holding pattern    :
      holdings_link...">Max Financial Services Ltd.</span></a></td>
      ...
      right-align">4.50%</td>
    """
    # Holdings count
    num = None
    m = re.search(r"Holdings\s*\((?:<!-- -->)?(\d+)", html)
    if m:
        num = m.group(1)
    else:
        # Fall back: count rows in the holdings table
        count = len(re.findall(r"holdings_row__", html))
        if count:
            num = str(count)

    # Top holdings
    # After BS4 processing, the right-align td has extra attributes before >
    # e.g. class="bodyBase right-align" colspan="1" rowspan="1" style="...">4.50%
    top: list[str] = []
    for m in re.finditer(
        r'holdings_link[^"]+">([^<]+)</span></a></td>.*?right-align"[^>]*>([\d.]+%)</td>',
        html,
        re.DOTALL,
    ):
        top.append(f"{m.group(1).strip()} {m.group(2)}")
        if len(top) >= 5:
            break

    return num, top


def _extract_elss_fields(raw_html: str) -> tuple[str | None, str | None]:
    """
    Lock-in period and Section 80C benefit for ELSS funds.

    IMPORTANT: receives the RAW (unstripped) HTML, not the BS4-cleaned
    version, because the lock-in data lives inside a
    <script id="__NEXT_DATA__"> tag that BS4 removes.

    Lock-in patterns (inside __NEXT_DATA__ JSON):
      "analysis_desc":"Lock-in period: 3Y"
      "lock_in":{"years":3,...}

    80C benefit is standard for all ELSS funds (₹1.5 lakh limit).
    """
    lock_in = None

    # Primary: "Lock-in period: 3Y" in analysis_desc JSON field
    m = re.search(r'Lock-in period:\s*(\d+)Y', raw_html)
    if m:
        lock_in = f"{m.group(1)} years"
    else:
        # Fallback: "lock_in":{"years":3,...}
        m = re.search(r'"lock_in"\s*:\s*\{"years"\s*:\s*(\d+)', raw_html)
        if m and m.group(1) != "0":
            lock_in = f"{m.group(1)} years"

    # 80C benefit is the same for all ELSS funds — standard SEBI/IT Act text
    tax_benefit = "Investments eligible for tax deduction under Section 80C up to ₹1.5 lakh per year"

    return lock_in, tax_benefit


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_fund_page(html: str, is_elss: bool = False) -> FundFields:
    """
    Parse a Groww fund page HTML string and return a FundFields instance.
    Missing fields are left as None — the caller handles partial data.
    """
    # Strip noise tags before regex pass to avoid false positives in JS/CSS
    cleaned = _strip_noise_tags(html)

    fields = FundFields()

    try:
        fields.nav, fields.nav_date = _extract_nav(cleaned)
    except Exception:
        logger.debug("nav extraction failed", exc_info=True)

    try:
        fields.aum = _extract_aum(cleaned)
    except Exception:
        logger.debug("aum extraction failed", exc_info=True)

    try:
        fields.expense_ratio = _extract_expense_ratio(cleaned)
    except Exception:
        logger.debug("expense_ratio extraction failed", exc_info=True)

    try:
        fields.risk_rating = _extract_risk_rating(cleaned)
    except Exception:
        logger.debug("risk_rating extraction failed", exc_info=True)

    try:
        fields.fund_category = _extract_fund_category(cleaned)
    except Exception:
        logger.debug("fund_category extraction failed", exc_info=True)

    try:
        fields.min_sip = _extract_min_sip(cleaned)
    except Exception:
        logger.debug("min_sip extraction failed", exc_info=True)

    try:
        fields.min_lumpsum = _extract_min_lumpsum(cleaned)
    except Exception:
        logger.debug("min_lumpsum extraction failed", exc_info=True)

    try:
        fields.exit_load = _extract_exit_load(cleaned)
    except Exception:
        logger.debug("exit_load extraction failed", exc_info=True)

    try:
        fields.stcg_tax, fields.ltcg_tax, fields.stamp_duty = _extract_tax(cleaned)
    except Exception:
        logger.debug("tax extraction failed", exc_info=True)

    try:
        fields.benchmark = _extract_benchmark(cleaned)
    except Exception:
        logger.debug("benchmark extraction failed", exc_info=True)

    try:
        fields.fund_managers = _extract_fund_managers(cleaned)
    except Exception:
        logger.debug("fund_managers extraction failed", exc_info=True)

    try:
        fields.num_holdings, fields.top_holdings = _extract_holdings(cleaned)
    except Exception:
        logger.debug("holdings extraction failed", exc_info=True)

    if is_elss:
        try:
            # Pass raw html — lock-in data is in __NEXT_DATA__ script tag (stripped by BS4)
            fields.lock_in_period, fields.elss_tax_benefit = _extract_elss_fields(html)
        except Exception:
            logger.debug("elss extraction failed", exc_info=True)

    return fields
