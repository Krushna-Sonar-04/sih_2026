"""Transparent KOL-candidate scoring.

Multiple network signals are combined - never follower count alone. Results are
always labelled "KOL candidate", never "confirmed influencer".
"""
from __future__ import annotations

from dataclasses import dataclass

from .network import NetworkSnapshot


@dataclass
class KolCandidate:
    account_id: str
    username: str
    platform: str
    label: str
    influence_score: float
    degree_centrality: float
    betweenness_centrality: float
    connected_accounts: list[str]
    cross_community_links: int
    post_count: int
    total_engagement: int
    related_narratives: list[str]
    rationale: str
    confidence: str


def score_kols(snapshot: NetworkSnapshot, posts: list, limit: int = 5) -> list[KolCandidate]:
    if not snapshot.nodes:
        return []

    posts_by_account: dict[str, list] = {}
    for post in posts:
        posts_by_account.setdefault(post.account_id, []).append(post)

    adjacency: dict[str, set[str]] = {}
    for edge in snapshot.edges:
        adjacency.setdefault(edge["source"], set()).add(edge["target"])
        adjacency.setdefault(edge["target"], set()).add(edge["source"])

    max_engagement = max(
        (sum(p.engagement for p in group) for group in posts_by_account.values()), default=1
    ) or 1

    candidates: list[KolCandidate] = []
    for node in snapshot.nodes:
        account_posts = posts_by_account.get(node.id, [])
        engagement = sum(p.engagement for p in account_posts)
        neighbours = adjacency.get(node.id, set())
        own_community = snapshot.communities.get(node.id)
        cross_community = sum(1 for n in neighbours if snapshot.communities.get(n) != own_community)

        score = round(
            100
            * (
                0.35 * node.degree_centrality
                + 0.25 * node.betweenness_centrality
                + 0.25 * (engagement / max_engagement)
                + 0.15 * min(1.0, cross_community / 3)
            ),
            1,
        )
        narratives = sorted({p.topic for p in account_posts if p.topic})
        rationale = (
            f"Degree centrality {node.degree_centrality:.2f}, betweenness {node.betweenness_centrality:.2f}, "
            f"{len(neighbours)} connected accounts, {cross_community} cross-community links, "
            f"{len(account_posts)} relevant posts with {engagement} total engagement."
        )
        candidates.append(
            KolCandidate(
                account_id=node.id,
                username=node.username,
                platform=node.platform,
                label="KOL candidate",
                influence_score=score,
                degree_centrality=node.degree_centrality,
                betweenness_centrality=node.betweenness_centrality,
                connected_accounts=sorted(neighbours),
                cross_community_links=cross_community,
                post_count=len(account_posts),
                total_engagement=engagement,
                related_narratives=narratives,
                rationale=rationale,
                confidence=(
                    "Derived from observed network structure in the selected window. "
                    "Indicative only - not a verified influencer identification."
                ),
            )
        )

    candidates.sort(key=lambda c: -c.influence_score)
    return candidates[:limit]
