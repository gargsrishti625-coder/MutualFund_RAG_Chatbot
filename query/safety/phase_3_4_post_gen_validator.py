"""
Phase 3.4 — Post-Generation Validator

What this phase does:
  Inspects the raw LLM answer (from Phase 2.7) before it is formatted and
  returned to the user. Catches two failure modes that the system prompt
  alone cannot guarantee to prevent:

  1. Advice leakage — the LLM gives investment advice despite being told
     not to (e.g. "I would recommend investing in this fund because...").
     Detected by matching known advisory phrase patterns.

  2. Uncertainty markers — the LLM hedges with phrases like "I think" or
     "probably", signalling it may be fabricating rather than grounding its
     answer in the provided context. These phrases should never appear in a
     factual, context-only answer.

Why not rely entirely on the system prompt?
  LLMs occasionally ignore instructions, especially when the retrieved
  context contains language that resembles advice (e.g. a chunk saying
  "ideal for long-term investors"). A code-level safety net is cheap,
  deterministic, and adds a second layer of protection.

What happens on failure?
  The validated_text is replaced with a safe fallback message that is
  factually neutral and tells the user to ask a specific factual question.
  The original LLM output is discarded. The issues list is logged for
  monitoring.

Input:
  raw_answer : str — LLM output from Phase 2.7 generate()

Output:
  ValidationResult — dataclass with:
    is_valid       : bool       — True if no issues found
    validated_text : str        — safe-to-display text (original or fallback)
    issues         : list[str]  — descriptions of what triggered the override
"""

from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

# Phrases that indicate the LLM is giving investment advice
_ADVICE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bshould (?:you )?invest\b",       re.IGNORECASE),
    re.compile(r"\bi (?:would |strongly )?recommend\b", re.IGNORECASE),
    re.compile(r"\bi (?:would |personally )?suggest\b", re.IGNORECASE),
    re.compile(r"\bgood (?:time|option|choice) to invest\b", re.IGNORECASE),
    re.compile(r"\bbetter (?:fund|option|choice)\b", re.IGNORECASE),
    re.compile(r"\bworth investing\b",               re.IGNORECASE),
    re.compile(r"\bideal for (?:you|investors who)\b", re.IGNORECASE),
    re.compile(r"\bsuitable for\b",                  re.IGNORECASE),
    re.compile(r"\bconsider (?:investing|this fund)\b", re.IGNORECASE),
]

# Phrases that indicate the LLM is fabricating or guessing
_UNCERTAINTY_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bi (?:think|believe|feel)\b",  re.IGNORECASE),
    re.compile(r"\bprobably\b",                  re.IGNORECASE),
    re.compile(r"\bmight be\b",                  re.IGNORECASE),
    re.compile(r"\bcould be\b",                  re.IGNORECASE),
    re.compile(r"\blikely\b",                    re.IGNORECASE),
    re.compile(r"\bi('m| am) not sure\b",        re.IGNORECASE),
    re.compile(r"\bto my knowledge\b",           re.IGNORECASE),
    re.compile(r"\bas far as i know\b",          re.IGNORECASE),
]

# Safe fallback returned when the LLM output fails validation
_FALLBACK_MESSAGE = (
    "I can only provide factual information directly from the fund data. "
    "Please ask a specific factual question about the fund — such as its "
    "NAV, expense ratio, exit load, minimum investment, or tax treatment."
)


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """
    Result of post-generation validation.

    Attributes:
      is_valid       — True if the LLM output passed all checks.
      validated_text — The text to pass to the Response Formatter:
                       original LLM output if is_valid, fallback if not.
      issues         — List of human-readable descriptions of failures,
                       e.g. ["advice_leakage: 'I would recommend'"].
                       Empty when is_valid is True.
    """
    is_valid:       bool
    validated_text: str
    issues:         list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def validate(raw_answer: str) -> ValidationResult:
    """
    Check the LLM output for advice leakage and uncertainty markers.

    Steps:
      1. Run each advice pattern against the raw answer.
      2. Run each uncertainty pattern against the raw answer.
      3. If any pattern matches, log the issues and return a ValidationResult
         with is_valid=False and validated_text set to the safe fallback.
      4. If no patterns match, return is_valid=True with the original text.

    Args:
      raw_answer: The string returned by Phase 2.7 generate().

    Returns:
      ValidationResult — always returns a result (never raises).
    """
    issues: list[str] = []

    for pattern in _ADVICE_PATTERNS:
        m = pattern.search(raw_answer)
        if m:
            issues.append(f"advice_leakage: matched '{m.group()}'")

    for pattern in _UNCERTAINTY_PATTERNS:
        m = pattern.search(raw_answer)
        if m:
            issues.append(f"uncertainty_marker: matched '{m.group()}'")

    if issues:
        logger.warning(
            "Post-generation validation FAILED (%d issue(s)): %s",
            len(issues), "; ".join(issues),
        )
        logger.debug("Rejected LLM output: %s", raw_answer[:200])
        return ValidationResult(
            is_valid=False,
            validated_text=_FALLBACK_MESSAGE,
            issues=issues,
        )

    logger.info("Post-generation validation passed")
    return ValidationResult(is_valid=True, validated_text=raw_answer)
