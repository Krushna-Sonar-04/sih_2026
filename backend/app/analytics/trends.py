"""Deterministic trend and topic detection over stored posts.

velocity = (mentions - previous_mentions) / max(previous_mentions, 1) * 100
Transparent and reproducible - no opaque scoring.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


MIN_EVIDENCE = 3


def classify(mentions: int, previous: int, velocity: float) -> tuple[str, str]:
    """Transparent, evidence-gated trend classification.

    A topic is never called rising - and never called "viral" anywhere in
    DRISHTI - on the strength of one or two records.
    """
    if mentions + previous < MIN_EVIDENCE:
        return "INSUFFICIENT EVIDENCE", "Too few records in this window for a reliable classification."
    if previous == 0 and mentions >= MIN_EVIDENCE:
        return "EMERGING", "No mentions in the previous interval; first sustained appearance."
    if velocity >= 50:
        return "RISING", f"Mentions grew {velocity}% against the previous equal-length interval."
    if velocity <= -50:
        return "FALLING", f"Mentions fell {abs(velocity)}% against the previous equal-length interval."
    return "STABLE", "Mention volume is broadly unchanged against the previous interval."


@dataclass
class TrendResult:
    topic: str
    mentions: int
    previous_mentions: int
    velocity: float
    rank: int
    event_time: datetime
    spark: list[int]
    classification: str = "INSUFFICIENT EVIDENCE"
    classification_note: str = ""


def compute_trends(
    posts: list,
    at: datetime,
    window: timedelta = timedelta(hours=36),
    limit: int = 6,
) -> list[TrendResult]:
    """Count topic mentions in [at-window, at] vs the previous equal window."""
    current_start = at - window
    previous_start = current_start - window

    current: dict[str, int] = {}
    previous: dict[str, int] = {}
    buckets: dict[str, list[int]] = {}

    for post in posts:
        topic = (post.topic or "Unclassified").strip()
        et = post.event_time
        if et is None:
            continue
        if current_start <= et <= at:
            current[topic] = current.get(topic, 0) + 1
        elif previous_start <= et < current_start:
            previous[topic] = previous.get(topic, 0) + 1

    for topic in set(current) | set(previous):
        prev = previous.get(topic, 0)
        curr = current.get(topic, 0)
        buckets[topic] = [max(0, prev - 2), prev, (prev + curr) // 2, curr]

    results: list[TrendResult] = []
    for topic in sorted(set(current) | set(previous), key=lambda t: -current.get(t, 0)):
        curr = current.get(topic, 0)
        prev = previous.get(topic, 0)
        velocity = round(((curr - prev) / max(prev, 1)) * 100, 1)
        classification, note = classify(curr, prev, velocity)
        results.append(
            TrendResult(
                topic=topic,
                mentions=curr,
                previous_mentions=prev,
                velocity=velocity,
                rank=0,
                event_time=at,
                spark=buckets[topic],
                classification=classification,
                classification_note=note,
            )
        )

    results.sort(key=lambda r: (-r.mentions, -r.velocity))
    for index, result in enumerate(results, start=1):
        result.rank = index
    return results[:limit]
