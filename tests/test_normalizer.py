"""
Tests for ingestion/scraper/normalizer.py

Why tests matter:
  The normalizer is the last line of defence before messy scraped strings
  enter the chatbot's knowledge base.  If it's broken, the chatbot gives
  wrong or inconsistent answers.  These tests prove every rule works
  before any real data is processed.

How to run:
  From the project root:
    pip install pytest
    pytest tests/test_normalizer.py -v
"""

import sys
import os

# Add ingestion/ to the path so we can import the scraper package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingestion"))

from scraper.phase_1_3_1_normalizer import (
    _normalize_currency,
    _normalize_percentage,
    _normalize_risk_rating,
    _normalize_benchmark,
    _normalize_text,
    _normalize_list,
    normalize,
)
from scraper.models import FundFields


# ─────────────────────────────────────────────────────────────────────────────
# Currency tests
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalizeCurrency:
    """
    We store NAV, AUM, Min SIP, Min Lump Sum as currency strings.
    All must come out as "₹<number>" with no spaces and proper commas.
    """

    def test_removes_space_after_rupee_symbol(self):
        assert _normalize_currency("₹ 218.21") == "₹218.21"

    def test_converts_rs_dot_to_rupee(self):
        assert _normalize_currency("Rs. 100") == "₹100"

    def test_converts_rs_no_dot_to_rupee(self):
        assert _normalize_currency("Rs 100") == "₹100"

    def test_bare_number_gets_rupee_symbol(self):
        assert _normalize_currency("100") == "₹100"

    def test_normalizes_crores_suffix(self):
        # "Crores" → "Cr"
        result = _normalize_currency("₹85,357.92 Crores")
        assert "Cr" in result
        assert "Crores" not in result

    def test_adds_comma_separator(self):
        # ₹85357.92 → ₹85,357.92
        result = _normalize_currency("₹85357.92 Cr")
        assert "85,357" in result

    def test_already_correct_unchanged(self):
        assert _normalize_currency("₹218.21") == "₹218.21"

    def test_none_returns_none(self):
        assert _normalize_currency(None) is None


# ─────────────────────────────────────────────────────────────────────────────
# Percentage tests
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalizePercentage:
    """
    Expense Ratio, STCG, LTCG, Stamp Duty are all percentages.
    Rule: no space before %, leading zero if missing, no trailing .0
    """

    def test_removes_space_before_percent(self):
        assert _normalize_percentage("0.77 %") == "0.77%"

    def test_adds_leading_zero(self):
        assert _normalize_percentage(".77%") == "0.77%"

    def test_strips_trailing_dot_zero(self):
        assert _normalize_percentage("20.0%") == "20%"

    def test_whole_number_no_decimal(self):
        assert _normalize_percentage("20%") == "20%"

    def test_decimal_preserved(self):
        assert _normalize_percentage("12.5%") == "12.5%"

    def test_none_returns_none(self):
        assert _normalize_percentage(None) is None

    def test_space_and_missing_zero_combined(self):
        assert _normalize_percentage(".77 %") == "0.77%"


# ─────────────────────────────────────────────────────────────────────────────
# Risk Rating tests
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalizeRiskRating:
    """
    The riskometer label should always come out in Title Case
    regardless of what the page renders.
    """

    def test_uppercase_to_title(self):
        assert _normalize_risk_rating("VERY HIGH RISK") == "Very High Risk"

    def test_lowercase_to_title(self):
        assert _normalize_risk_rating("very high risk") == "Very High Risk"

    def test_already_title_case_unchanged(self):
        assert _normalize_risk_rating("Moderately High Risk") == "Moderately High Risk"

    def test_strips_extra_whitespace(self):
        assert _normalize_risk_rating("  High Risk  ") == "High Risk"

    def test_none_returns_none(self):
        assert _normalize_risk_rating(None) is None


# ─────────────────────────────────────────────────────────────────────────────
# Benchmark tests
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalizeBenchmark:
    """
    Benchmark names contain acronyms (NIFTY, TRI, BSE) that must stay
    uppercase, while regular words get Title Case.
    """

    def test_nifty_uppercase(self):
        result = _normalize_benchmark("nifty midcap 150 total return index")
        assert result.startswith("NIFTY")

    def test_tri_uppercase(self):
        result = _normalize_benchmark("Nifty Midcap 150 Total Return Index")
        assert "TRI" not in result  # TRI only applies if the input has "tri"

    def test_already_correct(self):
        result = _normalize_benchmark("NIFTY Midcap 150 Total Return Index")
        assert "NIFTY" in result

    def test_bse_uppercase(self):
        result = _normalize_benchmark("bse sensex index")
        assert "BSE" in result
        assert "SENSEX" in result

    def test_none_returns_none(self):
        assert _normalize_benchmark(None) is None


# ─────────────────────────────────────────────────────────────────────────────
# Text / List tests
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalizeText:
    def test_strips_leading_trailing_whitespace(self):
        assert _normalize_text("  Chirag Setalvad  ") == "Chirag Setalvad"

    def test_collapses_internal_spaces(self):
        assert _normalize_text("Chirag  Setalvad") == "Chirag Setalvad"

    def test_none_returns_none(self):
        assert _normalize_text(None) is None

    def test_empty_string_returns_none(self):
        assert _normalize_text("   ") is None


class TestNormalizeList:
    def test_strips_each_item(self):
        result = _normalize_list(["  Chirag Setalvad  ", "  Dhruv Muchhal  "])
        assert result == ["Chirag Setalvad", "Dhruv Muchhal"]

    def test_removes_empty_items(self):
        result = _normalize_list(["Chirag Setalvad", "  ", ""])
        assert result == ["Chirag Setalvad"]

    def test_empty_list(self):
        assert _normalize_list([]) == []


# ─────────────────────────────────────────────────────────────────────────────
# Full normalize() integration test
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalizeIntegration:
    """
    End-to-end test: pass a FundFields with messy raw values (as the scraper
    might return), assert that normalize() cleans all of them correctly.
    This mirrors what happens in the real pipeline after every scrape.
    """

    def test_full_fund_fields_normalization(self):
        raw = FundFields(
            nav="₹ 218.21",
            nav_date="  17 Apr 2026  ",
            aum="Rs 85357.92 Crores",
            expense_ratio=".77 %",
            risk_rating="VERY HIGH RISK",
            fund_category="  Equity > Mid Cap  ",
            min_sip="Rs. 100",
            min_lumpsum="₹ 100",
            exit_load="1 % if redeemed within 1 year",
            stcg_tax="20.0%",
            ltcg_tax="12.5%",
            stamp_duty="0.005 %",
            benchmark="nifty midcap 150 total return index",
            fund_managers=["  Chirag Setalvad  ", "  Dhruv Muchhal  "],
            num_holdings="  78  ",
            top_holdings=["  Max Financial Services 4.50%  ", ""],
        )

        clean = normalize(raw)

        # Currency
        assert clean.nav == "₹218.21"
        assert clean.aum == "₹85,357.92 Cr"
        assert clean.min_sip == "₹100"
        assert clean.min_lumpsum == "₹100"

        # Percentage
        assert clean.expense_ratio == "0.77%"
        assert clean.stcg_tax == "20%"
        assert clean.stamp_duty == "0.005%"

        # Risk
        assert clean.risk_rating == "Very High Risk"

        # Benchmark
        assert clean.benchmark.startswith("NIFTY")

        # Text
        assert clean.fund_category == "Equity > Mid Cap"
        assert clean.nav_date == "17 Apr 2026"
        assert clean.num_holdings == "78"

        # Lists
        assert clean.fund_managers == ["Chirag Setalvad", "Dhruv Muchhal"]
        assert len(clean.top_holdings) == 1  # empty string was removed

    def test_none_fields_stay_none(self):
        """
        If the scraper couldn't find a field, normalize() must not invent a value.
        None in → None out.
        """
        empty = FundFields()  # all fields default to None / []
        clean = normalize(empty)

        assert clean.nav is None
        assert clean.expense_ratio is None
        assert clean.risk_rating is None
        assert clean.benchmark is None
        assert clean.fund_managers == []
