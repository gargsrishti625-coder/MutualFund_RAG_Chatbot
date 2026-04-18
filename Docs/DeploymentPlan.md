# Deployment Plan: Mutual Fund FAQ Assistant

## Overview

Three independently deployed services, each on the right platform for its job:

| Service | Platform | Why |
|---|---|---|
| **Ingestion Scheduler** | GitHub Actions | Already has the repo checked out; cron is free; secrets are stored as GitHub repo secrets |
| **FastAPI Backend** | Render (Web Service) | Native Python support; zero-config HTTPS; free tier; health checks built-in |
| **Next.js Frontend** | Render (Web Service) | Native Node support; SSR works out of the box; same free tier; instant deploy from same repo |

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PRODUCTION TOPOLOGY                             │
└────────────────────────────────────────────────────────────────────────┘

  GitHub Actions (cron 9:15 AM IST)
         │
         │  scrape → chunk → embed → push
         ▼
  ChromaDB Cloud ◄──────────────────────────────────────────────────┐
                                                                     │
  User Browser                                                       │
         │                                                           │
         │  HTTPS                                                    │
         ▼                                                           │
  Render: mfaq-frontend (Next.js)                                   │
         │  /api/* rewrite (server-side, same origin)               │
         ▼                                                           │
  Render: mfaq-backend (FastAPI)  ─── query_pipeline ───────────────┘
         │
         └── Groq API (llama-3.3-70b-versatile)
```

---

## Prerequisites

Before deploying, ensure you have:

- [ ] GitHub account with this repo pushed (any branch, e.g. `main`)
- [ ] [Render account](https://render.com) (free tier is sufficient to start)
- [ ] All four secrets ready to paste (do **not** commit these to git):

| Secret | Where to get it |
|---|---|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) → API Keys |
| `CHROMA_API_KEY` | [trychroma.com](https://trychroma.com) dashboard |
| `CHROMA_TENANT` | trychroma.com dashboard → tenant UUID |
| `CHROMA_DATABASE` | trychroma.com dashboard → database name |

---

## Step 1 — GitHub Actions (Scheduler)

The workflow file is already implemented at `.github/workflows/daily_ingestion.yml`.  
It runs every day at **9:15 AM IST** and on every manual trigger.

### 1.1 Add GitHub repository secrets

Go to: **GitHub repo → Settings → Secrets and variables → Actions → New repository secret**

Add all four:

| Secret name | Value |
|---|---|
| `CHROMA_API_KEY` | your ChromaDB Cloud API key |
| `CHROMA_TENANT` | your ChromaDB tenant UUID |
| `CHROMA_DATABASE` | your ChromaDB database name |

> `GROQ_API_KEY` is **not** needed by the ingestion pipeline.  
> The scheduler uses only local embeddings (bge-small-en-v1.5) + ChromaDB.

### 1.2 Verify

Trigger a manual run:  
**GitHub repo → Actions → Daily Mutual Fund Data Ingestion → Run workflow**

Expected output in the run log:
```
✓ Scrape run complete — 5/5 succeeded, 0 failed
✓ Normalized: HDFC Mid Cap Fund – Direct Growth
...
✓ Produced 28 embedded chunks (384 dims each)
✓ Inserted 28 chunks into 'mutual_fund_faq' on ChromaDB Cloud
Pipeline complete.
```

---

## Step 2 — Deploy Backend (FastAPI) on Render

### Option A — Blueprint (recommended, uses render.yaml)

1. Go to Render dashboard → **New → Blueprint**
2. Connect your GitHub repo
3. Render detects `render.yaml` and shows both services
4. Click **Apply** — both services are created
5. Skip to Step 2.3 to set the secret env vars

### Option B — Manual (if Blueprint is not available on your plan)

1. Render dashboard → **New → Web Service**
2. Connect your GitHub repo
3. Fill in:

| Field | Value |
|---|---|
| **Name** | `mfaq-backend` |
| **Region** | Singapore (closest to India) |
| **Runtime** | Python 3 |
| **Branch** | `main` |
| **Root Directory** | *(leave blank — project root)* |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn api.app:app --host 0.0.0.0 --port $PORT` |
| **Health Check Path** | `/health` |
| **Plan** | Free (or Starter $7/mo to avoid 15-min spin-down) |

### 2.3 Set environment variables

In Render → **mfaq-backend → Environment**:

| Key | Value | Notes |
|---|---|---|
| `GROQ_API_KEY` | `gsk_...` | Required for LLM generation |
| `CHROMA_API_KEY` | `...` | Required for vector store |
| `CHROMA_TENANT` | `...` | Required for vector store |
| `CHROMA_DATABASE` | `...` | Required for vector store |
| `ALLOWED_ORIGINS` | *(leave blank for now — update in Step 4.3)* | CORS |

### 2.4 Note the backend URL

After the first deploy succeeds, copy the URL from the Render dashboard.  
It will look like: `https://mfaq-backend.onrender.com`

### 2.5 Verify

```bash
curl https://mfaq-backend.onrender.com/health
# → {"status":"ok","version":"1.0.0"}
```

---

## Step 3 — Deploy Frontend (Next.js) on Render

### Option A — Blueprint (if using render.yaml)

Already created in Step 2 via Blueprint. Proceed to Step 3.2.

### Option B — Manual

1. Render dashboard → **New → Web Service**
2. Connect the same GitHub repo
3. Fill in:

| Field | Value |
|---|---|
| **Name** | `mfaq-frontend` |
| **Region** | Singapore |
| **Runtime** | Node |
| **Branch** | `main` |
| **Root Directory** | `frontend` |
| **Build Command** | `npm ci && npm run build` |
| **Start Command** | `npm start` |
| **Plan** | Free |

### 3.2 Set environment variables

In Render → **mfaq-frontend → Environment**:

| Key | Value | Notes |
|---|---|---|
| `BACKEND_URL` | `https://mfaq-backend.onrender.com` | From Step 2.4 |
| `NODE_ENV` | `production` | Enables Next.js production optimisations |

> **Why `BACKEND_URL`?**  
> `next.config.js` uses this to rewrite `/api/*` → backend. In production, the frontend
> and backend run on different Render URLs. The rewrite happens server-side inside Next.js,
> so the browser never makes a cross-origin request — CORS is only between the two Render
> services, not from the user's browser directly to the backend.

### 3.3 Note the frontend URL

After deploy: `https://mfaq-frontend.onrender.com`

---

## Step 4 — Wire Services Together

### 4.1 Update backend CORS

Now that both URLs are known, set the CORS origin on the backend:

Render → **mfaq-backend → Environment** → update:

| Key | Value |
|---|---|
| `ALLOWED_ORIGINS` | `https://mfaq-frontend.onrender.com` |

Click **Save changes** → Render redeploys the backend automatically.

### 4.2 Verify cross-service communication

From the frontend, open the browser console on `https://mfaq-frontend.onrender.com` and check:
- Network tab → `/api/health` → `200 {"status":"ok"}`
- No CORS errors in console

### 4.3 End-to-end smoke test

1. Open `https://mfaq-frontend.onrender.com`
2. Click example question: **"What is the expense ratio of HDFC Mid Cap Fund?"**
3. Confirm the answer appears with a green **✓ Answer** badge and a source URL

---

## Step 5 — Verify the Full System

| Check | Expected |
|---|---|
| `GET /health` (backend) | `{"status":"ok","version":"1.0.0"}` |
| Frontend loads | "How can I assist your research?" welcome screen |
| Factual question | Answer with `type: answer`, `source_url` set |
| Advisory question ("should I invest?") | Refusal with AMFI link |
| GitHub Actions daily run | 5/5 funds scraped, 28 chunks pushed to ChromaDB |
| GitHub Actions manual trigger | Same as above |

---

## Environment Variables: Complete Reference

### Backend (`mfaq-backend` on Render)

| Variable | Required | Set in | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes | Render env | Groq LPU API key for llama-3.3-70b |
| `CHROMA_API_KEY` | Yes | Render env | ChromaDB Cloud API key |
| `CHROMA_TENANT` | Yes | Render env | ChromaDB tenant UUID |
| `CHROMA_DATABASE` | Yes | Render env | ChromaDB database name |
| `ALLOWED_ORIGINS` | Yes | Render env | Comma-separated CORS origins |

### Frontend (`mfaq-frontend` on Render)

| Variable | Required | Set in | Description |
|---|---|---|---|
| `BACKEND_URL` | Yes | Render env | Full URL of the backend service |
| `NODE_ENV` | Yes | Render env | Set to `production` |

### GitHub Actions (Scheduler)

| Secret | Required | Description |
|---|---|---|
| `CHROMA_API_KEY` | Yes | ChromaDB Cloud API key |
| `CHROMA_TENANT` | Yes | ChromaDB tenant UUID |
| `CHROMA_DATABASE` | Yes | ChromaDB database name |

> `GROQ_API_KEY` is **not** needed by the scheduler — ingestion uses local embeddings only.

---

## Files Added / Modified for Deployment

| File | Change | Why |
|---|---|---|
| `render.yaml` | **New** | Render Blueprint IaC — declares both services |
| `runtime.txt` | **New** | Pins Python to 3.11.9 on Render (default is 3.7) |
| `frontend/next.config.js` | **Modified** | `http://localhost:8000` → `BACKEND_URL` env var |
| `frontend/package.json` | **Modified** | `next start --port 3000` → `next start` (uses Render's `$PORT`) |
| `frontend/.env.local.example` | **New** | Documents local dev env vars for other contributors |
| `.github/workflows/daily_ingestion.yml` | **No change** | Already production-ready |

---

## Render Free Tier Limitations & Workarounds

| Limitation | Impact | Workaround |
|---|---|---|
| **15-min spin-down** on free web services | First request after idle takes ~30–50s to wake up | Upgrade to Starter ($7/mo) to keep always-on; or use a free uptime monitor (e.g. UptimeRobot) to ping `/health` every 14 min |
| **750 free hours/month** per service | 2 services = 1500 hrs needed; free gives only 750 | Both services share the 750-hr pool on the free plan — consider upgrading one to Starter |
| **No persistent disk** on free tier | In-memory session store is wiped on each deploy/restart | Acceptable for a demo; for production, sessions would need Redis or a database |
| **Build time** can be slow | First build of the Python service installs torch (~700MB) | Render caches pip packages between builds after the first |

---

## Rollback Plan

### Backend rollback
Render keeps every successful deploy. To revert:  
**mfaq-backend → Deploys → [previous deploy] → Rollback to this deploy**

### Frontend rollback
Same path via the Render dashboard for `mfaq-frontend`.

### Scheduler rollback
Revert the workflow YAML via git and push. The previous cron schedule takes effect immediately.

### ChromaDB rollback
The vector store is rebuilt from scratch on each ingestion run. If a bad scrape pushed corrupted data, trigger a manual re-run of the GitHub Actions workflow after fixing the scraper — the collection is dropped and recreated atomically.

---

## Deployment Sequence (Must Follow This Order)

```
1. Push all code to GitHub (main branch)
       │
       ▼
2. Add GitHub Actions secrets (CHROMA_*)
       │
       ▼
3. Trigger manual GitHub Actions run → verify 28 chunks in ChromaDB
       │
       ▼
4. Deploy mfaq-backend on Render → note its URL
       │
       ▼
5. Deploy mfaq-frontend on Render → set BACKEND_URL = backend URL
       │
       ▼
6. Update mfaq-backend → set ALLOWED_ORIGINS = frontend URL → redeploy
       │
       ▼
7. Smoke test end-to-end (welcome screen → factual query → refusal query)
```

> **Why this order?**  
> The backend must exist before the frontend can proxy to it.  
> ChromaDB must have data before the backend can answer queries.  
> CORS must be set last because the frontend URL is only known after frontend deploy.
