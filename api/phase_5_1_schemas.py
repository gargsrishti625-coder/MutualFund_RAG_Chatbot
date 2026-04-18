"""
Phase 5.1 — Request / Response Schemas

What this phase does:
  Defines all Pydantic models that form the API contract between the
  client and the server. Every endpoint in Phase 5.2 and 5.3 uses these
  models for request validation and response serialisation.

Why a dedicated schemas file?
  Keeping models in one place lets the routers (5.2, 5.3) stay thin —
  they import types from here rather than defining them inline.
  It also makes the contract easy to read in isolation and export
  to an OpenAPI/JSON Schema client generator.

Request models:
  CreateSessionRequest  — body for POST /sessions
  RenameSessionRequest  — body for PATCH /sessions/{id}
  SendMessageRequest    — body for POST /sessions/{id}/messages

Response models:
  SessionResponse       — lightweight session info (no history)
  SessionDetailResponse — full session including message history
  HistoryMessage        — a single turn inside SessionDetailResponse
  MessageResponse       — answer from POST /sessions/{id}/messages
                          type="answer"  → factual RAG response
                          type="refusal" → advisory / performance redirect
  HealthResponse        — body for GET /health
  ErrorResponse         — body for all 4xx / 5xx responses
"""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    """Body for POST /sessions."""
    title: str = Field(
        default="New conversation",
        min_length=1,
        max_length=100,
        description="Human-readable display name shown in the sidebar.",
    )


class RenameSessionRequest(BaseModel):
    """Body for PATCH /sessions/{session_id}."""
    title: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="New display name for the session.",
    )


class SendMessageRequest(BaseModel):
    """Body for POST /sessions/{session_id}/messages."""
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User's question about an HDFC mutual fund scheme.",
    )


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class SessionResponse(BaseModel):
    """
    Lightweight session info — used in list and create responses.
    Does not include the full message history.
    """
    session_id:    str
    title:         str
    created_at:    str = Field(description="ISO 8601 creation timestamp (IST).")
    message_count: int = Field(description="Total messages (user + assistant) in the thread.")


class HistoryMessage(BaseModel):
    """A single turn within a session's conversation history."""
    role:      str = Field(description='"user" or "assistant".')
    text:      str = Field(description="Message body (PII-sanitized).")
    timestamp: str = Field(description="ISO 8601 message timestamp (IST).")


class SessionDetailResponse(BaseModel):
    """
    Full session detail — used in GET /sessions/{session_id}.
    Includes the complete message history.
    """
    session_id: str
    title:      str
    created_at: str
    history:    list[HistoryMessage]


class MessageResponse(BaseModel):
    """
    Response from POST /sessions/{session_id}/messages.

    type="answer"  — factual RAG response; source_url and last_updated are set.
    type="refusal" — advisory or performance redirect; redirect_url may be set.

    'text' always contains the full display-ready string (including citation
    footer for answers). Structured fields are also provided so clients can
    render source links and timestamps without parsing the text.
    """
    type:         Literal["answer", "refusal"]
    text:         str = Field(description="Full display-ready response text.")
    source_url:   str | None = Field(
        default=None,
        description="Citation URL (highest-ranked retrieved chunk). Set for type=answer.",
    )
    last_updated: str | None = Field(
        default=None,
        description="Date the source data was last scraped (YYYY-MM-DD). Set for type=answer.",
    )
    redirect_url: str | None = Field(
        default=None,
        description="URL to send the user to instead. Set for type=refusal.",
    )


class HealthResponse(BaseModel):
    """Body for GET /health."""
    status:  str = "ok"
    version: str


class ErrorResponse(BaseModel):
    """
    Unified error body returned for all 4xx and 5xx responses.

    FastAPI also produces its own validation error shape (422); this model
    is used for application-level errors handled in Phase 5.4.
    """
    error:      str = Field(description="Short error category (e.g. 'Not found').")
    detail:     str | None = Field(
        default=None,
        description="More specific description of what went wrong.",
    )
    status_code: int = Field(description="HTTP status code repeated in the body for client convenience.")
