"""Deterministic DRISHTI demo dataset.

Mirrors the frontend Demo Mode dataset: AI Regulation India, X + Telegram,
01-14 Sep 2026. Clearly simulated social activity - not real platform data.
"""
from __future__ import annotations

from datetime import datetime, timezone

YEAR = 2026


def ts(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(YEAR, 9, day, hour, minute, tzinfo=timezone.utc)


ACCOUNTS = [
    # id, username, platform, community, influence, centrality, first, peak, rationale
    ("aarav", "@AaravIntel", "X", "Policy analysts", 92, 0.88, ts(3, 9, 10), ts(10, 17, 20),
     "High network centrality combined with repeated amplification across connected accounts."),
    ("policy", "@PolicyWatch", "X", "Policy media", 81, 0.76, ts(1, 10, 0), ts(12, 12, 45),
     "Consistent bridge activity between policy and technology communities."),
    ("rights", "@DataRightsIndia", "X", "Digital rights", 86, 0.82, ts(5, 16, 20), ts(8, 14, 30),
     "Rapid cross-community amplification around privacy safeguards."),
    ("tech", "@TechPolicyHub", "Telegram", "Technology policy", 74, 0.69, ts(2, 11, 40), ts(9, 18, 5),
     "Early source of discussion later referenced across X."),
    ("open", "@OpenAIObserver", "X", "Open technology", 67, 0.58, ts(6, 8, 15), ts(11, 13, 15),
     "Repeated topical participation across open-source AI discussions."),
    ("digital", "@DigitalIndiaForum", "Telegram", "Digital governance", 78, 0.72, ts(1, 15, 25), ts(12, 18, 10),
     "Connects governance channels with wider technology-policy discussion."),
    ("jobs", "@FutureSkillsIN", "X", "Workforce", 59, 0.44, ts(9, 9, 40), ts(13, 15, 30),
     "Focused amplification within the employment and skills community."),
    ("civic", "@CivicStack", "Telegram", "Civic technology", 63, 0.51, ts(7, 19, 20), ts(10, 10, 50),
     "Cross-platform references connect civic technology conversations."),
]

# snapshot index -> timestamp / phase / event kind / label / summary
SNAPSHOTS = [
    (0, ts(1, 9, 0), "Low activity", "baseline", "Monitoring baseline",
     "Baseline monitoring: limited discussion across both platforms."),
    (1, ts(4, 18, 0), "Early discussion", "emergence", "Narrative emergence",
     "Discussion emerges in Telegram policy channels."),
    (2, ts(6, 11, 20), "Discussion accelerating", "trend", "Discussion velocity increasing",
     "Mention velocity increases across monitored sources."),
    (3, ts(8, 14, 30), "Narrative ignition", "sentiment", "Narrative ignition - Sentiment shift",
     "Privacy safeguards became the bridge from policy discussion to negative sentiment."),
    (4, ts(9, 18, 5), "Cross-platform acceleration", "cross-platform", "Cross-platform acceleration",
     "Telegram-origin discussion crossed into X and attracted new amplifiers."),
    (5, ts(10, 16, 40), "Influence expansion", "influence", "Influence activity",
     "High-centrality accounts expanded reach across communities."),
    (6, ts(12, 18, 10), "Peak activity", "peak", "Peak activity",
     "Policy discussion reached its highest observed volume in the demo window."),
    (7, ts(14, 20, 0), "Sustained discussion", "baseline", "Activity stabilizing after peak",
     "Activity stabilizes after the peak while implementation questions remain."),
]

EDGES = [
    ("e1", "tech", "policy", "cross-platform", 62, 1),
    ("e2", "policy", "aarav", "mention", 70, 2),
    ("e3", "tech", "rights", "cross-platform", 84, 3),
    ("e4", "rights", "aarav", "repost", 91, 3),
    ("e5", "aarav", "digital", "mention", 73, 4),
    ("e6", "civic", "rights", "forward", 67, 4),
    ("e7", "policy", "open", "reply", 58, 5),
    ("e8", "aarav", "jobs", "mention", 52, 6),
    ("e9", "digital", "jobs", "cross-platform", 64, 6),
    ("e10", "open", "digital", "repost", 61, 7),
]

# account, platform, topic, text, engagement, snapshot
POSTS = [
    ("policy", "X", "AI Regulation",
     "A practical AI framework needs clear implementation milestones, not only broad principles.", 280, 0),
    ("tech", "Telegram", "AI Regulation",
     "Early discussion: members are comparing the draft with existing technology policy frameworks.", 190, 0),
    ("digital", "Telegram", "Government Policy",
     "Good to see the consultation window include startups, researchers and citizen groups.", 430, 1),
    ("aarav", "X", "AI Regulation",
     "Regulatory clarity can support innovation and progress when safeguards are explicit. A welcome step.", 1100, 1),
    ("policy", "X", "Government Policy",
     "Mentions of implementation detail are rising across policy media accounts.", 620, 2),
    ("tech", "Telegram", "Data Privacy",
     "Members are worried about the vague data-retention language in the draft.", 540, 2),
    ("rights", "X", "Data Privacy",
     "Alarming: privacy safeguards are an afterthought here. This is a serious risk to citizens and we oppose it.",
     4800, 3),
    ("tech", "Telegram", "Data Privacy",
     "Retention rules are dangerously weak. Members fear misuse and there is no independent oversight at all.",
     1600, 3),
    ("aarav", "X", "Data Privacy",
     "Disappointing. The implementation detail fails on consent, and the harm to small developers is being ignored.",
     3900, 3),
    ("civic", "Telegram", "Data Privacy",
     "Forwarded warnings show the privacy concern spreading from specialist groups into worried civic channels.",
     2200, 4),
    ("policy", "X", "Government Policy",
     "A phased implementation plan could address industry readiness while preserving accountability.", 3100, 4),
    ("digital", "Telegram", "Government Policy",
     "Criticism of the government framing is now the dominant response to the privacy debate.", 1800, 4),
    ("open", "X", "Open Source AI",
     "Open-source developers fear compliance costs will crush smaller model providers.", 1700, 5),
    ("aarav", "X", "Government Policy",
     "Cross-community references indicate policy interpretation is now driving amplification.", 5200, 5),
    ("jobs", "X", "AI Jobs",
     "Exciting opportunity: new skills programmes could benefit workers if funding is confirmed.", 1400, 6),
    ("rights", "X", "Data Privacy",
     "Peak anger over consent and retention continues. Without independent review this remains a threat.",
     6100, 6),
    ("digital", "Telegram", "AI Regulation",
     "Activity is stabilizing, but unresolved implementation problems still concern members.", 2400, 7),
    ("civic", "Telegram", "AI Regulation",
     "Channels are summarising the fortnight of discussion for members.", 900, 7),
]

WATCHES = [
    ("ai-regulation-india", "AI Regulation India", "AI Act, regulation, privacy", "X,Telegram", "Rising"),
    ("data-privacy-discussion", "Data Privacy Discussion", "data rights, consent, retention", "X,Telegram", "Accelerating"),
    ("digital-public-infrastructure", "Digital Public Infrastructure", "DPI, India Stack, governance", "X", "Stable"),
    ("emerging-technology-policy", "Emerging Technology Policy", "deeptech, policy, innovation", "Telegram", "Monitoring"),
]

ALERTS = [
    ("alert-sentiment", "ai-regulation-india", 3, "Sentiment shift",
     "Negative sentiment increased around policy implementation discussion.", "High", None, None),
    ("alert-trend", "ai-regulation-india", 3, "Rising narrative",
     "Data Privacy accelerated across monitored platforms.", "Rising", "Data Privacy", None),
    ("alert-influence", "ai-regulation-india", 5, "Influence activity",
     "A high-centrality account amplified discussion across connected communities.", "Medium", None, "aarav"),
    ("alert-cross", "ai-regulation-india", 4, "Cross-platform signal",
     "Telegram-to-X references increased significantly.", "Signal", "Data Privacy", None),
]

HISTORY = [
    ("h1", "ai-regulation-india", 6, "Peak activity review", "Analyst Sonar", "Reviewed", None, None),
    ("h2", "ai-regulation-india", 6, "Network expansion", "Analyst Sonar", "Saved", None, "aarav"),
    ("h3", "data-privacy-discussion", 3, "Sentiment shift", "Meera K.", "Reviewed", "Data Privacy", None),
    ("h4", "digital-public-infrastructure", 2, "Narrative emergence", "Rajeev N.", "Archived", None, None),
]

DEMOGRAPHIC_DIMENSIONS = {
    "age_cohort": ["18-24", "25-34", "35-44", "45+"],
    "region": ["North India", "West India", "South India", "East India"],
    "language": ["English", "Hindi", "Marathi", "Mixed / Code-Mixed"],
    "professional_interest": ["Technology", "Policy", "Students", "Business"],
}


def demographics_for(index: int) -> dict[str, dict[str, float]]:
    """Aggregate cohort percentages that shift modestly across the timeline."""
    i = index
    return {
        "age_cohort": {"18-24": 34 + i, "25-34": 36 - i, "35-44": 20, "45+": max(3.0, 10 - i * 0.5)},
        "region": {"North India": 31 + i, "West India": 29, "South India": 25 - i, "East India": max(3.0, 15 - i * 0.6)},
        "language": {"English": 45 - i, "Hindi": 29 + i, "Marathi": 14, "Mixed / Code-Mixed": max(3.0, 12 - i * 0.4)},
        "professional_interest": {"Technology": 39 - i, "Policy": 26 + i, "Students": 22, "Business": max(3.0, 13 - i * 0.5)},
    }
