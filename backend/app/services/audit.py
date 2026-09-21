"""Lightweight auditable event logging (structured for later expansion)."""
from __future__ import annotations

import hashlib
import logging

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..models import AuditEvent

logger = logging.getLogger("drishti.audit")

ACTIONS = (
    "auth.login",
    "auth.login_failed",
    "auth.user_created",
    "watch.created",
    "watch.updated",
    "ingestion.run",
    "analysis.executed",
    "assistant.query",
    "export.generated",
    "connector.test",
)


def record(db: Session, action: str, detail: str = "", watch_id: str | None = None, actor: str = "analyst") -> None:
    """Never logs secrets - callers pass descriptive text only."""
    try:
        previous = db.scalar(select(AuditEvent).order_by(desc(AuditEvent.id)).limit(1))
        prev_hash = previous.record_hash if previous is not None else ""
        record_hash = hashlib.sha256(
            f"{prev_hash}|{action}|{actor}|{watch_id or ''}|{detail[:500]}".encode("utf-8")
        ).hexdigest()
        db.add(
            AuditEvent(
                action=action,
                actor=actor,
                watch_id=watch_id,
                detail=detail[:500],
                prev_hash=prev_hash,
                record_hash=record_hash,
            )
        )
        db.commit()
        logger.info("audit action=%s watch=%s detail=%s", action, watch_id, detail[:160])
    except Exception:  # pragma: no cover - audit must never break the request
        db.rollback()
        logger.exception("Failed to record audit event %s", action)
