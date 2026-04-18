"""
query/safety — Phase 3: Refusal & Safety Layer

This package is a cross-cutting safety layer that runs both BEFORE and
AFTER the core retrieval + generation pipeline.

  Phase 3.1 — PII Detector           : sanitize incoming query for logging
  Phase 3.2 — Query Classifier        : route FACTUAL / ADVISORY / PERFORMANCE
  Phase 3.3 — Refusal Handler         : canned responses for non-factual queries
  Phase 3.4 — Post-Generation Validator: catch advice leakage in LLM output

Pipeline position:

  User Query
      │
      ▼  Phase 3.1  PII Detector        ← sanitize before logging
      ▼  Phase 3.2  Classifier          ← gate before any retrieval
      │
      ├── Advisory / Performance ──► Phase 3.3 Refusal Handler ──► Response
      │
      └── Factual ──► [Phase 2.4 → 2.7 Retrieval + Generation]
                              │
                              ▼  Phase 3.4  Post-Gen Validator  ← before formatter
                              ▼  Phase 2.8  Response Formatter
"""

from .phase_3_1_pii_detector       import check_pii,  PIICheckResult
from .phase_3_2_classifier          import classify,   QueryType, extract_scheme_name
from .phase_3_3_refusal_handler     import handle_refusal, RefusalResponse
from .phase_3_4_post_gen_validator  import validate,   ValidationResult

__all__ = [
    "check_pii",        "PIICheckResult",
    "classify",         "QueryType",       "extract_scheme_name",
    "handle_refusal",   "RefusalResponse",
    "validate",         "ValidationResult",
]
