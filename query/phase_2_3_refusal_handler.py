"""
Phase 2.3 (legacy stub) — superseded by Phase 3.3

This module re-exports from query.safety.phase_3_3_refusal_handler so that
any code that still imports from here continues to work unchanged.

The canonical implementation now lives in:
  query/safety/phase_3_3_refusal_handler.py
"""

from query.safety.phase_3_3_refusal_handler import (   # noqa: F401
    RefusalResponse,
    handle_refusal,
    AMFI_EDUCATION_URL,
)

__all__ = [
    "RefusalResponse",
    "handle_refusal",
    "AMFI_EDUCATION_URL",
]
