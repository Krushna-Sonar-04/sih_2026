"""Endpoint verification checklist for a locally running DRISHTI backend.

Usage:
    python scripts/verify_api.py                 # defaults to http://localhost:8000
    python scripts/verify_api.py http://host:8000

Prints PASS/FAIL per endpoint and exits non-zero if anything fails.
No credentials are printed.
"""
from __future__ import annotations

import sys

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")


def main() -> int:
    failures = 0
    with httpx.Client(base_url=BASE, timeout=30.0) as client:
        watches = client.get("/api/watches")
        watch_id = watches.json()[0]["id"] if watches.status_code == 200 and watches.json() else "ai-regulation-india"

        checks: list[tuple[str, str, dict | None, int]] = [
            ("GET", "/api/health", None, 200),
            ("GET", "/api/watches", None, 200),
            ("GET", f"/api/watches/{watch_id}", None, 200),
            ("GET", f"/api/watches/{watch_id}/timeline?snapshot=3", None, 200),
            ("GET", f"/api/watches/{watch_id}/sentiment?snapshot=3", None, 200),
            ("GET", f"/api/watches/{watch_id}/trends?snapshot=3", None, 200),
            ("GET", f"/api/watches/{watch_id}/network?snapshot=3", None, 200),
            ("GET", f"/api/watches/{watch_id}/kols?snapshot=3", None, 200),
            ("GET", f"/api/watches/{watch_id}/demographics?snapshot=3", None, 200),
            ("GET", f"/api/watches/{watch_id}/evidence?snapshot=3", None, 200),
            ("GET", f"/api/watches/{watch_id}/cross-platform?snapshot=3", None, 200),
            ("GET", "/api/alerts", None, 200),
            ("GET", "/api/history", None, 200),
            ("GET", "/api/system-health", None, 200),
            ("GET", "/api/adapters", None, 200),
            ("POST", "/api/watches", {
                "name": "Verification Watch",
                "keywords": "verification, local readiness",
                "platforms": ["X", "Telegram"],
                "range_from": "2026-09-01T00:00:00+00:00",
                "range_to": "2026-09-14T23:59:00+00:00",
            }, 201),
            ("POST", f"/api/watches/{watch_id}/assistant/query?snapshot=3",
             {"question": "Why did sentiment shift here?"}, 200),
            ("POST", f"/api/watches/{watch_id}/assistant/query?snapshot=3",
             {"question": "What is the price of gold in Antarctica for zebras?"}, 200),
            ("POST", f"/api/watches/{watch_id}/refresh", None, 200),
            ("POST", "/api/ingestion/x", {"watch_id": watch_id}, 200),
            ("POST", "/api/ingestion/telegram", {"watch_id": watch_id}, 200),
            # Phase 4/5: connectors, ingestion pipeline and scheduler
            ("GET", "/api/connectors", None, 200),
            ("POST", "/api/connectors/telegram/test", None, 200),
            ("POST", "/api/connectors/x/test", None, 200),
            ("GET", "/api/scheduler", None, 200),
            ("PUT", "/api/scheduler", {"interval": "manual", "enabled": False}, 200),
            ("POST", f"/api/watches/{watch_id}/ingest", None, 200),
            ("POST", f"/api/watches/{watch_id}/backfill", {
                "from": "2026-09-01T00:00:00+00:00",
                "to": "2026-09-14T23:59:00+00:00",
            }, 200),
            ("GET", f"/api/watches/{watch_id}/provenance", None, 200),
            ("GET", "/api/ingestion/logs", None, 200),
            ("PATCH", f"/api/watches/{watch_id}", {"status": "Paused"}, 200),
            ("PATCH", f"/api/watches/{watch_id}", {"status": "Active"}, 200),
            ("PATCH", f"/api/watches/{watch_id}", {"mode": "live"}, 409),
            ("GET", "/api/ingestion/logs/does-not-exist", None, 404),
        ]

        for method, path, body, expected in checks:
            try:
                response = client.request(method, path, json=body)
                ok = response.status_code == expected
            except Exception as exc:  # noqa: BLE001 - verification output only
                ok = False
                response = None
                print(f"FAIL  {method:4} {path} -> {type(exc).__name__}")
            if response is not None:
                status = "PASS" if ok else "FAIL"
                print(f"{status}  {method:4} {path} -> {response.status_code}")
            if not ok:
                failures += 1

    print(f"\n{len(checks) - failures}/{len(checks)} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
