"""
Phase 2.7 — LLM Generation

What this phase does:
  Sends the user's question together with the retrieved context block to
  Groq's LLM API and returns a grounded, factual answer.

  The LLM receives two inputs:
    1. A strict system prompt that defines all behavioural rules.
    2. A user message containing the retrieved context and the question.

  It must answer using ONLY what is in the context — no outside knowledge,
  no invented figures, no investment advice.

Why Groq?
  Groq's LPU (Language Processing Unit) inference is significantly faster
  than GPU-based providers for the same model family, giving sub-second
  latency for a simple FAQ task. The API is OpenAI-compatible, making it
  easy to swap models without changing the calling code.

Why llama-3.3-70b-versatile?
  - 70B parameter models follow multi-rule instructions reliably
    (3-sentence cap, no hallucination, context-only grounding)
  - Still fast on Groq hardware — typically <1 s end-to-end
  - Free tier available for development

Why temperature=0?
  Temperature controls randomness. At 0, the model always picks the
  highest-probability token, producing deterministic and factual
  responses. Any value above 0 risks the model paraphrasing numbers
  incorrectly or softening a "not available" into a guess.

Prompt design:
  System prompt sets the hard rules.
  User message is structured as:
    "Context:\n<retrieved text>\n\nQuestion: <user query>"
  Separating context from question makes it unambiguous what the model
  is grounding its answer on.

Input:
  user_query : str          — the user's original factual question
  context    : QueryContext — context block + source URL + date from Phase 2.6

Output:
  str — raw LLM answer text (≤3 sentences, no citation appended yet).
        Citation and "Last updated" footer are added by Phase 2.8.

Environment variable required:
  GROQ_API_KEY — obtain from console.groq.com → API Keys
"""

from __future__ import annotations
import logging
import os

from groq import Groq

from query.retrieval.phase_2_6_context_builder import QueryContext

logger = logging.getLogger(__name__)

LLM_MODEL   = "llama-3.3-70b-versatile"
TEMPERATURE = 0
MAX_TOKENS  = 200

SYSTEM_PROMPT = """\
You are a facts-only mutual fund FAQ assistant. Your job is to answer \
questions about HDFC mutual fund schemes using ONLY the information \
provided in the context below.

Rules — follow every one of them without exception:
1. Answer in a MAXIMUM of 3 sentences. Stop after the third sentence even \
if more could be said.
2. Use ONLY facts from the provided context. Do not use any outside knowledge.
3. Do not provide investment advice, opinions, or fund recommendations.
4. Do not compare fund performance or make return projections.
5. If the answer is not present in the context, respond with exactly: \
"I don't have that information in my current data."
6. Do not fabricate any numbers, dates, or names.\
"""

# Module-level Groq client — created once, reused for every request
_client: Groq | None = None


def _get_client() -> Groq:
    """
    Lazily create the Groq client on first call.
    Reads GROQ_API_KEY from the environment at call time so the module
    can be imported safely even when the key is not yet set.

    Raises KeyError if GROQ_API_KEY is missing.
    """
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise KeyError(
                "GROQ_API_KEY environment variable is not set. "
                "Obtain your key from console.groq.com and add it to .env."
            )
        _client = Groq(api_key=api_key)
        logger.info("Groq client initialised (model: %s)", LLM_MODEL)
    return _client


def generate(user_query: str, context: QueryContext) -> str:
    """
    Call the Groq LLM with the system prompt, retrieved context, and user
    question. Returns the raw answer text (≤3 sentences).

    The user message is structured as:
        Context:
        <context.context_text>

        Question: <user_query>

    This layout makes the grounding boundary explicit and unambiguous.

    Args:
      user_query : The factual question the user asked.
      context    : QueryContext from Phase 2.6 — contains context_text,
                   source_url, and scraped_at (used here only for context_text;
                   source_url and scraped_at are used by Phase 2.8).

    Returns:
      Raw answer string from the LLM — at most 3 sentences, no citation.

    Raises:
      KeyError   if GROQ_API_KEY is not set.
      groq.APIError (or subclasses) on network or API failures — let these
      propagate to the pipeline so the UI can show an error message.
    """
    client = _get_client()

    user_message = (
        f"Context:\n{context.context_text}\n\n"
        f"Question: {user_query}"
    )

    logger.info("Calling Groq (%s) for query: %.80s", LLM_MODEL, user_query)

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )

    raw_answer = response.choices[0].message.content.strip()

    logger.info(
        "Groq response received (%d chars, %d tokens used)",
        len(raw_answer),
        response.usage.total_tokens if response.usage else 0,
    )
    return raw_answer
