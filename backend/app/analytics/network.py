"""Link analysis and network topology using NetworkX."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import networkx as nx


@dataclass
class NetworkNode:
    id: str
    username: str
    platform: str
    community: str
    degree_centrality: float
    betweenness_centrality: float
    influence_score: float
    connections: int


@dataclass
class NetworkSnapshot:
    nodes: list[NetworkNode] = field(default_factory=list)
    edges: list[dict] = field(default_factory=list)
    communities: dict[str, str] = field(default_factory=dict)
    density: float = 0.0


def build_graph(edges: list, accounts: list, at: datetime) -> nx.DiGraph:
    """Graph of relationships observed at or before the selected timestamp."""
    graph = nx.DiGraph()
    by_id = {a.id: a for a in accounts}
    for edge in edges:
        if edge.event_time and edge.event_time > at:
            continue
        for node_id in (edge.source_account, edge.target_account):
            if node_id not in graph:
                account = by_id.get(node_id)
                graph.add_node(
                    node_id,
                    username=getattr(account, "username", node_id),
                    platform=getattr(account, "platform", "X"),
                    community=getattr(account, "community", "Unassigned"),
                )
        graph.add_edge(
            edge.source_account,
            edge.target_account,
            weight=edge.weight,
            relationship_type=edge.relationship_type,
            event_time=edge.event_time,
            id=edge.id,
        )
    return graph


def analyze_network(edges: list, accounts: list, at: datetime) -> NetworkSnapshot:
    graph = build_graph(edges, accounts, at)
    if graph.number_of_nodes() == 0:
        return NetworkSnapshot()

    degree = nx.degree_centrality(graph)
    try:
        betweenness = nx.betweenness_centrality(graph)
    except Exception:  # pragma: no cover - defensive
        betweenness = {n: 0.0 for n in graph.nodes}

    undirected = graph.to_undirected()
    communities: dict[str, str] = {}
    try:
        detected = nx.community.greedy_modularity_communities(undirected)
        for index, group in enumerate(detected):
            for node in group:
                communities[node] = f"Community {index + 1}"
    except Exception:  # pragma: no cover
        for node in graph.nodes:
            communities[node] = graph.nodes[node].get("community", "Unassigned")

    nodes: list[NetworkNode] = []
    for node_id, data in graph.nodes(data=True):
        connections = graph.degree(node_id)
        influence = round(
            100 * (0.5 * degree.get(node_id, 0.0) + 0.3 * betweenness.get(node_id, 0.0) + 0.2 * min(1.0, connections / 6)),
            1,
        )
        nodes.append(
            NetworkNode(
                id=node_id,
                username=data.get("username", node_id),
                platform=data.get("platform", "X"),
                community=communities.get(node_id, data.get("community", "Unassigned")),
                degree_centrality=round(degree.get(node_id, 0.0), 4),
                betweenness_centrality=round(betweenness.get(node_id, 0.0), 4),
                influence_score=influence,
                connections=connections,
            )
        )

    edge_payload = [
        {
            "id": data.get("id", f"{s}-{t}"),
            "source": s,
            "target": t,
            "relationship_type": data.get("relationship_type", "mention"),
            "weight": data.get("weight", 1.0),
        }
        for s, t, data in graph.edges(data=True)
    ]
    return NetworkSnapshot(
        nodes=sorted(nodes, key=lambda n: -n.influence_score),
        edges=edge_payload,
        communities=communities,
        density=round(nx.density(graph), 4),
    )
