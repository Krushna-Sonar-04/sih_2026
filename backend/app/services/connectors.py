"""Connector Center service.

Reports the real state of every platform connector and keeps the
platform_source records in sync. Secrets never leave the backend: only
"configured / not configured" plus a masked identifier are ever returned.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import schemas
from ..adapters import ADAPTERS, PLATFORM_PRIORITY, get_adapter, mask
from ..adapters import test_connection as adapter_test
from ..config import get_settings
from ..models import IngestionError, IngestionRun, PlatformSource, Post
from . import audit

INTERVALS = {"manual": None, "5m": 300, "15m": 900, "hourly": 3600}


def _identifier(platform: str) -> str:
    s = get_settings()
    if platform == "Telegram":
        return mask(s.telegram_bot_token)
    if platform == "X":
        return mask(s.x_bearer_token)
    return ""


def ensure_sources(db: Session) -> None:
    for platform in PLATFORM_PRIORITY:
        source_id = f"source-{platform.lower()}"
        if db.get(PlatformSource, source_id) is None:
            db.add(
                PlatformSource(
                    id=source_id, platform=platform, name=f"{platform} source",
                    enabled=platform in ("Telegram", "X"), status="Not configured",
                    schedule=get_settings().scheduler_interval,
                )
            )
    db.commit()


def _next_run(schedule: str, last: datetime | None, enabled: bool) -> datetime | None:
    seconds = INTERVALS.get(schedule)
    if not enabled or not seconds:
        return None
    base = last or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base + timedelta(seconds=seconds)


def connector_states(db: Session) -> list[schemas.ConnectorState]:
    ensure_sources(db)
    settings = get_settings()
    states: list[schemas.ConnectorState] = []

    for platform in PLATFORM_PRIORITY:
        adapter = ADAPTERS[platform]
        source = db.get(PlatformSource, f"source-{platform.lower()}")
        try:
            health = adapter.health()
            status, detail = health.status, health.detail
        except Exception as exc:  # isolation
            status, detail = "Error", str(exc)[:160]

        last_run = db.scalar(
            select(func.max(IngestionRun.completed_at)).where(
                IngestionRun.platform == platform, IngestionRun.status == "Connected"
            )
        )
        collected = db.scalar(
            select(func.count()).select_from(Post).where(Post.platform == platform, Post.source_mode == "live")
        ) or 0
        last_error = db.scalar(
            select(IngestionRun.detail)
            .where(IngestionRun.platform == platform, IngestionRun.status.notin_(["Connected", "Completed", "Not configured", "Planned"]))
            .order_by(IngestionRun.started_at.desc())
            .limit(1)
        )
        schedule = source.schedule if source else "manual"
        enabled = bool(source.enabled) if source else False

        if source is not None:
            source.status = status
            source.last_success = last_run or source.last_success
            source.records_collected = collected
            source.last_error = last_error
            source.configuration = f'{{"identifier":"{_identifier(platform)}"}}'
        states.append(
            schemas.ConnectorState(
                platform=platform, status=status, detail=detail,
                configured=adapter.is_configured(), enabled=enabled, schedule=schedule,
                identifier=_identifier(platform), last_ingestion=last_run, last_success=last_run,
                next_ingestion=_next_run(schedule, last_run, enabled and settings.ingestion_enabled),
                records_collected=collected, last_error=last_error,
            )
        )
    db.commit()
    return states


def test(db: Session, platform: str) -> schemas.ConnectionTestOut:
    result = adapter_test(platform)
    audit.record(db, "connector.test", f"{platform} connection test: {result.status}")
    return schemas.ConnectionTestOut(
        platform=result.platform, configured=result.configured, authenticated=result.authenticated,
        source_reachable=result.source_reachable, source_accessible=result.source_reachable,
        api_accessible=result.source_reachable, source_name=result.source_name, account=result.account,
        status=result.status, identifier=result.identifier,
        last_message_time=result.last_message_time, last_success=result.last_success, error=result.error,
    )


def ingestion_summary(db: Session) -> schemas.IngestionSummary:
    last = db.scalar(
        select(func.max(IngestionRun.completed_at)).where(IngestionRun.status.in_(["Connected", "Completed"]))
    )
    return schemas.IngestionSummary(
        last_successful_run=last,
        records_processed=db.scalar(select(func.coalesce(func.sum(IngestionRun.records_new), 0))) or 0,
        records_rejected=db.scalar(select(func.count()).select_from(IngestionError)) or 0,
        duplicates=db.scalar(select(func.coalesce(func.sum(IngestionRun.records_duplicate), 0))) or 0,
        current_job=db.scalar(
            select(IngestionRun.platform).where(IngestionRun.completed_at.is_(None)).limit(1)
        ) or "Idle",
    )


def scheduler_state(db: Session) -> schemas.SchedulerState:
    ensure_sources(db)
    settings = get_settings()
    source = db.get(PlatformSource, "source-telegram")
    schedule = source.schedule if source else settings.scheduler_interval
    last = db.scalar(select(func.max(IngestionRun.completed_at)))
    enabled = settings.ingestion_enabled and schedule != "manual"
    return schemas.SchedulerState(
        enabled=enabled, interval=schedule, last_ingestion=last,
        next_ingestion=_next_run(schedule, last, enabled),
        status="Scheduled" if enabled else "Manual",
    )


def update_scheduler(db: Session, payload: schemas.SchedulerUpdate) -> schemas.SchedulerState:
    ensure_sources(db)
    for source in db.scalars(select(PlatformSource)):
        if payload.interval is not None:
            source.schedule = payload.interval
        if payload.enabled is not None:
            source.enabled = payload.enabled
    db.commit()
    audit.record(db, "connector.configuration", f"Scheduler updated: {payload.model_dump(exclude_none=True)}")
    return scheduler_state(db)


def watch_provenance(db: Session, watch) -> schemas.WatchProvenance:
    platforms = [p.strip() for p in watch.platforms.split(",") if p.strip()]
    states = [s for s in connector_states(db) if s.platform in platforms]
    records = db.scalar(select(func.count()).select_from(Post).where(Post.watch_id == watch.id)) or 0
    live = db.scalar(
        select(func.count()).select_from(Post).where(Post.watch_id == watch.id, Post.source_mode == "live")
    ) or 0
    if live and watch.last_ingestion_at:
        minutes = int(
            (datetime.now(timezone.utc) - watch.last_ingestion_at.replace(tzinfo=timezone.utc)).total_seconds() // 60
        )
        freshness = f"Live · {minutes} min ago" if minutes else "Live · just now"
    else:
        freshness = "Demo snapshot"
    return schemas.WatchProvenance(
        watch_id=watch.id, mode="live" if live else "demo", sources=states,
        last_ingestion=watch.last_ingestion_at, records=records, freshness=freshness,
    )
