"""
Phase 4.1 — Thread Manager

What this phase does:
  Manages conversation threads: create, retrieve, list, delete, rename,
  and append messages. A thread is a named chat session — the unit of
  conversation that maps to a sidebar entry in the UI.

  This replaces the inline Session / Message / create_session() / get_session()
  that were previously embedded in query/pipeline.py.

Thread vs Session:
  "Thread" is the user-facing concept (a named conversation in the sidebar).
  "Session" is the internal identifier (a UUID).
  Every Thread has exactly one session_id for its lifetime.

Backing store:
  Phase 4.3 ConcurrentSessionStore — thread-safe, singleton, in-memory.
  Replace with a Redis or DB adapter for production persistence.

Input:
  title : str — human-readable display name (e.g. "HDFC Mid Cap questions")

Output:
  Thread        — full conversation object (session_id + title + history)
  ThreadSummary — lightweight view for sidebar listing (no history copy)
  Message       — single user or assistant turn
"""

from __future__ import annotations
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from .phase_4_3_concurrency import get_store

logger = logging.getLogger(__name__)

_IST = timezone(timedelta(hours=5, minutes=30))


def _now_iso() -> str:
    return datetime.now(_IST).isoformat()


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Message:
    """
    A single turn in a conversation.

    Attributes:
      role      — "user" or "assistant"
      text      — message body (sanitized; PII already stripped by Phase 3.1)
      timestamp — ISO 8601 creation time in IST
    """
    role:      str
    text:      str
    timestamp: str = field(default_factory=_now_iso)


@dataclass
class Thread:
    """
    A conversation session.

    Attributes:
      session_id — UUID string, permanent identifier
      title      — display name shown in the UI sidebar
      created_at — ISO 8601 timestamp when the thread was created
      history    — ordered list of Messages (user + assistant turns)
    """
    session_id: str
    title:      str
    created_at: str
    history:    list[Message] = field(default_factory=list)


@dataclass
class ThreadSummary:
    """
    Lightweight view of a Thread for the sidebar.
    Does not include the full history to avoid unnecessary copying.

    Attributes:
      session_id      — UUID for routing / switching
      title           — display name
      created_at      — for sorting (newest first)
      message_count   — total messages (user + assistant)
      last_message_at — timestamp of the most recent message, or None
    """
    session_id:      str
    title:           str
    created_at:      str
    message_count:   int
    last_message_at: str | None


# ---------------------------------------------------------------------------
# Thread CRUD
# ---------------------------------------------------------------------------

def create_thread(title: str = "New conversation") -> Thread:
    """
    Create a new Thread, persist it in the store, and return it.

    Args:
      title: Display name shown in the UI sidebar.

    Returns:
      The newly created Thread (empty history).
    """
    thread = Thread(
        session_id=str(uuid.uuid4()),
        title=title,
        created_at=_now_iso(),
    )
    get_store().put(thread)
    logger.info("Thread created: %s ('%s')", thread.session_id[:8], thread.title)
    return thread


def get_thread(session_id: str) -> Thread:
    """
    Retrieve a thread by its session_id.

    Raises:
      KeyError if session_id does not exist in the store.
    """
    return get_store().get(session_id)


def list_threads() -> list[ThreadSummary]:
    """
    Return a summary of all threads sorted newest-first by created_at.

    Returns:
      List of ThreadSummary — does not include message history.
    """
    threads = get_store().list_all()
    summaries = [
        ThreadSummary(
            session_id=t.session_id,
            title=t.title,
            created_at=t.created_at,
            message_count=len(t.history),
            last_message_at=t.history[-1].timestamp if t.history else None,
        )
        for t in threads
    ]
    return sorted(summaries, key=lambda s: s.created_at, reverse=True)


def delete_thread(session_id: str) -> None:
    """
    Remove a thread from the store. No-op if not found.
    """
    get_store().delete(session_id)
    logger.info("Thread deleted: %s", session_id[:8])


def rename_thread(session_id: str, new_title: str) -> None:
    """
    Update the display title of an existing thread.

    Uses the per-session lock so concurrent renames are safe.

    Raises:
      KeyError if session_id does not exist.
    """
    store = get_store()
    with store.session_lock(session_id):
        thread = store.get(session_id)
        thread.title = new_title
        store.put(thread)
    logger.info("Thread renamed: %s → '%s'", session_id[:8], new_title)


# ---------------------------------------------------------------------------
# Message management
# ---------------------------------------------------------------------------

def add_message(session_id: str, role: str, text: str) -> None:
    """
    Append a Message to the thread's history under the per-session lock.

    The lock ensures that concurrent requests on the same session cannot
    interleave their history appends.

    Args:
      session_id : Target thread.
      role       : "user" or "assistant".
      text       : Message body (PII-sanitized).

    Raises:
      KeyError if session_id does not exist.
    """
    store = get_store()
    with store.session_lock(session_id):
        thread = store.get(session_id)
        thread.history.append(Message(role=role, text=text))
        store.put(thread)
