"""Audit hash-chain integrity and HTTP-level role enforcement.

No credentials and no live platform calls are involved.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.models import AuditEvent, Watch
from app.services import audit, auth as auth_service

WATCH_ID = "ai-regulation-india"


@pytest.fixture()
def seeded(db):
    from app.seed.seed_demo import seed

    if db.get(Watch, WATCH_ID) is None:
        seed(db)
    yield db
    db.rollback()


# --------------------------------------------------------------------------- audit chain
def test_audit_records_are_hash_chained(seeded):
    db = seeded
    audit.record(db, "watch.created", "chain test one", WATCH_ID, "analyst@example.test")
    audit.record(db, "assistant.query", "chain test two", WATCH_ID, "analyst@example.test")
    events = db.query(AuditEvent).order_by(AuditEvent.id).all()
    chained = [event for event in events if event.record_hash]
    assert len(chained) >= 2
    last, previous = chained[-1], chained[-2]
    assert last.prev_hash == previous.record_hash
    assert last.record_hash and last.record_hash != previous.record_hash
    assert "password" not in last.detail.lower()


def test_tampering_with_an_earlier_record_breaks_verification(seeded):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from verify_audit_chain import expected_hash

    db = seeded
    audit.record(db, "export.generated", "original detail", WATCH_ID, "analyst@example.test")
    event = db.query(AuditEvent).order_by(AuditEvent.id.desc()).first()
    assert event is not None
    assert expected_hash(event.prev_hash or "", event.action, event.actor, event.watch_id, event.detail) == event.record_hash

    event.detail = "tampered detail"
    db.commit()
    assert expected_hash(event.prev_hash or "", event.action, event.actor, event.watch_id, event.detail) != event.record_hash


# --------------------------------------------------------------------------- roles over HTTP
@pytest.fixture()
def client(seeded, monkeypatch):
    from app.config import get_settings
    from app.main import app

    monkeypatch.setattr(get_settings(), "auth_required", True)
    with TestClient(app) as test_client:
        yield test_client


def _token(db, email: str, role: str) -> str:
    user = auth_service.get_by_email(db, email)
    if user is None:
        user = auth_service.create_user(db, email=email, password="strong-password-123", display_name=email, role=role)
    token, _ = auth_service.issue_token(user)
    return token


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_protected_route_requires_authentication(client):
    assert client.get("/api/auth/users").status_code == 401


def test_invalid_token_is_rejected(client):
    assert client.get("/api/auth/me", headers=_headers("not-a-real-token")).status_code == 401


def test_analyst_cannot_administer_users_but_can_read_analysis(client, seeded):
    token = _token(seeded, "analyst@example.test", "analyst")
    assert client.get("/api/auth/users", headers=_headers(token)).status_code == 403
    assert client.get(f"/api/watches/{WATCH_ID}/timeline", headers=_headers(token)).status_code == 200
    assert client.get(f"/api/watches/{WATCH_ID}/briefing", headers=_headers(token)).status_code == 200


def test_lead_analyst_cannot_administer_users(client, seeded):
    token = _token(seeded, "lead@example.test", "lead_analyst")
    assert client.get("/api/auth/users", headers=_headers(token)).status_code == 403
    assert client.get("/api/alerts", headers=_headers(token)).status_code == 200


def test_admin_can_administer_users_and_read_audit(client, seeded):
    token = _token(seeded, "admin@example.test", "admin")
    assert client.get("/api/auth/users", headers=_headers(token)).status_code == 200
    assert client.get("/api/audit", headers=_headers(token)).status_code == 200
