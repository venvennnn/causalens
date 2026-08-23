from __future__ import annotations

from app.models.schemas import Article, CausalEdge, Event


def calculate_evidence_score(edge: CausalEdge, articles: dict[str, Article]) -> float:
    independent_sources = len(
        {
            articles[article_id].source
            for article_id in edge.supporting_article_ids
            if article_id in articles
        }
    )
    source_component = min(independent_sources / 3, 1.0)
    return round(min(1.0, 0.70 * edge.confidence + 0.30 * source_component), 2)


def annotate_cross_border(edge: CausalEdge, events: dict[str, Event]) -> CausalEdge:
    source = events.get(edge.source_event_id)
    target = events.get(edge.target_event_id)
    source_countries = list(source.countries) if source else []
    target_countries = list(target.countries) if target else []
    edge.source_countries = source_countries
    edge.target_countries = target_countries
    edge.cross_border = bool(
        set(source_countries)
        and set(target_countries)
        and set(source_countries) != set(target_countries)
    )
    return edge
