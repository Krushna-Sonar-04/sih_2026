"""System health aggregation from actual backend state."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import schemas
from ..adapters import adapter_health
from ..analytics import sentiment as sentiment_engine
from ..database import database_status
from ..models import DemographicAggregate, NetworkEdge, Post, PostEmbedding, TrendTopic, Watch
from . import assistant, connectors, embeddings as embedding_service


def build_health(db: Session) -> schemas.HealthResponse:
    db_state = database_status()
    post_count = db.scalar(select(func.count()).select_from(Post)) or 0
    watch_count = db.scalar(select(func.count()).select_from(Watch)) or 0
    edge_count = db.scalar(select(func.count()).select_from(NetworkEdge)) or 0
    demo_count = db.scalar(select(func.count()).select_from(DemographicAggregate)) or 0
    trend_count = db.scalar(select(func.count()).select_from(TrendTopic)) or 0
    last_ingestion = db.scalar(select(func.max(Watch.last_ingestion_at)))
    live_posts = db.scalar(select(func.count()).select_from(Post).where(Post.source_mode == "live")) or 0

    adapters = [
        schemas.ComponentHealth(
            component=f"{h.platform} adapter", status=h.status, detail=h.detail,
            last_operation=h.last_fetch_at, record_count=h.records_last_fetch or None,
        )
        for h in adapter_health(demo_mode=live_posts == 0)
    ]

    sentiment_state = sentiment_engine.engine_health()
    analytics = [
        schemas.ComponentHealth(
            component="Sentiment engine", status=sentiment_state["status"],
            detail=sentiment_state["detail"], record_count=post_count,
        ),
        schemas.ComponentHealth(
            component="Trend engine", status="Operational",
            detail="Deterministic mention-velocity computation over stored posts.",
            record_count=trend_count or post_count,
        ),
        schemas.ComponentHealth(
            component="Network engine", status="Operational",
            detail="NetworkX degree and betweenness centrality with community detection.",
            record_count=edge_count,
        ),
        schemas.ComponentHealth(
            component="Demographic engine", status="Operational",
            detail="Aggregate cohorts only, with minimum reporting threshold applied.",
            record_count=demo_count,
        ),
    ]

    embedding_state = embedding_service.engine_health()
    analytics.append(
        schemas.ComponentHealth(
            component="Embedding service", status=embedding_state["status"],
            detail=embedding_state["detail"],
            record_count=db.scalar(select(func.count()).select_from(PostEmbedding)) or 0,
        )
    )

    assistant_state = assistant.assistant_health()
    live_available = any(a.status == "Connected" for a in adapters)

    return schemas.HealthResponse(
        api=schemas.ComponentHealth(
            component="API", status="Operational",
            detail="FastAPI service responding.", record_count=watch_count,
        ),
        database=schemas.ComponentHealth(
            component="Database", status=db_state["status"], detail=db_state["detail"],
            last_operation=last_ingestion, record_count=post_count,
        ),
        adapters=adapters,
        analytics=analytics,
        assistant=schemas.ComponentHealth(
            component="Analyst assistant", status=assistant_state["status"], detail=assistant_state["detail"],
        ),
        ingestion=connectors.ingestion_summary(db),
        connectors=connectors.connector_states(db),
        mode="live" if live_posts else "demo",
        live_available=live_available,
        message=(
            "Live integrations are connected."
            if live_available
            else "Live integrations are not configured. Demo Mode remains available."
        ),
    )
