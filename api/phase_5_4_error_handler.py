"""
Phase 5.4 — Error Handler

What this phase does:
  Maps Python exceptions raised anywhere in the request path to
  well-structured JSON HTTP error responses using the ErrorResponse
  schema (Phase 5.1).

  Registered on the FastAPI app instance in api/app.py so that routers
  do not need try/except blocks for common error types.

Handled exceptions:
  KeyError   → 404 Not Found     (session_id does not exist in the store)
  ValueError → 422 Unprocessable (malformed input that passed Pydantic)
  Exception  → 500 Internal      (unexpected error — detail logged server-side)

Why explicit handlers instead of HTTPException everywhere?
  Phase 4.1 (Thread Manager) raises plain KeyError — not HTTPException.
  Adding FastAPI-specific imports to session/ would break the separation
  between the session layer and the API layer. The error handler bridges
  them cleanly without coupling.

Input:
  register_handlers(app) — call once during app startup (in api/app.py)

Output:
  JSONResponse with ErrorResponse body and the matching HTTP status code
"""

from __future__ import annotations
import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Individual handlers
# ---------------------------------------------------------------------------

async def _key_error_handler(request: Request, exc: KeyError) -> JSONResponse:
    """
    KeyError → 404 Not Found.
    Raised by Phase 4.1 get_thread() / rename_thread() when the
    session_id is not in the store.
    """
    return JSONResponse(
        status_code=404,
        content={
            "error":       "Not found",
            "detail":      f"Session {exc} does not exist.",
            "status_code": 404,
        },
    )


async def _value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """
    ValueError → 422 Unprocessable Entity.
    Raised for domain-level validation failures that pass Pydantic but
    fail business rules (e.g. empty query after stripping whitespace).
    """
    return JSONResponse(
        status_code=422,
        content={
            "error":       "Invalid input",
            "detail":      str(exc),
            "status_code": 422,
        },
    )


async def _generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all → 500 Internal Server Error.
    Logs the full exception server-side; returns a safe generic message
    to the client (no stack trace exposure).
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error":       "Internal server error",
            "detail":      "An unexpected error occurred. Please try again.",
            "status_code": 500,
        },
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_handlers(app) -> None:
    """
    Attach all exception handlers to the FastAPI app.
    Call this once in api/app.py during app construction.

    Args:
      app : FastAPI application instance.
    """
    app.add_exception_handler(KeyError,    _key_error_handler)
    app.add_exception_handler(ValueError,  _value_error_handler)
    app.add_exception_handler(Exception,   _generic_error_handler)
