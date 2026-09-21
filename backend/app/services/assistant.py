"""Analyst assistant: grounded, cite-or-refuse, provider-agnostic.

If no LLM credential is configured, a deterministic analyst response is
composed from the structured timeline state. The demo never fails because a
key is missing.
"""
from __future__ import annotations

import time
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from .. import schemas
from ..config import get_settings
from ..models import Watch
from . import citations as citation_service
from . import retrieval
from .timeline import build_timeline

INSUFFICIENT = "Insufficient evidence in the selected data to answer this question."


def provider_name() -> str:
    settings = get_settings()
    if settings.llm_provider == "local":
        return "local-deterministic"
    if settings.openai_api_key or (settings.llm_api_key and settings.llm_provider in ("auto", "openai")):
        return "openai"
    if settings.gemini_api_key or settings.llm_provider == "gemini":
        return "gemini"
    return "local-deterministic"


def assistant_health() -> dict:
    name = provider_name()
    if name == "local-deterministic":
        return {
            "component": "Analyst assistant",
            "status": "Demo",
            "detail": "No LLM credential configured. Deterministic grounded responses from stored analysis.",
        }
    return {
        "component": "Analyst assistant",
        "status": "Connected",
        "detail": f"LLM provider configured: {name}. Answers remain grounded in retrieved evidence.",
    }


def _deterministic_answer(question: str, timeline: schemas.TimelineResponse, evidence: list[schemas.EvidenceOut]) -> str:
    q = question.lower()
    s = timeline.sentiment
    top = timeline.top_trends[0] if timeline.top_trends else None
    kol = timeline.kol_candidates[0] if timeline.kol_candidates else None
    stamp = timeline.timestamp.strftime("%d %b %Y · %H:%M")

    if "sentiment" in q or "shift" in q or "why" in q:
        return (
            f"At {stamp} the distribution is {s.positive}% positive / {s.neutral}% neutral / {s.negative}% negative. "
            f"{s.annotation} The shift is concentrated in the '{top.topic if top else 'leading'}' narrative, where "
            f"{len(evidence)} retrieved records raise implementation and safeguard concerns."
        )
    if "who" in q or "driving" in q or "kol" in q or "influence" in q:
        if not kol:
            return INSUFFICIENT
        return (
            f"{kol.username} is the leading KOL candidate at {stamp} (influence {kol.influence_score}, "
            f"degree centrality {kol.degree_centrality}, {len(kol.connected_accounts)} connected accounts, "
            f"{kol.cross_community_links} cross-community links). {kol.confidence}"
        )
    if "spread" in q or "cross-platform" in q:
        parts = [
            f"{c.platform}: {c.mentions} records, {c.negative}% negative, role {c.role}"
            for c in timeline.cross_platform
        ]
        if not parts:
            return INSUFFICIENT
        return (
            f"Spread pattern at {stamp} — " + "; ".join(parts) +
            ". Early channel discussion precedes wider amplification."
        )
    if "rising" in q or "narrative" in q or "trend" in q:
        if not top:
            return INSUFFICIENT
        return (
            f"'{top.topic}' is the leading narrative at {stamp} with {top.mentions} mentions against "
            f"{top.previous_mentions} in the previous interval (velocity {top.velocity}%). "
            f"Rank {top.rank} of {len(timeline.top_trends)} tracked topics."
        )
    if "spread" in q or "cross" in q or "telegram" in q or "platform" in q:
        if not timeline.cross_platform:
            return INSUFFICIENT
        parts = [
            f"{c.platform}: {c.mentions} records, {c.negative}% negative, role {c.role}"
            for c in timeline.cross_platform
        ]
        return f"Cross-platform position at {stamp} — " + "; ".join(parts) + "."
    if "evidence" in q or "spike" in q or "show" in q:
        return (
            f"{len(evidence)} records from the selected window support the current reading at {stamp}. "
            "Open a citation to inspect the stored record."
        )
    return (
        f"At {stamp} the watch shows {s.negative}% negative sentiment with "
        f"'{top.topic if top else 'no dominant'}' leading the narrative ranking. {timeline.at_this_moment}"
    )


def _llm_answer(question: str, context: str) -> str | None:
    settings = get_settings()
    name = provider_name()
    prompt = (
        "You are DRISHTI's analyst assistant. Answer only from the supplied DRISHTI analysis context. "
        "If the context does not support an answer, reply exactly: " + INSUFFICIENT + "\n\n"
        f"CONTEXT:\n{context}\n\nQUESTION: {question}"
    )
    try:
        if name == "openai":
            key = settings.openai_api_key or settings.llm_api_key
            with httpx.Client(timeout=30.0) as client:
                res = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={
                        "model": settings.llm_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2,
                    },
                )
            if res.status_code != 200:
                return None
            return res.json()["choices"][0]["message"]["content"].strip()
        if name == "gemini":
            key = settings.gemini_api_key or settings.llm_api_key
            with httpx.Client(timeout=30.0) as client:
                res = client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{settings.llm_model}:generateContent",
                    params={"key": key},
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                )
            if res.status_code != 200:
                return None
            return res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return None
    return None



# --------------------------------------------------------------------------- rate limit
_CALLS: dict[str, list[float]] = {}


def rate_limit_ok(key: str) -> bool:
    """Simple in-process sliding-window limiter for assistant queries."""
    limit = get_settings().assistant_rate_limit_per_minute
    if limit <= 0:
        return True
    now = time.time()
    calls = [t for t in _CALLS.get(key, []) if now - t < 60]
    if len(calls) >= limit:
        _CALLS[key] = calls
        return False
    calls.append(now)
    _CALLS[key] = calls
    return True


def _refusal(watch_id: str, at: datetime, note: str = "") -> schemas.AssistantAnswer:
    return schemas.AssistantAnswer(
        answer=INSUFFICIENT + (f"\n\nValidation note: {note}" if note else ""),
        citations=[], grounded=False, provider=provider_name(),
        watch_id=watch_id, timestamp=at,
    )


def _format_response(
    finding: str,
    timeline: schemas.TimelineResponse,
    citations: list[schemas.Citation],
) -> str:
    """Responsible-AI response shape: what is observed, computed and inferred."""
    evidence_lines = [
        f"- {c.ref} · {c.platform} · {c.account_username} · "
        f"{c.event_time.strftime('%d %b %Y · %H:%M')} — \"{c.excerpt}\""
        for c in citations
    ]
    limitation = (
        "COMPUTED from stored records in the selected window. "
        f"Mean sentiment confidence {timeline.sentiment.confidence}; "
        f"{timeline.sentiment.unlabeled} record(s) unlabelled. "
        "Temporal association only - not causation."
    )
    if timeline.mode != "live":
        limitation += " Source: DEMO DATASET (simulated social activity)."
    for note in timeline.notes.values():
        limitation += f" {note}"
    return (
        f"Finding: {finding}\n\n"
        f"Evidence:\n" + "\n".join(evidence_lines) + "\n\n"
        f"Interpretation: OBSERVED activity and COMPUTED aggregates support the finding above; "
        f"anything beyond the cited records is INFERRED and stated as such.\n\n"
        f"Limitation / Confidence: {limitation}\n\n"
        f"Sources: " + ", ".join(c.ref for c in citations)
    )


def answer(
    db: Session,
    watch: Watch,
    query: schemas.AssistantQuery,
    snapshot: int | None = None,
) -> schemas.AssistantAnswer:
    timeline = build_timeline(db, watch, query.timestamp, snapshot)
    evidence = retrieval.retrieve(
        db, watch.id, timeline.timestamp, query.question, query.topic, query.account_id
    )

    if not evidence:
        return _refusal(watch.id, timeline.timestamp)

    citations = [
        schemas.Citation(
            ref=f"Evidence {index + 1:02d}", evidence_id=item.id,
            excerpt=item.text[:180], platform=item.platform,
            account_username=item.account_username, event_time=item.event_time,
        )
        for index, item in enumerate(evidence)
    ]

    context_lines = [
        f"Timestamp: {timeline.timestamp.isoformat()}",
        f"Sentiment: {timeline.sentiment.positive}/{timeline.sentiment.neutral}/{timeline.sentiment.negative} "
        f"(pos/neu/neg), change {timeline.sentiment.change}",
        "Top trends: " + ", ".join(f"{t.topic} {t.mentions} (v{t.velocity}%)" for t in timeline.top_trends),
        "KOL candidates: " + ", ".join(f"{k.username} {k.influence_score}" for k in timeline.kol_candidates),
        "Cross-platform: " + ", ".join(f"{c.platform} {c.mentions}" for c in timeline.cross_platform),
        "Evidence:",
    ] + [f"{c.ref} [{c.platform} {c.account_username}]: {c.excerpt}" for c in citations]

    llm = _llm_answer(query.question, "\n".join(context_lines))
    finding = llm or _deterministic_answer(query.question, timeline, evidence)
    if INSUFFICIENT in finding:
        return _refusal(watch.id, timeline.timestamp)

    # Citation validation happens OUTSIDE the model: identifier exists, belongs
    # to this Watch, sits inside the analytical scope, was actually retrieved
    # and its content supports the stated finding.
    validation = citation_service.validate(
        db,
        watch.id,
        min(c.event_time for c in citations),
        timeline.timestamp,
        [item.id for item in evidence],
        [c.evidence_id for c in citations],
        finding,
    )
    if not validation.valid:
        return _refusal(watch.id, timeline.timestamp, validation.reason)

    return schemas.AssistantAnswer(
        answer=_format_response(finding, timeline, citations),
        citations=citations, grounded=True, provider=provider_name(),
        watch_id=watch.id, timestamp=timeline.timestamp,
    )
