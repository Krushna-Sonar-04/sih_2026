"""Phase 6 tests: live-mode behaviour with mocked platform APIs.

No test requires or uses a real credential. Every external call is replaced by
a fixture, so `pytest` never reaches Telegram or X.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import pytest

from app.adapters.base import PermanentAuthError, RateLimitError
from app.adapters.telegram_bot import TelegramBotAdapter
from app.adapters.x_adapter import XAdapter, XConnectionTester, XNormalizer
from app.models import Account, IngestionRun, Post, Watch
from app.services import ingestion, timeline as timeline_service

NOW = datetime.now(timezone.utc)

X_PAYLOAD = {
    "data": [
        {
            "id": "1900000001",
            "author_id": "11",
            "created_at": (NOW - timedelta(hours=3)).isoformat().replace("+00:00", "Z"),
            "text": "The draft AI regulation raises serious privacy risk. @DataRightsIndia",
            "lang": "en",
            "public_metrics": {"like_count": 6, "retweet_count": 3, "reply_count": 1, "quote_count": 0},
            "entities": {"mentions": [{"username": "DataRightsIndia"}], "hashtags": [{"tag": "AIRegulation"}]},
        }
    ],
    "includes": {"users": [{"id": "11", "username": "aaravintel", "name": "Aarav Intel"}]},
}

TELEGRAM_UPDATES = {
    "ok": True,
    "result": [
        {
            "update_id": 5001,
            "channel_post": {
                "message_id": 11,
                "date": int((NOW - timedelta(hours=2)).timestamp()),
                "chat": {"id": -100999, "title": "Policy Watch", "username": "policywatch"},
                "text": "AI regulation debate continues in the committee.",
                "views": 300,
            },
        }
    ],
}


def x_payload(external_id: str) -> dict:
    """Same fixture with a unique external id, so each test starts clean."""
    payload = copy.deepcopy(X_PAYLOAD)
    payload["data"][0]["id"] = external_id
    return payload


def telegram_updates(update_id: int, message_id: int) -> dict:
    payload = copy.deepcopy(TELEGRAM_UPDATES)
    payload["result"][0]["update_id"] = update_id
    payload["result"][0]["channel_post"]["message_id"] = message_id
    return payload


def _live_watch(db, watch_id: str, platforms: str) -> Watch:
    watch = Watch(
        id=watch_id, name=f"Live {watch_id}", keywords="AI regulation,privacy",
        platforms=platforms, range_from=NOW - timedelta(days=2), range_to=NOW + timedelta(days=2),
        status="Active", mode="live",
    )
    db.add(watch)
    db.commit()
    return watch


# ------------------------------------------------------------------------- X API
def _x_adapter(monkeypatch, payload):
    adapter = XAdapter()
    monkeypatch.setattr(adapter.settings, "x_bearer_token", "fixture-token", raising=False)
    monkeypatch.setattr(adapter, "_search", lambda params: payload if not isinstance(payload, Exception) else (_ for _ in ()).throw(payload))
    return adapter


def test_x_connection_test_reports_connected_only_on_success(monkeypatch):
    adapter = _x_adapter(monkeypatch, X_PAYLOAD)
    result = XConnectionTester(adapter).test()
    assert result.configured and result.authenticated and result.source_reachable
    assert result.status == "Connected"
    assert "fixture" not in result.identifier  # masked, never the raw token
    assert result.source_name == "X API v2 recent search"


def test_x_connection_test_unauthorized(monkeypatch):
    adapter = _x_adapter(monkeypatch, PermanentAuthError("X authentication failed."))
    result = XConnectionTester(adapter).test()
    assert result.status == "Unauthorized"
    assert result.authenticated is False


def test_x_connection_test_not_configured():
    result = XConnectionTester(XAdapter()).test()
    assert result.status == "Not configured"
    assert result.authenticated is False


def test_x_rate_limit_is_surfaced_not_retried_as_success(monkeypatch):
    adapter = _x_adapter(monkeypatch, RateLimitError("Rate limit reached. Retrying later."))
    with pytest.raises(RateLimitError):
        adapter.fetch_posts("AI regulation")
    assert adapter.health().status == "Rate limited"


def test_x_ingestion_stores_and_deduplicates(db, monkeypatch):
    watch = _live_watch(db, "watch-x-live", "X")
    adapter = _x_adapter(monkeypatch, X_PAYLOAD)
    monkeypatch.setattr("app.services.ingestion.get_adapter", lambda platform: adapter)

    first = ingestion.run_ingestion(db, watch, "X")
    assert first.status == "Connected"
    assert first.records_stored == 1

    second = ingestion.run_ingestion(db, watch, "X")
    assert second.records_stored == 0
    assert second.records_duplicate == 1
    assert db.query(Post).filter(Post.watch_id == watch.id).count() == 1


def test_x_post_preserves_event_time_and_source_url(db, monkeypatch):
    watch = _live_watch(db, "watch-x-times", "X")
    adapter = _x_adapter(monkeypatch, x_payload("1900000002"))
    monkeypatch.setattr("app.services.ingestion.get_adapter", lambda platform: adapter)
    ingestion.run_ingestion(db, watch, "X")
    post = db.query(Post).filter(Post.watch_id == watch.id).one()
    assert post.source_url == "https://x.com/aaravintel/status/1900000002"
    assert post.event_time.replace(tzinfo=timezone.utc) < post.ingested_at.replace(tzinfo=timezone.utc)
    assert post.source_mode == "live"


# ------------------------------------------------------- cross-platform normalization
def test_cross_platform_records_share_one_schema_and_timeline(db, monkeypatch):
    watch = _live_watch(db, "watch-cross", "X,Telegram")

    x_adapter = _x_adapter(monkeypatch, x_payload("1900000003"))
    tg = TelegramBotAdapter()
    monkeypatch.setattr(tg.settings, "telegram_bot_token", "fixture-token", raising=False)
    monkeypatch.setattr(tg.settings, "telegram_channel_id", "@policywatch", raising=False)
    monkeypatch.setattr(tg, "_call", lambda method, params=None, timeout=25.0: telegram_updates(5003, 13))
    monkeypatch.setattr(
        "app.services.ingestion.get_adapter", lambda platform: x_adapter if platform == "X" else tg
    )

    job = ingestion.ingest_watch(db, watch)
    assert job.records_new == 2
    posts = db.query(Post).filter(Post.watch_id == watch.id).all()
    assert {p.platform for p in posts} == {"X", "Telegram"}
    # identical canonical shape regardless of platform
    for post in posts:
        assert post.external_id and post.account_id and post.text and post.event_time
        assert post.ingested_at is not None

    result = timeline_service.build_timeline(db, watch, timestamp=NOW + timedelta(minutes=5))
    platforms = {c.platform for c in result.cross_platform}
    assert platforms == {"X", "Telegram"}
    assert sum(c.mentions for c in result.cross_platform) == 2
    assert result.narrative_movement  # observed sequence backed by records
    assert result.evidence_summary


def test_timeline_reports_insufficient_data_instead_of_inventing_it(db, monkeypatch):
    watch = _live_watch(db, "watch-thin", "Telegram")
    tg = TelegramBotAdapter()
    monkeypatch.setattr(tg.settings, "telegram_bot_token", "fixture-token", raising=False)
    monkeypatch.setattr(tg.settings, "telegram_channel_id", "@policywatch", raising=False)
    monkeypatch.setattr(tg, "_call", lambda method, params=None, timeout=25.0: telegram_updates(5004, 14))
    monkeypatch.setattr("app.services.ingestion.get_adapter", lambda platform: tg)
    ingestion.run_ingestion(db, watch, "Telegram")

    result = timeline_service.build_timeline(db, watch, timestamp=NOW + timedelta(minutes=5))
    assert result.notes.get("network", "").startswith("Insufficient relationship data")
    assert result.narrative_movement == []  # only one platform: no cross-platform claim


# ------------------------------------------------------------------ live isolation
def test_live_watch_evidence_never_includes_other_watches(db, monkeypatch):
    other = Watch(
        id="watch-demo-other", name="Demo other", keywords="AI regulation", platforms="X",
        range_from=NOW - timedelta(days=2), range_to=NOW + timedelta(days=2), status="Active", mode="demo",
    )
    db.add(other)
    db.add(Account(id="acct-demo", platform="X", username="@demoacct", display_name="Demo"))
    db.commit()
    db.add(
        Post(
            id="demo-post-1", watch_id=other.id, platform="X", external_id="demo-1", account_id="acct-demo",
            username="@demoacct", text="Demo dataset record about AI regulation", event_time=NOW - timedelta(hours=1),
            source_mode="demo",
        )
    )
    db.commit()

    watch = _live_watch(db, "watch-live-isolated", "X")
    adapter = _x_adapter(monkeypatch, x_payload("1900000005"))
    monkeypatch.setattr("app.services.ingestion.get_adapter", lambda platform: adapter)
    ingestion.run_ingestion(db, watch, "X")

    evidence = timeline_service.evidence_at(db, watch.id, NOW + timedelta(minutes=5))
    assert evidence, "live watch must have its own evidence"
    assert all(item.watch_id == watch.id for item in evidence)
    assert all("Demo dataset record" not in item.text for item in evidence)


# ------------------------------------------------------------------- lifecycle
def test_paused_watch_does_not_ingest(db, monkeypatch):
    watch = _live_watch(db, "watch-paused", "X")
    watch.status = "Paused"
    db.commit()
    adapter = _x_adapter(monkeypatch, X_PAYLOAD)
    monkeypatch.setattr("app.services.ingestion.get_adapter", lambda platform: adapter)

    result = ingestion.run_ingestion(db, watch, "X")
    assert result.status == "Paused"
    assert db.query(Post).filter(Post.watch_id == watch.id).count() == 0


def test_records_outside_the_watch_range_are_flagged_not_silently_dropped(db, monkeypatch):
    watch = Watch(
        id="watch-range", name="Range bound", keywords="AI regulation", platforms="X",
        range_from=NOW - timedelta(days=400), range_to=NOW - timedelta(days=380), status="Active", mode="live",
    )
    db.add(watch)
    db.commit()
    adapter = _x_adapter(monkeypatch, X_PAYLOAD)
    monkeypatch.setattr("app.services.ingestion.get_adapter", lambda platform: adapter)

    result = ingestion.run_ingestion(db, watch, "X")
    assert result.records_stored == 0
    assert result.records_failed == 1
    run = db.query(IngestionRun).filter(IngestionRun.watch_id == watch.id).one()
    assert run.records_failed == 1


def test_x_failure_does_not_stop_telegram(db, monkeypatch):
    watch = _live_watch(db, "watch-isolation", "X,Telegram")
    failing_x = _x_adapter(monkeypatch, PermanentAuthError("X authentication failed."))
    tg = TelegramBotAdapter()
    monkeypatch.setattr(tg.settings, "telegram_bot_token", "fixture-token", raising=False)
    monkeypatch.setattr(tg.settings, "telegram_channel_id", "@policywatch", raising=False)
    monkeypatch.setattr(tg, "_call", lambda method, params=None, timeout=25.0: telegram_updates(5006, 16))
    monkeypatch.setattr(
        "app.services.ingestion.get_adapter", lambda platform: failing_x if platform == "X" else tg
    )

    job = ingestion.ingest_watch(db, watch)
    statuses = {s.platform: s.status for s in job.sources}
    assert statuses["X"] == "Unauthorized"
    assert statuses["Telegram"] == "Connected"
    assert job.records_new == 1
