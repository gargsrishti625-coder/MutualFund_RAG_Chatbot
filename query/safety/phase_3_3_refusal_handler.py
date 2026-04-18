"""
Phase 3.3 — Refusal Handler

What this phase does:
  Generates a ready-to-send response for queries that the assistant must
  not answer — advisory queries (investment advice) and performance queries
  (historical returns). Called immediately after the classifier routes
  a query to ADVISORY or PERFORMANCE, before any retrieval occurs.

Why separate from the classifier?
  The classifier decides the route; the refusal handler owns the response
  text. Keeping them separate means response wording can be updated without
  touching routing logic, and vice versa.

Response design principles:
  1. Polite — never accusatory or robotic.
  2. Transparent — explains exactly why the assistant can't answer.
  3. Actionable — gives the user somewhere useful to go instead.

  Advisory  → links to AMFI Investor Education (official, free guidance).
  Performance → links to the specific Groww fund page so the user can
               see live return figures directly (identified from query
               keywords; falls back to AMFI if no fund is matched).

Input:
  query_type : QueryType — must be ADVISORY or PERFORMANCE
  user_query : str       — original query (used to identify fund for
                           performance redirect URL)

Output:
  RefusalResponse — dataclass with message text and optional redirect URL
"""

from __future__ import annotations
import logging
from dataclasses import dataclass

from .phase_3_2_classifier import QueryType, extract_scheme_name

logger = logging.getLogger(__name__)

AMFI_EDUCATION_URL = "https://www.amfiindia.com/investor-corner/investor-education"

# Groww URLs for each fund — used for performance query redirects
_FUND_GROWW_URLS: dict[str, str] = {
    "HDFC Mid Cap Fund – Direct Growth":
        "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
    "HDFC Equity Fund – Direct Growth":
        "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
    "HDFC Focused Fund – Direct Growth":
        "https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth",
    "HDFC ELSS Tax Saver Fund – Direct Growth":
        "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth",
    "HDFC Large Cap Fund – Direct Growth":
        "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
}


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------

@dataclass
class RefusalResponse:
    """
    A ready-to-display refusal message.

    Attributes:
      message      — polite refusal text shown to the user
      redirect_url — optional URL the user should visit instead:
                     AMFI Investor Education for advisory queries,
                     Groww fund page for performance queries
    """
    message:      str
    redirect_url: str | None = None


# ---------------------------------------------------------------------------
# Response templates
# ---------------------------------------------------------------------------

_ADVISORY_MESSAGE = (
    "This assistant provides factual information about HDFC mutual fund schemes "
    "only — it cannot offer investment advice, recommendations, or opinions. "
    "For personalised guidance, please consult a SEBI-registered investment "
    "advisor or visit AMFI Investor Education."
)

_PERFORMANCE_MESSAGE = (
    "Performance data such as historical returns, CAGR, and year-wise figures "
    "are not available through this assistant. Please visit the fund's page on "
    "Groww for live return figures."
)

_UNKNOWN_MESSAGE = (
    "I'm unable to answer this query. Please ask a factual question about "
    "HDFC mutual fund schemes — such as expense ratio, NAV, exit load, "
    "minimum investment, or tax treatment."
)


# ---------------------------------------------------------------------------
# Refusal handler
# ---------------------------------------------------------------------------

def handle_refusal(
    query_type: QueryType,
    user_query: str = "",
) -> RefusalResponse:
    """
    Return the appropriate RefusalResponse for a non-factual query.

    For ADVISORY:
      Returns a polite decline with the AMFI Investor Education link.

    For PERFORMANCE:
      Returns a redirect message. Tries to identify the specific fund
      in the query (via extract_scheme_name) to give the user a direct
      link to that fund's Groww page. Falls back to AMFI if no fund
      is identified.

    Args:
      query_type : ADVISORY or PERFORMANCE (from Phase 3.2 classifier).
      user_query : Original query — used to find the right redirect URL
                   for performance queries.

    Returns:
      RefusalResponse with message and redirect_url.
    """
    if query_type == QueryType.ADVISORY:
        logger.info("Returning advisory refusal")
        return RefusalResponse(
            message=_ADVISORY_MESSAGE,
            redirect_url=AMFI_EDUCATION_URL,
        )

    if query_type == QueryType.PERFORMANCE:
        # Try to find the specific fund the user is asking about
        scheme_name = extract_scheme_name(user_query)
        redirect_url = (
            _FUND_GROWW_URLS.get(scheme_name, AMFI_EDUCATION_URL)
            if scheme_name
            else AMFI_EDUCATION_URL
        )
        logger.info(
            "Returning performance refusal (redirect: %s)", redirect_url
        )
        return RefusalResponse(
            message=_PERFORMANCE_MESSAGE,
            redirect_url=redirect_url,
        )

    # Fallback for any unexpected query type
    logger.warning("handle_refusal called with unexpected type: %s", query_type)
    return RefusalResponse(message=_UNKNOWN_MESSAGE, redirect_url=None)
