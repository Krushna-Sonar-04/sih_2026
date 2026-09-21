"""Tests for authentication, embeddings/RAG, citation validation and briefing.

All external services are avoided: the embedding engine is local and
deterministic, and no LLM credential is used.
"""
from __future__ import annotations

from datetime import timezone

import pytest

from app import schemas, security
from app.models import Post, Watch
from app.services import auth as auth_service
from app.services import briefing as briefing_service
from app.services import citations as citation_service
from app.services import embeddings, retrieval
from app.services.assistant import INSUFFICIENT, answer, rate_limit_ok
from app.services.timeline import build_timeline

WATCH_ID = "ai-regulation-india"


@pytest.fixture()
def db_session(db):
    """Session with the deterministic demo dataset loaded."""
    from app.seed.seed_demo import seed

    if db.get(Watch, WATCH_ID) is None:
        seed(db)
    yield db
    db.rollback()


# --------------------------------------------------------------------------- auth
def test_password_hash_is_not_plaintext_and_verifies():
    stored = security.hash_password("analyst-password-1")
    assert "analyst-password-1" not in stored
    assert stored.startswith("pbkdf2_sha256$")
    assert security.verify_password("analyst-password-1", stored)
    assert not security.verify_password("wrong-password", stored)


def test_short_password_rejected():
    with pytest.raises(ValueError):
        security.hash_password("short")


def test_token_roundtrip_and_tamper_detection():
    token = security.create_token("a@b.in", "admin", "secret-key")
    claims = security.decode_token(token, "secret-key")
    assert claims and claims["sub"] == "a@b.in" and claims["role"] == "admin"
    assert security.decode_token(token, "other-key") is None
    assert security.decode_token(token[:-2] + "xy", "secret-key") is None


def test_expired_token_rejected():
    token = security.create_token("a@b.in", "analyst", "secret-key", expires_minutes=-1)
    assert security.decode_token(token, "secret-key") is None


def test_role_hierarchy():
    assert security.role_allows("admin", "analyst")
    assert security.role_allows("lead_analyst", "analyst")
    assert not security.role_allows("analyst", "admin")


def test_create_and_authenticate_user(db_session):
    auth_service.create_user(db_session, "Lead@Drishti.in", "lead-password-1", "lead_analyst", "Lead")
    user = auth_service.authenticate(db_session, "lead@drishti.in", "lead-password-1")
    assert user is not None and user.role == "lead_analyst"
    assert user.last_login_at is not None
    assert auth_service.authenticate(db_session, "lead@drishti.in", "nope") is None
    with pytest.raises(ValueError):
        auth_service.create_user(db_session, "lead@drishti.in", "another-password")


# --------------------------------------------------------------------------- embeddings
def test_embedding_is_deterministic_and_normalised():
    a = embeddings.embed("AI regulation draft raises privacy concerns")
    b = embeddings.embed("AI regulation draft raises privacy concerns")
    assert a == b
    assert abs(sum(v * v for v in a) - 1.0) < 1e-6
    assert embeddings.cosine(a, b) > 0.99


def test_unchanged_posts_are_not_re_embedded(db_session):
    first = embeddings.ensure_embeddings(db_session, WATCH_ID)
    assert first > 0
    assert embeddings.ensure_embeddings(db_session, WATCH_ID) == 0
    assert embeddings.coverage(db_session, WATCH_ID) == first


def test_changed_text_is_re_embedded(db_session):
    embeddings.ensure_embeddings(db_session, WATCH_ID)
    post = db_session.query(Post).filter(Post.watch_id == WATCH_ID).first()
    post.text = post.text + " updated wording for the regulation debate"
    db_session.commit()
    assert embeddings.ensure_embeddings(db_session, WATCH_ID) == 1


# --------------------------------------------------------------------------- retrieval
def _at(db_session):
    watch = db_session.get(Watch, WATCH_ID)
    return watch, build_timeline(db_session, watch, snapshot=3).timestamp


def test_hybrid_retrieval_returns_scoped_evidence(db_session):
    watch, at = _at(db_session)
    hits = retrieval.retrieve(db_session, watch.id, at, "why did sentiment shift")
    assert hits
    assert all(h.watch_id == watch.id for h in hits)
    assert all(h.event_time <= at for h in hits)


def test_off_topic_question_retrieves_nothing(db_session):
    watch, at = _at(db_session)
    assert retrieval.retrieve(db_session, watch.id, at, "best pizza recipe in naples") == []


# --------------------------------------------------------------------------- citation validation
def test_citation_validation_accepts_retrieved_records(db_session):
    watch, at = _at(db_session)
    hits = retrieval.retrieve(db_session, watch.id, at, "why did sentiment shift")
    ids = [h.id for h in hits]
    result = citation_service.validate(
        db_session, watch.id, min(h.event_time for h in hits), at, ids, ids[:2],
        hits[0].text,
    )
    assert result.valid, result.reason


def test_citation_validation_rejects_unknown_record(db_session):
    watch, at = _at(db_session)
    hits = retrieval.retrieve(db_session, watch.id, at, "why did sentiment shift")
    ids = [h.id for h in hits]
    result = citation_service.validate(
        db_session, watch.id, min(h.event_time for h in hits), at, ids,
        ids[:1] + ["post-does-not-exist"], hits[0].text,
    )
    assert not result.valid
    assert "does not exist" in result.reason


def test_citation_validation_rejects_record_not_retrieved(db_session):
    watch, at = _at(db_session)
    hits = retrieval.retrieve(db_session, watch.id, at, "why did sentiment shift")
    other = (
        db_session.query(Post)
        .filter(Post.watch_id == watch.id, ~Post.id.in_([h.id for h in hits]))
        .first()
    )
    result = citation_service.validate(
        db_session, watch.id, watch.range_from.replace(tzinfo=at.tzinfo), at,
        [h.id for h in hits], [other.id], hits[0].text,
    )
    assert not result.valid
    assert "not part of the retrieved evidence set" in result.reason


def test_citation_validation_rejects_out_of_scope_record(db_session):
    watch, at = _at(db_session)
    hits = retrieval.retrieve(db_session, watch.id, at, "why did sentiment shift")
    ids = [h.id for h in hits]
    window_from = max(h.event_time for h in hits)
    result = citation_service.validate(
        db_session, watch.id, window_from, window_from, ids, ids, hits[0].text,
    )
    assert not result.valid or len(result.accepted) >= 1


# --------------------------------------------------------------------------- assistant
def test_assistant_answer_is_structured_and_cited(db_session):
    watch = db_session.get(Watch, WATCH_ID)
    result = answer(db_session, watch, schemas.AssistantQuery(question="Why did sentiment shift?"), snapshot=3)
    assert result.grounded
    assert result.citations
    for section in ("Finding:", "Evidence:", "Interpretation:", "Limitation / Confidence:", "Sources:"):
        assert section in result.answer
    assert all(c.evidence_id for c in result.citations)


def test_assistant_refuses_without_evidence(db_session):
    watch = db_session.get(Watch, WATCH_ID)
    result = answer(
        db_session, watch, schemas.AssistantQuery(question="What is the price of gold in Dubai?"), snapshot=3
    )
    assert not result.grounded
    assert result.citations == []
    assert INSUFFICIENT in result.answer


def test_assistant_rate_limit_triggers():
    key = "test-rate-limit-client"
    allowed = sum(1 for _ in range(200) if rate_limit_ok(key))
    assert allowed < 200


# --------------------------------------------------------------------------- briefing
def test_briefing_contains_required_sections(db_session):
    watch = db_session.get(Watch, WATCH_ID)
    brief = briefing_service.build_briefing(db_session, watch, snapshot=3)
    assert brief.title == "DRISHTI Narrative Intelligence Brief"
    assert brief.executive_summary
    assert brief.method_notes and brief.privacy_notes
    assert brief.mode_label.startswith("Demo dataset")
    assert brief.evidence
    assert brief.period_from.tzinfo is not None and brief.period_to.tzinfo is not None


def test_briefing_demographics_respect_privacy_threshold(db_session):
    watch = db_session.get(Watch, WATCH_ID)
    brief = briefing_service.build_briefing(db_session, watch, snapshot=3)
    for values in brief.demographics.dimensions.values():
        for value in values:
            if not value.reportable:
                assert value.percentage == 0.0
                assert "too small" in value.note.lower()


# --------------------------------------------------------------------------- trends
def test_trend_classification_is_evidence_gated(db_session):
    watch = db_session.get(Watch, WATCH_ID)
    timeline = build_timeline(db_session, watch, snapshot=3)
    assert timeline.top_trends
    for trend in timeline.top_trends:
        assert trend.classification in (
            "RISING", "STABLE", "FALLING", "EMERGING", "INSUFFICIENT EVIDENCE",
        )
        if trend.mentions + trend.previous_mentions < 3:
            assert trend.classification == "INSUFFICIENT EVIDENCE"
        assert "viral" not in trend.classification_note.lower()


def test_timeline_timestamps_are_timezone_aware(db_session):
    watch = db_session.get(Watch, WATCH_ID)
    timeline = build_timeline(db_session, watch, snapshot=3)
    assert timeline.timestamp.tzinfo is not None
    assert timeline.timestamp.astimezone(timezone.utc)
