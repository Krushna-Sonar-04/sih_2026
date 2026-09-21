"""Hybrid grounded retrieval (RAG) scoped to DRISHTI analysis state.

Filter stage (structured): watch -> time window -> platform -> topic -> account.
Rank stage (hybrid): lexical overlap + vector similarity + recency +
engagement + graph-neighbourhood proximity to the accounts under discussion.

Vectors come from the embedding service (local deterministic engine by
default). If embeddings are unavailable the lexical path still returns
evidence - an embedding outage never makes evidence unavailable.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas
from ..models import NetworkEdge
from . import embeddings
from .timeline import WINDOW, evidence_at

STOPWORDS = {"the", "a", "an", "is", "are", "did", "why", "what", "who", "how", "this", "that", "here", "in", "on", "of", "and", "to", "for"}

ANALYTICAL_TERMS = {
    "sentiment", "shift", "shifted", "narrative", "narratives", "trend", "trends", "rising",
    "driving", "influence", "influencer", "kol", "account", "accounts", "network", "spread",
    "spike", "evidence", "platform", "platforms", "telegram", "cross", "demographics", "cohort",
    "activity", "discussion", "changed", "change", "moment", "timeline",
}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z]{3,}", text.lower()) if t not in STOPWORDS}


def _graph_neighbourhood(db: Session, watch_id: str, account_id: str | None) -> set[str]:
    if not account_id:
        return set()
    edges = db.scalars(select(NetworkEdge).where(NetworkEdge.watch_id == watch_id))
    neighbours: set[str] = {account_id}
    for edge in edges:
        if edge.source_id == account_id:
            neighbours.add(edge.target_id)
        elif edge.target_id == account_id:
            neighbours.add(edge.source_id)
    return neighbours


def retrieve(
    db: Session,
    watch_id: str,
    at: datetime,
    question: str,
    topic: str | None = None,
    account_id: str | None = None,
    limit: int = 5,
    platforms: list[str] | None = None,
) -> list[schemas.EvidenceOut]:
    candidates = evidence_at(db, watch_id, at, topic, account_id, limit=60)
    if platforms:
        candidates = [c for c in candidates if c.platform in platforms]
    window_start = at - WINDOW * 2
    in_window = [c for c in candidates if c.event_time >= window_start] or candidates
    query_tokens = _tokens(question)

    # Vector stage - cached embeddings, refreshed only for changed text.
    try:
        embeddings.ensure_embeddings(db, watch_id)
        vectors = embeddings.load_vectors(db, watch_id, [c.id for c in in_window])
        query_vector = embeddings.embed(question)
    except Exception:  # pragma: no cover - retrieval degrades, never fails
        vectors, query_vector = {}, []

    neighbourhood = _graph_neighbourhood(db, watch_id, account_id)

    def score(item: schemas.EvidenceOut) -> float:
        overlap = len(query_tokens & _tokens(item.text))
        similarity = embeddings.cosine(query_vector, vectors.get(item.id, []))
        recency = 1.0 / (1.0 + max((at - item.event_time), timedelta(0)).total_seconds() / 86400)
        engagement = min(1.0, item.engagement / 5000)
        topical = 1.0 if topic and item.topic == topic else 0.0
        graph = 1.0 if item.account_id in neighbourhood else 0.0
        return overlap * 1.5 + similarity * 3.0 + recency * 2 + engagement + topical + graph

    # Relevance gate: a question with no lexical overlap, no analytical intent
    # and no vector similarity has no grounding in this watch, so the
    # assistant must refuse rather than answer from unrelated records.
    analytical_intent = bool(query_tokens & ANALYTICAL_TERMS)
    has_overlap = any(query_tokens & _tokens(c.text) or query_tokens & _tokens(c.topic) for c in in_window)
    best_similarity = max(
        (embeddings.cosine(query_vector, vectors.get(c.id, [])) for c in in_window), default=0.0
    )
    if not analytical_intent and not has_overlap and best_similarity < 0.45:
        return []

    return sorted(in_window, key=score, reverse=True)[:limit]
