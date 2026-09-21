"""Database + live-ingestion pipeline tests (fixtures only, no credentials).

Covers the Phase 5 acceptance points: migration, repository round-trip,
Telegram authentication success/failure, message normalization, update-offset
handling, duplicate prevention, timestamp preservation, inaccessible source,
ingestion statistics and end-to-end analysis into the shared timeline.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.adapters.base import PermanentAuthError
from app.adapters.telegram_bot import TelegramBotAdapter
from app.models import NetworkEdge, Account, IngestionCursor, IngestionRun, Post, SentimentResult, Watch
from app.services import ingestion, timeline

NOW = datetime(2026, 9, 8, 14, 30, tzinfo=timezone.utc)


def _update(update_id: int, message_id: int, text: str, when: datetime = NOW) -> dict:
    return {
        "update_id": update_id,
        "channel_post": {
            "message_id": message_id,
            "date": int(when.timestamp()),
            "chat": {"id": -100123, "title": "Policy Watch", "username": "policywatch"},
            "text": text,
            "views": 340,
        },
    }


class FakeTelegram(TelegramBotAdapter):
    """Bot adapter with the HTTP layer replaced by fixtures."""

    def __init__(self, updates, *, authenticated=True, chat_ok=True):
        super().__init__()
        self.settings.telegram_bot_token = "fixture-token"
        self.settings.telegram_channel_id = "@policywatch"
        self._updates = updates
        self._authenticated = authenticated
        self._chat_ok = chat_ok
        self.calls: list[dict] = []

    def _call(self, method, params=None, timeout=15.0):  # type: ignore[override]
        self.calls.append({"method": method, "params": params or {}})
        if not self._authenticated:
            raise PermanentAuthError("Telegram rejected the bot token (HTTP 401).")
        if method == "getMe":
            return {"ok": True, "result": {"username": "drishti_test_bot"}}
        if method == "getChat":
            if not self._chat_ok:
                raise RuntimeError("chat not found")
            return {"ok": True, "result": {"id": -100123, "title": "Policy Watch"}}
        if method == "getUpdates":
            offset = (params or {}).get("offset")
            pending = [u for u in self._updates if offset is None or u["update_id"] >= offset]
            return {"ok": True, "result": pending}
        return {"ok": True, "result": {}}


def _purge_live_watch(db) -> None:
    """Remove leftovers so the fixture is safe to re-enter after a failed test."""
    db.rollback()
    db.query(Post).filter(Post.watch_id == "telegram-live-test").delete()
    db.query(IngestionRun).filter(IngestionRun.watch_id == "telegram-live-test").delete()
    db.flush()
    # Only remove accounts that nothing else references (the demo dataset keeps its own).
    referenced = {row[0] for row in db.query(Post.account_id).distinct()}
    for table, column in ((NetworkEdge, NetworkEdge.source_account), (NetworkEdge, NetworkEdge.target_account)):
        referenced.update(row[0] for row in db.query(column).distinct())
    for account in db.query(Account).all():
        if account.id not in referenced:
            db.delete(account)
    existing = db.get(Watch, "telegram-live-test")
    if existing is not None:
        db.delete(existing)
    db.commit()


@pytest.fixture()
def live_watch(db):
    _purge_live_watch(db)
    watch = Watch(
        id="telegram-live-test",
        name="AI Regulation India — Telegram Live Test",
        keywords="AI regulation,privacy",
        platforms="Telegram",
        range_from=NOW - timedelta(days=7),
        range_to=NOW + timedelta(days=7),
        status="Live",
        mode="live",
    )
    db.add(watch)
    db.commit()
    yield watch
    _purge_live_watch(db)


# ------------------------------------------------------------------ migration/db
def test_migration_creates_schema(migrated_database):
    assert migrated_database not in ("", "none")


def test_repository_round_trip(db, live_watch):
    db.add(Account(id="acct-1", platform="Telegram", username="@policywatch"))
    db.commit()
    post = Post(
        id="repo-1", watch_id=live_watch.id, platform="Telegram", external_id="repo-1",
        account_id="acct-1", username="@policywatch", text="Draft AI regulation published.",
        event_time=NOW, source_mode="live",
    )
    db.add(post)
    db.commit()
    stored = db.get(Post, "repo-1")
    assert stored is not None and stored.event_time.replace(tzinfo=timezone.utc) == NOW
    stored.topic = "AI Regulation"
    db.commit()
    assert db.get(Post, "repo-1").topic == "AI Regulation"


# ------------------------------------------------------------------- connection
def test_telegram_authentication_success_fixture():
    adapter = FakeTelegram([])
    result = adapter.test_connection()
    assert result.authenticated and result.source_reachable
    assert result.status == "Connected"
    assert "fixture-token" not in result.identifier  # token never echoed in full


def test_telegram_authentication_failure_fixture():
    result = FakeTelegram([], authenticated=False).test_connection()
    assert result.status == "Invalid credentials"
    assert result.authenticated is False


def test_telegram_source_inaccessible():
    result = FakeTelegram([], chat_ok=False).test_connection()
    assert result.status == "No accessible source"
    assert result.authenticated is True


# -------------------------------------------------------------------- ingestion
def test_offset_advances_and_persists(db, live_watch, monkeypatch):
    adapter = FakeTelegram([_update(1000, 10, "AI regulation draft released")])
    monkeypatch.setattr(ingestion, "get_adapter", lambda platform: adapter)

    first = ingestion.run_ingestion(db, live_watch, "Telegram")
    assert first.records_stored == 1
    assert adapter.offset == 1001
    assert db.get(IngestionCursor, "Telegram").cursor == "1001"

    # a fresh adapter instance restores the persisted offset instead of replaying
    adapter2 = FakeTelegram([_update(1000, 10, "AI regulation draft released")])
    monkeypatch.setattr(ingestion, "get_adapter", lambda platform: adapter2)
    ingestion.run_ingestion(db, live_watch, "Telegram")
    assert adapter2.calls[-1]["params"].get("offset") == 1001


def test_duplicate_messages_do_not_create_duplicate_posts(db, live_watch, monkeypatch):
    update = _update(2000, 20, "Privacy concerns over AI regulation")
    adapter = FakeTelegram([update])
    monkeypatch.setattr(ingestion, "get_adapter", lambda platform: adapter)
    first = ingestion.run_ingestion(db, live_watch, "Telegram")

    # simulate a replayed batch: forget both the in-memory and persisted offset
    adapter.offset = None
    db.query(IngestionCursor).delete()
    db.commit()
    second = ingestion.run_ingestion(db, live_watch, "Telegram")

    assert first.records_stored == 1
    assert second.records_stored == 0 and second.records_duplicate == 1
    count = db.scalar(
        select(func.count()).select_from(Post).where(Post.external_id == "20", Post.platform == "Telegram")
    )
    assert count == 1


def test_ingestion_statistics_and_run_record(db, live_watch, monkeypatch):
    adapter = FakeTelegram([
        _update(3000, 30, "AI regulation debate intensifies"),
        _update(3001, 31, "Unrelated football score"),  # filtered by watch keywords
    ])
    monkeypatch.setattr(ingestion, "get_adapter", lambda platform: adapter)
    result = ingestion.run_ingestion(db, live_watch, "Telegram")

    assert result.status == "Connected"
    assert result.records_fetched == 1 and result.records_stored == 1
    run = db.scalar(
        select(IngestionRun).where(IngestionRun.watch_id == live_watch.id).order_by(IngestionRun.started_at.desc())
    )
    assert run is not None and run.platform == "Telegram" and run.records_new == 1


def test_bad_message_does_not_lose_the_batch(db, live_watch, monkeypatch):
    broken = {"update_id": 4000}  # no message payload at all
    adapter = FakeTelegram([broken, _update(4001, 40, "AI regulation hearing scheduled")])
    monkeypatch.setattr(ingestion, "get_adapter", lambda platform: adapter)
    result = ingestion.run_ingestion(db, live_watch, "Telegram")
    assert result.records_stored == 1
    assert adapter.offset == 4002


# ----------------------------------------------------------- end-to-end analysis
def test_live_post_reaches_analysis_and_timeline(db, live_watch, monkeypatch):
    adapter = FakeTelegram([
        _update(5000, 50, "Draft AI regulation is alarming and raises serious privacy risk", NOW - timedelta(hours=2)),
        _update(5001, 51, "AI regulation consultation welcomed by industry", NOW - timedelta(hours=1)),
    ])
    monkeypatch.setattr(ingestion, "get_adapter", lambda platform: adapter)
    result = ingestion.run_ingestion(db, live_watch, "Telegram")
    assert result.records_stored == 2

    stored = db.scalars(select(Post).where(Post.watch_id == live_watch.id)).all()
    assert all(p.source_mode == "live" and p.ingested_at is not None for p in stored)
    # the platform timestamp drives the timeline, not the ingestion time
    assert all(p.event_time.replace(tzinfo=timezone.utc) < p.ingested_at.replace(tzinfo=timezone.utc) for p in stored)

    labels = db.scalars(
        select(SentimentResult.label).where(SentimentResult.post_id.in_([p.id for p in stored]))
    ).all()
    assert len(labels) == 2 and "Unlabeled" not in labels

    response = timeline.build_timeline(db, live_watch, timestamp=NOW)
    assert response.mode == "live"
    assert response.evidence_summary, "live records must be traceable as evidence"
    assert any(item.platform == "Telegram" for item in response.evidence_summary)
