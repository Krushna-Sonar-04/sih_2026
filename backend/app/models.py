"""DRISHTI relational schema.

Every time-sensitive entity carries an event_time so that one shared timeline
can drive sentiment, trends, network, demographics and evidence.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Watch(Base):
    __tablename__ = "watch"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    keywords: Mapped[str] = mapped_column(String(400), default="")
    platforms: Mapped[str] = mapped_column(String(200), default="X,Telegram")  # comma separated
    range_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    range_to: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(60), default="Demo analysis")
    mode: Mapped[str] = mapped_column(String(20), default="demo")  # demo | live
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_ingestion_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_analysis_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    posts: Mapped[list["Post"]] = relationship(back_populates="watch", cascade="all, delete-orphan")


class Account(Base):
    __tablename__ = "account"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    platform: Mapped[str] = mapped_column(String(30))
    username: Mapped[str] = mapped_column(String(120))
    display_name: Mapped[str] = mapped_column(String(160), default="")
    community: Mapped[str] = mapped_column(String(120), default="Unassigned")
    influence_score: Mapped[float] = mapped_column(Float, default=0.0)
    centrality: Mapped[float] = mapped_column(Float, default=0.0)
    first_observed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    peak_activity: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rationale: Mapped[str] = mapped_column(Text, default="")


class Post(Base):
    __tablename__ = "post"
    __table_args__ = (
        UniqueConstraint("platform", "external_id", name="uq_post_platform_external"),
        Index("ix_post_watch_event_time", "watch_id", "event_time"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    watch_id: Mapped[str] = mapped_column(ForeignKey("watch.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(30), index=True)
    external_id: Mapped[str] = mapped_column(String(160))
    account_id: Mapped[str] = mapped_column(ForeignKey("account.id"), index=True)
    username: Mapped[str] = mapped_column(String(120), default="")
    display_name: Mapped[str] = mapped_column(String(160), default="")
    text: Mapped[str] = mapped_column(Text)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    engagement: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str] = mapped_column(String(30), default="en")
    topic: Mapped[str] = mapped_column(String(120), default="")
    reply_to: Mapped[str | None] = mapped_column(String(160), nullable=True)
    repost_of: Mapped[str | None] = mapped_column(String(160), nullable=True)
    mentions: Mapped[str] = mapped_column(String(400), default="")  # comma separated
    hashtags: Mapped[str] = mapped_column(String(400), default="")  # comma separated
    source_url: Mapped[str | None] = mapped_column(String(400), nullable=True)
    raw_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_mode: Mapped[str] = mapped_column(String(20), default="demo")  # demo | live
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    watch: Mapped[Watch] = relationship(back_populates="posts")
    sentiment: Mapped["SentimentResult | None"] = relationship(
        back_populates="post", cascade="all, delete-orphan", uselist=False
    )


class SentimentResult(Base):
    __tablename__ = "sentiment_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[str] = mapped_column(ForeignKey("post.id", ondelete="CASCADE"), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(20), default="Neutral")  # Positive | Neutral | Negative | Unlabeled
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    stance: Mapped[str] = mapped_column(String(30), default="Neutral")  # Support | Opposition | Neutral
    engine: Mapped[str] = mapped_column(String(40), default="demo")
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    post: Mapped[Post] = relationship(back_populates="sentiment")
    emotions: Mapped[list["EmotionResult"]] = relationship(
        back_populates="sentiment", cascade="all, delete-orphan"
    )


class EmotionResult(Base):
    __tablename__ = "emotion_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sentiment_id: Mapped[int] = mapped_column(ForeignKey("sentiment_result.id", ondelete="CASCADE"))
    emotion: Mapped[str] = mapped_column(String(30))  # Support|Opposition|Anxiety|Excitement|Sarcasm
    score: Mapped[float] = mapped_column(Float, default=0.0)

    sentiment: Mapped[SentimentResult] = relationship(back_populates="emotions")


class TrendTopic(Base):
    __tablename__ = "trend_topic"
    __table_args__ = (Index("ix_trend_watch_bucket_velocity", "watch_id", "event_time", "velocity_score"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    watch_id: Mapped[str] = mapped_column(ForeignKey("watch.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(120))
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    mentions: Mapped[int] = mapped_column(Integer, default=0)
    previous_mentions: Mapped[int] = mapped_column(Integer, default=0)
    velocity_score: Mapped[float] = mapped_column(Float, default=0.0)
    rank: Mapped[int] = mapped_column(Integer, default=0)


class NetworkEdge(Base):
    __tablename__ = "network_edge"
    __table_args__ = (
        Index("ix_edge_source_event_time", "source_account", "event_time"),
        Index("ix_edge_target_event_time", "target_account", "event_time"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    watch_id: Mapped[str] = mapped_column(ForeignKey("watch.id", ondelete="CASCADE"), index=True)
    source_account: Mapped[str] = mapped_column(ForeignKey("account.id"))
    target_account: Mapped[str] = mapped_column(ForeignKey("account.id"))
    relationship_type: Mapped[str] = mapped_column(String(30))  # reply|mention|repost|forward|cross-platform
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class DemographicAggregate(Base):
    """Aggregate only. No individual demographic label is ever stored."""

    __tablename__ = "demographic_aggregate"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    watch_id: Mapped[str] = mapped_column(ForeignKey("watch.id", ondelete="CASCADE"), index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    dimension: Mapped[str] = mapped_column(String(40))  # age_cohort|region|language|professional_interest
    cohort: Mapped[str] = mapped_column(String(80))
    percentage: Mapped[float] = mapped_column(Float, default=0.0)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)


class TimelineEvent(Base):
    __tablename__ = "timeline_event"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    watch_id: Mapped[str] = mapped_column(ForeignKey("watch.id", ondelete="CASCADE"), index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(160))
    phase: Mapped[str] = mapped_column(String(80), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    snapshot_index: Mapped[int] = mapped_column(Integer, default=0)


class Alert(Base):
    __tablename__ = "alert"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    watch_id: Mapped[str] = mapped_column(ForeignKey("watch.id", ondelete="CASCADE"), index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    snapshot_index: Mapped[int] = mapped_column(Integer, default=0)
    alert_type: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(30), default="Medium")
    topic: Mapped[str | None] = mapped_column(String(120), nullable=True)
    account_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)


class AnalysisHistory(Base):
    __tablename__ = "analysis_history"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    watch_id: Mapped[str] = mapped_column(ForeignKey("watch.id", ondelete="CASCADE"), index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    snapshot_index: Mapped[int] = mapped_column(Integer, default=0)
    event: Mapped[str] = mapped_column(String(160))
    analyst: Mapped[str] = mapped_column(String(80), default="Analyst")
    status: Mapped[str] = mapped_column(String(40), default="Saved")
    topic: Mapped[str | None] = mapped_column(String(120), nullable=True)
    account_id: Mapped[str | None] = mapped_column(String(80), nullable=True)


class AuditEvent(Base):
    """Lightweight auditable event log, structured for later expansion."""

    __tablename__ = "audit_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    actor: Mapped[str] = mapped_column(String(80), default="analyst")
    watch_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    # Tamper-evident chain: each record hashes its own content plus the
    # previous record hash. Credentials are never part of the detail text.
    prev_hash: Mapped[str] = mapped_column(String(64), default="")
    record_hash: Mapped[str] = mapped_column(String(64), default="")


class PlatformSource(Base):
    """Connector configuration state. Raw secrets are NEVER stored here."""

    __tablename__ = "platform_source"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    platform: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(40), default="Not configured")
    configuration: Mapped[str] = mapped_column(Text, default="{}")  # non-secret metadata only
    schedule: Mapped[str] = mapped_column(String(20), default="manual")  # manual|5m|15m|hourly
    last_success: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    records_collected: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class IngestionRun(Base):
    """Structured ingestion log entry for one platform within one job."""

    __tablename__ = "ingestion_run"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    watch_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    platform: Mapped[str] = mapped_column(String(30), index=True)
    job_type: Mapped[str] = mapped_column(String(20), default="ingest")  # ingest|backfill|webhook|scheduled
    status: Mapped[str] = mapped_column(String(30), default="Completed", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    records_found: Mapped[int] = mapped_column(Integer, default=0)
    records_new: Mapped[int] = mapped_column(Integer, default=0)
    records_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str] = mapped_column(Text, default="")


class IngestionError(Base):
    """Validation and adapter failures are recorded, never silently discarded."""

    __tablename__ = "ingestion_error"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    watch_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    platform: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(String(120))
    external_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class IngestionCursor(Base):
    """Durable ingestion cursor, e.g. the Telegram getUpdates offset.

    Persisting the offset means a restart never re-ingests updates that were
    already processed. No credential is ever stored here.
    """

    __tablename__ = "ingestion_cursor"

    platform: Mapped[str] = mapped_column(String(30), primary_key=True)
    cursor: Mapped[str] = mapped_column(String(120), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class User(Base):
    """Local analyst account. Passwords are stored only as PBKDF2 hashes."""

    __tablename__ = "app_user"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160), default="")
    role: Mapped[str] = mapped_column(String(30), default="analyst")  # analyst|lead_analyst|admin
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PostEmbedding(Base):
    """Cached retrieval embedding for a stored post.

    `content_hash` prevents re-embedding unchanged text. The vector is stored
    as JSON so the same code path runs on SQLite and PostgreSQL; with pgvector
    installed the column can be migrated to `vector` without touching callers.
    """

    __tablename__ = "post_embedding"

    post_id: Mapped[str] = mapped_column(ForeignKey("post.id", ondelete="CASCADE"), primary_key=True)
    watch_id: Mapped[str] = mapped_column(String(80), index=True)
    model_name: Mapped[str] = mapped_column(String(120), default="")
    dimensions: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    vector: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
