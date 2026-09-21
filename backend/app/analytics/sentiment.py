"""Multi-dimensional sentiment inference.

Primary engine: VADER (open-source, CPU-only, runs within normal demo compute).
Fallback: deterministic lexicon scoring so the pipeline never hard-fails.

Beyond polarity the module reports the DRISHTI analytical vocabulary
(support / opposition / anxiety / excitement / sarcasm) using transparent
lexicon heuristics. These are heuristic indicators, not a trained sarcasm
classifier, and the API labels them accordingly.
"""
from __future__ import annotations

from dataclasses import dataclass, field

try:  # pragma: no cover - import guard
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    _vader: SentimentIntensityAnalyzer | None = SentimentIntensityAnalyzer()
    ENGINE = "vader"
except Exception:  # pragma: no cover
    _vader = None
    ENGINE = "lexicon-fallback"

POSITIVE_WORDS = {"support", "welcome", "clarity", "positive", "benefit", "innovation", "progress", "good", "improve"}
NEGATIVE_WORDS = {"concern", "risk", "afterthought", "fail", "threat", "oppose", "problem", "unresolved", "harm"}

EMOTION_LEXICON: dict[str, set[str]] = {
    "Support": {"support", "welcome", "endorse", "agree", "constructive", "positive", "backing"},
    "Opposition": {"oppose", "reject", "against", "resist", "criticism", "objection", "pushback"},
    "Anxiety": {"concern", "worry", "risk", "fear", "uncertain", "threat", "unresolved", "afterthought"},
    "Excitement": {"exciting", "breakthrough", "opportunity", "innovation", "promising", "momentum"},
    "Sarcasm": {"sure", "obviously", "brilliant", "genius", "totally", "of course", "wow"},
}

EMOTIONS = list(EMOTION_LEXICON.keys())


@dataclass
class SentimentInference:
    label: str
    confidence: float
    stance: str
    engine: str
    emotions: dict[str, float] = field(default_factory=dict)


def _lexicon_polarity(text: str) -> float:
    tokens = set(text.lower().replace(".", " ").replace(",", " ").split())
    pos = len(tokens & POSITIVE_WORDS)
    neg = len(tokens & NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total


def _emotion_scores(text: str) -> dict[str, float]:
    lowered = text.lower()
    scores: dict[str, float] = {}
    for emotion, words in EMOTION_LEXICON.items():
        hits = sum(1 for word in words if word in lowered)
        scores[emotion] = round(min(1.0, hits / 3.0), 3)
    if "!" in text and "?" in text:
        scores["Sarcasm"] = round(min(1.0, scores["Sarcasm"] + 0.2), 3)
    return scores


def analyze(text: str) -> SentimentInference:
    """Classify a single post. Never raises - callers mark failures Unlabeled."""
    if not text or not text.strip():
        return SentimentInference("Unlabeled", 0.0, "Neutral", ENGINE, {e: 0.0 for e in EMOTIONS})

    if _vader is not None:
        scores = _vader.polarity_scores(text)
        compound = scores["compound"]
        confidence = round(min(0.99, 0.55 + abs(compound) * 0.45), 3)
    else:
        compound = _lexicon_polarity(text)
        confidence = round(min(0.95, 0.5 + abs(compound) * 0.4), 3)

    if compound >= 0.15:
        label, stance = "Positive", "Support"
    elif compound <= -0.15:
        label, stance = "Negative", "Opposition"
    else:
        label, stance = "Neutral", "Neutral"

    emotions = _emotion_scores(text)
    return SentimentInference(label, confidence, stance, ENGINE, emotions)


def engine_health() -> dict:
    return {
        "component": "Sentiment engine",
        "status": "Operational",
        "detail": (
            "VADER open-source polarity model with lexicon-based emotion indicators."
            if _vader is not None
            else "Deterministic lexicon fallback active (vaderSentiment not installed)."
        ),
        "engine": ENGINE,
    }
