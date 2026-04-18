"""
Phase 2.1 — User Interface (Streamlit)

What this file does:
  Multi-thread chat interface for the Mutual Fund FAQ Assistant.
  Uses Phase 4.4 (UI Thread Mapper) for sidebar thread management and
  query/pipeline.py (answer_query) for answering questions.

UI layout:
  ┌──────────────┬────────────────────────────────────────────────────┐
  │   SIDEBAR    │                   MAIN AREA                        │
  │              │                                                    │
  │ [+ New Conv] │  Mutual Fund FAQ Assistant                         │
  │ ──────────── │  Facts-only. No investment advice.                 │
  │ • Thread 1   │  ─────────────────────────────────────────────     │
  │   Thread 2   │  [Example questions — shown when thread is empty]  │
  │   Thread 3   │                                                    │
  │              │  [Chat history bubbles]                            │
  │              │                                                    │
  │              │  [Type your question…]                  [Send]     │
  └──────────────┴────────────────────────────────────────────────────┘

Phase 4.4 state keys in st.session_state:
  mfaq_active_session_id — session_id of the current thread
  mfaq_thread_order      — list of session_ids in sidebar order

How to run:
  pip install streamlit
  streamlit run ui/phase_2_1_ui.py
"""

import sys
import os

# Add project root to sys.path so imports work when run as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from query.pipeline import answer_query, create_session
from query.phase_2_8_response_formatter import FormattedResponse
from session import (
    get_or_create_active_thread,
    new_thread,
    switch_thread,
    delete_thread_from_ui,
    list_sidebar_threads,
    auto_title_from_query,
    get_thread,
    rename_thread,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DISCLAIMER = "Facts-only. No investment advice."

EXAMPLE_QUESTIONS = [
    "What is the expense ratio of HDFC Mid Cap Fund?",
    "What is the minimum SIP amount for HDFC ELSS Tax Saver?",
    "Who manages the HDFC Large Cap Fund?",
]

WELCOME_MESSAGE = (
    "Welcome! I can answer factual questions about these 5 HDFC mutual funds: "
    "**Mid Cap**, **Equity**, **Focused**, **ELSS Tax Saver**, and **Large Cap** "
    "(Direct Growth plans only). I cannot provide investment advice or performance data."
)


# ---------------------------------------------------------------------------
# Sidebar — thread list (Phase 4.4)
# ---------------------------------------------------------------------------

def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### Conversations")

        if st.button("＋ New Conversation", use_container_width=True, type="primary"):
            new_thread(st.session_state)
            st.rerun()

        st.divider()

        threads = list_sidebar_threads(st.session_state)
        active_id = st.session_state.get("mfaq_active_session_id", "")

        if not threads:
            st.caption("No conversations yet.")
            return

        for summary in threads:
            is_active = summary.session_id == active_id
            col_title, col_del = st.columns([5, 1])

            # Thread title button — click to switch
            button_label = f"**{summary.title}**" if is_active else summary.title
            if col_title.button(
                button_label,
                key=f"thread_btn_{summary.session_id}",
                use_container_width=True,
                help=f"{summary.message_count} message(s)",
            ):
                if not is_active:
                    switch_thread(st.session_state, summary.session_id)
                    st.rerun()

            # Delete button
            if col_del.button(
                "✕",
                key=f"del_btn_{summary.session_id}",
                help="Delete this conversation",
            ):
                delete_thread_from_ui(st.session_state, summary.session_id)
                st.rerun()


# ---------------------------------------------------------------------------
# Main area — chat (Phase 2.1 + Phase 4.1)
# ---------------------------------------------------------------------------

def _render_main() -> None:
    st.title("Mutual Fund FAQ Assistant")
    st.caption(f"_{DISCLAIMER}_")
    st.divider()

    # Ensure there is an active thread (Phase 4.4 auto-creates one on first load)
    session_id = get_or_create_active_thread(st.session_state)
    thread = get_thread(session_id)

    # Example questions — only shown when the thread has no messages yet
    if not thread.history:
        st.info(WELCOME_MESSAGE)
        st.markdown("**Try asking:**")
        for q in EXAMPLE_QUESTIONS:
            if st.button(q, key=f"example_{q}"):
                _process_query(q, session_id)
                st.rerun()
        return   # don't show chat input until user picks a starter or types

    # Render conversation history
    for msg in thread.history:
        with st.chat_message(msg.role):
            st.markdown(msg.text)

    # Chat input box
    if user_input := st.chat_input("Ask a factual question about HDFC mutual funds…"):
        _process_query(user_input, session_id)
        st.rerun()


# ---------------------------------------------------------------------------
# Query processing
# ---------------------------------------------------------------------------

def _process_query(user_input: str, session_id: str) -> None:
    """
    Send the query to answer_query() and (if first message) auto-title the thread.

    answer_query() internally handles:
      - Phase 3.1 PII detection + logging to session history
      - Phase 3.2 classification
      - Phase 3.3 refusal (advisory / performance)
      - Phase 2.4–2.8 retrieval + generation + formatting
      - Phase 3.4 post-generation validation
      - Phase 4.2 context window trimming

    After the call, the thread's history already contains both the user
    message and the assistant response — we just re-read it on st.rerun().
    """
    thread = get_thread(session_id)
    is_first_message = (len(thread.history) == 0)

    # Show a spinner while the RAG pipeline runs
    with st.spinner("Looking that up…"):
        answer_query(user_input, session_id)

    # Auto-rename "New conversation" after the first exchange
    if is_first_message:
        rename_thread(session_id, auto_title_from_query(user_input))


# ---------------------------------------------------------------------------
# App entry point
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="Mutual Fund FAQ Assistant",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _render_sidebar()
    _render_main()


if __name__ == "__main__":
    main()
