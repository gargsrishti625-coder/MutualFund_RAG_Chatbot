"""
Phase 5.3 — Chat Router

What this phase does:
  Exposes the single endpoint that drives the chatbot:
    POST /sessions/{session_id}/messages

  Accepts the user's query, delegates to answer_query() (query/pipeline.py),
  and serialises the result into a MessageResponse.

  Two response shapes depending on the query type (set by Phase 3.2):
    type="answer"  — factual RAG response (FormattedResponse from Phase 2.8)
    type="refusal" — advisory or performance redirect (RefusalResponse from Phase 3.3)

Pipeline flow (inside answer_query):
  Phase 3.1 PII Detector → Phase 3.2 Classifier
    ├── Advisory/Performance → Phase 3.3 Refusal → RefusalResponse
    └── Factual → Phase 2.4–2.8 RAG → Phase 3.4 Validate → FormattedResponse
                                              → Phase 4.1 add_message
                                              → Phase 4.2 Context Window trim

Error handling:
  KeyError (session not found)  → 404 via Phase 5.4 global handler
  All other exceptions          → 500 via Phase 5.4 global handler
"""

from __future__ import annotations
import logging

from fastapi import APIRouter, HTTPException, status

from query.pipeline import answer_query
from query.phase_2_8_response_formatter import FormattedResponse
from query.safety import RefusalResponse
from session import get_thread

from .phase_5_1_schemas import SendMessageRequest, MessageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["Chat"])


# ---------------------------------------------------------------------------
# POST /sessions/{session_id}/messages
# ---------------------------------------------------------------------------

@router.post(
    "/{session_id}/messages",
    response_model=MessageResponse,
    summary="Send a message and get a factual answer",
    description=(
        "Submits the user's query to the full RAG pipeline and returns a response. "
        "The response `type` is `'answer'` for factual questions or `'refusal'` for "
        "advisory / performance queries. Message history is automatically updated in the session."
    ),
    responses={
        200: {"description": "Successful answer or refusal response"},
        404: {"description": "Session not found"},
        422: {"description": "Query is empty or exceeds 2 000 characters"},
    },
)
def send_message(session_id: str, body: SendMessageRequest) -> MessageResponse:
    """
    Main chat endpoint.

    Steps:
      1. Validate the session exists (raises KeyError → 404 if not).
      2. Delegate to answer_query() — handles all phases (3.1 → 3.3 or 2.4 → 4.2).
      3. Serialise FormattedResponse or RefusalResponse into MessageResponse.
    """
    # Validate session existence before calling the pipeline.
    # answer_query() would also raise KeyError on the first add_message() call,
    # but checking here gives a clearer error context.
    get_thread(session_id)   # KeyError → 404 via Phase 5.4 handler

    logger.info(
        "API: query on session %s — '%s'",
        session_id[:8],
        body.query[:60],
    )

    result = answer_query(body.query, session_id)

    # --- Factual answer (FormattedResponse from Phase 2.8) ---
    if isinstance(result, FormattedResponse):
        return MessageResponse(
            type="answer",
            text=result.full_text,
            source_url=result.source_url,
            last_updated=result.last_updated,
            redirect_url=None,
        )

    # --- Refusal (RefusalResponse from Phase 3.3) ---
    return MessageResponse(
        type="refusal",
        text=result.message,
        source_url=None,
        last_updated=None,
        redirect_url=result.redirect_url,
    )
