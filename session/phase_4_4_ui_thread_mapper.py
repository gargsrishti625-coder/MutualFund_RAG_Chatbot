"""
Phase 4.4 — UI Thread Mapper

What this phase does:
  Bridges Phase 4.1 Thread Manager and the Streamlit UI layer.
  Manages which thread is active in the current browser tab and maintains
  the sidebar thread order — all through Streamlit's session_state dict.

Streamlit session_state keys (all prefixed "mfaq_"):
  mfaq_active_session_id : str        — session_id of the active thread
  mfaq_thread_order      : list[str]  — session_ids in display order (newest first)

  These keys live in st.session_state which is per-browser-tab, so each
  tab maintains its own active thread and order list independently.

Why separate from Phase 4.1?
  Phase 4.1 owns the backing store (server-side, shared across tabs).
  Phase 4.4 owns the UI state (client-side, one dict per Streamlit tab).
  Keeping them separate means non-Streamlit callers (tests, FastAPI) can
  use Phase 4.1 without importing Streamlit.

Auto-title:
  When the user sends their first message, the thread title is still
  "New conversation". auto_title_from_query() generates a short, readable
  title from the query text. pipeline.py calls rename_thread() after the
  first successful answer.

Input:
  state : dict-like — st.session_state (or any dict in tests)

Output:
  session_id strings and ThreadSummary lists for the UI to render
"""

from __future__ import annotations
import logging

from .phase_4_1_thread_manager import (
    ThreadSummary,
    create_thread, get_thread, delete_thread, list_threads, rename_thread,
)

logger = logging.getLogger(__name__)

# Streamlit session_state keys
_ACTIVE_KEY = "mfaq_active_session_id"
_ORDER_KEY  = "mfaq_thread_order"

_DEFAULT_TITLE = "New conversation"
_MAX_TITLE_LEN = 60   # characters before truncation with "…"


# ---------------------------------------------------------------------------
# Active thread management
# ---------------------------------------------------------------------------

def get_or_create_active_thread(state: dict) -> str:
    """
    Return the session_id of the currently active thread.
    Creates a new thread automatically if none exists (first page load).

    Args:
      state : Streamlit st.session_state or a plain dict in tests.

    Returns:
      session_id string of the active thread.
    """
    if _ACTIVE_KEY not in state:
        _make_new_thread(state)
    return state[_ACTIVE_KEY]


def new_thread(state: dict) -> str:
    """
    Create a new thread and make it active.

    Returns:
      session_id of the new thread.
    """
    return _make_new_thread(state)


def switch_thread(state: dict, session_id: str) -> None:
    """
    Make an existing thread the active one.

    Raises:
      KeyError if session_id does not exist in the backing store.
    """
    get_thread(session_id)   # validates existence
    state[_ACTIVE_KEY] = session_id
    logger.info("Switched active thread → %s", session_id[:8])


def delete_thread_from_ui(state: dict, session_id: str) -> None:
    """
    Delete a thread from both the backing store and the sidebar order list.

    If the deleted thread was active, automatically switches to the next
    available thread, or creates a new one if none remain.

    Args:
      state      : Streamlit st.session_state.
      session_id : Thread to delete.
    """
    delete_thread(session_id)

    order: list[str] = state.get(_ORDER_KEY, [])
    state[_ORDER_KEY] = [s for s in order if s != session_id]

    if state.get(_ACTIVE_KEY) == session_id:
        remaining = state[_ORDER_KEY]
        if remaining:
            state[_ACTIVE_KEY] = remaining[0]
        else:
            _make_new_thread(state)

    logger.info("Thread deleted from UI: %s", session_id[:8])


# ---------------------------------------------------------------------------
# Sidebar listing
# ---------------------------------------------------------------------------

def list_sidebar_threads(state: dict) -> list[ThreadSummary]:
    """
    Return thread summaries in sidebar display order (newest first).

    Combines the display order stored in state with live data from
    Phase 4.1. Filters out any stale session_ids that were deleted
    outside the UI (e.g. in tests or via a direct API call).

    Args:
      state : Streamlit st.session_state.

    Returns:
      List of ThreadSummary objects ready for sidebar rendering.
    """
    all_summaries = {s.session_id: s for s in list_threads()}
    order: list[str] = state.get(_ORDER_KEY, [])

    # Return threads in the recorded display order, skipping stale IDs
    ordered = [all_summaries[sid] for sid in order if sid in all_summaries]

    # Append any threads not captured in order (created outside the UI)
    known = set(order)
    extras = [s for sid, s in all_summaries.items() if sid not in known]
    return ordered + extras


# ---------------------------------------------------------------------------
# Auto-title
# ---------------------------------------------------------------------------

def auto_title_from_query(query: str) -> str:
    """
    Generate a short sidebar title from the user's first message.

    Truncates to _MAX_TITLE_LEN characters and appends "…" if cut.
    Used to rename a "New conversation" thread after the first exchange.

    Args:
      query : Raw user query string.

    Returns:
      Display title, at most _MAX_TITLE_LEN characters.
    """
    title = query.strip()
    if len(title) > _MAX_TITLE_LEN:
        title = title[:_MAX_TITLE_LEN].rstrip() + "…"
    return title


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _make_new_thread(state: dict) -> str:
    """Create a thread, register it in state as the active thread, and return its session_id."""
    thread = create_thread(title=_DEFAULT_TITLE)
    sid = thread.session_id

    state[_ACTIVE_KEY] = sid
    order: list[str] = state.get(_ORDER_KEY, [])
    state[_ORDER_KEY] = [sid] + order   # prepend — newest thread appears at top

    logger.info("New thread created and set as active: %s", sid[:8])
    return sid
