"""Citation validation - performed OUTSIDE the language model.

A generated answer is only accepted when every citation it carries:
  1. refers to a stored evidence record that exists,
  2. belongs to the Watch under analysis,
  3. falls inside the selected analytical time scope,
  4. was actually part of the retrieved evidence set,
  5. carries content that overlaps the claim text (lexical support check).

Any failure rejects the answer; the assistant then refuses rather than
presenting an ungrounded statement.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import Post

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "over", "under", "about",
    "their", "there", "these", "those", "have", "has", "was", "were", "are", "its", "it",
    "evidence", "sources", "finding", "interpretation", "limitation", "confidence",
}


@dataclass
class ValidationResult:
    valid: bool
    accepted: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    reason: str = ""


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z]{4,}", (text or "").lower()) if t not in STOPWORDS}


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def validate(
    db: Session,
    watch_id: str,
    window_from: datetime,
    window_to: datetime,
    retrieved_ids: list[str],
    citation_ids: list[str],
    answer_text: str,
) -> ValidationResult:
    if not citation_ids:
        return ValidationResult(False, reason="No citation supplied.")

    retrieved = set(retrieved_ids)
    accepted: list[str] = []
    rejected: list[str] = []
    claim_tokens = _tokens(answer_text)

    for evidence_id in citation_ids:
        post = db.get(Post, evidence_id)
        if post is None:
            rejected.append(f"{evidence_id}: record does not exist")
            continue
        if post.watch_id != watch_id:
            rejected.append(f"{evidence_id}: record belongs to a different Watch")
            continue
        event_time = _aware(post.event_time)
        if event_time is None or not (window_from <= event_time <= window_to):
            rejected.append(f"{evidence_id}: record is outside the selected time scope")
            continue
        if evidence_id not in retrieved:
            rejected.append(f"{evidence_id}: record was not part of the retrieved evidence set")
            continue
        accepted.append(evidence_id)

    # Content-support check: at least one cited record must share vocabulary
    # with the answer, otherwise the citation does not support the claim.
    supported = any(
        claim_tokens & _tokens(getattr(db.get(Post, pid), "text", "")) for pid in accepted
    )
    if accepted and not supported and claim_tokens:
        rejected.append("no cited record shares content with the stated finding")

    valid = bool(accepted) and not rejected
    reason = "" if valid else "; ".join(rejected)
    return ValidationResult(valid=valid, accepted=accepted, rejected=rejected, reason=reason)
