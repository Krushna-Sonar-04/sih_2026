# DRISHTI — AI-Driven Social Media Analytics & Narrative Intelligence

Smart India Hackathon 2026 · Problem Statement 26152 · NTRO

DRISHTI is a full-stack prototype: a React + TypeScript analyst workspace, a
FastAPI + PostgreSQL backend with real analytics engines (VADER sentiment,
transparent trend velocity, NetworkX graph/KOL scoring, aggregate-only
demographics), and a grounded analyst assistant. Its defining feature is the
**Narrative Time-Machine** — one shared clock drives sentiment, trends,
demographics, influence network and evidence for the same Watch.

The stack runs entirely on your own machine. **No Lovable service, account or
hosted URL is required to run it locally.**

---

## 🚀 Quick Start (Demo Mode)

Run these commands in two separate terminal windows:

**Terminal 1: Database & Backend**
```powershell
# Start the database
docker compose up -d db

# Setup and run backend
cd backend
python -m venv .venv
.\.venv\Scripts\activate   # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env     # (Windows) cp .env.example .env on macOS/Linux
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Terminal 2: Frontend**
```powershell
# Setup and run frontend
npm install
copy .env.example .env.local  # (Windows) cp .env.example .env.local on macOS/Linux
npm run dev
```

Open **http://localhost:8080** in your browser. For detailed instructions and live data setup, see the **Local Development** section below.

---

## Project structure

```
/                     frontend (React 19 + TypeScript + Vite + Tailwind)
  src/                UI, routes, demo engine, API client
  .env.example        frontend config (VITE_API_BASE_URL)
/backend              FastAPI application (real executable Python)
  app/main.py         ASGI entry point
  app/api.py          all /api routes
  app/adapters/       X, Telegram (+ planned platform adapters)
  app/analytics/      sentiment, trends, network, KOL, demographics
  app/services/       timeline (shared clock), ingestion, assistant, health
  app/seed/           deterministic demo dataset
  scripts/verify_api.py   endpoint verification checklist
  .env.example        backend config + credential placeholders
/docker-compose.yml   PostgreSQL (+ optional backend container)
```

> Note: the frontend lives at the repository root rather than in a `/frontend`
> folder, because the Vite/TanStack build is configured from the root
> (`vite.config.ts`, `package.json`, `src/`). Everything else matches the
> requested layout.

---

## LOCAL DEVELOPMENT (Windows / macOS / Linux)

### 1. Install dependencies

Frontend (Node 20+ with npm, or Bun):

```powershell
npm install          # or: bun install
```

Backend (Python 3.11+):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate         # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure .env

```powershell
copy .env.example .env.local             # repo root   (frontend)
copy backend\.env.example backend\.env   # backend
```

Leave every credential blank to run in Demo Mode. Nothing breaks when they are
empty.

### 3. Start PostgreSQL (primary database)

Docker (recommended):

```powershell
docker compose up -d db
```

Then in `backend\.env`:

```
DATABASE_URL=postgresql+psycopg://drishti:drishti_local_dev@localhost:5432/drishti
```

PostgreSQL is the intended database. If `DATABASE_URL` points at PostgreSQL and
the server is unreachable, the backend **fails with a clear error** instead of
quietly using another database.

SQLite remains an **explicit development fallback only** — choose it deliberately:

```
DATABASE_URL=sqlite:///./drishti.db
```

### 4. Run migrations

```powershell
cd backend
alembic upgrade head
```

Migrations are versioned with Alembic (`backend/migrations`). The backend also
runs `alembic upgrade head` on startup — it never blindly recreates tables.

### 5. Start FastAPI

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

On startup the schema is migrated **and the demo dataset is seeded
automatically** (idempotent). Interactive API docs: http://localhost:8000/docs

### 6. Start the frontend

```powershell
npm run dev          # or: bun run dev
```

### 7. Open localhost

http://localhost:8080 — the header shows `DEMO MODE`, and System Health shows
the database as Connected (with PostgreSQL version and latency) once FastAPI is
running.

---

## Database setup, migration and seed

Creation → migration → seed:

```powershell
docker compose up -d db                     # 1. PostgreSQL 16 with a persistent volume
cd backend
alembic upgrade head                        # 2. versioned schema migration
python -c "from app.database import SessionLocal; from app.seed.seed_demo import seed; db=SessionLocal(); print(seed(db)); db.close()"   # 3. demo seed
```

The backend startup performs steps 2 and 3 automatically, so in practice
`uvicorn app.main:app --reload --port 8000` is enough.

Indexes created by the migration for the main access patterns:
`post(watch_id, event_time)`, `network_edge(source_account, event_time)`,
`network_edge(target_account, event_time)`,
`trend_topic(watch_id, event_time, velocity_score)`.

Reset a local database: stop the API, then `docker compose down -v` and start
again (or delete `backend\drishti.db` when using the SQLite fallback).

### Database tests

```powershell
cd backend
pytest tests -q                                                              # SQLite, no credentials
$env:DRISHTI_TEST_DATABASE_URL="postgresql+psycopg://drishti:drishti_local_dev@localhost:5432/drishti_test"
pytest tests -q                                                              # identical suite on PostgreSQL
```

62 tests pass on both databases. External platforms are exercised through
fixtures, so no credential is ever required.

### Audit chain verification

```powershell
cd backend
python scripts/verify_audit_chain.py      # prints VALID or INVALID, never prints secrets
```

Each audit record stores `prev_hash` and `record_hash`; editing an earlier
record makes the chain verification fail. Records created before migration
`0002` predate the chain and are reported separately as unverifiable.

### Additional documentation

- `docs/SIH_DEMO_SCRIPT.md` — 3-minute demo walkthrough.
- `docs/RESUME_PROJECT_DESCRIPTION.md` — truthful portfolio description.

---

## DEMO MODE

Default and always available. Watch **AI Regulation India**, 01–14 Sep 2026,
X + Telegram, 8 analysis points with 08 Sep · 14:30 as the narrative ignition
point. Demo Mode works with **no** X, Telegram or LLM credentials. All data is
labelled `DEMO DATASET · SIMULATED SOCIAL ACTIVITY`.

If the backend is not running, the frontend automatically falls back to its
built-in deterministic demo engine so the full journey still works.

## LIVE MODE

Live Mode activates per adapter, only when server-side credentials are present
and the provider actually returns data. Adapter status is reported honestly as
`Connected`, `Not configured`, `Demo`, `Planned` or `Unavailable`. One failing
adapter never stops the others or the application.

## TELEGRAM CONFIGURATION

Step by step:

1. Create a bot through Telegram's official bot-management workflow (BotFather)
   and copy the token it issues. Keep the token private — never paste it into a
   frontend file, a ticket, or a screenshot.
2. Add the bot to the channel or group you are permitted to analyse, and give it
   the access required to receive messages.
3. Put the credentials **only** in `backend\.env` (they are read server-side and
   are never exposed to the browser):

```
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHANNEL_ID=@your_channel
TELEGRAM_POLL_SECONDS=60
INGESTION_ENABLED=true
SCHEDULER_INTERVAL=5m        # manual | 5m | 15m | hourly
```

4. Test the credentials:

```powershell
cd backend
python scripts/test_telegram_connection.py
```

The script calls the official Bot API (`getMe`, then `getChat`) and prints a safe
status. It never prints the token. `Connected` is reported only after a real
successful request.

5. Start ingestion — the *Refresh Data* button in the workspace, the
   `POST /api/watches/{id}/ingest` endpoint, or the background polling worker
   when `INGESTION_ENABLED=true` with a non-manual interval.

The worker uses long polling (`getUpdates`) and persists the update offset in the
`ingestion_cursor` table, so a restart never re-ingests processed updates. A
single message that fails processing is logged and skipped without losing the
batch. Telegram treats polling and webhooks as mutually exclusive — polling is
the local default; configure `TELEGRAM_WEBHOOK_SECRET` and
`POST /api/webhooks/telegram` only if you switch to webhooks instead.

Without both values the status is `Not configured` — no live connection is
simulated, and Demo Mode continues to work unchanged.

**Live test Watch:** once Telegram is configured, the backend creates
*AI Regulation India — Telegram Live Test* (Telegram only, live mode) so ingested
messages have a Watch to land in. It is never created without credentials.

Telegram data is only read through the official API / authorized client paths.
No web scraping is used.

## X CONFIGURATION

```
X_BEARER_TOKEN=your-bearer-token
X_CLIENT_ID=
X_CLIENT_SECRET=
```

The adapter calls the official X API v2 recent-search endpoint. No scraping and
no bypassing of platform restrictions. Without a bearer token the status is
`Not configured`.

## LLM CONFIGURATION

```
LLM_PROVIDER=auto        # auto | openai | gemini | local
LLM_API_KEY=             # or OPENAI_API_KEY / GEMINI_API_KEY
LLM_MODEL=gpt-4o-mini
```

With no key the assistant uses the deterministic local analyst, which answers
only from stored records, cites `Evidence 01…`, and otherwise replies
"Insufficient evidence in the selected data to answer this question."

---

## CONNECTOR TESTING

The **Connector Center** page (`/connectors`) lists every platform with its
status, configuration state, last ingestion, records collected and last error,
and offers a per-platform *Test connection*. It never displays a token — only
`Configured`/`Not configured` and a masked identifier.

```powershell
curl -X POST http://localhost:8000/api/connectors/telegram/test
curl -X POST http://localhost:8000/api/connectors/x/test
```

Response fields: `configured`, `authenticated`, `source_reachable`,
`status`, `identifier`, `last_message_time`, `error`. Statuses are
`Connected`, `Not configured`, `Invalid credentials`, `Unauthorized`,
`Rate limited`, `No accessible source`, `Unavailable`, `Error`, `Planned`.

## INGESTION

Pipeline: `platform → adapter → normalization → validation → deduplication
(platform + external_id) → PostgreSQL → incremental analysis → shared timeline`.

```powershell
curl -X POST http://localhost:8000/api/watches/ai-regulation-india/ingest
curl "http://localhost:8000/api/ingestion/logs?platform=Telegram&status=Connected"
```

The *Refresh Data* button in the Narrative Time-Machine calls the same job and
reports the real counts (`records fetched / new / duplicates / rejected`). In
Demo Mode it refreshes the deterministic snapshot instead.

Scheduling is off by default. `INGESTION_ENABLED=true` with
`SCHEDULER_INTERVAL=5m|15m|hourly` starts exactly one background worker
(`GET`/`PUT /api/scheduler` to inspect or change it); `manual` disables it.

## BACKFILL

```powershell
curl -X POST http://localhost:8000/api/watches/ai-regulation-india/backfill ^
  -H "content-type: application/json" ^
  -d "{\"from\":\"2026-09-01T00:00:00Z\",\"to\":\"2026-09-14T00:00:00Z\"}"
```

Adapters honour real capability limits: X recent search reaches back 7 days,
and the Telegram Bot API cannot replay history — those requests return a clear
explanation (`Historical data is unavailable for this connector.`) rather than
a fake success. An optional MTProto/Telethon adapter is wired as a separate
historical path and stays `Not configured` unless `TELEGRAM_API_ID`,
`TELEGRAM_API_HASH`, `TELEGRAM_SESSION` and Telethon are all present.

## Adapter tests (no credentials required)

```powershell
cd backend
python -m pytest tests -q
```

Fixture-based tests cover Telegram and X normalization, shared-schema
validation, duplicate handling, authentication failure (not retried),
transient retry, rate-limit surfacing and timestamp preservation. Live network
calls happen only when `LIVE_CONNECTOR_TEST=true` is explicitly set.

## TROUBLESHOOTING

| Symptom | Cause / fix |
| --- | --- |
| Connector shows `Not configured` | The matching environment variable is empty in `backend\.env`. Restart the API after editing. |
| `Telegram is configured but the bot cannot access this source.` | The bot is not a member/admin of `TELEGRAM_CHANNEL_ID`, or the channel id is wrong. |
| `X authentication failed.` | Bearer token invalid or revoked; the adapter does not retry permanent auth failures. |
| `Rate limit reached. Retrying later.` | X API window exhausted; the adapter backs off and resumes after the window. |
| Frontend shows `DEMO MODE` with the backend running | `VITE_API_BASE_URL` not set, or CORS origin missing from `CORS_ORIGINS`. |
| No ingestion runs recorded | Scheduler is `manual`; use *Refresh Data* or `POST /api/watches/{id}/ingest`. |

---

## Endpoint verification checklist

With the backend running:

```powershell
cd backend
python scripts/verify_api.py            # defaults to http://localhost:8000
```

It checks `/api/health`, `/api/watches`, `/api/watches/{id}`, and per watch
`/timeline`, `/sentiment`, `/trends`, `/network`, `/kols`, `/demographics`,
`/evidence`, `/cross-platform`, plus `/api/alerts`, `/api/history`,
`/api/system-health`, `/api/adapters`, `POST /api/watches`,
`POST /api/watches/{id}/assistant/query` (grounded and insufficient-evidence),
`POST /api/watches/{id}/refresh` and both ingestion endpoints.

---

## Security

- Platform and LLM credentials are read **only** from the backend environment.
- The React code contains no credentials, no secrets in `localStorage`, and no
  hosted or vendor URLs — only `VITE_API_BASE_URL`.
- `.env` files are git-ignored; `.env.example` files hold placeholders only.
- Secret values are never logged; audit events record actions, not credentials.

## Docker

Docker is optional. `docker compose up -d db` for PostgreSQL only (simplest on
Windows), or `docker compose up --build` to run PostgreSQL and the API together.
The frontend always runs on the host.
