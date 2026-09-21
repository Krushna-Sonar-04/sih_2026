"""Lightweight local scheduler and Telegram polling worker.

A single asyncio task, started only when INGESTION_ENABLED=true and the
schedule is not "manual". A module-level guard makes sure two polling workers
never run against the same bot configuration, and shutdown is graceful.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from ..config import get_settings
from ..database import SessionLocal
from ..models import Watch

logger = logging.getLogger("drishti.scheduler")

_task: asyncio.Task | None = None
_stop = asyncio.Event()

INTERVALS = {"manual": 0, "5m": 300, "15m": 900, "hourly": 3600}


def is_running() -> bool:
    return _task is not None and not _task.done()


MAX_BACKOFF = 900  # 15 minutes


async def _cycle() -> None:
    """Poll configured live sources off the request path, with bounded backoff."""
    from . import ingestion  # imported lazily to avoid a circular import
    from ..adapters.base import PermanentAuthError

    settings = get_settings()
    interval = max(INTERVALS.get(settings.scheduler_interval, 0), settings.telegram_poll_seconds)
    failures = 0
    while not _stop.is_set():
        wait = interval
        try:
            with SessionLocal() as db:
                watches = list(db.scalars(select(Watch).where(Watch.mode == "live")))
                if not watches:
                    watches = list(db.scalars(select(Watch)))
                for watch in watches:
                    result = ingestion.ingest_watch(db, watch, job_type="scheduled")
                    if result.records_new:
                        logger.info(
                            "Scheduled ingestion: watch=%s new=%s duplicates=%s",
                            watch.id, result.records_new, result.records_duplicate,
                        )
            failures = 0
        except PermanentAuthError as exc:
            # Never retry an invalid credential in a tight loop.
            logger.error("Ingestion worker stopping: %s", str(exc)[:200])
            break
        except Exception as exc:  # a worker failure must never kill the API
            failures += 1
            wait = min(interval * (2 ** failures), MAX_BACKOFF)
            logger.warning(
                "Scheduled ingestion cycle failed (%s consecutive): %s — retrying in %ss",
                failures, str(exc)[:160], wait,
            )
        try:
            await asyncio.wait_for(_stop.wait(), timeout=wait)
        except asyncio.TimeoutError:
            continue


def start() -> bool:
    """Start the worker once. Returns True when a worker was started here."""
    global _task
    settings = get_settings()
    if not settings.ingestion_enabled or settings.scheduler_interval == "manual":
        logger.info("Scheduler idle: ingestion disabled or interval is manual.")
        return False
    if is_running():
        logger.info("Scheduler already running; not starting a second worker.")
        return False
    _stop.clear()
    _task = asyncio.create_task(_cycle(), name="drishti-ingestion-worker")
    logger.info("Ingestion worker started (interval=%s).", settings.scheduler_interval)
    return True


async def stop() -> None:
    """Graceful shutdown."""
    global _task
    _stop.set()
    if _task is not None:
        try:
            await asyncio.wait_for(_task, timeout=5)
        except Exception:
            _task.cancel()
        _task = None
        logger.info("Ingestion worker stopped at %s.", datetime.now(timezone.utc).isoformat())
