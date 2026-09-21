"""Timeline aggregation: one Watch + one timestamp -> every analytical vector.

This is the shared-clock contract. All analytical views in the frontend read
from this single computation so sentiment, trends, network, demographics and
evidence can never drift apart.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..analytics import demographics as demo_engine
from ..analytics import kol as kol_engine
from ..analytics import network as network_engine
from ..analytics import sentiment as sentiment_engine
from ..analytics import trends as trend_engine
from ..config import get_settings
from ..models import (
    Account,
    DemographicAggregate,
    EmotionResult,
    NetworkEdge,
    Post,
    SentimentResult,
    TimelineEvent,
    Watch,
)
from .. import schemas

WINDOW = timedelta(hours=36)
settings = get_settings()


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class _TimeView:
    """Read-only view of an ORM row with a timezone-aware event_time.

    SQLite returns naive datetimes; the analytics engines compare against the
    aware selected timestamp, so rows are normalised before they are passed in.
    """

    __slots__ = ("_row", "event_time")

    def __init__(self, row) -> None:
        self._row = row
        self.event_time = _aware(getattr(row, "event_time", None))

    def __getattr__(self, name: str):
        return getattr(self._row, name)


def get_events(db: Session, watch_id: str) -> list[TimelineEvent]:
    return list(
        db.scalars(select(TimelineEvent).where(TimelineEvent.watch_id == watch_id).order_by(TimelineEvent.event_time))
    )


def resolve_timestamp(
    db: Session, watch: Watch, timestamp: datetime | None, snapshot: int | None
) -> tuple[datetime, list[TimelineEvent]]:
    events = get_events(db, watch.id)
    if timestamp is not None:
        return _aware(timestamp), events
    if snapshot is not None and events:
        index = max(0, min(snapshot, len(events) - 1))
        return _aware(events[index].event_time), events
    if events:
        return _aware(events[min(3, len(events) - 1)].event_time), events
    return _aware(watch.range_to) or datetime.now(timezone.utc), events


def posts_until(db: Session, watch_id: str, at: datetime, platforms: list[str] | None = None) -> list[Post]:
    stmt = select(Post).where(Post.watch_id == watch_id).order_by(Post.event_time)
    posts = [p for p in db.scalars(stmt) if _aware(p.event_time) <= at]
    if platforms:
        posts = [p for p in posts if p.platform in platforms]
    return posts


def sentiment_summary(db: Session, posts: list[Post], at: datetime) -> schemas.SentimentSummary:
    window_posts = [p for p in posts if _aware(p.event_time) >= at - WINDOW]
    previous_posts = [p for p in posts if at - 2 * WINDOW <= _aware(p.event_time) < at - WINDOW]

    def distribution(items: list[Post]) -> tuple[float, float, float, float, int, list[str]]:
        if not items:
            return 0.0, 0.0, 0.0, 0.0, 0, []
        labels: list[str] = []
        confidences: list[float] = []
        unlabeled = 0
        engines: list[str] = []
        for post in items:
            result = post.sentiment
            if result is None or result.label == "Unlabeled":
                unlabeled += 1
                continue
            labels.append(result.label)
            confidences.append(result.confidence)
            engines.append(result.engine)
        total = len(labels) or 1
        pos = round(100 * labels.count("Positive") / total, 1)
        neu = round(100 * labels.count("Neutral") / total, 1)
        neg = round(100 * labels.count("Negative") / total, 1)
        conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
        return pos, neu, neg, conf, unlabeled, engines

    pos, neu, neg, conf, unlabeled, engines = distribution(window_posts)
    ppos, _, pneg, _, _, _ = distribution(previous_posts)
    change = round(neg - pneg, 1)

    # emotion aggregation over the same window
    emotion_totals: dict[str, float] = {e: 0.0 for e in sentiment_engine.EMOTIONS}
    counted = 0
    for post in window_posts:
        if post.sentiment is None:
            continue
        counted += 1
        for emotion in post.sentiment.emotions:
            emotion_totals[emotion.emotion] = emotion_totals.get(emotion.emotion, 0.0) + emotion.score
    emotions = {k: round(100 * v / max(counted, 1), 1) for k, v in emotion_totals.items()}

    # series across the whole history up to `at`
    series: list[schemas.SentimentPoint] = []
    by_day: dict[str, list[Post]] = {}
    for post in posts:
        key = _aware(post.event_time).strftime("%Y-%m-%d %H:00")
        by_day.setdefault(key, []).append(post)
    for key in sorted(by_day):
        p, n, g, _, _, _ = distribution(by_day[key])
        stamp = datetime.strptime(key, "%Y-%m-%d %H:00").replace(tzinfo=timezone.utc)
        dominant = max((("Positive", p), ("Neutral", n), ("Negative", g)), key=lambda x: x[1])[0]
        series.append(schemas.SentimentPoint(event_time=stamp, label=dominant, positive=p, neutral=n, negative=g))

    modes = {p.source_mode for p in window_posts}
    if modes == {"live"}:
        source = "Live analysis"
    elif "live" in modes:
        source = "Mixed analysis"
    else:
        source = "Demo analysis"

    annotation = (
        f"Negative sentiment {'increased' if change > 0 else 'decreased' if change < 0 else 'held steady'} "
        f"by {abs(change)} points. Change compared with the previous analysis interval."
    )

    return schemas.SentimentSummary(
        positive=pos, neutral=neu, negative=neg, confidence=conf, change=change,
        annotation=annotation, engine=engines[0] if engines else sentiment_engine.ENGINE,
        analysis_source=source, unlabeled=unlabeled, series=series, emotions=emotions,
    )


def demographics_at(db: Session, watch_id: str, at: datetime) -> schemas.DemographicsOut:
    rows = list(db.scalars(select(DemographicAggregate).where(DemographicAggregate.watch_id == watch_id)))
    rows = [r for r in rows if _aware(r.event_time) <= at]
    if rows:
        latest = max(_aware(r.event_time) for r in rows)
        rows = [r for r in rows if _aware(r.event_time) == latest]
    else:
        latest = at
    grouped = demo_engine.aggregate(rows, settings.min_cohort_percentage)
    return schemas.DemographicsOut(
        event_time=latest,
        min_reporting_threshold=settings.min_cohort_percentage,
        privacy_note=(
            "Aggregate, anonymized cohort estimates only. No individual demographic attributes are stored "
            f"or returned. Cohorts below {settings.min_cohort_percentage}% are suppressed."
        ),
        dimensions={
            dim: [schemas.CohortOut(**vars(v)) for v in values] for dim, values in grouped.items()
        },
    )


def network_at(db: Session, watch_id: str, at: datetime):
    edges = list(db.scalars(select(NetworkEdge).where(NetworkEdge.watch_id == watch_id)))
    views = [_TimeView(e) for e in edges if _aware(e.event_time) <= at]
    accounts = list(db.scalars(select(Account)))
    return network_engine.analyze_network(views, accounts, at)


def evidence_at(
    db: Session,
    watch_id: str,
    at: datetime,
    topic: str | None = None,
    account_id: str | None = None,
    limit: int = 12,
) -> list[schemas.EvidenceOut]:
    posts = posts_until(db, watch_id, at)
    accounts = {a.id: a for a in db.scalars(select(Account))}
    if topic:
        posts = [p for p in posts if p.topic == topic]
    if account_id:
        posts = [p for p in posts if p.account_id == account_id]
    posts.sort(key=lambda p: _aware(p.event_time), reverse=True)
    out = []
    for post in posts[:limit]:
        result = post.sentiment
        out.append(
            schemas.EvidenceOut(
                id=post.id, watch_id=post.watch_id, platform=post.platform, account_id=post.account_id,
                account_username=getattr(accounts.get(post.account_id), "username", post.account_id),
                text=post.text, event_time=_aware(post.event_time), engagement=post.engagement,
                topic=post.topic, sentiment=result.label if result else "Unlabeled",
                confidence=result.confidence if result else 0.0,
                stance=result.stance if result else "Neutral", source_mode=post.source_mode,
            )
        )
    return out


def cross_platform(posts: list[Post]) -> list[schemas.CrossPlatformOut]:
    grouped: dict[str, list[Post]] = {}
    for post in posts:
        grouped.setdefault(post.platform, []).append(post)
    out = []
    first_seen_overall = {
        platform: min(_aware(p.event_time) for p in group) for platform, group in grouped.items()
    }
    earliest = min(first_seen_overall.values(), default=None)
    total_posts = len(posts) or 1
    for platform, group in grouped.items():
        labels = [p.sentiment.label for p in group if p.sentiment]
        total = len(labels) or 1
        first_seen = first_seen_overall[platform]
        role = "Early discussion" if earliest and first_seen == earliest else "Amplification"
        out.append(
            schemas.CrossPlatformOut(
                platform=platform, mentions=len(group),
                positive=round(100 * labels.count("Positive") / total, 1),
                negative=round(100 * labels.count("Negative") / total, 1),
                first_seen=first_seen, role=role,
                share=round(100 * len(group) / total_posts, 1),
            )
        )
    out.sort(key=lambda c: -c.mentions)
    return out


def narrative_movement(
    platforms: list[schemas.CrossPlatformOut],
    network: schemas.NetworkOut,
    sentiment: schemas.SentimentSummary,
) -> list[schemas.NarrativeStepOut]:
    """Observed sequence across platforms.

    Every step is backed by stored records. Wording stays correlational -
    adjacency in time is never reported as causation.
    """
    if len(platforms) < 2:
        return []
    ordered = sorted(
        [p for p in platforms if p.first_seen is not None], key=lambda p: (p.first_seen, -p.mentions)
    )
    steps: list[schemas.NarrativeStepOut] = []
    for index, item in enumerate(ordered):
        steps.append(
            schemas.NarrativeStepOut(
                stage="Observed first activity" if index == 0 else "Associated later activity",
                platform=item.platform,
                detail=(
                    f"{item.mentions} stored record(s), {item.share}% of activity in this window."
                ),
                event_time=item.first_seen,
                records=item.mentions,
            )
        )
    if network.edges:
        steps.append(
            schemas.NarrativeStepOut(
                stage="Network spread",
                platform="Cross-platform",
                detail=(
                    f"{len(network.edges)} observed relationship(s) between "
                    f"{len(network.nodes)} accounts in the same window."
                ),
                records=len(network.edges),
            )
        )
    if sentiment.change:
        direction = "more negative" if sentiment.change > 0 else "less negative"
        steps.append(
            schemas.NarrativeStepOut(
                stage="Sentiment shift",
                platform="Cross-platform",
                detail=(
                    f"Cross-platform correlation: negative share moved {abs(sentiment.change)} points "
                    f"({direction}) over the same period."
                ),
                records=0,
            )
        )
    return steps


def build_timeline(
    db: Session,
    watch: Watch,
    timestamp: datetime | None = None,
    snapshot: int | None = None,
    platforms: list[str] | None = None,
) -> schemas.TimelineResponse:
    at, events = resolve_timestamp(db, watch, timestamp, snapshot)
    posts = posts_until(db, watch.id, at, platforms)

    sentiment = sentiment_summary(db, posts, at)
    trends = trend_engine.compute_trends([_TimeView(p) for p in posts], at, WINDOW)
    network_snapshot = network_at(db, watch.id, at)
    kols = kol_engine.score_kols(network_snapshot, posts)
    demographics = demographics_at(db, watch.id, at)
    evidence = evidence_at(db, watch.id, at)
    current_event = next((e for e in reversed(events) if _aware(e.event_time) <= at), None)

    network_out = schemas.NetworkOut(
        nodes=[schemas.NetworkNodeOut(**vars(n)) for n in network_snapshot.nodes],
        edges=[schemas.NetworkEdgeOut(**e) for e in network_snapshot.edges],
        density=network_snapshot.density,
    )
    platform_split = cross_platform(posts)

    # Honest data notes: never manufacture a trend or a relationship.
    notes: dict[str, str] = {}
    if not trends or all(t.previous_mentions == 0 for t in trends):
        notes["trends"] = "Insufficient historical data for a velocity comparison in this window."
    if not network_out.edges:
        notes["network"] = "Insufficient relationship data: no reply, mention, forward or reference observed."
    if not posts:
        notes["records"] = "No stored records for this Watch in the selected window."

    return schemas.TimelineResponse(
        watch_id=watch.id,
        timestamp=at,
        window_from=at - WINDOW,
        window_to=at,
        mode=watch.mode,
        events=[
            schemas.TimelineEventOut(
                id=e.id, snapshot_index=e.snapshot_index, event_time=_aware(e.event_time), kind=e.kind,
                label=e.label, phase=e.phase, summary=e.summary,
            )
            for e in events
        ],
        sentiment_series=sentiment.series,
        sentiment=sentiment,
        emotion_summary=sentiment.emotions,
        top_trends=[
            schemas.TrendOut(
                topic=t.topic, mentions=t.mentions, previous_mentions=t.previous_mentions,
                velocity=t.velocity, rank=t.rank, event_time=t.event_time, spark=t.spark,
                classification=t.classification, classification_note=t.classification_note,
            )
            for t in trends
        ],
        demographics=demographics,
        network_snapshot=network_out,
        kol_candidates=[schemas.KolOut(**vars(k)) for k in kols],
        evidence_summary=evidence,
        cross_platform=platform_split,
        narrative_movement=narrative_movement(platform_split, network_out, sentiment),
        notes=notes,
        at_this_moment=(
            current_event.summary if current_event else "Monitoring baseline for the selected watch."
        ),
    )
