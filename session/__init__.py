"""
session — Phase 4: Multi-Thread Chat Architecture

This package manages conversation sessions end-to-end, from the backing
store up to the UI sidebar mapping.

  Phase 4.1 — Thread Manager      : Thread CRUD (create/get/list/delete/rename)
                                     and message appends (add_message)
  Phase 4.2 — Context Window Policy: History trimming (max turns / max chars)
  Phase 4.3 — Concurrency Handler  : Thread-safe backing store with RLock +
                                     per-session locks
  Phase 4.4 — UI Thread Mapper     : Streamlit sidebar ↔ session_id mapping,
                                     auto-title from first message

Concurrency model:
  Phase 4.3 holds a module-level ConcurrentSessionStore singleton.
  Phase 4.1 writes under per-session locks (safe for multi-threaded FastAPI).
  Phase 4.4 maintains display order and active-thread state in
  Streamlit session_state (per-browser-tab, no server-side sharing needed).

Pipeline position:
  Called by query/pipeline.py (Phases 4.1 + 4.2) and ui/phase_2_1_ui.py (Phase 4.4).
"""

from .phase_4_1_thread_manager import (
    Message, Thread, ThreadSummary,
    create_thread, get_thread, list_threads,
    delete_thread, rename_thread, add_message,
)
from .phase_4_2_context_window import (
    ContextPolicy, DEFAULT_POLICY, apply_policy,
)
from .phase_4_3_concurrency import (
    ConcurrentSessionStore, get_store,
)
from .phase_4_4_ui_thread_mapper import (
    get_or_create_active_thread, new_thread, switch_thread,
    delete_thread_from_ui, list_sidebar_threads, auto_title_from_query,
)

__all__ = [
    # 4.1 — Thread Manager
    "Message", "Thread", "ThreadSummary",
    "create_thread", "get_thread", "list_threads",
    "delete_thread", "rename_thread", "add_message",
    # 4.2 — Context Window Policy
    "ContextPolicy", "DEFAULT_POLICY", "apply_policy",
    # 4.3 — Concurrency Handler
    "ConcurrentSessionStore", "get_store",
    # 4.4 — UI Thread Mapper
    "get_or_create_active_thread", "new_thread", "switch_thread",
    "delete_thread_from_ui", "list_sidebar_threads", "auto_title_from_query",
]
