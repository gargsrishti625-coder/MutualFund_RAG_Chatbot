"""
Phase 4.2 — Context Window Policy

What this phase does:
  Defines how much conversation history each thread retains.
  When a thread's history exceeds the configured limits, the oldest
  messages are dropped from the front to keep the store bounded.

Why this matters:
  This assistant is single-turn RAG — the LLM does NOT see prior turns.
  However, the UI displays the full conversation, and the in-memory store
  grows indefinitely for long-running sessions without a cap.

  This phase enforces two soft limits. Whichever triggers first causes
  a trim:
    max_turns — maximum total messages (user + assistant combined)
    max_chars — maximum total character count of all message texts

Trimming strategy:
  Drop messages from the FRONT (oldest first) so the most recent context
  is always preserved. Always drop in pairs (user + assistant) to keep
  the conversation coherent — no orphaned assistant messages at the start.

  The current message is never dropped (minimum retained: 1 message).

Position in pipeline:
  Called by query/pipeline.py after adding each assistant response, so
  trimming happens at most once per query (not on every read).

Input:
  history : list[Message] — current thread history
  policy  : ContextPolicy — limits to apply (defaults to DEFAULT_POLICY)

Output:
  list[Message] — trimmed copy (original list is not mutated)
"""

from __future__ import annotations
import logging
from dataclasses import dataclass

from .phase_4_1_thread_manager import Message

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Policy model
# ---------------------------------------------------------------------------

@dataclass
class ContextPolicy:
    """
    Retention policy for a thread's message history.

    Attributes:
      max_turns : Maximum total messages (user + assistant combined).
                  0 = unlimited.
      max_chars : Maximum total characters across all message texts.
                  0 = unlimited.
    """
    max_turns: int = 40       # 20 question-answer pairs
    max_chars: int = 16_000   # ~4 000 tokens of history text


# Shared default — used by pipeline.py unless overridden
DEFAULT_POLICY = ContextPolicy()


# ---------------------------------------------------------------------------
# Trim function
# ---------------------------------------------------------------------------

def apply_policy(
    history: list[Message],
    policy:  ContextPolicy = DEFAULT_POLICY,
) -> list[Message]:
    """
    Return a trimmed copy of history that satisfies the policy limits.

    Algorithm:
      1. While either limit is exceeded, drop the oldest pair of messages
         (index 0 = user turn, index 1 = assistant turn).
      2. If only one message remains, drop it individually rather than
         leaving an empty list when the single message is over-budget.
      3. Return the trimmed copy; the input list is never mutated.

    Args:
      history : Current list of Message objects for a thread.
      policy  : Limits to enforce.

    Returns:
      New list satisfying both limits (may be shorter than input).
    """
    result = list(history)
    original_len = len(result)

    while result:
        turns_ok = (policy.max_turns == 0) or (len(result) <= policy.max_turns)
        total_chars = sum(len(m.text) for m in result)
        chars_ok  = (policy.max_chars == 0) or (total_chars <= policy.max_chars)

        if turns_ok and chars_ok:
            break

        # Drop oldest pair to keep conversation coherent.
        # If only one message is left, drop it individually.
        drop = 2 if len(result) >= 2 else 1
        result = result[drop:]

    if len(result) < original_len:
        logger.debug(
            "Context policy trimmed %d message(s) (was %d, now %d)",
            original_len - len(result), original_len, len(result),
        )

    return result
