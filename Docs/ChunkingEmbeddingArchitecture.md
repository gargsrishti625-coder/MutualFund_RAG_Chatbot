# Chunking & Embedding Architecture

## Overview

This document details how scraped HTML content from the 5 HDFC Groww fund pages is transformed into a searchable vector store. It covers every step from raw scraped text through to persisted chunk embeddings — including field-level text construction, chunking strategy, embedding model choice, metadata schema, and vector store structure.

This pipeline runs as part of the daily GitHub Actions ingestion job (9:15 AM IST), after the Scraping Service completes.

---

## Pipeline Position

```
Scraping Service
(5 Groww HTML pages → structured dicts)
        │
        ▼
Normalizer (1.3.1)
(clean & standardize all field values)
        │
        ▼
┌───────────────────────────────────────────────────────┐
│           CHUNKING & EMBEDDING PIPELINE               │
│                                                       │
│  1. Text Constructor                                  │
│  2. Text Chunker                                      │
│  3. Chunk Embedder                                    │
│  4. Vector Store Builder                              │
└───────────────────────────────────────────────────────┘
        │
        ▼
ChromaDB Vector Store
(persisted as GitHub Actions artifact)
        │
        ▼
Query Pipeline (runtime retrieval)
```

---

## Stage 1 — Text Constructor

Converts the structured scraper output dict for each fund into a set of labelled plain-text passages. Each passage covers one logical topic (e.g., expense details, tax details) so that chunks stay semantically focused.

### Why construct passages before chunking?

Groww pages are structured (NAV here, exit load there, fund manager elsewhere). If the raw HTML text is chunked directly, a chunk may straddle unrelated fields (e.g., half about expense ratio, half about benchmark). Pre-constructing topic passages ensures each chunk stays on one subject, which improves retrieval precision.

### Passage construction per fund

For each fund, the following passages are constructed from the scraper dict:

#### Passage 1 — Fund Identity
```
Scheme: HDFC Mid Cap Fund – Direct Growth
Category: Equity > Mid Cap
AMC: HDFC Mutual Fund
Source: https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth
Data as of: 2026-04-17
```

#### Passage 2 — NAV & Fund Size
```
NAV (Net Asset Value): ₹218.21 as of 17 Apr 2026
AUM (Assets Under Management): ₹85,357.92 Cr
```

#### Passage 3 — Investment Requirements
```
Minimum SIP amount: ₹100 per month
Minimum lump sum (one-time) investment: ₹100
```

#### Passage 4 — Expense & Exit Details
```
Expense Ratio (Total Expense Ratio / TER): 0.77% per annum
Exit Load: 1% if redeemed within 1 year from the date of allotment.
No exit load applies after 1 year.
```

#### Passage 5 — Risk & Classification
```
Riskometer / Risk Rating: Very High Risk
Fund Category: Mid Cap Equity Fund
Benchmark Index: NIFTY Midcap 150 Total Return Index
```

#### Passage 6 — Fund Manager(s)
```
Fund Manager: Chirag Setalvad (managing since January 2013)
Co-Fund Manager: Dhruv Muchhal (managing since June 2023)
```

#### Passage 7 — Tax Information
```
Short Term Capital Gains (STCG): 20% tax applicable if redeemed before 1 year.
Long Term Capital Gains (LTCG): 12.5% tax on gains exceeding ₹1.25 lakh per financial year, applicable after 1 year.
Stamp Duty: 0.005% of investment amount (effective July 1, 2020).
```

#### Passage 8 — Holdings (optional, included if available)
```
Number of holdings: 78 stocks
Top holding: Max Financial Services — 4.50%
Sector exposure: Financial Services, Healthcare, Automobile and Auto Components
```

> **ELSS-specific passage** (added only for HDFC ELSS Tax Saver):

#### Passage 9 — Lock-in Period (ELSS only)
```
Lock-in Period: 3 years from the date of each SIP instalment / lump sum investment.
This is mandated by SEBI for all ELSS (Equity Linked Savings Scheme) funds.
Tax benefit: Investments up to ₹1.5 lakh per year are eligible for deduction under Section 80C of the Income Tax Act.
```

### Output

For each of the 5 funds, 7–9 passages are produced.
**Total passages across all funds: ~40 passages.**

---

## Stage 2 — Text Chunker

Splits each passage into smaller chunks that fit comfortably within the embedding model's token limit and stay semantically tight.

### Why chunk if passages are already small?

Most passages above are short enough to be a single chunk. The chunker acts as a safety net — it handles any passage that exceeds the token budget (e.g., a holdings passage with many entries) and ensures consistent chunk sizing across the corpus.

### Chunking parameters

| Parameter            | Value                         | Rationale                                                             |
|----------------------|-------------------------------|-----------------------------------------------------------------------|
| Chunk size           | **300 tokens**                | Passages are short; 300 tokens keeps each chunk tightly focused       |
| Chunk overlap        | **50 tokens**                 | Preserves sentence continuity across chunk boundaries                 |
| Splitter             | `RecursiveCharacterTextSplitter` | Splits on `\n\n` → `\n` → `. ` → ` ` in order; respects sentence boundaries |
| Minimum chunk size   | 30 tokens                     | Discards trivially small fragments (e.g., a lone label line)          |

### Chunking library

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=50,
    length_function=tiktoken_len,   # token-accurate length via tiktoken cl100k_base
    separators=["\n\n", "\n", ". ", " ", ""],
)
```

### Metadata attached to every chunk

Each chunk carries a metadata dict that travels with it into the vector store:

| Metadata field   | Example value                                                        | Purpose                                      |
|------------------|----------------------------------------------------------------------|----------------------------------------------|
| `source_url`     | `https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth`     | Citation link surfaced in the response       |
| `scheme_name`    | `HDFC Mid Cap Fund – Direct Growth`                                  | Metadata filter for scheme-specific queries  |
| `fund_category`  | `Mid Cap`                                                            | Metadata filter by category                  |
| `passage_topic`  | `expense_exit` / `tax` / `risk_benchmark` / `fund_manager` / etc.   | Semantic label for the chunk's subject       |
| `scraped_at`     | `2026-04-17T09:15:00+05:30`                                         | Used for "Last updated" footer in responses  |
| `chunk_index`    | `0`, `1`, `2` …                                                      | Position within the parent passage           |

### Expected chunk count

| Fund                       | Passages | Estimated Chunks |
|----------------------------|----------|-----------------|
| HDFC Mid Cap Fund          | 8        | ~10             |
| HDFC Equity Fund           | 7        | ~9              |
| HDFC Focused Fund          | 7        | ~9              |
| HDFC ELSS Tax Saver        | 9        | ~11             |
| HDFC Large Cap Fund        | 7        | ~9              |
| **Total**                  | **38**   | **~48 chunks**  |

> This is a very small corpus. All 48 chunks fit comfortably in a local ChromaDB collection with no performance concerns.

---

## Stage 3 — Chunk Embedder

Converts each text chunk into a dense vector representation for semantic similarity search.

### Embedding model

| Property          | Detail                                                              |
|-------------------|---------------------------------------------------------------------|
| Model             | `BAAI/bge-small-en-v1.5` (local, via `sentence-transformers`)      |
| Dimensions        | **384** (fixed output size — no truncation needed)                  |
| Context window    | 512 tokens — well above the 300-token chunk ceiling                |
| Batching          | All ~48 chunks encoded locally in a single call (no API needed)    |
| API call          | `model.encode(texts)` via `SentenceTransformer`                    |
| Cost              | **$0** — runs locally; no API key or network call required         |

### Why `bge-small-en-v1.5`?

- Runs **locally** — no OpenAI API key needed for embeddings, zero cost per daily run
- Strong semantic understanding for financial terminology (expense ratio, riskometer, LTCG, etc.)
- 384-dimensional vectors are compact and fast to search — more than sufficient for a 48-chunk corpus
- BGE (BAAI General Embedding) models are specifically trained for retrieval tasks, making them well-suited for RAG
- Deterministic: same text always produces the same vector (no temperature / randomness)
- For queries, BGE models benefit from a short instruction prefix: `"Represent this sentence for searching relevant passages: "` — this is applied in Phase 2.4 (Query Embedder) but not during ingestion

### Embedding call structure

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-small-en-v1.5")

def embed_chunks(chunks: list[str]) -> list[list[float]]:
    embeddings = model.encode(chunks, normalize_embeddings=True)
    return embeddings.tolist()
```

### Embedding output

Each chunk produces a **384-dimensional float vector**. For ~48 chunks this yields a matrix of shape `(48, 384)` — approximately **74 KB** of raw float data, trivially small.

---

## Stage 4 — Vector Store Builder

Persists all chunk embeddings alongside their text and metadata into ChromaDB Cloud.

### Vector store choice: ChromaDB Cloud (trychroma.com)

| Property           | Detail                                                             |
|--------------------|-------------------------------------------------------------------|
| Engine             | ChromaDB Cloud (hosted at trychroma.com)                          |
| Index type         | HNSW (Hierarchical Navigable Small World) — managed by Chroma     |
| Distance metric    | **Cosine similarity** (configured at collection creation)         |
| Host               | `api.trychroma.com`                                               |
| Collection name    | `mutual_fund_faq`                                                 |
| Rebuild strategy   | **Drop and recreate** the collection on each daily run (48 chunks — full rebuild is instant) |

### Why ChromaDB Cloud instead of local?

A local `PersistentClient` writes files to disk on the machine running the pipeline (a GitHub Actions runner). Runners are ephemeral — they are deleted after the job ends — so the files would have to be uploaded as an artifact and re-downloaded by the query service every time it starts. This is fragile and slow.

With ChromaDB Cloud, the collection lives in a permanent hosted database. Both the ingestion pipeline (GitHub Actions) and the query service (Streamlit app, wherever it runs) connect to the same collection using credentials — no file passing required.

### Why drop-and-recreate instead of upsert?

With only 48 chunks and a full daily re-scrape, drop-and-recreate is simpler, avoids stale chunk ghosts, and completes in milliseconds. Upsert logic adds complexity with no benefit at this scale.

### ChromaDB Cloud connection and collection setup

```python
import chromadb
import os

# Credentials come from environment variables
# (locally: .env file  |  CI: GitHub Actions secrets)
client = chromadb.HttpClient(
    ssl=True,
    host="api.trychroma.com",
    tenant=os.environ["CHROMA_TENANT"],
    database=os.environ["CHROMA_DATABASE"],
    headers={"x-chroma-token": os.environ["CHROMA_API_KEY"]},
)

# Drop existing collection to ensure clean rebuild
try:
    client.delete_collection("mutual_fund_faq")
except Exception:
    pass

collection = client.create_collection(
    name="mutual_fund_faq",
    metadata={"hnsw:space": "cosine"},
)

# Add all chunks in one batch
collection.add(
    ids=[f"chunk_{i}" for i in range(len(chunks))],
    embeddings=embeddings,          # list of 384-dim vectors
    documents=chunks,               # raw chunk text
    metadatas=metadatas,            # list of metadata dicts
)
```

### Environment variables required

| Variable           | Where to get it                          | Used by                        |
|--------------------|------------------------------------------|--------------------------------|
| `CHROMA_API_KEY`   | trychroma.com dashboard → API Keys       | Ingestion pipeline + query app |
| `CHROMA_TENANT`    | trychroma.com dashboard → Tenant ID      | Ingestion pipeline + query app |
| `CHROMA_DATABASE`  | Database name you create on trychroma.com | Ingestion pipeline + query app |

Set these as **GitHub Actions secrets** for the ingestion job, and as environment variables wherever the query service runs (local `.env`, Streamlit Cloud secrets, Render env vars, etc.).

### What gets stored per entry

```
┌─────────────────────────────────────────────────────────────────┐
│  ChromaDB Entry                                                 │
├────────────────┬────────────────────────────────────────────────┤
│ id             │  "chunk_0", "chunk_1", …                       │
│ document       │  Raw chunk text (plain English passage)        │
│ embedding      │  [0.023, -0.187, 0.041, …]  (384 floats)      │
│ metadata       │  {                                             │
│                │    source_url: "https://groww.in/...",         │
│                │    scheme_name: "HDFC Mid Cap Fund…",          │
│                │    fund_category: "Mid Cap",                   │
│                │    passage_topic: "expense_exit",              │
│                │    scraped_at: "2026-04-17T09:15:00+05:30",    │
│                │    chunk_index: 0                              │
│                │  }                                             │
└────────────────┴────────────────────────────────────────────────┘
```

---

## Query-Time Retrieval (how embeddings are used at runtime)

At query time, the user's question is embedded with the same `BAAI/bge-small-en-v1.5` model (384 dims) and queried against the collection. A BGE instruction prefix is added to the query string for better retrieval accuracy:

```python
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
query_embedding = embed_chunks([BGE_QUERY_PREFIX + user_query])[0]

results = collection.query(
    query_embeddings=[query_embedding],
    n_results=4,                         # Top-4 most similar chunks
    include=["documents", "metadatas", "distances"],
    where={"scheme_name": "HDFC Mid Cap Fund – Direct Growth"},  # optional filter
)
```

### Similarity threshold

Chunks with cosine distance > **0.5** (similarity < 0.5) are dropped before sending context to the LLM. This prevents weakly related chunks from polluting the prompt with irrelevant text.

```python
SIMILARITY_THRESHOLD = 0.5   # cosine distance — lower = more similar

filtered = [
    (doc, meta)
    for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0])
    if dist < SIMILARITY_THRESHOLD
]
```

> **Note:** Because `normalize_embeddings=True` is set during encoding, cosine similarity is equivalent to dot product — ChromaDB's `hnsw:space: cosine` handles this correctly.

---

## End-to-End Data Flow

```
Scraper output (5 dicts)
        │
        ▼
Normalizer (1.3.1)
 ├─ Currency    : "Rs. 100"   → "₹100"
 ├─ Percentage  : ".77 %"     → "0.77%"
 ├─ Risk Rating : "VERY HIGH" → "Very High Risk"
 └─ Benchmark   : acronyms uppercase, rest Title Case
        │
        ▼
Text Constructor
 ├─ Fund Identity passage
 ├─ NAV & AUM passage
 ├─ Investment Requirements passage
 ├─ Expense & Exit passage
 ├─ Risk & Benchmark passage
 ├─ Fund Manager passage
 ├─ Tax Information passage
 ├─ Holdings passage
 └─ Lock-in passage (ELSS only)
        │
        ▼  ~38 passages across 5 funds
Text Chunker (RecursiveCharacterTextSplitter)
 ├─ chunk_size=300 tokens
 ├─ chunk_overlap=50 tokens
 └─ Metadata tagged per chunk
        │
        ▼  ~48 chunks
Chunk Embedder (BAAI/bge-small-en-v1.5, 384 dims)
 └─ Single local encode() call via sentence-transformers
        │
        ▼  48 × 384-dim vectors
Vector Store Builder (ChromaDB)
 ├─ Drop existing collection
 ├─ Create fresh collection (cosine similarity)
 └─ Insert all chunks + embeddings + metadata
        │
        ▼
Persisted in ChromaDB Cloud (trychroma.com)
(permanent — no artifact upload needed)
```

---

## Dependency Summary

| Package                    | Version    | Purpose                                      |
|----------------------------|------------|----------------------------------------------|
| `langchain-text-splitters` | ≥ 0.2      | `RecursiveCharacterTextSplitter`             |
| `tiktoken`                 | ≥ 0.7      | Token-accurate chunk length measurement      |
| `sentence-transformers`    | ≥ 3.0      | `BAAI/bge-small-en-v1.5` local embeddings   |
| `torch`                    | ≥ 2.0      | Backend for sentence-transformers inference  |
| `chromadb`                 | ≥ 0.5      | ChromaDB Cloud client (`HttpClient`)         |

---

## Failure Modes & Handling

| Failure                              | Behaviour                                                           |
|--------------------------------------|---------------------------------------------------------------------|
| sentence-transformers model load failure | Pipeline raises exception; GitHub Actions job fails; previous artifact retained |
| Empty passage (scraper returned `""`)| Chunk skipped; logged as warning; other chunks proceed             |
| Chunk below minimum size (< 30 tok) | Discarded silently by splitter                                      |
| ChromaDB Cloud write error           | Pipeline raises exception; job fails; previous cloud collection remains intact |
| Missing CHROMA_* env vars            | `_get_client()` raises `KeyError` with a clear message before any API call is made |
| Embedding dimension mismatch         | Collection is dropped and recreated daily — no stale dimension conflicts |
