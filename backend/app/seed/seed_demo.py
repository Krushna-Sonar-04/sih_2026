"""Idempotent demo seeding: Demo Mode -> AI Regulation India, 01-14 Sep 2026."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..analytics import sentiment as sentiment_engine
from ..models import (
    Account,
    Alert,
    AnalysisHistory,
    DemographicAggregate,
    EmotionResult,
    NetworkEdge,
    Post,
    SentimentResult,
    TimelineEvent,
    Watch,
)
from . import demo_dataset as ds


def _aware(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def seed(db: Session, force: bool = False) -> dict:
    if force:
        for model in (
            EmotionResult, SentimentResult, Post, NetworkEdge, DemographicAggregate,
            TimelineEvent, Alert, AnalysisHistory, Account, Watch,
        ):
            db.query(model).delete()
        db.commit()

    if db.scalar(select(Watch).limit(1)) is not None:
        return {"seeded": False, "reason": "Demo data already present."}

    for aid, username, platform, community, influence, centrality, first, peak, rationale in ds.ACCOUNTS:
        db.add(
            Account(
                id=aid, platform=platform, username=username, display_name=username.lstrip("@"),
                community=community, influence_score=float(influence), centrality=float(centrality),
                first_observed=first, peak_activity=peak, rationale=rationale,
            )
        )

    db.flush()  # accounts must exist before posts/edges reference them (FK enforced on PostgreSQL)

    post_count = 0
    for widx, (wid, name, keywords, platforms, status) in enumerate(ds.WATCHES):
        allowed = platforms.split(",")
        db.add(
            Watch(
                id=wid, name=name, keywords=keywords, platforms=platforms,
                range_from=ds.ts(1, 0), range_to=ds.ts(14, 23, 59), status=status, mode="demo",
            )
        )
        db.flush()  # the watch row must exist before its dependent rows

        for index, event_time, phase, kind, label, summary in ds.SNAPSHOTS:
            db.add(
                TimelineEvent(
                    id=f"{wid}-event-{index}", watch_id=wid, event_time=event_time, kind=kind,
                    label=label, phase=phase, summary=summary, snapshot_index=index,
                )
            )
            for dimension, cohorts in ds.demographics_for(index).items():
                for cohort, percentage in cohorts.items():
                    db.add(
                        DemographicAggregate(
                            watch_id=wid, event_time=event_time, dimension=dimension,
                            cohort=cohort, percentage=float(percentage), sample_size=120 + index * 40,
                        )
                    )

        for eid, source, target, kind, weight, snap in ds.EDGES:
            db.add(
                NetworkEdge(
                    id=f"{wid}-{eid}", watch_id=wid, source_account=source, target_account=target,
                    relationship_type=kind, weight=float(weight), event_time=ds.SNAPSHOTS[snap][1],
                )
            )

        for pidx, (account, platform, topic, text, engagement, snap) in enumerate(ds.POSTS):
            if platform not in allowed:
                continue
            post_id = f"{wid}-post-{pidx + 1}"
            event_time = ds.SNAPSHOTS[snap][1]
            db.add(
                Post(
                    id=post_id, watch_id=wid, platform=platform, external_id=f"demo-{widx}-{pidx}",
                    account_id=account, text=text, event_time=event_time, engagement=engagement,
                    language="en", topic=topic, source_mode="demo",
                )
            )
            inference = sentiment_engine.analyze(text)
            result = SentimentResult(
                post_id=post_id, label=inference.label, confidence=inference.confidence,
                stance=inference.stance, engine=f"demo:{inference.engine}",
            )
            db.add(result)
            db.flush()
            for emotion, score in inference.emotions.items():
                db.add(EmotionResult(sentiment_id=result.id, emotion=emotion, score=score))
            post_count += 1

    for aid, wid, snap, alert_type, detail, severity, topic, account in ds.ALERTS:
        db.add(
            Alert(
                id=aid, watch_id=wid, event_time=ds.SNAPSHOTS[snap][1], snapshot_index=snap,
                alert_type=alert_type, detail=detail, severity=severity, topic=topic, account_id=account,
            )
        )

    for hid, wid, snap, event, analyst, status, topic, account in ds.HISTORY:
        db.add(
            AnalysisHistory(
                id=hid, watch_id=wid, event_time=ds.SNAPSHOTS[snap][1], snapshot_index=snap,
                event=event, analyst=analyst, status=status, topic=topic, account_id=account,
            )
        )

    db.commit()
    return {"seeded": True, "watches": len(ds.WATCHES), "posts": post_count}


LIVE_TEST_WATCH_ID = "telegram-live-test"


def ensure_live_test_watch(db: Session) -> bool:
    """Create the documented local live Watch — only when Telegram is configured.

    "AI Regulation India - Telegram Live Test" exists solely so a configured
    Telegram source has a Watch to ingest into. Without credentials it is never
    created, so the UI never shows a live Watch that cannot receive data.
    """
    from ..config import get_settings

    settings = get_settings()
    if not (settings.telegram_bot_token and settings.telegram_channel_id):
        return False
    if db.get(Watch, LIVE_TEST_WATCH_ID) is not None:
        return False
    db.add(
        Watch(
            id=LIVE_TEST_WATCH_ID,
            name="AI Regulation India - Telegram Live Test",
            keywords="AI regulation,privacy,policy",
            platforms="Telegram",
            # A live Watch collects current messages, so its range tracks "now".
            range_from=datetime.now(timezone.utc) - timedelta(days=7),
            range_to=datetime.now(timezone.utc) + timedelta(days=90),
            status="Live ingestion",
            mode="live",
        )
    )
    db.commit()
    return True
