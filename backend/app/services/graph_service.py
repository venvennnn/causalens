from __future__ import annotations

from collections import defaultdict

import networkx as nx

from app.models.schemas import CausalEdge, Event


def build_graph(events: list[Event], edges: list[CausalEdge]) -> nx.DiGraph:
    graph = nx.DiGraph()
    for event in events:
        graph.add_node(event.id, event=event)
    for edge in edges:
        if edge.source_event_id in graph and edge.target_event_id in graph:
            graph.add_edge(edge.source_event_id, edge.target_event_id, edge=edge)
    return graph


def _event_map(graph: nx.DiGraph) -> dict[str, Event]:
    return {node: data["event"] for node, data in graph.nodes(data=True)}


def _edge_map(graph: nx.DiGraph) -> dict[tuple[str, str], CausalEdge]:
    return {(u, v): data["edge"] for u, v, data in graph.edges(data=True)}


def get_why(graph: nx.DiGraph, event_id: str) -> dict:
    if event_id not in graph:
        return {"event_id": event_id, "ancestors": [], "paths": [], "narrative": []}
    ancestors = list(nx.ancestors(graph, event_id))
    subgraph_nodes = ancestors + [event_id]
    paths: list[list[str]] = []
    for ancestor in ancestors:
        if nx.has_path(graph, ancestor, event_id):
            for path in nx.all_simple_paths(graph.subgraph(subgraph_nodes), ancestor, event_id, cutoff=6):
                if len(path) >= 2:
                    paths.append(path)
    paths = sorted(paths, key=len)[:12]
    events = _event_map(graph)
    edges = _edge_map(graph)
    narrative = []
    best = max(paths, key=len, default=[event_id])
    for step, (source, target) in enumerate(zip(best, best[1:]), start=1):
        edge = edges.get((source, target))
        narrative.append(
            {
                "step": step,
                "from_event_id": source,
                "to_event_id": target,
                "from_title": events[source].title,
                "to_title": events[target].title,
                "relation": edge.relation if edge else "AFFECTS",
                "text": edge.reason if edge else events[target].summary,
                "status": edge.status if edge else "inferred",
            }
        )
    if not narrative:
        narrative.append(
            {
                "step": 1,
                "from_event_id": event_id,
                "to_event_id": event_id,
                "from_title": events[event_id].title,
                "to_title": events[event_id].title,
                "relation": None,
                "text": events[event_id].summary,
                "status": "observed",
            }
        )
    return {
        "event_id": event_id,
        "ancestors": [events[node_id].model_dump(mode="json") for node_id in ancestors],
        "highlight_node_ids": subgraph_nodes,
        "highlight_edge_ids": [
            edges[(u, v)].id
            for path in paths
            for u, v in zip(path, path[1:])
            if (u, v) in edges
        ],
        "paths": paths,
        "narrative": narrative,
        "title": "WHY THIS HAPPENED",
    }


def get_what_next(graph: nx.DiGraph, event_id: str) -> dict:
    if event_id not in graph:
        return {"event_id": event_id, "descendants": [], "observed": [], "predicted": [], "paths": []}
    descendants = list(nx.descendants(graph, event_id))
    subgraph_nodes = [event_id] + descendants
    events = _event_map(graph)
    edges = _edge_map(graph)
    observed = []
    predicted = []
    paths: list[list[str]] = []
    for descendant in descendants:
        if nx.has_path(graph, event_id, descendant):
            for path in nx.all_simple_paths(graph.subgraph(subgraph_nodes), event_id, descendant, cutoff=6):
                if len(path) >= 2:
                    paths.append(path)
        edge_statuses = [
            edges[(pred, descendant)].status
            for pred in graph.predecessors(descendant)
            if (pred, descendant) in edges and pred in subgraph_nodes
        ]
        payload = events[descendant].model_dump(mode="json")
        if edge_statuses and all(status == "predicted" for status in edge_statuses):
            payload["via_status"] = "predicted"
            predicted.append(payload)
        else:
            payload["via_status"] = "observed" if any(status == "observed" for status in edge_statuses) else "inferred"
            observed.append(payload)
    return {
        "event_id": event_id,
        "title": "LIKELY DOWNSTREAM EFFECTS",
        "descendants": [events[node_id].model_dump(mode="json") for node_id in descendants],
        "highlight_node_ids": subgraph_nodes,
        "highlight_edge_ids": [
            edges[(u, v)].id
            for path in paths
            for u, v in zip(path, path[1:])
            if (u, v) in edges
        ],
        "observed": observed,
        "predicted": predicted,
        "paths": sorted(paths, key=len)[:16],
    }


def get_regional_ripple(graph: nx.DiGraph, event_id: str) -> dict:
    if event_id not in graph:
        return {"event_id": event_id, "markets": [], "nodes": [], "paths": []}
    events = _event_map(graph)
    edges = _edge_map(graph)
    descendants = list(nx.descendants(graph, event_id))
    ripple_nodes: set[str] = set()
    ripple_paths: list[list[str]] = []
    cross_ids: list[str] = []
    for descendant in descendants:
        for path in nx.all_simple_paths(graph, event_id, descendant, cutoff=8):
            if any(edges.get((u, v)) and edges[(u, v)].cross_border for u, v in zip(path, path[1:])):
                ripple_paths.append(path)
                ripple_nodes.update(path)
                for u, v in zip(path, path[1:]):
                    edge = edges.get((u, v))
                    if edge and edge.cross_border:
                        cross_ids.append(edge.id)
    grouped: dict[str, list[str]] = defaultdict(list)
    for node_id in ripple_nodes:
        for country in events[node_id].countries or ["Unspecified"]:
            if node_id not in grouped[country]:
                grouped[country].append(node_id)
    markets = [
        {
            "country": country,
            "event_ids": node_ids,
            "events": [events[node_id].model_dump(mode="json") for node_id in node_ids],
        }
        for country, node_ids in grouped.items()
    ]
    markets.sort(key=lambda item: (-len(item["event_ids"]), item["country"]))
    return {
        "event_id": event_id,
        "title": "REGIONAL RIPPLE",
        "markets_connected": len(markets),
        "markets": markets,
        "highlight_node_ids": list(ripple_nodes),
        "highlight_edge_ids": list(dict.fromkeys(cross_ids)),
        "paths": ripple_paths[:20],
        "cross_border_edge_ids": list(dict.fromkeys(cross_ids)),
    }


def get_path(graph: nx.DiGraph, source_id: str, target_id: str) -> dict:
    if source_id not in graph or target_id not in graph or not nx.has_path(graph, source_id, target_id):
        return {"source_id": source_id, "target_id": target_id, "paths": []}
    paths = list(nx.all_simple_paths(graph, source_id, target_id, cutoff=8))
    return {"source_id": source_id, "target_id": target_id, "paths": paths[:10]}
