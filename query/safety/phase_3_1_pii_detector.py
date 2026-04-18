"""
Phase 3.1 — PII Detector

What this phase does:
  Scans the incoming user query for Personally Identifiable Information (PII)
  before any logging, storage, or further processing happens.

  If PII is found, the detector returns a sanitized copy of the query
  (PII tokens replaced with [REDACTED-TYPE] tags) that is safe to log.
  The original query is still passed through for processing — we do not
  block the user — but the PII-free version is what gets written to logs
  and session history.

Why is this the first phase?
  Logging happens throughout the pipeline. If PII reaches the logger before
  this phase runs, it could be written to disk. Phase 3.1 must run first
  so every downstream log line uses only the sanitized query.

PII types detected (India-specific):
  PAN card    — 10-char alphanumeric: AAAAA9999A  (Income Tax identifier)
  Aadhaar     — 12-digit number beginning 2–9      (National ID)
  Phone       — 10-digit mobile starting 6–9, with optional +91 / 0 prefix
  Email       — standard RFC-5321 address

Design decision — sanitize, not block:
  This is a FAQ assistant, not a financial transaction system. A user who
  accidentally pastes their PAN in a question ("What is the exit load for
  AAAPZ1234Q?") should still get an answer; we just don't log their PAN.
  The architecture doc says "no PII in logs" — not "no PII in queries".

Input:
  user_query : str — raw query text from the UI

Output:
  PIICheckResult — dataclass with:
    has_pii          : bool          — True if any PII was detected
    sanitized_query  : str           — query with PII replaced by [REDACTED-*] tags
    detected_types   : list[str]     — e.g. ["PAN", "phone"]
    original_query   : str           — unchanged original (for processing, not logging)
"""

from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PII regex patterns
# ---------------------------------------------------------------------------

_PAN_PATTERN     = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b')
_AADHAAR_PATTERN = re.compile(r'\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b')
_PHONE_PATTERN   = re.compile(r'\b(?:\+91[\s-]?|0)?[6-9]\d{9}\b')
_EMAIL_PATTERN   = re.compile(r'\b[\w.+\-]+@[\w\-]+\.[a-zA-Z]{2,}\b')


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------

@dataclass
class PIICheckResult:
    """
    Result of running PII detection on a user query.

    Attributes:
      has_pii         — True if at least one PII pattern matched.
      sanitized_query — Safe-to-log version; PII replaced with [REDACTED-TYPE].
      detected_types  — List of PII category names found, e.g. ["PAN", "email"].
      original_query  — Unmodified original query for use in processing.
    """
    has_pii:          bool
    sanitized_query:  str
    detected_types:   list[str]     = field(default_factory=list)
    original_query:   str           = ""


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

def check_pii(user_query: str) -> PIICheckResult:
    """
    Scan user_query for PII and return a PIICheckResult.

    Steps:
      1. Run each PII regex against the query.
      2. For each match, record the type and replace the token with a
         [REDACTED-TYPE] tag in the sanitized copy.
      3. Return PIICheckResult with has_pii=True if any pattern matched.

    The sanitized_query is what callers should pass to the logger and
    session history. The original_query should be used for classification
    and retrieval — PII tokens like a PAN number don't affect the fund
    query logic, but they must not end up in logs.

    Args:
      user_query: Raw text from the user.

    Returns:
      PIICheckResult — always returns a result (never raises).
    """
    detected: list[str] = []
    sanitized = user_query

    if _PAN_PATTERN.search(sanitized):
        sanitized = _PAN_PATTERN.sub("[REDACTED-PAN]", sanitized)
        detected.append("PAN")

    if _AADHAAR_PATTERN.search(sanitized):
        sanitized = _AADHAAR_PATTERN.sub("[REDACTED-AADHAAR]", sanitized)
        detected.append("Aadhaar")

    if _PHONE_PATTERN.search(sanitized):
        sanitized = _PHONE_PATTERN.sub("[REDACTED-PHONE]", sanitized)
        detected.append("phone")

    if _EMAIL_PATTERN.search(sanitized):
        sanitized = _EMAIL_PATTERN.sub("[REDACTED-EMAIL]", sanitized)
        detected.append("email")

    if detected:
        logger.warning(
            "PII detected in query (types: %s) — sanitized for logging",
            ", ".join(detected),
        )

    return PIICheckResult(
        has_pii=bool(detected),
        sanitized_query=sanitized,
        detected_types=detected,
        original_query=user_query,
    )
