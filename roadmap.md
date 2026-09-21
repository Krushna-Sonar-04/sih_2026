# DRISHTI Phase 2 Roadmap

- [x] Inspect Phase 1 architecture and preserve approved visual system
- [x] Design shared typed demo engine and analysis state
- [x] Implement synchronized Time-Machine interactions and selectors
- [x] Implement KOL, trend, and evidence drill-downs
- [x] Implement watch creation, switching, and contextual navigation
- [x] Wire alerts and history into exact analysis states
- [x] Verify all acceptance flows and responsive layouts

## Phase 3 — frontend integration
- [x] Typed API client with VITE_DRISHTI_API_URL and demo fallback
- [x] Demo/Live mode badge in the shell from backend health
- [x] System Health driven by GET /api/system-health
- [x] Analyst Assistant panel with citations (backend or local grounded)
- [x] Refresh Data control with ingestion status
- [x] Platform connection states in Create Watch

## Phase 5 — PostgreSQL primary + live Telegram ingestion
- [x] PostgreSQL as primary database; clear failure when unreachable (no silent SQLite fallback)
- [x] Alembic migration system (17 tables) with the required composite indexes
- [x] Real database health: Connected/Unavailable, version, latency, revision, record count
- [x] Durable Telegram update offset (ingestion_cursor) + per-message failure isolation
- [x] Polling worker: single instance, bounded backoff, no retry on permanent auth failure
- [x] Documented live test watch, created only when Telegram credentials exist
- [x] scripts/test_telegram_connection.py (explicit live credential test, never prints token)
- [x] Tests: 21 passing on SQLite and on real PostgreSQL (no credentials required)
- [x] 30/30 endpoint checklist verified against PostgreSQL
- [x] README: PostgreSQL, migrations, seed, Telegram setup guide
