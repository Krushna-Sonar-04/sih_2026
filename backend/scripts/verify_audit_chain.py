"""Verify the tamper-evident audit hash chain.

Usage (from the backend/ directory):

    python scripts/verify_audit_chain.py

Prints VALID or INVALID. Never prints secrets: only action names, actor
identifiers already stored in the audit table, and record positions.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import AuditEvent  # noqa: E402


def expected_hash(prev_hash: str, action: str, actor: str, watch_id: str | None, detail: str) -> str:
    payload = f"{prev_hash}|{action}|{actor}|{watch_id or ''}|{detail[:500]}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify() -> tuple[bool, list[str], int, int]:
    problems: list[str] = []
    with SessionLocal() as db:
        events = list(db.scalars(select(AuditEvent).order_by(AuditEvent.id)))
    hashed = [event for event in events if event.record_hash]
    legacy = len(events) - len(hashed)
    previous = ""
    for index, event in enumerate(hashed, start=1):
        if index == 1:
            previous = event.prev_hash or ""
        if (event.prev_hash or "") != previous:
            problems.append(f"record #{index} (id={event.id}, action={event.action}): broken link to previous record")
        computed = expected_hash(previous, event.action, event.actor, event.watch_id, event.detail or "")
        if computed != event.record_hash:
            problems.append(f"record #{index} (id={event.id}, action={event.action}): content does not match stored hash")
        previous = event.record_hash
    return (not problems), problems, len(hashed), legacy


def main() -> int:
    ok, problems, checked, legacy = verify()
    print(f"DRISHTI audit chain check - {checked} hash-chained record(s) inspected")
    if legacy:
        print(f"  note: {legacy} record(s) predate the hash chain (migration 0002) and are not verifiable")
    if ok:
        print("VALID")
        return 0
    for problem in problems:
        print(f"  - {problem}")
    print("INVALID")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
