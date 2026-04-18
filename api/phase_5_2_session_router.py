"""
Phase 5.2 — Session Router

What this phase does:
  Exposes CRUD endpoints for conversation sessions (threads).
  Delegates all state management to Phase 4.1 Thread Manager.

Endpoints:
  POST   /sessions              — create a new session
  GET    /sessions              — list all sessions (summary, no history)
  GET    /sessions/{session_id} — get one session with full history
  PATCH  /sessions/{session_id} — rename a session
  DELETE /sessions/{session_id} — delete a session

Error handling:
  KeyError (session not found) is caught by Phase 5.4 global handler → 404.
  Pydantic validation failures → 422 (automatic FastAPI behaviour).
"""

from __future__ import annotations
import logging

from fastapi import APIRouter, status

from session import (
    create_thread, get_thread, list_threads,
    delete_thread, rename_thread,
)
from .phase_5_1_schemas import (
    CreateSessionRequest, RenameSessionRequest,
    SessionResponse, SessionDetailResponse, HistoryMessage,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["Sessions"])


# ---------------------------------------------------------------------------
# POST /sessions — create
# ---------------------------------------------------------------------------

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SessionResponse,
    summary="Create a new conversation session",
    description=(
        "Creates a new named conversation thread and returns its session_id. "
        "Pass `session_id` in subsequent `/messages` requests to continue the conversation."
    ),
)
def create_session(body: CreateSessionRequest) -> SessionResponse:
    thread = create_thread(title=body.title)
    logger.info("API: session created %s", thread.session_id[:8])
    return SessionResponse(
        session_id=thread.session_id,
        title=thread.title,
        created_at=thread.created_at,
        message_count=0,
    )


# ---------------------------------------------------------------------------
# GET /sessions — list
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=list[SessionResponse],
    summary="List all conversation sessions",
    description="Returns a summary of every session, sorted newest-first. Does not include message history.",
)
def list_sessions() -> list[SessionResponse]:
    return [
        SessionResponse(
            session_id=s.session_id,
            title=s.title,
            created_at=s.created_at,
            message_count=s.message_count,
        )
        for s in list_threads()
    ]


# ---------------------------------------------------------------------------
# GET /sessions/{session_id} — get detail
# ---------------------------------------------------------------------------

@router.get(
    "/{session_id}",
    response_model=SessionDetailResponse,
    summary="Get a session with its full message history",
    responses={404: {"description": "Session not found"}},
)
def get_session(session_id: str) -> SessionDetailResponse:
    thread = get_thread(session_id)   # KeyError → 404 via Phase 5.4 handler
    return SessionDetailResponse(
        session_id=thread.session_id,
        title=thread.title,
        created_at=thread.created_at,
        history=[
            HistoryMessage(role=m.role, text=m.text, timestamp=m.timestamp)
            for m in thread.history
        ],
    )


# ---------------------------------------------------------------------------
# PATCH /sessions/{session_id} — rename
# ---------------------------------------------------------------------------

@router.patch(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Rename a session",
    responses={404: {"description": "Session not found"}},
)
def rename_session(session_id: str, body: RenameSessionRequest) -> SessionResponse:
    rename_thread(session_id, body.title)   # KeyError → 404 via Phase 5.4 handler
    thread = get_thread(session_id)
    logger.info("API: session %s renamed → '%s'", session_id[:8], body.title)
    return SessionResponse(
        session_id=thread.session_id,
        title=thread.title,
        created_at=thread.created_at,
        message_count=len(thread.history),
    )


# ---------------------------------------------------------------------------
# DELETE /sessions/{session_id} — delete
# ---------------------------------------------------------------------------

@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete a session",
    description="Permanently removes the session and its message history.",
)
def delete_session(session_id: str) -> None:
    delete_thread(session_id)   # no-op if not found (idempotent delete)
    logger.info("API: session deleted %s", session_id[:8])
