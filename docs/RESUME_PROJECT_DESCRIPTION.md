# DRISHTI — resume / portfolio description

Truthful descriptions only. Every claim below corresponds to code in this
repository and to behaviour covered by the automated test suite.

## Short version (2 lines)

**DRISHTI — Social Media Narrative Intelligence Workspace** (React + TypeScript,
FastAPI, PostgreSQL). Built a full-stack analysis tool that ingests public X and
Telegram activity into one canonical schema and replays narrative evolution
through a single shared timeline with sentiment, trend, graph and
retrieval-grounded assistant analysis, with evidence-level traceability.

## Medium version (bullets)

- Designed a **canonical post schema** so trend, sentiment, graph and evidence
  logic is identical regardless of source platform; platform adapters are the
  only source-specific code.
- Implemented **Telegram Bot API** ingestion with durable offsets, deduplication,
  per-message failure isolation and bounded backoff, plus an **official X API**
  adapter with pagination and rate-limit handling. No scraping.
- Built a **Narrative Time-Machine**: one selected timestamp drives sentiment,
  emotion, trend velocity, NetworkX centrality/community analysis, aggregate
  demographics and supporting evidence from the same time window.
- Implemented a **retrieval-grounded assistant** with hybrid retrieval (watch,
  time window, platform, topic and account filters plus vector similarity) and
  **citation validation performed outside the model** — unsupported answers are
  rejected and replaced with an explicit insufficient-evidence response.
- Engineered the data layer on **PostgreSQL** with Alembic migrations, composite
  indexes, cached embeddings and incremental analysis.
- Added **responsible-AI safeguards**: aggregate-only demographics with a minimum
  cohort threshold, "KOL candidate" rather than confirmed influencer, observed
  sequence rather than causation, and honest connector states
  (Connected / Not configured / Error / Rate limited / Planned).
- Added **JWT authentication** with Analyst / Lead Analyst / Admin roles and a
  hash-chained audit log with a standalone chain verification script.
- **62 automated tests** run against both SQLite and PostgreSQL; external
  platform calls are exercised through fixtures, never live credentials.

## Technologies

React 19, TypeScript, TanStack Router/Query, Recharts, React Flow, Tailwind;
Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL, NetworkX, transformer-based
sentiment inference, vector retrieval; Docker Compose; pytest; Playwright-based
UI verification.

## What NOT to claim

- Not a production deployment; it runs locally.
- Live X / Telegram ingestion is implemented and fixture-tested, but no live
  credentials were used, so live connectivity is not benchmarked.
- No accuracy or F1 figures are claimed — no labelled evaluation dataset is
  bundled.
- It is a student/team SIH project, not an official government system.
