#!/usr/bin/env python3
"""Print CORE / CONTEXT / REJECTED diagnostics for a query using fixture articles."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.models.schemas import Article, CausalEdge, Event
from app.services.graph_quality import (
    assemble_events,
    build_diagnostics,
    classify_articles,
    finalize_edges,
    format_diagnostics_text,
)
from app.services.query_intent import parse_query_intent
from app.services.relations import apply_relation_policy


def article(title: str, body: str, url: str, country: str = "Malaysia") -> Article:
    return Article(
        id="art_" + url[-12:].replace("/", ""),
        title=title,
        url=url,
        source="CNA",
        country=country,
        body=body,
        ingested_at=datetime.utcnow(),
        summary=title,
    )


def main() -> None:
    query = " ".join(sys.argv[1:]) or "Semiconductor investment in Malaysia"
    intent = parse_query_intent(query)
    articles = [
        article(
            "Infineon invests in new Kulim semiconductor capacity",
            "Infineon will invest in additional semiconductor manufacturing capacity at its Kulim, Malaysia facility.",
            "https://example.com/infineon-kulim",
        ),
        article(
            "Intel expands advanced packaging capacity in Penang",
            "Intel is expanding advanced packaging and semiconductor assembly capacity in Penang, Malaysia.",
            "https://example.com/intel-penang",
        ),
        article(
            "Malaysia semiconductor packaging houses see utilisation rebound",
            "Malaysian OSAT houses reported higher semiconductor packaging utilisation in Penang and Kulim.",
            "https://example.com/osat",
        ),
        article(
            "Vietnam expands semiconductor manufacturing",
            "Vietnam is expanding semiconductor manufacturing as electronics FDI grows.",
            "https://example.com/vietnam-semi",
            "Vietnam",
        ),
        article(
            "Microsoft launches new cloud region in Malaysia",
            "Microsoft launched a new cloud region in Malaysia for enterprise software.",
            "https://example.com/msft-cloud",
        ),
        article(
            "Nvidia launches new gaming GPU",
            "Nvidia launched a new GeForce gaming GPU with DLSS 4.5.",
            "https://example.com/nvidia-gpu",
            "United States",
        ),
        article(
            "Alibaba increases cloud investment in Southeast Asia",
            "Alibaba Cloud is increasing data-centre investment across Southeast Asia.",
            "https://example.com/alibaba",
            "Singapore",
        ),
        article(
            "The art of protest is alive and well in Kansas",
            "A Kansas gallery show. Related stories: Malaysia semiconductor, Vietnam data center.",
            "https://example.com/protest",
            "United States",
        ),
        article(
            "Malaysia electricity demand rises around Kulim industrial corridor",
            "Electricity demand is rising around the Kulim industrial corridor as factories expand.",
            "https://example.com/kulim-power",
        ),
    ]
    classified = classify_articles(intent, articles)
    events = []
    for item in classified:
        if item.result.classification == "REJECTED":
            continue
        events.append(
            Event(
                id="evt_" + item.article.id,
                title=item.article.title,
                summary=item.article.body,
                countries=[item.article.country],
                companies=[],
                industries=["Semiconductors"] if item.result.classification == "CORE" else [],
                source_article_ids=[item.article.id],
                event_type="INVESTMENT",
                confidence=item.result.overall_relevance,
            )
        )
    core, context = assemble_events(intent, events, articles, classified)
    kept = core + context
    edges = []
    if len(core) >= 2:
        raw = CausalEdge(
            id="edg_demo",
            source_event_id=core[0].id,
            target_event_id=core[1].id,
            relation="CAUSES",
            confidence=0.6,
            reason="Both articles cover Malaysian semiconductor investment.",
            supporting_article_ids=core[0].source_article_ids + core[1].source_article_ids,
        )
        edges = finalize_edges(kept, [raw], articles)
    diagnostics = build_diagnostics(intent, classified, kept, edges)
    print(format_diagnostics_text(diagnostics))
    print("\nEdges:")
    for edge in edges:
        print(f"- {edge.relation} ({edge.confidence:.2f}) {edge.source_event_id} -> {edge.target_event_id}")
        print(f"  {edge.explanation or edge.reason}")
    print("\nMetrics:")
    for key, value in diagnostics.metrics.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
