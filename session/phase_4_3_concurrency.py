"""
Phase 4.3 — Concurrency Handler

What this phase does:
  Provides a thread-safe in-memory backing store for conversation threads.
  Used by Phase 4.1 (Thread Manager) as its singleton store.

Two levels of locking:
  Store-level RLock — protects the dict itself during reads, writes,
                      and deletions (prevents dict corruption under
                      concurrent create/delete operations).
  Per-session Lock  — serialises concurrent requests on the same session
                      so two simultaneous queries cannot interleave their
                      history appends.

Why this matters:
  FastAPI and test runners can call answer_query() from multiple threads
  simultaneously. Without per-session locks, two requests on the same
  session could race when both append a message to session.history.

Module-level singleton:
  get_store() returns the single shared instance. All phases import and
  use this singleton — there is only one store per process.

Input:
  Thread objects (from Phase 4.1)

Output:
  ConcurrentSessionStore — dict-like store with session-level locking
"""

from __future__ import annotations
import threading
import logging
from contextlib import contextmanager
from typing import Iterator, TYPE_CHECKING

if TYPE_CHECKING:
    from .phase_4_1_thread_manager import Thread

logger = logging.getLogger(__name__)


class ConcurrentSessionStore:
    """
    Thread-safe store for Thread objects.

    Usage:
        store = get_store()

        # Basic CRUD
        store.put(thread)
        thread = store.get(session_id)   # raises KeyError if missing
        store.delete(session_id)
        all_threads = store.list_all()

        # Serialise multiple operations on the same session
        with store.session_lock(session_id):
            thread = store.get(session_id)
            thread.history.append(message)
            store.put(thread)
    """

    def __init__(self) -> None:
        self._store:              dict[str, "Thread"] = {}
        self._store_lock          = threading.RLock()
        self._session_locks:      dict[str, threading.Lock] = {}
        self._session_locks_lock  = threading.Lock()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def put(self, thread: "Thread") -> None:
        """Store or overwrite a thread."""
        with self._store_lock:
            self._store[thread.session_id] = thread
        self._ensure_session_lock(thread.session_id)

    def get(self, session_id: str) -> "Thread":
        """Return thread by ID. Raises KeyError if not found."""
        with self._store_lock:
            return self._store[session_id]

    def delete(self, session_id: str) -> None:
        """Remove a thread. No-op if session_id is not in the store."""
        with self._store_lock:
            self._store.pop(session_id, None)
        with self._session_locks_lock:
            self._session_locks.pop(session_id, None)

    def list_all(self) -> list["Thread"]:
        """Return a snapshot list of all threads (order not guaranteed)."""
        with self._store_lock:
            return list(self._store.values())

    def __contains__(self, session_id: str) -> bool:
        with self._store_lock:
            return session_id in self._store

    # ------------------------------------------------------------------
    # Per-session locking
    # ------------------------------------------------------------------

    @contextmanager
    def session_lock(self, session_id: str) -> Iterator[None]:
        """
        Context manager that holds the per-session lock for the duration.
        Use this when performing a read-modify-write on a single thread.
        """
        self._ensure_session_lock(session_id)
        with self._session_locks[session_id]:
            yield

    def _ensure_session_lock(self, session_id: str) -> None:
        """Create a per-session Lock if one does not already exist."""
        if session_id not in self._session_locks:
            with self._session_locks_lock:
                if session_id not in self._session_locks:
                    self._session_locks[session_id] = threading.Lock()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_store = ConcurrentSessionStore()


def get_store() -> ConcurrentSessionStore:
    """Return the shared module-level singleton store."""
    return _store
