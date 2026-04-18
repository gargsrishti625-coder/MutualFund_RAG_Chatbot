"""
Query Pipeline — orchestrator for all query phases

What this file does:
  Wires every query phase into a single callable: answer_query().
  The UI (Phase 2.1) and any API layer call this — they never talk to
  individual phases directly.

Full phase sequence per request:

  User query
      │
      ▼  Phase 3.1  PII Detector         ← sanitize before any logging
      ▼  Phase 3.2  Query Classifier     ← route before any retrieval
      │
      ├── Advisory / Performance ──► Phase 3.3 Refusal Handler ──► RefusalResponse
      │
      └── Factual
              │
              ▼  Phase 2.4  Query Embedder    (text → 384-dim vector)
              ▼  Phase 2.5  Retriever         (vector → top-4 chunks from ChromaDB)
              ▼  Phase 2.6  Context Builder   (chunks → context text + source + date)
              ▼  Phase 2.7  LLM / Groq        (context + question → raw answer)
              ▼  Phase 3.4  Post-Gen Validator (catch advice leakage before formatting)
              ▼  Phase 2.8  Response Formatter (max 3 sentences + citation)
              │
              ▼  FormattedResponse (returned to UI)

Session management:
  Delegated entirely to the session package (Phase 4):
    Phase 4.1 — Thread Manager     : create_thread, get_thread, add_message
    Phase 4.2 — Context Window     : apply_policy (trim history after response)
    Phase 4.3 — Concurrency        : thread-safe store (used internally by 4.1)
  Public aliases create_session / get_session are kept for UI compatibility.
"""

from __future__ import annotations
import logging

from query.safety import (
    check_pii,
    classify, QueryType, extract_scheme_name,
    handle_refusal, RefusalResponse,
    validate,
)
from query.retrieval import (
    embed_query, retrieve, build_context,
    EmptyRetrievalError,
)
from query.phase_2_7_llm import generate
from query.phase_2_8_response_formatter import format_response, FormattedResponse
from session import (
    create_thread, get_thread,
    add_message,
    apply_policy, DEFAULT_POLICY,
    get_store,
)

logger = logging.getLogger(__name__)

# Safe reply when no relevant chunks are found in the vector store
_NO_CONTEXT_MESSAGE = (
    "I don't have information about that in my current knowledge base. "
    "Please ask a factual question about one of the 5 HDFC mutual fund schemes — "
    "such as expense ratio, NAV, exit load, minimum investment, or tax treatment."
)

# ---------------------------------------------------------------------------
# Public session aliases — keep the UI import (create_session, get_session) working
# ---------------------------------------------------------------------------

def create_session(title: str = "New conversation") -> str:
    """Create a new conversation thread. Returns the session_id."""
    return create_thread(title=title).session_id


def get_session(session_id: str):
    """Retrieve an existing thread. Raises KeyError if not found."""
    return get_thread(session_id)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def answer_query(
    user_query: str,
    session_id: str,
) -> FormattedResponse | RefusalResponse:
    """
    Process a single user question end-to-end.

    Returns either:
      FormattedResponse — factual answer with citation and last-updated footer
      RefusalResponse   — polite decline for advisory / performance queries,
                          or when no relevant context is found

    Phase sequence:
      3.1 PII Detector      → sanitize query for safe logging
      3.2 Classifier        → FACTUAL / ADVISORY / PERFORMANCE
      3.3 Refusal Handler   → canned response for non-factual queries (early return)
      2.4 Query Embedder    → 384-dim vector
      2.5 Retriever         → top-4 chunks from ChromaDB
      2.6 Context Builder   → context text + source URL + date
      2.7 LLM               → raw answer
      3.4 Post-Gen Validator → discard answer if advice / uncertainty detected
      2.8 Response Formatter → final text with citation
      4.2 Context Policy    → trim history if thread exceeds configured limits

    Args:
      user_query : Raw text from the UI (may contain PII).
      session_id : UUID identifying the current conversation thread.

    Returns:
      FormattedResponse or RefusalResponse — always returns, never raises.
    """
    # ------------------------------------------------------------------
    # Phase 3.1 — PII Detector
    # Store sanitized text in history; use original for processing.
    # ------------------------------------------------------------------
    pii_result = check_pii(user_query)
    add_message(session_id, role="user", text=pii_result.sanitized_query)

    # ------------------------------------------------------------------
    # Phase 3.2 — Query Classifier
    # ------------------------------------------------------------------
    query_type  = classify(user_query)
    scheme_name = extract_scheme_name(user_query)   # None = search all funds

    # ------------------------------------------------------------------
    # Phase 3.3 — Refusal Handler  (advisory / performance — early exit)
    # ------------------------------------------------------------------
    if query_type in (QueryType.ADVISORY, QueryType.PERFORMANCE):
        response = handle_refusal(query_type, user_query)
        add_message(session_id, role="assistant", text=response.message)
        return response

    # ------------------------------------------------------------------
    # FACTUAL path
    # ------------------------------------------------------------------

    # Phase 2.4 — Query Embedder
    query_embedding = embed_query(user_query)

    # Phase 2.5 + 2.6 — Retriever → Context Builder
    try:
        chunks  = retrieve(query_embedding, scheme_name=scheme_name)
        context = build_context(chunks)
    except EmptyRetrievalError:
        logger.warning("No relevant chunks found: %s", pii_result.sanitized_query)
        fallback = RefusalResponse(message=_NO_CONTEXT_MESSAGE)
        add_message(session_id, role="assistant", text=fallback.message)
        return fallback

    # Phase 2.7 — LLM Generation
    raw_answer = generate(user_query, context)

    # Phase 3.4 — Post-Generation Validator
    validation = validate(raw_answer)
    if not validation.is_valid:
        logger.info(
            "Post-gen validator overrode LLM output (%d issue(s))",
            len(validation.issues),
        )

    # Phase 2.8 — Response Formatter
    formatted = format_response(validation.validated_text, context)
    add_message(session_id, role="assistant", text=formatted.full_text)

    # Phase 4.2 — Context Window Policy (trim history after each response)
    store = get_store()
    with store.session_lock(session_id):
        thread = store.get(session_id)
        trimmed = apply_policy(thread.history, DEFAULT_POLICY)
        if len(trimmed) < len(thread.history):
            thread.history = trimmed
            store.put(thread)

    return formatted
