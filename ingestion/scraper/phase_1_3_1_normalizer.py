"""
Normalizer — cleans raw scraped strings into a consistent format.

Why this exists:
  The same field can appear differently on different days or across fund pages:
    "Rs. 100"  /  "₹ 100"  /  "₹100"   → all mean the same thing
    ".77 %"    /  "0.77%"  /  "0.77 %" → all mean the same thing
  Inconsistent values would cause the chatbot to give different answers
  for the same question on different days.  This module fixes that before
  the data reaches the chunker.

Rules:
  - Currency  : always "₹<number>"  — no space between ₹ and the number
  - Percentage: always "<number>%"  — no space before %, no trailing .0
  - Text      : strip whitespace, collapse internal spaces
  - Risk      : Title Case
  - None      : kept as None — never replaced with a guess
"""

import re
from .models import FundFields


# ---------------------------------------------------------------------------
# Low-level string helpers
# ---------------------------------------------------------------------------

def _strip(value: str | None) -> str | None:
    """Strip leading/trailing whitespace and collapse internal spaces."""
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value.strip())
    return cleaned if cleaned else None


def _normalize_currency(value: str | None) -> str | None:
    """
    Normalize a currency string to "₹<number>" format.

    Handles:
      "₹ 218.21"        → "₹218.21"
      "Rs. 100"         → "₹100"
      "Rs 85,357.92 Cr" → "₹85,357.92 Cr"
      "100"             → "₹100"
      "₹85357.92 Cr"   → "₹85,357.92 Cr"
    """
    if value is None:
        return None

    v = value.strip()

    # Replace Rs. / Rs / INR with ₹
    v = re.sub(r"\b(Rs\.?|INR)\s*", "₹", v, flags=re.IGNORECASE)

    # Remove space between ₹ and the number
    v = re.sub(r"₹\s+", "₹", v)

    # If there's no currency symbol at all but looks like a number, add ₹
    if v and v[0].isdigit():
        v = "₹" + v

    # Normalize "Crores" / "crores" → "Cr"
    v = re.sub(r"\bCrores?\b", "Cr", v, flags=re.IGNORECASE)

    # Add thousands separator if missing (e.g. ₹85357.92 Cr → ₹85,357.92 Cr)
    # Only apply to the numeric part before any suffix
    def _add_commas(match: re.Match) -> str:
        num_str = match.group(1)
        # Only reformat if no commas already
        if "," not in num_str:
            # Split on decimal
            parts = num_str.split(".")
            integer_part = parts[0]
            decimal_part = parts[1] if len(parts) > 1 else None
            # Indian numbering: last 3 digits, then groups of 2
            integer_part = _indian_commas(integer_part)
            return integer_part + ("." + decimal_part if decimal_part else "")
        return num_str

    v = re.sub(r"₹([\d,]+(?:\.\d+)?)", lambda m: "₹" + _add_commas(m), v)

    return v.strip()


def _indian_commas(integer_str: str) -> str:
    """
    Add Indian-style thousands separators.
    e.g. "85357" → "85,357"   "1234567" → "12,34,567"
    """
    s = integer_str.lstrip("0") or "0"
    if len(s) <= 3:
        return s
    # Last 3 digits always grouped
    result = s[-3:]
    s = s[:-3]
    while s:
        result = s[-2:] + "," + result
        s = s[:-2]
    return result


def _normalize_percentage(value: str | None) -> str | None:
    """
    Normalize a percentage string to "<number>%" format.

    Handles:
      "0.77 %"  → "0.77%"
      ".77%"    → "0.77%"
      "20.0%"   → "20%"
      "20 %"    → "20%"
      "12.5%"   → "12.5%"
    """
    if value is None:
        return None

    v = value.strip()

    # Remove space before %
    v = re.sub(r"\s+%", "%", v)

    # Find the numeric part and normalize it
    match = re.search(r"([\d.]+)\s*%", v)
    if match:
        raw_num = match.group(1)
        # Add leading zero if starts with "."
        if raw_num.startswith("."):
            raw_num = "0" + raw_num
        # Remove trailing .0
        num = float(raw_num)
        formatted = str(int(num)) if num == int(num) else f"{num:g}"
        v = re.sub(r"[\d.]+\s*%", f"{formatted}%", v, count=1)

    return v.strip() if v else None


def _normalize_text(value: str | None) -> str | None:
    """Strip and collapse whitespace."""
    return _strip(value)


def _normalize_risk_rating(value: str | None) -> str | None:
    """
    Normalize risk rating to Title Case.

    Handles:
      "VERY HIGH RISK"        → "Very High Risk"
      "very high risk"        → "Very High Risk"
      "Moderately High Risk"  → "Moderately High Risk"  (unchanged)
    """
    if value is None:
        return None
    return _strip(value.title())


def _normalize_benchmark(value: str | None) -> str | None:
    """
    Normalize benchmark index name.
    Keeps known acronyms (NIFTY, TRI, BSE, SENSEX) in uppercase.
    """
    if value is None:
        return None

    ACRONYMS = {"nifty", "tri", "bse", "sensex", "nse", "crisil", "amfi"}

    words = _strip(value).split()
    normalized = []
    for word in words:
        if word.lower() in ACRONYMS:
            normalized.append(word.upper())
        else:
            normalized.append(word.title())
    return " ".join(normalized)


def _normalize_list(values: list[str]) -> list[str]:
    """Strip whitespace from each item in a list, remove empty entries."""
    return [_strip(v) for v in values if _strip(v) is not None]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize(fields: FundFields) -> FundFields:
    """
    Return a new FundFields with all values normalized.
    The original FundFields is not modified.

    Called after scraping, before text chunking:
      ScrapedFund.fields → normalize(fields) → Text Chunker
    """
    return FundFields(
        # Currency fields
        nav=_normalize_currency(fields.nav),
        nav_date=_normalize_text(fields.nav_date),
        aum=_normalize_currency(fields.aum),
        min_sip=_normalize_currency(fields.min_sip),
        min_lumpsum=_normalize_currency(fields.min_lumpsum),

        # Percentage fields
        expense_ratio=_normalize_percentage(fields.expense_ratio),
        stamp_duty=_normalize_percentage(fields.stamp_duty),

        # Risk rating — Title Case
        risk_rating=_normalize_risk_rating(fields.risk_rating),

        # Benchmark — acronyms uppercase, rest Title Case
        benchmark=_normalize_benchmark(fields.benchmark),

        # Tax fields — normalize the percentage part, keep surrounding text intact
        stcg_tax=_normalize_percentage(fields.stcg_tax),
        ltcg_tax=_normalize_percentage(fields.ltcg_tax),

        # Plain text fields — strip whitespace only
        fund_category=_normalize_text(fields.fund_category),
        exit_load=_normalize_text(fields.exit_load),
        num_holdings=_normalize_text(fields.num_holdings),
        lock_in_period=_normalize_text(fields.lock_in_period),
        elss_tax_benefit=_normalize_text(fields.elss_tax_benefit),

        # List fields
        fund_managers=_normalize_list(fields.fund_managers),
        top_holdings=_normalize_list(fields.top_holdings),
    )
