"""Narrative intelligence briefing assembly.

Builds a structured, print-ready brief from the same shared-clock timeline
used by every analytical view. No external PDF service: the frontend renders
the brief and the browser prints it.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from .. import schemas
from ..models import Watch
from .timeline import build_timeline


def build_briefing(
    db: Session, watch: Watch, timestamp: datetime | None = None, snapshot: int | None = None
) -> schemas.BriefingOut:
    timeline = build_timeline(db, watch, timestamp, snapshot)
    sentiment = timeline.sentiment
    top = timeline.top_trends[0] if timeline.top_trends else None
    kol = timeline.kol_candidates[0] if timeline.kol_candidates else None
    mode_label = "Live data" if watch.mode == "live" else "Demo dataset (simulated social activity)"

    executive = [
        (
            f"At {timeline.timestamp.strftime('%d %b %Y · %H:%M')} the watch '{watch.name}' shows "
            f"{sentiment.negative}% negative, {sentiment.neutral}% neutral and {sentiment.positive}% "
            f"positive sentiment across {len(timeline.evidence_summary)} sampled records."
        ),
        sentiment.annotation,
    ]
    if top:
        executive.append(
            f"Rising narrative: '{top.topic}' with {top.mentions} mentions against "
            f"{top.previous_mentions} in the previous interval (velocity {top.velocity}%)."
        )
    else:
        executive.append("No topic reached the reporting threshold in this window.")
    if kol:
        executive.append(
            f"Leading KOL candidate: {kol.username} (influence {kol.influence_score}). "
            "Candidate status only - not a confirmed influencer."
        )

    method_notes = [
        "Sentiment: open-source polarity model with lexicon-based emotion indicators; "
        "unlabelled records are reported, never inferred.",
        "Trends: velocity = current mentions / max(previous mentions, 1), computed over the same window.",
        "Network: NetworkX degree and betweenness centrality over observed reply, mention, "
        "forward and reference relationships only.",
        "Narrative movement is an observed temporal sequence and a correlation - not causation.",
    ]
    privacy_notes = [
        "Demographics are aggregate, anonymized cohort estimates. No individual demographic "
        "attribute is stored or reported.",
        f"Cohorts below {timeline.demographics.min_reporting_threshold}% of the sample are suppressed.",
        "Every finding in this brief links to a stored record with platform, account, timestamp and text.",
    ]

    return schemas.BriefingOut(
        title="DRISHTI Narrative Intelligence Brief",
        watch_id=watch.id,
        watch_name=watch.name,
        keywords=[k for k in (watch.keywords or "").split(",") if k.strip()],
        mode=watch.mode,
        mode_label=mode_label,
        generated_at=datetime.now(timeline.timestamp.tzinfo),
        period_from=timeline.window_from,
        period_to=timeline.window_to,
        timestamp=timeline.timestamp,
        sources=[c.platform for c in timeline.cross_platform] or [p for p in (watch.platforms or "").split(",") if p],
        executive_summary=executive,
        narrative_movement=timeline.narrative_movement,
        sentiment=sentiment,
        top_trends=timeline.top_trends,
        kol_candidates=timeline.kol_candidates,
        demographics=timeline.demographics,
        cross_platform=timeline.cross_platform,
        evidence=timeline.evidence_summary,
        events=timeline.events,
        notes=timeline.notes,
        method_notes=method_notes,
        privacy_notes=privacy_notes,
    )
