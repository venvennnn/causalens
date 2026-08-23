from __future__ import annotations

from dataclasses import dataclass, field

from app.config import get_settings
from app.logging import log
from app.models.schemas import Article, CausalEdge, Event, GraphDiagnostics, RejectedCandidate
from app.services.event_dedup import dedupe_events
from app.services.query_intent import QueryIntent
from app.services.relations import apply_relation_policy
from app.services.relevance import RelevanceResult, classify_article, classify_event

STRONG_CAUSAL = {"CAUSES", "TRIGGERS", "CONTRIBUTES_TO", "ENABLES", "CONSTRAINS"}


@dataclass
class ClassifiedArticle:
    article: Article
    result: RelevanceResult


@dataclass
class GraphBuildResult:
    events: list[Event]
    edges: list[CausalEdge]
    articles: list[Article]
    diagnostics: GraphDiagnostics
    classified: list[ClassifiedArticle] = field(default_factory=list)


def _norm(values: list[str]) -> set[str]:
    return {item.strip().lower() for item in values if item and str(item).strip()}


def context_connection_score(candidate: Event, core: Event) -> tuple[float, dict[str, float]]:
    shared_entities = len(_norm(candidate.companies) & _norm(core.companies)) + len(
        {ent.name.lower() for ent in candidate.entities} & {ent.name.lower() for ent in core.entities}
    )
    shared_entity_score = min(1.0, shared_entities * 0.35)
    shared_industries = len(_norm(candidate.industries) & _norm(core.industries))
    shared_supply_chain_score = min(1.0, shared_industries * 0.4)
    if "semiconductor" in " ".join(candidate.industries + core.industries).lower():
        shared_supply_chain_score = max(shared_supply_chain_score, 0.35)
    explicit_relation_score = 0.0
    blob = f"{candidate.title} {candidate.summary} {core.title} {core.summary}".lower()
    if any(term in blob for term in ("supply chain", "spillover", "corridor", "capacity", "demand")):
        explicit_relation_score = 0.25
    temporal_proximity_score = 0.1
    if candidate.event_date and core.event_date:
        delta = abs((candidate.event_date - core.event_date).days)
        temporal_proximity_score = 0.35 if delta <= 14 else 0.2 if delta <= 60 else 0.05
    geo_overlap = _norm(candidate.countries) & _norm(core.countries)
    geography_connection_score = 0.4 if geo_overlap else 0.12 if candidate.countries and core.countries else 0.0
    total = (
        shared_entity_score
        + shared_supply_chain_score
        + explicit_relation_score
        + temporal_proximity_score
        + geography_connection_score
    )
    breakdown = {
        "shared_entity_score": round(shared_entity_score, 2),
        "shared_supply_chain_score": round(shared_supply_chain_score, 2),
        "explicit_relation_score": round(explicit_relation_score, 2),
        "temporal_proximity_score": round(temporal_proximity_score, 2),
        "geography_connection_score": round(geography_connection_score, 2),
        "contextScore": round(total, 2),
    }
    return total, breakdown


def classify_articles(intent: QueryIntent, articles: list[Article]) -> list[ClassifiedArticle]:
    return [ClassifiedArticle(article=article, result=classify_article(intent, article)) for article in articles]


def annotate_events(
    intent: QueryIntent,
    events: list[Event],
    articles: dict[str, Article],
    article_class: dict[str, RelevanceResult],
) -> list[Event]:
    annotated: list[Event] = []
    for event in events:
        source_labels = [
            article_class[article_id].classification
            for article_id in event.source_article_ids
            if article_id in article_class
        ]
        result = classify_event(intent, event, articles)
        if result.classification == "CORE" or "CORE" in source_labels and result.core_eligible:
            event.relevance_class = "CORE"
        elif result.classification == "CONTEXT" or "CONTEXT" in source_labels:
            event.relevance_class = "CONTEXT"
        else:
            event.relevance_class = "CONTEXT" if result.context_eligible else None
            if event.relevance_class is None:
                continue
        if event.relevance_class == "CORE" and result.classification == "REJECTED":
            # Event text failed gates even if a noisy source was tagged CORE.
            if not result.core_eligible:
                event.relevance_class = "CONTEXT" if result.context_eligible else None
                if event.relevance_class is None:
                    continue
        event.relevance_score = result.overall_relevance
        event.relevance_breakdown = result.breakdown()
        event.relevance_reason = result.reason
        annotated.append(event)
    return annotated


def admit_context_events(
    core_events: list[Event],
    context_events: list[Event],
    *,
    min_score: float,
    limit: int,
) -> list[Event]:
    if not core_events:
        return []
    admitted: list[tuple[float, Event]] = []
    for event in context_events:
        best = 0.0
        best_break: dict[str, float] = {}
        for core in core_events:
            score, breakdown = context_connection_score(event, core)
            if score > best:
                best = score
                best_break = breakdown
        if best < min_score:
            continue
        breakdown = dict(event.relevance_breakdown or {})
        breakdown["contextConnection"] = round(best, 2)
        breakdown.update(best_break)
        event.relevance_breakdown = breakdown
        event.relevance_score = max(event.relevance_score or 0.0, min(0.67, best / 2.2))
        admitted.append((best, event))
    admitted.sort(key=lambda item: item[0], reverse=True)
    return [event for _, event in admitted[:limit]]


def filter_edges_to_core_graph(events: list[Event], edges: list[CausalEdge]) -> list[CausalEdge]:
    by_id = {event.id: event for event in events}
    kept: list[CausalEdge] = []
    seen: set[tuple[str, str, str]] = set()
    for edge in edges:
        source = by_id.get(edge.source_event_id)
        target = by_id.get(edge.target_event_id)
        if source is None or target is None or source.id == target.id:
            continue
        source_cls = source.relevance_class or "CORE"
        target_cls = target.relevance_class or "CORE"
        if source_cls == "CONTEXT" and target_cls == "CONTEXT":
            continue
        key = (edge.source_event_id, edge.target_event_id, edge.relation)
        if key in seen:
            continue
        seen.add(key)
        kept.append(edge)
    return kept


def finalize_edges(
    events: list[Event],
    edges: list[CausalEdge],
    articles: list[Article] | dict[str, Article],
) -> list[CausalEdge]:
    article_map = articles if isinstance(articles, dict) else {item.id: item for item in articles}
    by_id = {event.id: event for event in events}
    finalized: list[CausalEdge] = []
    for edge in edges:
        source = by_id.get(edge.source_event_id)
        target = by_id.get(edge.target_event_id)
        if source is None or target is None:
            continue
        finalized.append(apply_relation_policy(edge, source, target, article_map))
    return filter_edges_to_core_graph(events, finalized)


def graph_metrics(events: list[Event], edges: list[CausalEdge], rejected_count: int) -> dict:
    core = [event for event in events if (event.relevance_class or "CORE") == "CORE"]
    context = [event for event in events if event.relevance_class == "CONTEXT"]
    core_scores = [event.relevance_score or 0.0 for event in core]
    edge_scores = [edge.evidence_score or edge.confidence for edge in edges]
    related = sum(1 for edge in edges if edge.relation == "RELATED_TO")
    strong = sum(1 for edge in edges if edge.relation in STRONG_CAUSAL)
    core_count = len(core)
    context_count = len(context)
    metrics = {
        "core_node_count": core_count,
        "context_node_count": context_count,
        "rejected_candidate_count": rejected_count,
        "core_ratio": round(core_count / max(core_count + context_count, 1), 2),
        "context_to_core_ratio": round(context_count / max(core_count, 1), 2),
        "average_core_relevance": round(sum(core_scores) / max(len(core_scores), 1), 2),
        "average_edge_confidence": round(sum(edge_scores) / max(len(edge_scores), 1), 2),
        "strong_causal_edge_count": strong,
        "related_to_edge_count": related,
    }
    return metrics


def build_diagnostics(
    intent: QueryIntent,
    classified: list[ClassifiedArticle],
    events: list[Event],
    edges: list[CausalEdge],
) -> GraphDiagnostics:
    rejected = [item for item in classified if item.result.classification == "REJECTED"]
    core_events = [event for event in events if (event.relevance_class or "CORE") == "CORE"]
    context_events = [event for event in events if event.relevance_class == "CONTEXT"]
    metrics = graph_metrics(events, edges, len(rejected))
    warnings: list[str] = []
    if metrics["context_node_count"] > metrics["core_node_count"]:
        warnings.append("context nodes > core nodes")
        log.info(
            "graph_quality_warning",
            extra={
                "source": "graph",
                "success": True,
                "warning": "context_gt_core",
                "core_node_count": metrics["core_node_count"],
                "context_node_count": metrics["context_node_count"],
            },
        )
    return GraphDiagnostics(
        query=intent.raw_query,
        intent=intent.to_dict(),
        candidate_count=len(classified),
        core_count=len(core_events),
        context_count=len(context_events),
        rejected_count=len(rejected),
        core=[{"id": event.id, "title": event.title, "score": event.relevance_score} for event in core_events],
        context=[
            {"id": event.id, "title": event.title, "score": event.relevance_score} for event in context_events
        ],
        rejected=[
            RejectedCandidate(
                title=item.article.title,
                url=item.article.url,
                reason=item.result.reason,
            )
            for item in rejected[:40]
        ],
        metrics=metrics,
        warnings=warnings,
    )


def select_eligible_articles(
    classified: list[ClassifiedArticle],
    *,
    max_articles: int = 24,
) -> list[Article]:
    ranked_core = sorted(
        [item for item in classified if item.result.classification == "CORE"],
        key=lambda item: item.result.overall_relevance,
        reverse=True,
    )
    ranked_context = sorted(
        [item for item in classified if item.result.classification == "CONTEXT"],
        key=lambda item: item.result.overall_relevance,
        reverse=True,
    )
    chosen = [item.article for item in ranked_core] + [item.article for item in ranked_context]
    return chosen[:max_articles]


def assemble_events(
    intent: QueryIntent,
    events: list[Event],
    articles: list[Article],
    classified: list[ClassifiedArticle],
) -> tuple[list[Event], list[Event]]:
    settings = get_settings()
    article_map = {article.id: article for article in articles}
    article_class = {item.article.id: item.result for item in classified}
    events = annotate_events(intent, dedupe_events(events), article_map, article_class)
    core = [event for event in events if event.relevance_class == "CORE"]
    context = [event for event in events if event.relevance_class == "CONTEXT"]
    core.sort(key=lambda event: event.relevance_score or 0.0, reverse=True)
    core = core[: settings.graph_max_core_nodes]
    context = admit_context_events(
        core,
        context,
        min_score=settings.graph_context_min_score,
        limit=settings.graph_max_context_nodes,
    )
    return core, context


def format_diagnostics_text(diagnostics: GraphDiagnostics) -> str:
    lines = [
        f"Query: {diagnostics.query}",
        f"Candidates: {diagnostics.candidate_count}",
        f"CORE: {diagnostics.core_count}",
        f"CONTEXT: {diagnostics.context_count}",
        f"REJECTED: {diagnostics.rejected_count}",
        "",
        "Rejected:",
    ]
    if not diagnostics.rejected:
        lines.append("- (none)")
    for item in diagnostics.rejected[:15]:
        title = item.title[:88] + ("…" if len(item.title) > 88 else "")
        lines.append(f"- {title}")
        lines.append(f"  reason: {item.reason}")
    return "\n".join(lines)
