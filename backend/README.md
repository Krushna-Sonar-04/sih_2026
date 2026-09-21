# DRISHTI backend (SIH 2026 · PS 26152 · NTRO)

FastAPI + PostgreSQL + NetworkX backend for the DRISHTI narrative intelligence
prototype. Demo Mode always works; live platform adapters activate only when
credentials are configured server-side.

## Run locally

```bash
cd backend
cp .env.example .env            # fill in only what you have; blanks are fine
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

With PostgreSQL via Docker:

```bash
cd backend
docker compose up -d db
uvicorn app.main:app --reload --port 8000
```

Or the whole stack: `docker compose up --build`.

On startup the schema is created and the deterministic demo dataset is seeded
(AI Regulation India, 01–14 Sep 2026, X + Telegram).

API docs: http://localhost:8000/docs

## Connect the frontend

In the project root create `.env` with:

```
VITE_API_BASE_URL=http://localhost:8000
```

When the backend is unreachable the frontend automatically falls back to its
built-in deterministic demo engine, so the UI never breaks.

## Architecture

```
platform adapters → normalization → PostgreSQL → analytics engines
   → shared timeline state → API → frontend
```

- `app/adapters/` — X and Telegram adapters behind one `PlatformAdapter`
  interface; Instagram/Facebook/Reddit/YouTube registered as Planned.
- `app/analytics/` — sentiment (VADER + emotion indicators), trends
  (transparent velocity formula), network (NetworkX centrality + communities),
  KOL candidate scoring, aggregate-only demographics with a minimum reporting
  threshold.
- `app/services/timeline.py` — the shared clock: one Watch + one timestamp
  returns every analytical vector for the same window.
- `app/services/assistant.py` — grounded analyst assistant, cite-or-refuse,
  provider-agnostic LLM with a deterministic local fallback.

## Key endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /api/watches`, `GET /api/watches`, `GET /api/watches/{id}` | Watch management |
| `GET /api/watches/{id}/timeline` | All analytical vectors for one timestamp |
| `.../sentiment` `.../trends` `.../network` `.../kols` `.../demographics` `.../evidence` `.../cross-platform` | Individual vectors from the same clock |
| `POST /api/watches/{id}/assistant/query` | Grounded assistant with citations |
| `POST /api/watches/{id}/refresh` | Refresh data (live adapters or demo) |
| `POST /api/ingestion/x`, `POST /api/ingestion/telegram` | Adapter ingestion |
| `GET /api/alerts`, `GET /api/history` | Alerts and analysis history |
| `GET /api/system-health`, `GET /api/health` | Real backend component state |

## Honesty and privacy

- Credentials are read from the environment server-side only; no key is ever
  returned by an endpoint or exposed to the browser.
- Platform status is reported as Connected / Not configured / Demo / Planned /
  Unavailable — a live label is used only when an adapter actually returned data.
- Demographics are aggregate-only; cohorts below the reporting threshold return
  "Cohort too small to report."
- The assistant cites stored evidence or replies "Insufficient evidence in the
  selected data to answer this question."
