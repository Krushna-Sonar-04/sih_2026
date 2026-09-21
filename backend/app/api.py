"""DRISHTI API routes.

Every analytical endpoint resolves the same Watch + timestamp through the
shared timeline service, so no view can drift from the selected clock.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import schemas, security
from .adapters import ADAPTERS, adapter_health, get_adapter
from .config import get_settings
from .database import get_db
from .models import Alert, AnalysisHistory, AuditEvent, IngestionError, IngestionRun, Post, User, Watch
from .services import assistant as assistant_service
from .services import auth as auth_service
from .services import briefing as briefing_service
from .services import audit, connectors, health as health_service, ingestion, timeline as timeline_service

router = APIRouter(prefix="/api")


# --------------------------------------------------------------------------- helpers
def _load_watch(db: Session, watch_id: str) -> Watch:
    watch = db.get(Watch, watch_id)
    if watch is None:
        raise HTTPException(status_code=404, detail=f"Watch '{watch_id}' not found.")
    return watch


def _platform_states(platforms: list[str]) -> list[schemas.PlatformState]:
    states = []
    for platform in platforms:
        adapter = get_adapter(platform)
        if adapter is None:
            states.append(schemas.PlatformState(platform=platform, status="Unavailable", detail="No adapter registered."))
            continue
        state = adapter.health()
        states.append(schemas.PlatformState(platform=platform, status=state.status, detail=state.detail))
    return states


def _watch_out(db: Session, watch: Watch) -> schemas.WatchOut:
    platforms = [p.strip() for p in watch.platforms.split(",") if p.strip()]
    count = db.scalar(select(func.count()).select_from(Post).where(Post.watch_id == watch.id)) or 0
    return schemas.WatchOut(
        id=watch.id, name=watch.name, keywords=watch.keywords, platforms=platforms,
        range_from=watch.range_from, range_to=watch.range_to, status=watch.status, mode=watch.mode,
        created_at=watch.created_at, last_ingestion_at=watch.last_ingestion_at,
        last_analysis_at=watch.last_analysis_at, post_count=count,
        platform_states=_platform_states(platforms),
    )


# --------------------------------------------------------------------------- watches
@router.post("/watches", tags=["Watches"], response_model=schemas.WatchOut, status_code=201)
def create_watch(payload: schemas.WatchCreate, db: Session = Depends(get_db)) -> schemas.WatchOut:
    if payload.range_to < payload.range_from:
        raise HTTPException(status_code=422, detail="range_to must be on or after range_from.")
    watch = Watch(
        id=f"watch-{uuid.uuid4().hex[:10]}", name=payload.name.strip(), keywords=payload.keywords.strip(),
        platforms=",".join(payload.platforms), range_from=payload.range_from, range_to=payload.range_to,
        status="Active", mode=payload.mode,
    )
    db.add(watch)
    db.commit()
    db.refresh(watch)
    audit.record(db, "watch.created", f"Watch '{watch.name}' created in {watch.mode} mode.", watch.id)
    return _watch_out(db, watch)


@router.get("/watches", tags=["Watches"], response_model=list[schemas.WatchOut])
def list_watches(db: Session = Depends(get_db)) -> list[schemas.WatchOut]:
    watches = db.scalars(select(Watch).order_by(Watch.created_at.desc())).all()
    return [_watch_out(db, w) for w in watches]


@router.patch("/watches/{watch_id}", tags=["Watches"], response_model=schemas.WatchOut)
def update_watch(
    watch_id: str, payload: schemas.WatchUpdate, db: Session = Depends(get_db)
) -> schemas.WatchOut:
    """Lifecycle (Active / Paused / Archived) and Demo <-> Live mode changes.

    Live Mode is refused when no connector is actually configured, so the UI can
    never display Live while only demo records exist.
    """
    watch = _load_watch(db, watch_id)
    if payload.mode == "live":
        platforms = [p.strip() for p in watch.platforms.split(",") if p.strip()]
        configured = [p for p in platforms if (get_adapter(p) is not None and get_adapter(p).is_configured())]
        if not configured:
            raise HTTPException(
                status_code=409,
                detail="Live integrations are not configured. Demo Mode remains available.",
            )
    if payload.mode is not None:
        watch.mode = payload.mode
    if payload.status is not None:
        watch.status = payload.status
    db.commit()
    db.refresh(watch)
    audit.record(db, "watch.updated", f"Watch '{watch.name}' set to {watch.status} / {watch.mode}.", watch.id)
    return _watch_out(db, watch)


@router.get("/watches/{watch_id}", tags=["Watches"], response_model=schemas.WatchOut)
def get_watch(watch_id: str, db: Session = Depends(get_db)) -> schemas.WatchOut:
    return _watch_out(db, _load_watch(db, watch_id))


# --------------------------------------------------------------------------- timeline
@router.get("/watches/{watch_id}/timeline", tags=["Timeline"], response_model=schemas.TimelineResponse)
def get_timeline(
    watch_id: str,
    timestamp: datetime | None = None,
    snapshot: int | None = Query(default=None, ge=0),
    platforms: str | None = None,
    db: Session = Depends(get_db),
) -> schemas.TimelineResponse:
    watch = _load_watch(db, watch_id)
    selected = [p.strip() for p in platforms.split(",")] if platforms else None
    return timeline_service.build_timeline(db, watch, timestamp, snapshot, selected)


@router.get("/watches/{watch_id}/sentiment", tags=["Sentiment"], response_model=schemas.SentimentSummary)
def get_sentiment(
    watch_id: str, timestamp: datetime | None = None, snapshot: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
) -> schemas.SentimentSummary:
    return get_timeline(watch_id, timestamp, snapshot, None, db).sentiment


@router.get("/watches/{watch_id}/trends", tags=["Trends"], response_model=list[schemas.TrendOut])
def get_trends(
    watch_id: str, timestamp: datetime | None = None, snapshot: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
) -> list[schemas.TrendOut]:
    return get_timeline(watch_id, timestamp, snapshot, None, db).top_trends


@router.get("/watches/{watch_id}/network", tags=["Network & Influence"], response_model=schemas.NetworkOut)
def get_network(
    watch_id: str, timestamp: datetime | None = None, snapshot: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
) -> schemas.NetworkOut:
    return get_timeline(watch_id, timestamp, snapshot, None, db).network_snapshot


@router.get("/watches/{watch_id}/kols", tags=["Network & Influence"], response_model=list[schemas.KolOut])
def get_kols(
    watch_id: str, timestamp: datetime | None = None, snapshot: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
) -> list[schemas.KolOut]:
    return get_timeline(watch_id, timestamp, snapshot, None, db).kol_candidates


@router.get("/watches/{watch_id}/demographics", tags=["Demographics"], response_model=schemas.DemographicsOut)
def get_demographics(
    watch_id: str, timestamp: datetime | None = None, snapshot: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
) -> schemas.DemographicsOut:
    return get_timeline(watch_id, timestamp, snapshot, None, db).demographics


@router.get("/watches/{watch_id}/evidence", tags=["Evidence"], response_model=list[schemas.EvidenceOut])
def get_evidence(
    watch_id: str,
    timestamp: datetime | None = None,
    snapshot: int | None = Query(default=None, ge=0),
    topic: str | None = None,
    account_id: str | None = None,
    limit: int = Query(default=12, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[schemas.EvidenceOut]:
    watch = _load_watch(db, watch_id)
    at, _ = timeline_service.resolve_timestamp(db, watch, timestamp, snapshot)
    return timeline_service.evidence_at(db, watch.id, at, topic, account_id, limit)


@router.get("/watches/{watch_id}/cross-platform", tags=["Timeline"], response_model=list[schemas.CrossPlatformOut])
def get_cross_platform(
    watch_id: str, timestamp: datetime | None = None, snapshot: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
) -> list[schemas.CrossPlatformOut]:
    return get_timeline(watch_id, timestamp, snapshot, None, db).cross_platform


# --------------------------------------------------------------------------- assistant
@router.post("/watches/{watch_id}/assistant/query", tags=["Assistant"], response_model=schemas.AssistantAnswer)
def assistant_query(
    watch_id: str,
    payload: schemas.AssistantQuery,
    request: Request,
    snapshot: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    user: User | None = Depends(auth_service.require_role("analyst")),
) -> schemas.AssistantAnswer:
    watch = _load_watch(db, watch_id)
    client = auth_service.actor_name(user)
    if client == "anonymous":
        client = request.client.host if request.client else "local"
    if not assistant_service.rate_limit_ok(client):
        raise HTTPException(
            status_code=429, detail="Assistant rate limit reached. Please retry in a moment."
        )
    result = assistant_service.answer(db, watch, payload, snapshot)
    audit.record(db, "assistant.query", payload.question[:160], watch.id, auth_service.actor_name(user))
    return result


# --------------------------------------------------------------------------- ingestion
@router.post("/watches/{watch_id}/refresh", tags=["Ingestion"], response_model=list[schemas.IngestionResult])
def refresh_watch(watch_id: str, db: Session = Depends(get_db)) -> list[schemas.IngestionResult]:
    return ingestion.refresh_watch(db, _load_watch(db, watch_id))


@router.post("/ingestion/x", tags=["Ingestion"], response_model=schemas.IngestionResult)
def ingest_x(payload: schemas.IngestionRequest, db: Session = Depends(get_db)) -> schemas.IngestionResult:
    watch = _load_watch(db, payload.watch_id)
    return ingestion.run_ingestion(db, watch, "X", payload.query, payload.limit)


@router.post("/ingestion/telegram", tags=["Ingestion"], response_model=schemas.IngestionResult)
def ingest_telegram(payload: schemas.IngestionRequest, db: Session = Depends(get_db)) -> schemas.IngestionResult:
    watch = _load_watch(db, payload.watch_id)
    return ingestion.run_ingestion(db, watch, "Telegram", payload.query, payload.limit, payload.payload)


# --------------------------------------------------------------------------- alerts / history
@router.get("/alerts", tags=["Alerts"], response_model=list[schemas.AlertOut])
def list_alerts(watch_id: str | None = None, db: Session = Depends(get_db)) -> list[schemas.AlertOut]:
    stmt = select(Alert).order_by(Alert.event_time.desc())
    if watch_id:
        stmt = stmt.where(Alert.watch_id == watch_id)
    return [
        schemas.AlertOut(
            id=a.id, watch_id=a.watch_id, snapshot_index=a.snapshot_index, event_time=a.event_time,
            alert_type=a.alert_type, detail=a.detail, severity=a.severity, topic=a.topic, account_id=a.account_id,
        )
        for a in db.scalars(stmt)
    ]


@router.get("/history", tags=["History"], response_model=list[schemas.HistoryOut])
def list_history(watch_id: str | None = None, db: Session = Depends(get_db)) -> list[schemas.HistoryOut]:
    stmt = select(AnalysisHistory).order_by(AnalysisHistory.event_time.desc())
    if watch_id:
        stmt = stmt.where(AnalysisHistory.watch_id == watch_id)
    return [
        schemas.HistoryOut(
            id=h.id, watch_id=h.watch_id, snapshot_index=h.snapshot_index, event_time=h.event_time,
            event=h.event, analyst=h.analyst, status=h.status, topic=h.topic, account_id=h.account_id,
        )
        for h in db.scalars(stmt)
    ]


# --------------------------------------------------------------------------- health
@router.get("/system-health", tags=["System Health"], response_model=schemas.HealthResponse)
def system_health(db: Session = Depends(get_db)) -> schemas.HealthResponse:
    return health_service.build_health(db)


@router.get("/health", tags=["System Health"], response_model=schemas.HealthResponse)
def health(db: Session = Depends(get_db)) -> schemas.HealthResponse:
    """Non-sensitive health summary - never exposes credentials or secrets."""
    return health_service.build_health(db)


@router.get("/adapters", tags=["Connectors"], response_model=list[schemas.PlatformState])
def list_adapters(db: Session = Depends(get_db)) -> list[schemas.PlatformState]:
    live_posts = db.scalar(select(func.count()).select_from(Post).where(Post.source_mode == "live")) or 0
    return [
        schemas.PlatformState(platform=h.platform, status=h.status, detail=h.detail)
        for h in adapter_health(demo_mode=live_posts == 0)
    ]


# --------------------------------------------------------------------------- connectors
@router.get("/connectors", tags=["Connectors"], response_model=list[schemas.ConnectorState])
def list_connectors(db: Session = Depends(get_db)) -> list[schemas.ConnectorState]:
    """Connector Center state. Never returns tokens - only configured state and a masked identifier."""
    return connectors.connector_states(db)


@router.post("/connectors/telegram/test", tags=["Connectors"], response_model=schemas.ConnectionTestOut)
def test_telegram(db: Session = Depends(get_db)) -> schemas.ConnectionTestOut:
    return connectors.test(db, "Telegram")


@router.post("/connectors/x/test", tags=["Connectors"], response_model=schemas.ConnectionTestOut)
def test_x(db: Session = Depends(get_db)) -> schemas.ConnectionTestOut:
    return connectors.test(db, "X")


@router.post("/connectors/{platform}/test", tags=["Connectors"], response_model=schemas.ConnectionTestOut)
def test_connector(platform: str, db: Session = Depends(get_db)) -> schemas.ConnectionTestOut:
    if platform not in ADAPTERS:
        raise HTTPException(status_code=404, detail=f"No connector registered for '{platform}'.")
    return connectors.test(db, platform)


@router.get("/scheduler", tags=["Ingestion"], response_model=schemas.SchedulerState)
def get_scheduler(db: Session = Depends(get_db)) -> schemas.SchedulerState:
    return connectors.scheduler_state(db)


@router.put("/scheduler", tags=["Ingestion"], response_model=schemas.SchedulerState)
def put_scheduler(payload: schemas.SchedulerUpdate, db: Session = Depends(get_db)) -> schemas.SchedulerState:
    return connectors.update_scheduler(db, payload)


# --------------------------------------------------------------------------- ingestion jobs
@router.post("/watches/{watch_id}/ingest", tags=["Ingestion"], response_model=schemas.IngestionJobResult)
def ingest_watch(
    watch_id: str,
    platforms: str | None = None,
    db: Session = Depends(get_db),
) -> schemas.IngestionJobResult:
    watch = _load_watch(db, watch_id)
    selected = [p.strip() for p in platforms.split(",") if p.strip()] if platforms else None
    return ingestion.ingest_watch(db, watch, selected)


@router.post("/watches/{watch_id}/backfill", tags=["Ingestion"], response_model=schemas.IngestionJobResult)
def backfill_watch(
    watch_id: str, payload: schemas.BackfillRequest, db: Session = Depends(get_db)
) -> schemas.IngestionJobResult:
    watch = _load_watch(db, watch_id)
    if payload.to_time < payload.from_time:
        raise HTTPException(status_code=422, detail="'to' must be on or after 'from'.")
    return ingestion.backfill_watch(db, watch, payload.from_time, payload.to_time, payload.platforms)


@router.get("/watches/{watch_id}/provenance", tags=["Ingestion"], response_model=schemas.WatchProvenance)
def watch_provenance(watch_id: str, db: Session = Depends(get_db)) -> schemas.WatchProvenance:
    return connectors.watch_provenance(db, _load_watch(db, watch_id))


@router.get("/ingestion/logs", tags=["Ingestion"], response_model=list[schemas.IngestionLogOut])
def ingestion_logs(
    platform: str | None = None,
    watch_id: str | None = None,
    status: str | None = None,
    since: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[schemas.IngestionLogOut]:
    stmt = select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(limit)
    if platform:
        stmt = stmt.where(IngestionRun.platform == platform)
    if watch_id:
        stmt = stmt.where(IngestionRun.watch_id == watch_id)
    if status:
        stmt = stmt.where(IngestionRun.status == status)
    if since:
        stmt = stmt.where(IngestionRun.started_at >= since)
    return [
        schemas.IngestionLogOut(
            id=r.id, watch_id=r.watch_id, platform=r.platform, job_type=r.job_type, status=r.status,
            started_at=r.started_at, completed_at=r.completed_at, records_found=r.records_found,
            records_new=r.records_new, records_duplicate=r.records_duplicate,
            records_failed=r.records_failed, detail=r.detail,
        )
        for r in db.scalars(stmt)
    ]


@router.get("/ingestion/logs/{run_id}", tags=["Ingestion"], response_model=schemas.IngestionRunDetail)
def ingestion_log_detail(run_id: str, db: Session = Depends(get_db)) -> schemas.IngestionRunDetail:
    run = db.get(IngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Ingestion run '{run_id}' not found.")
    errors = db.scalars(
        select(IngestionError).where(IngestionError.run_id == run_id).order_by(IngestionError.created_at)
    ).all()
    return schemas.IngestionRunDetail(
        id=run.id, watch_id=run.watch_id, platform=run.platform, job_type=run.job_type, status=run.status,
        started_at=run.started_at, completed_at=run.completed_at, records_found=run.records_found,
        records_new=run.records_new, records_duplicate=run.records_duplicate,
        records_failed=run.records_failed, detail=run.detail,
        errors=[
            schemas.IngestionErrorOut(
                reason=e.reason, external_id=e.external_id, detail=e.detail, event_time=e.created_at
            )
            for e in errors
        ],
    )


# --------------------------------------------------------------------------- webhooks
@router.post("/webhooks/telegram", tags=["Ingestion"])
async def telegram_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    """Optional deployment path. Polling remains the default for local development."""
    settings = get_settings()
    if settings.telegram_webhook_secret:
        header = request.headers.get("x-telegram-bot-api-secret-token", "")
        if header != settings.telegram_webhook_secret:
            raise HTTPException(status_code=401, detail="Invalid webhook secret token.")
    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed webhook payload.")
    watch = db.scalars(select(Watch).where(Watch.mode == "live").limit(1)).first() or db.scalars(
        select(Watch).limit(1)
    ).first()
    if watch is None:
        raise HTTPException(status_code=404, detail="No Watch configured to receive updates.")
    result = ingestion.run_ingestion(db, watch, "Telegram", payload=update, job_type="webhook")
    return {"ok": True, "records_new": result.records_stored, "status": result.status}


# --------------------------------------------------------------------------- authentication
@router.get("/auth/status", tags=["Auth"], response_model=schemas.AuthStatus)
def auth_status(db: Session = Depends(get_db)) -> schemas.AuthStatus:
    settings = get_settings()
    return schemas.AuthStatus(
        auth_required=settings.auth_required,
        users_provisioned=auth_service.user_count(db),
        roles=list(security.ROLES),
    )


@router.post("/auth/login", tags=["Auth"], response_model=schemas.TokenOut)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)) -> schemas.TokenOut:
    user = auth_service.authenticate(db, payload.email, payload.password)
    if user is None:
        audit.record(db, "auth.login_failed", f"email={payload.email[:80]}", None, payload.email[:80])
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token, expires = auth_service.issue_token(user)
    audit.record(db, "auth.login", f"role={user.role}", None, user.email)
    return schemas.TokenOut(
        access_token=token,
        expires_in=expires,
        user=schemas.UserOut(
            id=user.id, email=user.email, display_name=user.display_name,
            role=user.role, active=user.active, last_login_at=user.last_login_at,
        ),
    )


@router.get("/auth/me", tags=["Auth"], response_model=schemas.UserOut)
def me(user: User | None = Depends(auth_service.current_user)) -> schemas.UserOut:
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return schemas.UserOut(
        id=user.id, email=user.email, display_name=user.display_name,
        role=user.role, active=user.active, last_login_at=user.last_login_at,
    )


@router.get("/auth/users", tags=["Auth"], response_model=list[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User | None = Depends(auth_service.require_role("admin")),
) -> list[schemas.UserOut]:
    return [
        schemas.UserOut(
            id=u.id, email=u.email, display_name=u.display_name,
            role=u.role, active=u.active, last_login_at=u.last_login_at,
        )
        for u in db.scalars(select(User).order_by(User.created_at))
    ]


@router.post("/auth/users", tags=["Auth"], response_model=schemas.UserOut, status_code=201)
def create_user(
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
    actor: User | None = Depends(auth_service.require_role("admin")),
) -> schemas.UserOut:
    try:
        user = auth_service.create_user(
            db, payload.email, payload.password, payload.role, payload.display_name
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit.record(db, "auth.user_created", f"{user.email} role={user.role}", None, auth_service.actor_name(actor))
    return schemas.UserOut(
        id=user.id, email=user.email, display_name=user.display_name,
        role=user.role, active=user.active, last_login_at=user.last_login_at,
    )


# --------------------------------------------------------------------------- audit log (admin)
@router.get("/audit", tags=["Audit"])
def audit_log(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User | None = Depends(auth_service.require_role("admin")),
) -> list[dict]:
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit))
    return [
        {
            "id": r.id,
            "created_at": r.created_at,
            "action": r.action,
            "actor": r.actor,
            "watch_id": r.watch_id,
            "detail": r.detail,
            "record_hash": r.record_hash,
            "prev_hash": r.prev_hash,
        }
        for r in rows
    ]


# --------------------------------------------------------------------------- briefing export
@router.get("/watches/{watch_id}/briefing", tags=["Export"], response_model=schemas.BriefingOut)
def watch_briefing(
    watch_id: str,
    timestamp: datetime | None = None,
    snapshot: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    user: User | None = Depends(auth_service.require_role("analyst")),
) -> schemas.BriefingOut:
    watch = _load_watch(db, watch_id)
    brief = briefing_service.build_briefing(db, watch, timestamp, snapshot)
    audit.record(db, "export.generated", "Narrative intelligence brief", watch.id, auth_service.actor_name(user))
    return brief
