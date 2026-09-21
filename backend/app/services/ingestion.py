"""Ingestion pipeline.

    Watch -> resolve adapters -> fetch -> normalize -> validate -> deduplicate
          -> persist -> analyze (sentiment, edges) -> shared timeline

One failing adapter never stops the others, demo records always stay available,
and every record keeps the platform's own event_time alongside ingested_at.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas
from ..adapters import (
    HistoryUnsupported,
    NormalizedPost,
    PermanentAuthError,
    RateLimitError,
    get_adapter,
    get_telegram_history_adapter,
)
from ..analytics import sentiment as sentiment_engine
from ..models import (
    Account,
    IngestionCursor,
    EmotionResult,
    IngestionError,
    IngestionRun,
    NetworkEdge,
    Post,
    SentimentResult,
    Watch,
)
from . import audit

VALID_PLATFORMS = {"X", "Telegram", "Instagram", "Facebook", "Reddit", "YouTube"}


# --------------------------------------------------------------- ingestion cursor
def load_cursor(db: Session, platform: str) -> int | None:
    """Durable getUpdates offset, so a restart never replays processed updates."""
    row = db.get(IngestionCursor, platform)
    if row is None or not row.cursor:
        return None
    try:
        return int(row.cursor)
    except ValueError:
        return None


def save_cursor(db: Session, platform: str, value: int | None) -> None:
    if value is None:
        return
    row = db.get(IngestionCursor, platform)
    if row is None:
        db.add(IngestionCursor(platform=platform, cursor=str(value)))
    else:
        row.cursor = str(value)
        row.updated_at = datetime.now(timezone.utc)
    db.commit()


def _account_id(username: str, platform: str) -> str:
    return hashlib.sha1(f"{platform}:{username.lower()}".encode()).hexdigest()[:16]


def _ensure_account(db: Session, platform: str, username: str, display_name: str = "") -> str:
    account_id = _account_id(username, platform)
    if db.get(Account, account_id) is None:
        db.add(
            Account(
                id=account_id, platform=platform, username=username,
                display_name=display_name or username, community="Observed",
            )
        )
    return account_id


def _classify_topic(text: str, keywords: str) -> str:
    lowered = text.lower()
    for keyword in [k.strip() for k in keywords.split(",") if k.strip()]:
        if keyword.lower() in lowered:
            return keyword.title()
    return "Unclassified"


# --------------------------------------------------------------------- validation
def validate(item: NormalizedPost, watch: Watch | None = None) -> str | None:
    """Return a rejection reason, or None when the record is acceptable."""
    if item.platform not in VALID_PLATFORMS:
        return "invalid platform"
    if not item.external_id or not str(item.external_id).strip():
        return "invalid external id"
    if not item.text or not item.text.strip():
        return "missing text"
    if not isinstance(item.event_time, datetime):
        return "missing timestamp"
    if watch is not None:
        event_time = item.event_time if item.event_time.tzinfo else item.event_time.replace(tzinfo=timezone.utc)
        start, end = _aware(watch.range_from), _aware(watch.range_to)
        if start and end and not (start <= event_time <= end):
            return "outside watch date range"
    return None


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


# ------------------------------------------------------------------- lifecycle
PAUSED_STATES = {"paused", "archived", "disabled"}


def watch_accepts_ingestion(watch: Watch) -> str | None:
    """Return a reason when the Watch must not ingest, else None."""
    status = (watch.status or "").strip().lower()
    if status in PAUSED_STATES:
        return f"Watch is {status}. Ingestion is not run while the Watch is {status}."
    return None


def _log_error(db: Session, run_id: str, watch_id: str, platform: str, reason: str, external_id: str | None, detail: str = "") -> None:
    db.add(
        IngestionError(
            run_id=run_id, watch_id=watch_id, platform=platform, reason=reason,
            external_id=str(external_id)[:160] if external_id else None, detail=detail[:400],
        )
    )


# ------------------------------------------------------------------------ persist
def store_posts(
    db: Session, watch: Watch, normalized: list[NormalizedPost], run_id: str = "", platform: str = ""
) -> tuple[int, int, int, int]:
    """Returns (new, duplicate, failed, analyzed)."""
    new = duplicate = failed = analyzed = 0
    now = datetime.now(timezone.utc)

    for item in normalized:
        reason = validate(item, watch)
        if reason:
            failed += 1
            _log_error(db, run_id, watch.id, platform or item.platform, reason, item.external_id, item.text[:120])
            continue

        existing = db.scalar(
            select(Post).where(Post.platform == item.platform, Post.external_id == item.external_id)
        )
        if existing is not None:
            existing.last_seen = now
            if item.engagement > existing.engagement:
                existing.engagement = item.engagement
            duplicate += 1
            continue

        account_id = _ensure_account(db, item.platform, item.account_username, item.account_display_name)
        post_id = f"{watch.id}-{item.platform.lower()}-{item.external_id}"
        db.add(
            Post(
                id=post_id, watch_id=watch.id, platform=item.platform, external_id=str(item.external_id),
                account_id=account_id, username=item.account_username, display_name=item.account_display_name,
                text=item.text, event_time=item.event_time, engagement=item.engagement, language=item.language,
                topic=_classify_topic(item.text, watch.keywords),
                reply_to=item.reply_to, repost_of=item.repost_of,
                mentions=",".join(item.mentions)[:400], hashtags=",".join(item.hashtags)[:400],
                source_url=item.source_url, raw_reference=item.raw_reference,
                source_mode="live", ingested_at=now, first_seen=now, last_seen=now,
            )
        )
        new += 1

        # incremental analysis: only the newly stored record is inferred
        try:
            inference = sentiment_engine.analyze(item.text)
            result = SentimentResult(
                post_id=post_id, label=inference.label, confidence=inference.confidence,
                stance=inference.stance, engine=f"live:{inference.engine}",
            )
            db.add(result)
            db.flush()
            for emotion, score in inference.emotions.items():
                db.add(EmotionResult(sentiment_id=result.id, emotion=emotion, score=score))
            analyzed += 1
        except Exception as exc:
            db.add(SentimentResult(post_id=post_id, label="Unlabeled", confidence=0.0, engine="failed"))
            _log_error(db, run_id, watch.id, item.platform, "sentiment inference failed", item.external_id, str(exc))

        for relation in item.relationships:
            target_username = relation.get("target")
            if not target_username:
                continue
            target_id = _ensure_account(db, item.platform, str(target_username))
            edge_id = f"{watch.id}-{account_id}-{target_id}-{relation.get('type')}"
            if db.get(NetworkEdge, edge_id) is None:
                db.add(
                    NetworkEdge(
                        id=edge_id, watch_id=watch.id, source_account=account_id, target_account=target_id,
                        relationship_type=str(relation.get("type", "mention")), weight=1.0,
                        event_time=item.event_time,
                    )
                )

    db.commit()
    return new, duplicate, failed, analyzed


# ---------------------------------------------------------------- single platform
def run_ingestion(
    db: Session, watch: Watch, platform: str, query: str | None = None, limit: int = 50,
    payload: dict | list | None = None, job_type: str = "ingest",
) -> schemas.IngestionResult:
    adapter = get_adapter(platform)
    started = datetime.now(timezone.utc)
    run_id = f"run-{uuid.uuid4().hex[:12]}"

    def finish(status: str, detail: str, found=0, new=0, dup=0, failed=0, analyzed=0) -> schemas.IngestionResult:
        completed = datetime.now(timezone.utc)
        db.add(
            IngestionRun(
                id=run_id, watch_id=watch.id, platform=platform, job_type=job_type, status=status,
                started_at=started, completed_at=completed, records_found=found, records_new=new,
                records_duplicate=dup, records_failed=failed, detail=detail[:400],
            )
        )
        db.commit()
        return schemas.IngestionResult(
            platform=platform, status=status, detail=detail, records_fetched=found,
            records_stored=new, analyzed=analyzed, last_ingestion_at=completed, mode=watch.mode,
            records_duplicate=dup, records_failed=failed,
        )

    blocked = watch_accepts_ingestion(watch)
    if blocked:
        return finish("Paused", blocked)
    if adapter is None:
        return finish("Unavailable", f"No adapter registered for {platform}.")
    if not adapter.is_configured():
        health = adapter.health()
        return finish(health.status, health.detail)

    try:
        if payload is not None and platform == "Telegram":
            updates = payload if isinstance(payload, list) else [payload]
            normalized = [adapter.normalize_post(u) for u in updates]
        else:
            # restore the persisted Telegram offset before polling
            if platform == "Telegram" and getattr(adapter, "offset", None) is None:
                adapter.offset = load_cursor(db, platform)
            normalized = adapter.fetch_posts(query or watch.keywords, limit)
            if platform == "Telegram":
                save_cursor(db, platform, getattr(adapter, "offset", None))
    except PermanentAuthError as exc:
        return finish("Unauthorized", str(exc))
    except RateLimitError as exc:
        return finish("Rate limited", str(exc))
    except Exception as exc:
        return finish("Error", f"Ingestion failed: {str(exc)[:160]}")

    new, dup, failed, analyzed = store_posts(db, watch, normalized, run_id, platform)
    watch.last_ingestion_at = datetime.now(timezone.utc)
    watch.last_analysis_at = watch.last_ingestion_at
    if new:
        watch.mode = "live"
    db.commit()
    audit.record(
        db, "ingestion.run",
        f"{platform}: found {len(normalized)}, new {new}, duplicate {dup}, failed {failed}", watch.id,
    )
    return finish(
        "Connected", f"Fetched {len(normalized)} permitted records from {platform}.",
        found=len(normalized), new=new, dup=dup, failed=failed, analyzed=analyzed,
    )


# -------------------------------------------------------------------------- jobs
def ingest_watch(
    db: Session, watch: Watch, platforms: list[str] | None = None, job_type: str = "ingest"
) -> schemas.IngestionJobResult:
    started = datetime.now(timezone.utc)
    selected = platforms or [p.strip() for p in watch.platforms.split(",") if p.strip()]
    sources: list[schemas.IngestionSourceResult] = []

    for platform in selected:
        try:
            result = run_ingestion(db, watch, platform, job_type=job_type)
            sources.append(
                schemas.IngestionSourceResult(
                    platform=platform, status=result.status, detail=result.detail,
                    records_found=result.records_fetched, records_new=result.records_stored,
                    records_duplicate=result.records_duplicate, records_failed=result.records_failed,
                )
            )
        except Exception as exc:  # adapter isolation
            sources.append(
                schemas.IngestionSourceResult(
                    platform=platform, status="Error", detail=f"{platform} ingestion failed: {str(exc)[:140]}",
                )
            )

    completed = datetime.now(timezone.utc)
    connected = [s for s in sources if s.status == "Connected"]
    if not connected:
        message = "Live sources unavailable. Demo Mode is available."
        if not any(s.status not in ("Not configured", "Planned") for s in sources):
            message = "No live connector is configured. The deterministic demo snapshot remains in use."
    else:
        message = f"{len(connected)} live source(s) ingested."

    return schemas.IngestionJobResult(
        watch_id=watch.id, job_type=job_type, mode=watch.mode,
        records_found=sum(s.records_found for s in sources),
        records_new=sum(s.records_new for s in sources),
        records_duplicate=sum(s.records_duplicate for s in sources),
        records_failed=sum(s.records_failed for s in sources),
        started_at=started, completed_at=completed, sources=sources, message=message,
    )


def backfill_watch(
    db: Session, watch: Watch, since: datetime, until: datetime, platforms: list[str] | None = None
) -> schemas.IngestionJobResult:
    started = datetime.now(timezone.utc)
    selected = platforms or [p.strip() for p in watch.platforms.split(",") if p.strip()]
    sources: list[schemas.IngestionSourceResult] = []

    for platform in selected:
        adapter = get_adapter(platform)
        if adapter is None:
            sources.append(schemas.IngestionSourceResult(platform=platform, status="Unavailable", detail="No adapter registered."))
            continue
        if not adapter.is_configured():
            state = adapter.health()
            sources.append(schemas.IngestionSourceResult(platform=platform, status=state.status, detail=state.detail))
            continue
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        try:
            if platform == "Telegram" and get_telegram_history_adapter().is_configured():
                normalized = get_telegram_history_adapter().fetch_range(watch.keywords, since, until)
            else:
                normalized = adapter.fetch_range(watch.keywords, since, until)
        except HistoryUnsupported as exc:
            sources.append(schemas.IngestionSourceResult(platform=platform, status="Unsupported window", detail=str(exc)))
            db.add(
                IngestionRun(
                    id=run_id, watch_id=watch.id, platform=platform, job_type="backfill",
                    status="Unsupported window", started_at=started, completed_at=datetime.now(timezone.utc),
                    detail=str(exc)[:400],
                )
            )
            db.commit()
            continue
        except Exception as exc:
            sources.append(schemas.IngestionSourceResult(platform=platform, status="Error", detail=str(exc)[:160]))
            continue

        new, dup, failed, _ = store_posts(db, watch, normalized, run_id, platform)
        db.add(
            IngestionRun(
                id=run_id, watch_id=watch.id, platform=platform, job_type="backfill", status="Completed",
                started_at=started, completed_at=datetime.now(timezone.utc), records_found=len(normalized),
                records_new=new, records_duplicate=dup, records_failed=failed,
                detail=f"Backfill {since.isoformat()} to {until.isoformat()}",
            )
        )
        db.commit()
        audit.record(db, "ingestion.backfill", f"{platform} backfill {since.date()} - {until.date()}", watch.id)
        sources.append(
            schemas.IngestionSourceResult(
                platform=platform, status="Connected", detail=f"Backfilled {len(normalized)} permitted records.",
                records_found=len(normalized), records_new=new, records_duplicate=dup, records_failed=failed,
            )
        )

    completed = datetime.now(timezone.utc)
    return schemas.IngestionJobResult(
        watch_id=watch.id, job_type="backfill", mode=watch.mode,
        records_found=sum(s.records_found for s in sources),
        records_new=sum(s.records_new for s in sources),
        records_duplicate=sum(s.records_duplicate for s in sources),
        records_failed=sum(s.records_failed for s in sources),
        started_at=started, completed_at=completed, sources=sources,
        message="Backfill completed. Unsupported windows are reported per connector.",
    )


def refresh_watch(db: Session, watch: Watch) -> list[schemas.IngestionResult]:
    """'Refresh Data' - live adapters fetch, unconfigured platforms stay on demo records."""
    results = []
    for platform in watch.platforms.split(","):
        platform = platform.strip()
        if not platform:
            continue
        try:
            results.append(run_ingestion(db, watch, platform))
        except Exception as exc:  # adapter isolation
            results.append(
                schemas.IngestionResult(
                    platform=platform, status="Error", detail=f"{platform} unavailable: {str(exc)[:140]}",
                    records_fetched=0, records_stored=0, analyzed=0, mode=watch.mode,
                )
            )
    if not any(r.records_stored for r in results):
        watch.last_ingestion_at = datetime.now(timezone.utc)
        db.commit()
    return results
