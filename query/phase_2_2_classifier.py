"""
Phase 2.2 (legacy stub) — superseded by Phase 3.2

This module re-exports from query.safety.phase_3_2_classifier so that any
code that still imports from here continues to work unchanged.

The canonical implementation now lives in:
  query/safety/phase_3_2_classifier.py
"""

from query.safety.phase_3_2_classifier import (   # noqa: F401
    QueryType,
    classify,
    extract_scheme_name,
    ADVISORY_KEYWORDS,
    PERFORMANCE_KEYWORDS,
)

__all__ = [
    "QueryType",
    "classify",
    "extract_scheme_name",
    "ADVISORY_KEYWORDS",
    "PERFORMANCE_KEYWORDS",
]
