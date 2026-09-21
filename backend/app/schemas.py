"""Typed request/response models for the DRISHTI API."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

DataMode = Literal["demo", "live"]


class WatchCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    keywords: str = Field(default="", max_length=400)
    platforms: list[str] = Field(default_factory=lambda: ["X", "Telegram"])
    range_from: datetime
    range_to: datetime
    mode: DataMode = "demo"

    @field_validator("platforms")
    @classmethod
    def validate_platforms(cls, value: list[str]) -> list[str]:
        allowed = {"X", "Telegram", "Instagram", "Facebook", "Reddit", "YouTube"}
        invalid = [p for p in value if p not in allowed]
        if invalid:
            raise ValueError(f"Unsupported platforms: {', '.join(invalid)}")
        return value or ["X"]


class PlatformState(BaseModel):
    platform: str
    status: str
    detail: str


class WatchOut(BaseModel):
    id: str
    name: str
    keywords: str
    platforms: list[str]
    range_from: datetime
    range_to: datetime
    status: str
    mode: DataMode
    created_at: datetime
    last_ingestion_at: datetime | None = None
    last_analysis_at: datetime | None = None
    post_count: int = 0
    platform_states: list[PlatformState] = Field(default_factory=list)


class TimelineEventOut(BaseModel):
    id: str
    snapshot_index: int
    event_time: datetime
    kind: str
    label: str
    phase: str
    summary: str


class SentimentPoint(BaseModel):
    event_time: datetime
    label: str
    positive: float
    neutral: float
    negative: float


class SentimentSummary(BaseModel):
    positive: float
    neutral: float
    negative: float
    confidence: float
    change: float
    annotation: str
    engine: str
    analysis_source: Literal["Demo analysis", "Live analysis", "Mixed analysis"]
    unlabeled: int = 0
    series: list[SentimentPoint] = Field(default_factory=list)
    emotions: dict[str, float] = Field(default_factory=dict)


class TrendOut(BaseModel):
    topic: str
    mentions: int
    previous_mentions: int
    velocity: float
    rank: int
    event_time: datetime
    spark: list[int] = Field(default_factory=list)
    # RISING | STABLE | FALLING | EMERGING | INSUFFICIENT EVIDENCE
    classification: str = "INSUFFICIENT EVIDENCE"
    classification_note: str = ""


class NetworkNodeOut(BaseModel):
    id: str
    username: str
    platform: str
    community: str
    degree_centrality: float
    betweenness_centrality: float
    influence_score: float
    connections: int


class NetworkEdgeOut(BaseModel):
    id: str
    source: str
    target: str
    relationship_type: str
    weight: float


class NetworkOut(BaseModel):
    nodes: list[NetworkNodeOut] = Field(default_factory=list)
    edges: list[NetworkEdgeOut] = Field(default_factory=list)
    density: float = 0.0


class KolOut(BaseModel):
    account_id: str
    username: str
    platform: str
    label: str = "KOL candidate"
    influence_score: float
    degree_centrality: float
    betweenness_centrality: float
    connected_accounts: list[str]
    cross_community_links: int
    post_count: int
    total_engagement: int
    related_narratives: list[str]
    rationale: str
    confidence: str


class CohortOut(BaseModel):
    cohort: str
    percentage: float
    reportable: bool
    note: str = ""


class DemographicsOut(BaseModel):
    event_time: datetime
    min_reporting_threshold: float
    privacy_note: str
    dimensions: dict[str, list[CohortOut]]


class EvidenceOut(BaseModel):
    id: str
    watch_id: str
    platform: str
    account_id: str
    account_username: str
    text: str
    event_time: datetime
    engagement: int
    topic: str
    sentiment: str
    confidence: float
    stance: str
    source_mode: str


class CrossPlatformOut(BaseModel):
    platform: str
    mentions: int
    positive: float
    negative: float
    first_seen: datetime | None
    role: str
    share: float = 0.0


class NarrativeStepOut(BaseModel):
    """One observed step in the cross-platform sequence. Correlation, not causation."""

    stage: str
    platform: str
    detail: str
    event_time: datetime | None = None
    records: int = 0


class TimelineResponse(BaseModel):
    watch_id: str
    timestamp: datetime
    window_from: datetime
    window_to: datetime
    mode: DataMode
    events: list[TimelineEventOut]
    sentiment_series: list[SentimentPoint]
    sentiment: SentimentSummary
    emotion_summary: dict[str, float]
    top_trends: list[TrendOut]
    demographics: DemographicsOut
    network_snapshot: NetworkOut
    kol_candidates: list[KolOut]
    evidence_summary: list[EvidenceOut]
    cross_platform: list[CrossPlatformOut]
    narrative_movement: list[NarrativeStepOut] = Field(default_factory=list)
    notes: dict[str, str] = Field(default_factory=dict)
    at_this_moment: str


class AlertOut(BaseModel):
    id: str
    watch_id: str
    snapshot_index: int
    event_time: datetime
    alert_type: str
    detail: str
    severity: str
    topic: str | None = None
    account_id: str | None = None


class HistoryOut(BaseModel):
    id: str
    watch_id: str
    snapshot_index: int
    event_time: datetime
    event: str
    analyst: str
    status: str
    topic: str | None = None
    account_id: str | None = None


class ComponentHealth(BaseModel):
    component: str
    status: str
    detail: str
    last_operation: datetime | None = None
    record_count: int | None = None


class HealthResponse(BaseModel):
    api: ComponentHealth
    database: ComponentHealth
    adapters: list[ComponentHealth]
    analytics: list[ComponentHealth]
    assistant: ComponentHealth
    mode: DataMode
    live_available: bool
    message: str
    ingestion: "IngestionSummary | None" = None
    connectors: list["ConnectorState"] = Field(default_factory=list)


class IngestionRequest(BaseModel):
    watch_id: str
    query: str | None = None
    limit: int = Field(default=50, ge=1, le=100)
    payload: dict | list | None = None  # webhook delivery (Telegram)


class IngestionResult(BaseModel):
    platform: str
    status: str
    detail: str
    records_fetched: int
    records_stored: int
    analyzed: int
    records_duplicate: int = 0
    records_failed: int = 0
    last_ingestion_at: datetime | None = None
    mode: DataMode


class AssistantQuery(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    timestamp: datetime | None = None
    topic: str | None = None
    account_id: str | None = None


class Citation(BaseModel):
    ref: str
    evidence_id: str
    excerpt: str
    platform: str
    account_username: str
    event_time: datetime


class AssistantAnswer(BaseModel):
    answer: str
    citations: list[Citation]
    grounded: bool
    provider: str
    watch_id: str
    timestamp: datetime


# --------------------------------------------------------------------- Phase 4
class ConnectorState(BaseModel):
    platform: str
    status: str
    detail: str
    configured: bool = False
    enabled: bool = True
    schedule: str = "manual"
    identifier: str = ""  # masked only - never a secret
    last_ingestion: datetime | None = None
    last_success: datetime | None = None
    next_ingestion: datetime | None = None
    records_collected: int = 0
    last_error: str | None = None


class ConnectionTestOut(BaseModel):
    """Safe connection state only. Never carries a token or raw configuration."""

    platform: str
    configured: bool
    authenticated: bool
    source_reachable: bool
    source_accessible: bool = False  # Telegram wording
    api_accessible: bool = False  # X wording
    source_name: str = ""
    account: str = ""
    status: str
    identifier: str = ""
    last_message_time: datetime | None = None
    last_success: datetime | None = None
    error: str | None = None


class IngestionSourceResult(BaseModel):
    platform: str
    status: str
    detail: str
    records_found: int = 0
    records_new: int = 0
    records_duplicate: int = 0
    records_failed: int = 0


class IngestionJobResult(BaseModel):
    watch_id: str
    job_type: str = "ingest"
    mode: DataMode
    records_found: int = 0
    records_new: int = 0
    records_duplicate: int = 0
    records_failed: int = 0
    started_at: datetime
    completed_at: datetime
    sources: list[IngestionSourceResult] = Field(default_factory=list)
    message: str = ""


class BackfillRequest(BaseModel):
    from_time: datetime = Field(alias="from")
    to_time: datetime = Field(alias="to")
    platforms: list[str] | None = None

    model_config = {"populate_by_name": True}


class IngestionLogOut(BaseModel):
    id: str
    watch_id: str | None
    platform: str
    job_type: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    records_found: int
    records_new: int
    records_duplicate: int
    records_failed: int
    detail: str


class IngestionErrorOut(BaseModel):
    reason: str
    external_id: str | None = None
    detail: str = ""
    event_time: datetime | None = None


class IngestionRunDetail(IngestionLogOut):
    errors: list[IngestionErrorOut] = Field(default_factory=list)


class WatchUpdate(BaseModel):
    """Lifecycle and data-mode changes for an existing Watch."""

    status: Literal["Active", "Paused", "Archived", "Live ingestion", "Demo analysis"] | None = None
    mode: DataMode | None = None


class SchedulerState(BaseModel):
    enabled: bool
    interval: str  # manual | 5m | 15m | hourly
    last_ingestion: datetime | None = None
    next_ingestion: datetime | None = None
    status: str = "Idle"


class SchedulerUpdate(BaseModel):
    enabled: bool | None = None
    interval: Literal["manual", "5m", "15m", "hourly"] | None = None


class IngestionSummary(BaseModel):
    last_successful_run: datetime | None = None
    records_processed: int = 0
    records_rejected: int = 0
    duplicates: int = 0
    current_job: str = "Idle"


class WatchProvenance(BaseModel):
    watch_id: str
    mode: DataMode
    sources: list[ConnectorState]
    last_ingestion: datetime | None = None
    records: int = 0
    freshness: str = "Demo snapshot"


HealthResponse.model_rebuild()


# --------------------------------------------------------------------------- auth
class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    active: bool
    last_login_at: datetime | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=8, max_length=200)
    display_name: str = ""
    role: str = "analyst"


class AuthStatus(BaseModel):
    auth_required: bool
    users_provisioned: int
    roles: list[str]


# --------------------------------------------------------------------------- briefing
class BriefingOut(BaseModel):
    title: str
    watch_id: str
    watch_name: str
    keywords: list[str] = Field(default_factory=list)
    mode: str
    mode_label: str
    generated_at: datetime
    period_from: datetime
    period_to: datetime
    timestamp: datetime
    sources: list[str] = Field(default_factory=list)
    executive_summary: list[str] = Field(default_factory=list)
    narrative_movement: list["NarrativeStepOut"] = Field(default_factory=list)
    sentiment: "SentimentSummary"
    top_trends: list[TrendOut] = Field(default_factory=list)
    kol_candidates: list["KolOut"] = Field(default_factory=list)
    demographics: "DemographicsOut"
    cross_platform: list["CrossPlatformOut"] = Field(default_factory=list)
    evidence: list["EvidenceOut"] = Field(default_factory=list)
    events: list["TimelineEventOut"] = Field(default_factory=list)
    notes: dict[str, str] = Field(default_factory=dict)
    method_notes: list[str] = Field(default_factory=list)
    privacy_notes: list[str] = Field(default_factory=list)
