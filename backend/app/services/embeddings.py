"""Embedding service abstraction for grounded retrieval.

Default engine: a deterministic local hashing embedding (no download, no API
key, runs offline on a laptop). If `sentence-transformers` is installed and
EMBEDDING_MODEL_NAME names a real model, that model is used instead - the
calling code never changes.

Vectors are cached per post and keyed by a content hash, so unchanged posts
are never re-embedded. The storage column is JSON text for portability;
PostgreSQL + pgvector can replace it without touching this interface.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Post, PostEmbedding

logger = logging.getLogger("drishti.embeddings")

TOKEN_RE = re.compile(r"[a-z0-9\u0900-\u097f]{2,}")

_model = None
_model_name = ""


def _try_load_model() -> None:
    """Optional upgrade path - absent library simply keeps the local engine."""
    global _model, _model_name
    settings = get_settings()
    name = settings.embedding_model_name
    if not name or name.startswith("drishti-local"):
        return
    try:  # pragma: no cover - only exercised when the extra is installed
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(name)
        _model_name = name
    except Exception:
        logger.info("Embedding model '%s' unavailable; using the local hashing engine.", name)
        _model = None


_try_load_model()


def model_name() -> str:
    return _model_name or get_settings().embedding_model_name


def dimensions() -> int:
    if _model is not None:  # pragma: no cover
        return int(_model.get_sentence_embedding_dimension())
    return int(get_settings().embedding_dimensions)


def engine_health() -> dict:
    return {
        "component": "Embedding service",
        "status": "Operational",
        "detail": (
            f"Local deterministic hashing embeddings ({dimensions()} dimensions), cached per post."
            if _model is None
            else f"Sentence-transformers model '{model_name()}' loaded."
        ),
    }


def content_hash(text: str) -> str:
    return hashlib.sha256(f"{model_name()}::{text}".encode("utf-8")).hexdigest()


def embed(text: str) -> list[float]:
    """Return an L2-normalised vector for the supplied text."""
    if _model is not None:  # pragma: no cover
        return [float(v) for v in _model.encode(text)]
    size = dimensions()
    vector = [0.0] * size
    tokens = TOKEN_RE.findall((text or "").lower())
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % size
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        return vector
    return [v / norm for v in vector]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))


def ensure_embeddings(db: Session, watch_id: str, posts: Iterable[Post] | None = None) -> int:
    """Embed any post of the watch whose text is new or changed.

    Returns the number of vectors written. Failures are logged and skipped -
    an embedding outage must never make evidence unavailable.
    """
    items = list(posts) if posts is not None else list(
        db.scalars(select(Post).where(Post.watch_id == watch_id))
    )
    existing = {
        row.post_id: row
        for row in db.scalars(select(PostEmbedding).where(PostEmbedding.watch_id == watch_id))
    }
    written = 0
    for post in items:
        digest = content_hash(post.text or "")
        row = existing.get(post.id)
        if row is not None and row.content_hash == digest:
            continue  # unchanged - no re-embedding
        try:
            vector = embed(post.text or "")
        except Exception:  # pragma: no cover - defensive
            logger.exception("Embedding failed for post %s", post.id)
            continue
        if row is None:
            db.add(
                PostEmbedding(
                    post_id=post.id,
                    watch_id=watch_id,
                    model_name=model_name(),
                    dimensions=len(vector),
                    content_hash=digest,
                    vector=json.dumps(vector),
                )
            )
        else:
            row.model_name = model_name()
            row.dimensions = len(vector)
            row.content_hash = digest
            row.vector = json.dumps(vector)
        written += 1
    if written:
        try:
            db.commit()
        except Exception:  # pragma: no cover
            db.rollback()
            logger.exception("Failed to persist embeddings for watch %s", watch_id)
            return 0
    return written


def load_vectors(db: Session, watch_id: str, post_ids: Iterable[str] | None = None) -> dict[str, list[float]]:
    stmt = select(PostEmbedding).where(PostEmbedding.watch_id == watch_id)
    rows = list(db.scalars(stmt))
    wanted = set(post_ids) if post_ids is not None else None
    out: dict[str, list[float]] = {}
    for row in rows:
        if wanted is not None and row.post_id not in wanted:
            continue
        try:
            out[row.post_id] = json.loads(row.vector)
        except Exception:  # pragma: no cover
            continue
    return out


def coverage(db: Session, watch_id: str) -> int:
    return len(load_vectors(db, watch_id))
