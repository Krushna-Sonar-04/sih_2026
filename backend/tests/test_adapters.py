"""Adapter and ingestion tests. Fixtures only - no live credentials required.

Live calls are performed only when LIVE_CONNECTOR_TEST=true is set explicitly,
which these tests never do.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_drishti.db")
os.environ.setdefault("SEED_DEMO_DATA", "false")

from app.adapters.base import PermanentAuthError, RateLimitError, with_retries  # noqa: E402
from app.adapters.telegram_bot import TelegramBotAdapter  # noqa: E402
from app.adapters.telegram_normalizer import CommonTelegramNormalizer  # noqa: E402
from app.adapters.x_adapter import XAdapter, XNormalizer  # noqa: E402
from app.services import ingestion  # noqa: E402

TELEGRAM_UPDATE = {
    "update_id": 900001,
    "channel_post": {
        "message_id": 4242,
        "date": 1789000000,
        "chat": {"id": -100123, "title": "Policy Watch", "username": "policywatch"},
        "text": "New #AIRegulation draft raises privacy risk, says @DataRightsIndia",
        "views": 1200,
    },
}

X_TWEET = {
    "id": "1799990000",
    "author_id": "77",
    "created_at": "2026-09-08T14:30:00.000Z",
    "text": "Draft #AIRegulation is vague on enforcement. @DataRightsIndia",
    "lang": "en",
    "public_metrics": {"like_count": 10, "retweet_count": 4, "reply_count": 2, "quote_count": 1},
    "entities": {"mentions": [{"username": "DataRightsIndia"}], "hashtags": [{"tag": "AIRegulation"}]},
    "referenced_tweets": [{"type": "replied_to", "id": "1799980000"}],
}
X_USERS = {"77": {"id": "77", "username": "aaravintel", "name": "Aarav Intel"}}


# ------------------------------------------------------------------ normalization
def test_telegram_normalization_preserves_platform_timestamp():
    post = CommonTelegramNormalizer.from_bot_update(TELEGRAM_UPDATE)
    assert post.platform == "Telegram"
    assert post.external_id == "4242"
    assert post.account_username == "@policywatch"
    assert post.event_time == datetime.fromtimestamp(1789000000, tz=timezone.utc)
    assert post.engagement == 1200
    assert "@DataRightsIndia" in post.mentions
    assert "#AIRegulation" in post.hashtags
    assert post.source_url == "https://t.me/policywatch/4242"


def test_telegram_mtproto_uses_the_same_schema():
    post = CommonTelegramNormalizer.from_mtproto_message(
        {"id": 7, "channel": "policywatch", "message": "AI regulation debate", "date": datetime(2026, 9, 8, 12, 0)}
    )
    assert post.platform == "Telegram"
    assert post.external_id == "7"
    assert post.event_time.tzinfo is not None


def test_x_normalization():
    post = XNormalizer().normalize(X_TWEET, X_USERS)
    assert post.platform == "X"
    assert post.account_username == "@aaravintel"
    assert post.engagement == 17
    assert post.reply_to == "1799980000"
    assert post.source_url == "https://x.com/aaravintel/status/1799990000"
    assert post.event_time.isoformat().startswith("2026-09-08T14:30")


def test_shared_schema_validation():
    telegram = CommonTelegramNormalizer.from_bot_update(TELEGRAM_UPDATE)
    x_post = XNormalizer().normalize(X_TWEET, X_USERS)
    for post in (telegram, x_post):
        assert ingestion.validate(post) is None
    telegram.text = ""
    assert ingestion.validate(telegram) == "missing text"
    x_post.platform = "Nowhere"
    assert ingestion.validate(x_post) == "invalid platform"


# --------------------------------------------------------------- duplicate handling
def _watch(db):
    from app.models import Watch

    watch = Watch(
        id="watch-test", name="Test", keywords="AI regulation",
        platforms="X,Telegram", range_from=datetime(2026, 9, 1, tzinfo=timezone.utc),
        range_to=datetime(2026, 9, 14, tzinfo=timezone.utc), mode="live",
    )
    db.add(watch)
    db.commit()
    return watch


@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    from app import database
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    database.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        yield session


def test_telegram_duplicate_handling(db_session):
    watch = _watch(db_session)
    post = CommonTelegramNormalizer.from_bot_update(TELEGRAM_UPDATE)
    new, dup, failed, _ = ingestion.store_posts(db_session, watch, [post])
    assert (new, dup, failed) == (1, 0, 0)
    new, dup, failed, _ = ingestion.store_posts(db_session, watch, [post])
    assert (new, dup, failed) == (0, 1, 0)


def test_x_duplicate_handling_and_timestamp_preservation(db_session):
    watch = _watch(db_session)
    post = XNormalizer().normalize(X_TWEET, X_USERS)
    ingestion.store_posts(db_session, watch, [post])
    ingestion.store_posts(db_session, watch, [post])

    from app.models import Post

    stored = db_session.query(Post).filter(Post.platform == "X").all()
    assert len(stored) == 1
    assert stored[0].event_time.replace(tzinfo=timezone.utc).isoformat().startswith("2026-09-08T14:30")
    assert stored[0].ingested_at is not None


def test_invalid_records_are_logged_not_discarded(db_session):
    watch = _watch(db_session)
    broken = CommonTelegramNormalizer.from_bot_update(TELEGRAM_UPDATE)
    broken.text = ""
    new, dup, failed, _ = ingestion.store_posts(db_session, watch, [broken], run_id="run-1", platform="Telegram")
    assert failed == 1

    from app.models import IngestionError

    assert db_session.query(IngestionError).count() == 1


# ------------------------------------------------------------------ failure modes
def test_authentication_failures_are_not_retried():
    calls = {"count": 0}

    def _fail():
        calls["count"] += 1
        raise PermanentAuthError("Telegram rejected the bot token.")

    with pytest.raises(PermanentAuthError):
        with_retries(_fail, attempts=3, base_delay=0)
    assert calls["count"] == 1


def test_transient_failures_are_retried():
    calls = {"count": 0}

    def _flaky():
        calls["count"] += 1
        if calls["count"] < 2:
            raise TimeoutError("network")
        return "ok"

    assert with_retries(_flaky, attempts=3, base_delay=0) == "ok"


def test_x_rate_limit_surfaces(monkeypatch):
    adapter = XAdapter()
    monkeypatch.setattr(adapter.settings, "x_bearer_token", "test-token")

    def _rate_limited(_params):
        raise RateLimitError("Rate limit reached. Retrying later.")

    monkeypatch.setattr(adapter, "_search", _rate_limited)
    with pytest.raises(RateLimitError):
        adapter.fetch_posts("AI regulation")
    assert adapter.health().status == "Rate limited"


def test_unconfigured_adapters_report_not_configured():
    telegram = TelegramBotAdapter()
    telegram.settings.telegram_bot_token = ""
    assert telegram.fetch_posts("AI regulation") == []
    assert telegram.test_connection().status == "Not configured"
