# RAG Architecture: Mutual Fund FAQ Assistant

## Overview

This document describes the Retrieval-Augmented Generation (RAG) architecture for the Mutual Fund FAQ Assistant. The system retrieves factual information from a curated corpus of official mutual fund documents and generates concise, source-backed responses — without offering investment advice.

---

## High-Level Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          MUTUAL FUND FAQ ASSISTANT                           │
└──────────────────────────────────────────────────────────────────────────────┘

  ┌────────────────────────┐          ┌──────────────────────────────────────┐
  │   INGESTION PIPELINE   │          │           QUERY PIPELINE             │
  │  (Daily 9:15 AM IST)   │          │           (Online / Real-time)       │
  └────────────────────────┘          └──────────────────────────────────────┘

  ┌──────────────┐                          ┌──────────────────┐
  │ Groww Fund   │                          │  User Interface  │
  │ Pages (HTML) │                          │  (Chat UI)       │
  │              │                          └────────┬─────────┘
  │ 5 HDFC fund  │                                   │ User Query
  │ detail pages │                                   ▼
  │ (no PDFs)    │                    ┌──────────────────────────┐
  │              │                    │ Phase 3.1 PII Detector   │
  └──────┬───────┘                    │ (sanitize before logging)│
         │                            └────────────┬─────────────┘
         ▼                                         ▼
  ┌──────────────┐                    ┌──────────────────────────┐
  │  Document    │                    │ Phase 3.2 Classifier      │
  │  Loader      │                    │ (Factual / Advisory /    │
  │  (HTML)      │                    │  Performance)            │
  └──────┬───────┘                    └──────────┬───────────────┘
         │                                        │
         ▼                       Advisory/        │    Factual
  ┌──────────────┐               Performance      │
  │  Text        │               ┌────────────────┘└──────────────────┐
  │  Chunker     │               ▼                                     ▼
  └──────┬───────┘  ┌──────────────────────────┐        ┌──────────────────────┐
         │          │ Phase 3.3 Refusal Handler │        │ Phase 2.4            │
         ▼          │ (polite decline + link)   │        │ Query Embedder       │
  ┌──────────────┐  └──────────────────────────┘        └────────────┬─────────┘
  │  Chunk       │                                                    │ Query Vector
  │  Embedder    │                                                    ▼
  │  (Embedding  │                                       ┌──────────────────────┐
  │   Model)     │                                       │ Phase 2.5            │
  └──────┬───────┘                                       │ Vector Store         │◄── Indexed Chunks
         │ Chunk Vectors                                  │ (Similarity Search)  │    + Metadata
         ▼                                               └────────────┬─────────┘
  ┌──────────────┐                                                    │ Top-K Chunks
  │  Vector      │                                                    ▼
  │  Store       │                                       ┌──────────────────────┐
  │  (ChromaDB   │                                       │ Phase 2.6            │
  │   Cloud)     │                                       │ Context Builder      │
  └──────────────┘                                       │ + Source Tracker     │
                                                         └────────────┬─────────┘
                                                                      │ Prompt + Context
                                                                      ▼
                                                         ┌──────────────────────┐
                                                         │ Phase 2.7 LLM        │
                                                         │ (Groq / llama-3.3)   │
                                                         └────────────┬─────────┘
                                                                      │ Raw Answer
                                                                      ▼
                                                         ┌──────────────────────┐
                                                         │ Phase 3.4            │
                                                         │ Post-Gen Validator   │
                                                         │ (advice / halluc.)   │
                                                         └────────────┬─────────┘
                                                                      │ Validated Answer
                                                                      ▼
                                                         ┌──────────────────────┐
                                                         │ Phase 2.8 Response   │
                                                         │ Formatter            │
                                                         │ - Max 3 sentences    │
                                                         │ - 1 citation         │
                                                         │ - Last updated       │
                                                         └────────────┬─────────┘
                                                                      │
                                                                      ▼
                                                         ┌──────────────────────┐
                                                         │  User Interface      │
                                                         │  (Final Answer)      │
                                                         └──────────────────────┘
```

---

## Component Breakdown

### 1. Ingestion Pipeline (Scheduled Daily)

Runs every day at **9:15 AM IST** via a scheduler to fetch the latest fund data and refresh the vector store.

#### 1.1 Source Corpus Definition

**AMC:** HDFC Mutual Fund (via Groww fund detail pages)
**Source format:** HTML only — no PDFs in scope.

| Scheme Name                            | Category   | Groww URL                                                                 |
|----------------------------------------|------------|---------------------------------------------------------------------------|
| HDFC Mid Cap Fund – Direct Growth      | Mid Cap    | https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth             |
| HDFC Equity Fund – Direct Growth       | Flexi Cap  | https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth              |
| HDFC Focused Fund – Direct Growth      | Focused    | https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth             |
| HDFC ELSS Tax Saver – Direct Growth    | ELSS       | https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth |
| HDFC Large Cap Fund – Direct Growth    | Large Cap  | https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth           |

**Data fields available per page (confirmed from live page inspection):**

| Field                   | Example (HDFC Mid Cap)                          |
|-------------------------|-------------------------------------------------|
| NAV                     | ₹218.21 (as of 16 Apr '26)                     |
| AUM                     | ₹85,357.92 Cr                                  |
| Expense Ratio           | 0.77%                                           |
| Risk Rating             | Very High Risk                                  |
| Fund Category           | Equity > Mid Cap                                |
| Minimum SIP             | ₹100                                            |
| Minimum Lump Sum        | ₹100                                            |
| Exit Load               | 1% if redeemed within 1 year                    |
| STCG Tax                | 20% (before 1 year)                             |
| LTCG Tax                | 12.5% on gains above ₹1.25 lakh after 1 year   |
| Stamp Duty              | 0.005%                                          |
| Benchmark Index         | NIFTY Midcap 150 Total Return Index             |
| Fund Manager(s)         | Chirag Setalvad, Dhruv Muchhal                  |
| Number of Holdings      | 78 stocks                                       |
| Top Holdings            | Max Financial Services (4.50%), etc.            |
| Historical Returns      | 1Y, 3Y, 5Y, 10Y annualized                     |

> **Note:** Performance returns and return comparisons are **out of scope** per the problem statement. These fields will be excluded from the retrieval corpus. For performance queries, the assistant will redirect users to the source URL.

#### 1.2 Scheduler — GitHub Actions

The ingestion pipeline is triggered automatically on a daily schedule using **GitHub Actions**.

| Property        | Detail                                                                     |
|----------------|----------------------------------------------------------------------------|
| Schedule        | Every day at **9:15 AM IST** → `03:45 UTC` (GitHub Actions uses UTC)      |
| Trigger type    | `schedule` with `cron: '45 3 * * *'`                                      |
| Runner          | `ubuntu-latest` (GitHub-hosted)                                            |
| On failure      | Job marked failed in GitHub Actions UI; previous vector store artifact retained |
| Re-ingestion    | Full re-scrape + full vector store rebuild on each run                     |
| Artifact output | Rebuilt ChromaDB vector store persisted as a GitHub Actions artifact or committed to a dedicated branch |
| Manual trigger  | `workflow_dispatch` also enabled for on-demand re-ingestion               |

**GitHub Actions workflow (`.github/workflows/daily_ingestion.yml`):**
```yaml
name: Daily Mutual Fund Data Ingestion

on:
  schedule:
    - cron: '45 3 * * *'   # 9:15 AM IST (UTC+5:30)
  workflow_dispatch:         # Allow manual trigger

jobs:
  ingest:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run scraping + ingestion pipeline
        env:
          OPENAI_API_KEY:  ${{ secrets.OPENAI_API_KEY }}
          CHROMA_API_KEY:  ${{ secrets.CHROMA_API_KEY }}
          CHROMA_TENANT:   ${{ secrets.CHROMA_TENANT }}
          CHROMA_DATABASE: ${{ secrets.CHROMA_DATABASE }}
        run: python ingestion/run_pipeline.py

      # No vector store artifact — chunks are pushed directly to ChromaDB Cloud.
      # The query service connects to trychroma.com using the same credentials.
```

#### 1.3 Scraping Service (`phase_1_3_scraper.py` + `phase_1_3_parser.py`)

Responsible for fetching and extracting clean, structured text from each of the 5 Groww fund pages.

**Scraping flow per URL:**

```
URL
 │
 ▼
HTTP GET (requests / httpx)
 │
 ├─ Success (static HTML) ──► phase_1_3_parser.py  (targeted HTML regex extraction)
 │
 └─ JS-rendered / blocked  ──► Playwright headless Chromium
                                 └─ page.goto(url) + page.content()
                                      │
                                      ▼
                               phase_1_3_parser.py
                                      │
                                      ▼
                           Structured document dict
                           {scheme_name, url, scraped_at, fields{...}}
```

**Fields extracted per page:**

| Field                  | HTML Target / Selector Strategy                        |
|------------------------|--------------------------------------------------------|
| Scheme Name            | Page `<h1>` / fund title element                       |
| NAV                    | NAV value element (updated daily)                      |
| AUM                    | Fund size / AUM element                                |
| Expense Ratio          | Expense ratio section                                  |
| Risk Rating            | Riskometer label element                               |
| Fund Category          | Category breadcrumb / tag                              |
| Minimum SIP            | Min SIP investment field                               |
| Minimum Lump Sum       | Min one-time investment field                          |
| Exit Load              | Exit load description text                             |
| STCG / LTCG / Stamp Duty | Tax information section                             |
| Benchmark Index        | Benchmark label element                               |
| Fund Manager(s)        | Fund manager name(s) and since-date                   |
| Number of Holdings     | Holdings count                                         |
| Top Holdings           | Top 3–5 stock names and weights                        |

**Excluded fields (not scraped):**
- Historical returns (1Y, 3Y, 5Y, 10Y) — performance data is out of scope
- Return calculator inputs/outputs
- Peer comparison tables

**Scraper output format:**
```python
{
  "scheme_name": "HDFC Mid Cap Fund – Direct Growth",
  "category": "Mid Cap",
  "source_url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
  "scraped_at": "2026-04-17T09:15:00+05:30",
  "fields": {
    "nav": "₹218.21",
    "aum": "₹85,357.92 Cr",
    "expense_ratio": "0.77%",
    "risk_rating": "Very High Risk",
    "min_sip": "₹100",
    "min_lumpsum": "₹100",
    "exit_load": "1% if redeemed within 1 year",
    "stcg_tax": "20% (before 1 year)",
    "ltcg_tax": "12.5% on gains above ₹1.25 lakh after 1 year",
    "stamp_duty": "0.005%",
    "benchmark": "NIFTY Midcap 150 Total Return Index",
    "fund_managers": ["Chirag Setalvad (since Jan 2013)", "Dhruv Muchhal (since Jun 2023)"],
    "num_holdings": "78",
    "top_holdings": ["Max Financial Services 4.50%", "..."]
  }
}
```

After scraping all 5 URLs, each result passes through the Normalizer before reaching the Text Chunker.

#### 1.3.1 Normalizer (`phase_1_3_1_normalizer.py`)

Cleans and standardizes the raw scraped strings into a consistent format before they are converted into text passages and embedded. Without this step, the same field could look different on different days (e.g. `"Rs. 100"` vs `"₹100"` vs `"₹ 100"`), causing the chatbot to give inconsistent answers.

**What it fixes, field by field:**

| Field | Problem example | Normalized output |
|---|---|---|
| NAV | `"₹ 218.21"`, `"218.21"` | `"₹218.21"` |
| Fund Size (AUM) | `"₹85357.92 Cr"`, `"85,357 Crores"` | `"₹85,357.92 Cr"` |
| Expense Ratio | `".77 %"`, `"0.77 %"` | `"0.77%"` |
| Risk Rating | `"VERY HIGH RISK"`, `"very high risk"` | `"Very High Risk"` |
| Min SIP / Lump Sum | `"Rs. 100"`, `"₹ 100"`, `"100"` | `"₹100"` |
| Exit Load | `"1 % if redeemed within 1 year"` | `"1% if redeemed within 1 year"` |
| Tax fields | `"20 %"`, `"20.0%"` | `"20%"` |
| Fund Managers | `"  Chirag Setalvad  "` | `"Chirag Setalvad"` |
| Benchmark | `"nifty midcap 150 total return index"` | `"NIFTY Midcap 150 Total Return Index"` |

**Rules applied:**
- Currency: always use `₹` symbol, no spaces between symbol and number, commas in thousands
- Percentages: remove spaces before `%`, strip trailing `.0` (e.g. `20.0%` → `20%`)
- Text fields: strip leading/trailing whitespace and collapse internal multiple spaces
- Risk Rating: Title Case
- Missing / unparseable values: kept as `None` — never replaced with a guess

**Position in pipeline:**
```
phase_1_3_scraper.py  →  phase_1_3_1_normalizer.py  →  phase_1_4_chunker.py
```

#### 1.4 Text Chunker

Splits documents into semantically coherent chunks suitable for embedding and retrieval.

| Parameter       | Value                        | Rationale                                      |
|----------------|------------------------------|------------------------------------------------|
| Chunk size      | 400–600 tokens               | Fits within embedding model limits; stays focused |
| Chunk overlap   | 50–100 tokens                | Preserves context across chunk boundaries      |
| Chunking strategy | Recursive character splitter | Respects paragraph and sentence boundaries    |
| Metadata per chunk | URL, scheme name, section, date | Enables precise source citation           |

#### 1.5 Chunk Embedder

- Converts each text chunk into a dense vector representation
- **Embedding model:** `BAAI/bge-small-en-v1.5` (local, via `sentence-transformers`) — runs entirely on the GitHub Actions runner, no API key required for embeddings
- Outputs **384-dimensional** vectors per chunk
- Given the small corpus (~48 chunks), the full encoding completes in seconds on CPU
- `normalize_embeddings=True` is set so cosine similarity equals dot product

#### 1.6 Vector Store

Persists chunk embeddings alongside metadata for fast similarity search.

| Property        | Detail                                                             |
|----------------|--------------------------------------------------------------------|
| Storage engine  | **ChromaDB Cloud** (hosted at trychroma.com)                      |
| Index type      | HNSW (managed by ChromaDB Cloud)                                   |
| Distance metric | Cosine similarity (`hnsw:space: cosine`)                          |
| Host            | `api.trychroma.com`                                               |
| Collection name | `mutual_fund_faq`                                                 |
| Metadata stored | `source_url`, `scheme_name`, `fund_category`, `passage_topic`, `scraped_at`, `chunk_index` |

The collection is rebuilt from scratch on every daily run (drop-and-recreate). Since the corpus is only ~48 chunks, the rebuild takes milliseconds and guarantees no stale data.

**Why cloud, not local?** The ingestion job runs on a temporary GitHub Actions runner that is deleted after the job ends. ChromaDB Cloud gives both the ingestion pipeline and the query service a single permanent store — no file passing or artifact downloads required.

---

### 2. Query Pipeline (Online)

Handles each user query end-to-end in real time. Safety and refusal logic is handled by the cross-cutting **Phase 3 layer** (see below) which runs both before retrieval and after generation.

#### 2.1 User Interface

- Simple chat interface (Streamlit or React + FastAPI)
- Welcome message on load
- Three pre-populated example questions
- Persistent disclaimer: **"Facts-only. No investment advice."**
- Support for multiple independent conversation threads (session-isolated)

#### 2.4 Query Embedder

- Embeds the user query using the same `BAAI/bge-small-en-v1.5` model used during ingestion
- Prepends the BGE instruction prefix `"Represent this sentence for searching relevant passages: "` to the query string before encoding — this improves retrieval accuracy for BGE models
- Produces a **384-dimensional** query vector for similarity search

#### 2.5 Vector Store Retrieval (Similarity Search)

- Performs approximate nearest neighbor (ANN) search against the vector store
- Retrieves **top-K chunks** (K = 3–5) most semantically similar to the query
- Applies optional metadata filters (e.g., restrict to a specific scheme or doc type) if the query specifies one

#### 2.6 Context Builder & Source Tracker

- Concatenates the top-K retrieved chunks into a single context block
- Deduplicates overlapping chunk content
- Identifies the **single best source URL** to cite — the source from the highest-ranked retrieved chunk
- Extracts the `retrieved_date` from chunk metadata for the "Last updated" footer

#### 2.7 LLM (Generation)

The language model generates the final answer grounded in the retrieved context.

| Property          | Detail                                                      |
|------------------|--------------------------------------------------------------|
| Provider          | Groq (LPU inference API)                                    |
| Model             | `llama-3.3-70b-versatile`                                   |
| Input             | System prompt + retrieved context + user query              |
| Temperature       | 0 (deterministic, factual responses)                        |
| Max output tokens | 200 (enforces brevity)                                      |

**System prompt (key instructions):**
```
You are a facts-only mutual fund FAQ assistant. Answer using only the provided context.
Rules:
- Answer in a maximum of 3 sentences.
- Do not provide investment advice, opinions, or recommendations.
- Do not compare fund performance or calculate returns.
- If the answer is not in the context, say you don't have that information.
- Do not fabricate facts.
- Do not use hedging phrases like "I think", "probably", or "I believe".
```

#### 2.8 Response Formatter

Post-processes the LLM output before returning to the user.

- Enforces 3-sentence maximum (truncates if exceeded)
- Appends exactly one citation link (the best-matched source URL)
- Appends footer: `Last updated from sources: <retrieved_date>`

**Example formatted response:**
> The expense ratio for Mirae Asset Large Cap Fund – Regular Plan is 1.57% per annum as of the latest factsheet.
> This is the Total Expense Ratio (TER) as disclosed under SEBI regulations.
>
> Source: [Mirae Asset Large Cap Fund Factsheet](https://www.miraeassetmf.co.in/...)
> *Last updated from sources: 2026-04-01*

---

### 3. Refusal & Safety Layer (Cross-Cutting — Phase 3)

This layer runs at two points in the pipeline: **before retrieval** (3.1–3.3) and **after generation** (3.4). It is entirely code-level — no extra LLM calls — making it fast and deterministic.

```
User Query
    │
    ▼  Phase 3.1  PII Detector        ← sanitize before any logging
    ▼  Phase 3.2  Classifier          ← block advisory/performance before retrieval
    │
    ├── Advisory / Performance ──► Phase 3.3 Refusal Handler ──► Response (no retrieval)
    │
    └── Factual ──► [Phase 2.4 → 2.7  Retrieval + Generation]
                            │
                            ▼  Phase 3.4  Post-Gen Validator  ← before formatter
                            ▼  Phase 2.8  Response Formatter
```

#### 3.1 PII Detector

Scans the incoming query for Personally Identifiable Information before any logging or downstream processing.

| PII Type | Pattern                                          |
|----------|--------------------------------------------------|
| PAN card | `[A-Z]{5}[0-9]{4}[A-Z]` (10-char India tax ID) |
| Aadhaar  | `[2-9]\d{3}\s?\d{4}\s?\d{4}` (12-digit)        |
| Phone    | `(?:\+91[\s-]?|0)?[6-9]\d{9}` (Indian mobile)  |
| Email    | RFC-5321 `user@domain.tld`                      |

**Design decision — sanitize, not block:** The query is still processed normally; only the logged copy has PII replaced with `[REDACTED-TYPE]` tags. A user who accidentally pastes their PAN in a question should still get an answer.

#### 3.2 Query Classifier

Routes the query to FACTUAL, ADVISORY, or PERFORMANCE before any retrieval occurs.

| Track       | Example                                    | Action                              |
|-------------|--------------------------------------------|-------------------------------------|
| FACTUAL     | "What is the expense ratio of HDFC Mid Cap?" | Continue to retrieval             |
| ADVISORY    | "Should I invest in this fund?"            | Refuse → Phase 3.3                  |
| PERFORMANCE | "What is the 3-year return?"               | Redirect → Phase 3.3                |

**Classification approach:** Keyword matching (Layer 1, zero latency). ADVISORY takes priority over PERFORMANCE. Defaults to FACTUAL for unmatched queries (LLM system prompt is the second safety net).

Also exports `extract_scheme_name()` — identifies which of the 5 HDFC funds the query refers to, used to narrow ChromaDB retrieval to that fund's chunks.

#### 3.3 Refusal Handler

Returns a polite, informative canned response for non-factual queries. No retrieval or LLM call is made.

| Query Type  | Response                                                         | Redirect URL                     |
|-------------|------------------------------------------------------------------|----------------------------------|
| ADVISORY    | Explains facts-only scope; links to SEBI-registered advisor      | AMFI Investor Education page     |
| PERFORMANCE | Explains performance data is out of scope                        | Groww fund page for that fund (or AMFI fallback) |

#### 3.4 Post-Generation Validator

Inspects the raw LLM answer after generation but before the Response Formatter sees it. Catches two failure modes that the system prompt alone cannot guarantee to prevent.

| Check              | Patterns detected (examples)                                      |
|--------------------|-------------------------------------------------------------------|
| Advice leakage     | "I would recommend", "should you invest", "ideal for investors"   |
| Uncertainty markers| "I think", "probably", "might be", "to my knowledge"             |

**On failure:** The LLM output is discarded. A safe fallback message is substituted. All triggered patterns are logged for monitoring.

---

### 4. Multi-Thread Chat Architecture (Phase 4)

Manages independent conversation threads — one per browser tab. Each thread has its own message history, display title, and session ID. All four sub-phases live in the `session/` package.

```
Browser Tab A (st.session_state)        Browser Tab B (st.session_state)
  mfaq_active_session_id = "abc..."       mfaq_active_session_id = "xyz..."
  mfaq_thread_order = ["abc...", ...]     mfaq_thread_order = ["xyz...", ...]
         │                                        │
         └──────────────────┬─────────────────────┘
                            ▼
                Phase 4.4 UI Thread Mapper
                   (maps sidebar → session_id)
                            │
                            ▼
                Phase 4.1 Thread Manager
                   (CRUD on Thread objects)
                            │
                            ▼
                Phase 4.3 Concurrency Handler
                   (ConcurrentSessionStore — shared singleton)
                        store: { "abc...": Thread, "xyz...": Thread }
```

#### 4.1 Thread Manager (`session/phase_4_1_thread_manager.py`)

Owns the Thread data model and all CRUD operations.

| Function | Description |
|---|---|
| `create_thread(title)` | Create a new Thread with a UUID, store it, return it |
| `get_thread(session_id)` | Retrieve a Thread by ID (raises `KeyError` if missing) |
| `list_threads()` | Return `ThreadSummary` list, sorted newest-first |
| `delete_thread(session_id)` | Remove from store, no-op if missing |
| `rename_thread(session_id, title)` | Update display title under per-session lock |
| `add_message(session_id, role, text)` | Append a `Message` under per-session lock |

**Data models:**

| Class | Key fields |
|---|---|
| `Thread` | `session_id`, `title`, `created_at`, `history: list[Message]` |
| `Message` | `role` ("user"/"assistant"), `text`, `timestamp` |
| `ThreadSummary` | `session_id`, `title`, `message_count`, `last_message_at` |

#### 4.2 Context Window Policy (`session/phase_4_2_context_window.py`)

Limits how much history each thread retains in memory.

| Property | Default | Rationale |
|---|---|---|
| `max_turns` | 40 messages | = 20 question-answer pairs |
| `max_chars` | 16 000 chars | ≈ 4 000 tokens of history text |

**Trimming strategy:** Drop from the front (oldest first) in pairs (user + assistant) to keep conversations coherent. Applied by `pipeline.py` after each assistant response.

> **Note:** This assistant is single-turn RAG — the LLM does **not** see prior turns. The context window policy only limits the in-memory store size and UI history display; it does not affect what the LLM receives.

#### 4.3 Concurrency Handler (`session/phase_4_3_concurrency.py`)

Thread-safe backing store for Thread objects.

| Mechanism | Purpose |
|---|---|
| Store-level `RLock` | Protects the `dict` during concurrent create / delete operations |
| Per-session `Lock` | Serialises concurrent requests on the **same** session (prevents interleaved history appends) |
| `session_lock(session_id)` context manager | Used by Phase 4.1 for all read-modify-write operations |

A module-level singleton (`get_store()`) is shared across all phases. For production persistence, swap the in-memory `dict` for a Redis or database adapter without changing the interface.

#### 4.4 UI Thread Mapper (`session/phase_4_4_ui_thread_mapper.py`)

Maps Streamlit `session_state` (per-browser-tab) to server-side Thread objects.

| Function | Description |
|---|---|
| `get_or_create_active_thread(state)` | Return active session_id; auto-create on first load |
| `new_thread(state)` | Create a thread and make it the active one |
| `switch_thread(state, session_id)` | Change active thread (validates existence first) |
| `delete_thread_from_ui(state, session_id)` | Delete + auto-switch to next available thread |
| `list_sidebar_threads(state)` | Return `ThreadSummary` list in sidebar display order |
| `auto_title_from_query(query)` | Generate a ≤60-char title from the first user message |

**UI session isolation:** Streamlit `session_state` is per-browser-tab. Tab A and Tab B each maintain independent `mfaq_active_session_id` and `mfaq_thread_order` values, while the Thread objects themselves live in the shared server-side store (Phase 4.3).

---

### 5. API & Application Layer (Phase 5)

Exposes the query pipeline as a REST API via **FastAPI**. All four sub-phases live in the `api/` package. The API is the integration point between any frontend (React, mobile, Postman) and the backend pipeline.

```
Client (browser / app / curl)
    │
    ▼  HTTP request
┌──────────────────────────────────────────────────────────────┐
│                     FastAPI  (api/app.py)                     │
│                                                              │
│  Phase 5.2 Session Router    /sessions  (CRUD)               │
│  Phase 5.3 Chat Router       /sessions/{id}/messages          │
│  Phase 5.4 Error Handler     KeyError→404, Exception→500      │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
                   query/pipeline.py  (answer_query)
                   session/ package   (Phase 4.1–4.3)
```

#### 5.1 Request / Response Schemas (`api/phase_5_1_schemas.py`)

All Pydantic models that define the API contract.

**Request models:**

| Model | Used by | Key fields |
|---|---|---|
| `CreateSessionRequest` | `POST /sessions` | `title` (default: "New conversation") |
| `RenameSessionRequest` | `PATCH /sessions/{id}` | `title` |
| `SendMessageRequest` | `POST /sessions/{id}/messages` | `query` (1–2 000 chars) |

**Response models:**

| Model | Used by | Key fields |
|---|---|---|
| `SessionResponse` | POST/GET/PATCH /sessions | `session_id`, `title`, `created_at`, `message_count` |
| `SessionDetailResponse` | GET /sessions/{id} | `session_id`, `title`, `created_at`, `history[]` |
| `HistoryMessage` | inside SessionDetailResponse | `role`, `text`, `timestamp` |
| `MessageResponse` | POST /sessions/{id}/messages | `type`, `text`, `source_url`, `last_updated`, `redirect_url` |
| `ErrorResponse` | all 4xx / 5xx | `error`, `detail`, `status_code` |

**`MessageResponse` type discriminator:**

```json
// type = "answer" — factual RAG response
{
  "type": "answer",
  "text": "The expense ratio of HDFC Mid Cap Fund – Direct Growth is 0.77% per annum.\n\nSource: https://groww.in/...\nLast updated from sources: 2026-04-18",
  "source_url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
  "last_updated": "2026-04-18",
  "redirect_url": null
}

// type = "refusal" — advisory or performance query
{
  "type": "refusal",
  "text": "This assistant provides factual information only...",
  "source_url": null,
  "last_updated": null,
  "redirect_url": "https://www.amfiindia.com/investor-corner/investor-education"
}
```

#### 5.2 Session Router (`api/phase_5_2_session_router.py`)

All session management endpoints. Delegates to Phase 4.1 Thread Manager.

| Method | Path | Status | Description |
|---|---|---|---|
| `POST` | `/sessions` | 201 | Create a new session → `SessionResponse` |
| `GET` | `/sessions` | 200 | List all sessions (summary, no history) → `list[SessionResponse]` |
| `GET` | `/sessions/{session_id}` | 200 / 404 | Get session with full history → `SessionDetailResponse` |
| `PATCH` | `/sessions/{session_id}` | 200 / 404 | Rename session → `SessionResponse` |
| `DELETE` | `/sessions/{session_id}` | 204 | Delete session (idempotent — no error if not found) |

#### 5.3 Chat Router (`api/phase_5_3_chat_router.py`)

The single endpoint that drives the chatbot. Routes through the full pipeline.

| Method | Path | Status | Description |
|---|---|---|---|
| `POST` | `/sessions/{session_id}/messages` | 200 / 404 / 422 | Send a query → `MessageResponse` |

**Request:**
```json
POST /sessions/abc123/messages
{ "query": "What is the expense ratio of HDFC Mid Cap Fund?" }
```

**Response flow inside the endpoint:**
```
answer_query(query, session_id)
    │
    ├── returns FormattedResponse → MessageResponse(type="answer", ...)
    └── returns RefusalResponse   → MessageResponse(type="refusal", ...)
```

#### 5.4 Error Handler (`api/phase_5_4_error_handler.py`)

Maps Python exceptions to HTTP error responses globally — routers stay clean.

| Exception | HTTP Status | `error` field |
|---|---|---|
| `KeyError` | 404 Not Found | `"Not found"` |
| `ValueError` | 422 Unprocessable Entity | `"Invalid input"` |
| `Exception` (catch-all) | 500 Internal Server Error | `"Internal server error"` |

All errors return the `ErrorResponse` schema:
```json
{ "error": "Not found", "detail": "Session 'abc123' does not exist.", "status_code": 404 }
```

#### Running the API

```bash
# Install dependencies
pip install -r requirements.txt

# Start the server (from project root)
uvicorn api.app:app --reload --port 8000

# Interactive docs
open http://localhost:8000/docs    # Swagger UI
open http://localhost:8000/redoc   # ReDoc

# Health check
curl http://localhost:8000/health
# → {"status":"ok","version":"1.0.0"}

# Create a session
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "HDFC Mid Cap questions"}'

# Send a query
curl -X POST http://localhost:8000/sessions/{session_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the expense ratio of HDFC Mid Cap Fund?"}'
```

---

## Data Flow Summary

```
Scheduler (GitHub Actions cron — 9:15 AM IST daily)
    │
    ▼  [Ingestion — Triggered]
Phase 1.3   Scraper          (fetch 5 Groww URLs)
Phase 1.3.1 Normalizer       (clean field values)
Phase 1.4   Text Chunker     (text passages + metadata)
Phase 1.5   Chunk Embedder   (384-dim vectors via bge-small-en-v1.5)
Phase 1.6   Vector Store     (ChromaDB Cloud — full rebuild)

                                [Query — Online, per browser tab]

Client (browser / app / curl)
    │ HTTP POST /sessions/{id}/messages  ← Phase 5.3 Chat Router
    │ or
Phase 2.1 UI (Streamlit)
    │ new tab → Phase 4.4 creates Thread + registers in session_state
    │
    │ user message
    ▼
Phase 3.1  PII Detector        (sanitize query before any logging)
Phase 3.2  Classifier          (FACTUAL / ADVISORY / PERFORMANCE)
    │
    ├── Advisory / Performance ──► Phase 3.3 Refusal Handler ──► Response
    │
    └── Factual
            │
            ▼  Phase 2.4  Query Embedder         (384-dim vector)
            ▼  Phase 2.5  Retriever              (top-4 chunks from ChromaDB)
            ▼  Phase 2.6  Context Builder        (context text + source URL + date)
            ▼  Phase 2.7  LLM / Groq             (raw answer)
            ▼  Phase 3.4  Post-Gen Validator     (discard if advice/uncertainty detected)
            ▼  Phase 2.8  Response Formatter     (max 3 sentences + citation)
            ▼  Phase 4.1  add_message            (append to thread history under lock)
            ▼  Phase 4.2  Context Window Policy  (trim if history exceeds limits)
            │
            ▼
        Final Response → Phase 2.1 UI (chat bubble)
```

---

## Technology Stack

| Layer                  | Component                     | Technology Choice                                            |
|------------------------|-------------------------------|--------------------------------------------------------------|
| Scheduling             | Daily trigger (9:15 AM IST)   | GitHub Actions `schedule` cron (`45 3 * * *`)               |
| Document Loading       | HTML scraper                  | `BeautifulSoup4` + `requests` / `httpx`                      |
| Document Loading       | JS-rendered pages             | `playwright` (headless Chromium)                             |
| Text Chunking          | Splitter                      | LangChain `RecursiveCharacterTextSplitter`                   |
| Embeddings             | Embedding model               | `BAAI/bge-small-en-v1.5` (local, sentence-transformers)      |
| Vector Store           | Database                      | ChromaDB Cloud (trychroma.com, v2 API)                       |
| Phase 3.1 — Safety     | PII detection                 | Regex (PAN, Aadhaar, phone, email — India-specific)          |
| Phase 3.2 — Safety     | Query classification          | Keyword rules (FACTUAL / ADVISORY / PERFORMANCE)             |
| Phase 3.3 — Safety     | Refusal handler               | Canned response templates + redirect URLs                    |
| Phase 3.4 — Safety     | Post-generation validation    | Regex (advice leakage + uncertainty markers)                 |
| LLM                    | Generation model              | Groq API — `llama-3.3-70b-versatile`                        |
| Phase 5.1 — API        | Request/Response schemas      | Pydantic v2 models (`CreateSessionRequest`, `MessageResponse`, etc.) |
| Phase 5.2 — API        | Session Router                | `POST/GET/PATCH/DELETE /sessions` (CRUD via Phase 4.1)       |
| Phase 5.3 — API        | Chat Router                   | `POST /sessions/{id}/messages` → `answer_query()` pipeline   |
| Phase 5.4 — API        | Error Handler                 | `KeyError`→404, `ValueError`→422, `Exception`→500            |
| API Server             | ASGI server                   | Uvicorn (`uvicorn api.app:app --reload`)                     |
| User Interface         | Frontend                      | Streamlit (`ui/phase_2_1_ui.py`) or React (production)       |
| Phase 4.1 — Session    | Thread Manager                | UUID session store, CRUD + `add_message` with per-session lock |
| Phase 4.2 — Session    | Context Window Policy         | Trim history: max 40 turns / 16 000 chars (oldest-first)     |
| Phase 4.3 — Session    | Concurrency Handler           | `ConcurrentSessionStore` with `RLock` + per-session `Lock`   |
| Phase 4.4 — Session    | UI Thread Mapper              | Streamlit `session_state` ↔ server-side Thread mapping       |

---

## Multi-Thread (Multi-Session) Support

Each conversation is isolated by a unique session ID:

- A UUID is generated per chat session at initialization
- Conversation history (user turns + assistant turns) is stored per session in memory or a lightweight store (e.g., Redis or in-memory dict)
- The vector store and corpus are shared (read-only) across all sessions
- No cross-session data leakage; PAN, Aadhaar, account numbers, and contact details are never stored

---

## Security & Privacy Constraints

| Constraint              | Implementation                                                   |
|-------------------------|------------------------------------------------------------------|
| No PII collection       | UI has no input fields for PAN, Aadhaar, phone, or email         |
| No PII in logs          | Response and query logging strips any detected PII patterns      |
| Official sources only   | Ingestion pipeline allowlist validates against approved domains  |
| No third-party data     | Corpus loader rejects URLs outside AMC/AMFI/SEBI domains         |
| No performance advice   | LLM system prompt and query classifier both block advisory output |

---

## Limitations

- **Corpus freshness:** The daily 9:15 AM scrape keeps NAV and AUM current. Structural fields (exit load, expense ratio) change less frequently but are also refreshed daily as part of the full re-ingest.
- **Groww page structure changes:** If Groww updates its HTML structure, the scraper selectors will break and require maintenance.
- **JavaScript rendering:** Groww pages may require a headless browser for full content; `requests` + `BeautifulSoup4` alone may miss dynamically loaded sections.
- **Ambiguous queries:** Edge-case phrasing may be misclassified by the rule-based query classifier; a fallback LLM-based classifier adds latency.
- **Single citation:** Only one source link is surfaced per response, even when multiple chunks contribute — this is a deliberate simplicity constraint from the problem statement.
- **No return data:** Performance comparisons and return calculations are out of scope; queries on these topics redirect users to the Groww fund page.
- **5-fund scope only:** Queries about HDFC funds not in the corpus (or funds from other AMCs) will receive an "information not available" response.

---

## Known Risks & Mitigations

| Risk                                      | Mitigation                                                       |
|-------------------------------------------|------------------------------------------------------------------|
| LLM hallucination                         | Temperature=0; strict system prompt; context-only grounding      |
| Stale data in responses                   | "Last updated" footer; periodic re-ingestion schedule            |
| Advisory query slipping through           | Three-layer guard: Phase 3.2 classifier → system prompt → Phase 3.4 post-gen validator |
| LLM advice leakage despite system prompt  | Phase 3.4 regex validator discards answer and substitutes a safe fallback message       |
| Source URL going offline                  | Crawl validation at ingestion; fallback to AMC homepage                                 |
| Sensitive data in user queries            | Phase 3.1 PII detector sanitizes query before any logging                               |
