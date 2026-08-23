from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy.orm import Session

from app.clients.gdelt import GDELTClient
from app.clients.llm import llm_available
from app.config import get_settings
from app.exceptions import AnalysisNotFound, CausaLensError, EventNotFound, GDELTUnavailable, LLMExtractionError
from app.logging import log
from app.models.db import (
    AnalysisEdgeRow,
    AnalysisEventRow,
    AnalysisRow,
    ArticleRow,
    CausalEdgeRow,
    EventRow,
)
from app.models.schemas import Article, CausalEdge, DataMode, Event, GraphDiagnostics, GraphPayload
from app.services.causal_extractor import extract_causal_edges
from app.services.dedupe import merge_article_streams
from app.services.demo_seed import DEMO_QUERIES, edges_for_events, events_for_query, seed_articles, seed_edges, seed_events
from app.services.graph_service import build_graph, get_path, get_regional_ripple, get_what_next, get_why
from app.services.event_extractor import extract_events
from app.services.graph_quality import (
    assemble_events,
    build_diagnostics,
    classify_articles,
    finalize_edges,
    format_diagnostics_text,
    select_eligible_articles,
)
from app.services.query_intent import parse_query_intent
from app.services.ingest import (
    fetch_configured_articles,
    fetch_open_web_articles,
    get_articles_by_ids,
    load_recent_articles,
)
from app.services.pipeline import log_pipeline_event
from app.sources.adapters import canonicalize_url
from app.sources.registry import source_for_url

PRIMARY_ANALYSIS_ID = "demo-ai-infrastructure"


def _allows_demo_seed(query: str) -> bool:
    q = (query or "").strip().lower()
    if q in {item.lower() for item in DEMO_QUERIES}:
        return True
    return "ai infrastructure" in q and "southeast" in q


def _stub_events_from_core(classified) -> list[Event]:
    events: list[Event] = []
    for item in classified:
        if item.result.classification != "CORE":
            continue
        article = item.article
        events.append(
            Event(
                id="evt_" + hashlib.sha1(article.id.encode()).hexdigest()[:12],
                title=article.title,
                summary=(article.summary or (article.body or "")[:280] or article.title),
                event_date=article.published_at,
                countries=[article.country] if article.country else [],
                companies=[],
                industries=[],
                source_article_ids=[article.id],
                confidence=item.result.overall_relevance,
                event_type="INVESTMENT" if item.result.event_type_relevance >= 0.4 else "MARKET_MOVE",
                relevance_class="CORE",
                relevance_score=item.result.overall_relevance,
                relevance_breakdown=item.result.breakdown(),
                relevance_reason=item.result.reason,
            )
        )
    return events


def _apply_intent_to_seed(query: str, articles: list[Article], events: list[Event], edges: list[CausalEdge]):
    intent = parse_query_intent(query)
    classified = classify_articles(intent, articles)
    core, context = assemble_events(intent, events, articles, classified)
    kept = core + context
    kept_ids = {event.id for event in kept}
    trimmed = [edge for edge in edges if edge.source_event_id in kept_ids and edge.target_event_id in kept_ids]
    return kept, finalize_edges(kept, trimmed, articles), classified, intent


def persist_article(db: Session, article: Article, valid: bool = True) -> None:
    row = db.get(ArticleRow, article.id)
    payload = dict(
        title=article.title,
        url=article.url,
        canonical_url=canonicalize_url(article.url),
        source=article.source,
        country=article.country,
        language=article.language,
        published_at=article.published_at,
        author=article.author,
        category=article.category,
        summary=article.summary,
        body=article.body,
        image_url=article.image_url,
        ingested_at=article.ingested_at,
        raw=article.raw,
        valid=valid,
    )
    if row is None:
        db.add(ArticleRow(id=article.id, **payload))
    else:
        for key, value in payload.items():
            setattr(row, key, value)


def persist_event(db: Session, event: Event) -> None:
    row = db.get(EventRow, event.id)
    payload = dict(
        title=event.title,
        summary=event.summary,
        event_date=event.event_date,
        countries=event.countries,
        companies=event.companies,
        industries=event.industries,
        entities=[entity.model_dump() for entity in event.entities],
        source_article_ids=event.source_article_ids,
        confidence=event.confidence,
        event_type=event.event_type,
        meta={
            "relevance_class": event.relevance_class,
            "relevance_score": event.relevance_score,
            "relevance_breakdown": event.relevance_breakdown,
            "relevance_reason": event.relevance_reason,
        },
    )
    if row is None:
        db.add(EventRow(id=event.id, **payload))
    else:
        for key, value in payload.items():
            setattr(row, key, value)


def persist_edge(db: Session, edge: CausalEdge) -> None:
    row = db.get(CausalEdgeRow, edge.id)
    payload = edge.model_dump()
    payload.pop("id")
    evidence = payload.pop("evidence", [])
    explanation = payload.pop("explanation", None)
    payload["meta"] = {"evidence": evidence, "explanation": explanation}
    if row is None:
        db.add(CausalEdgeRow(id=edge.id, **payload))
    else:
        for key, value in payload.items():
            setattr(row, key, value)


def event_from_row(row: EventRow) -> Event:
    from app.models.schemas import Entity

    meta = row.meta or {}
    return Event(
        id=row.id,
        title=row.title,
        summary=row.summary,
        event_date=row.event_date,
        countries=row.countries or [],
        companies=row.companies or [],
        industries=row.industries or [],
        entities=[Entity(**item) for item in (row.entities or [])],
        source_article_ids=row.source_article_ids or [],
        confidence=row.confidence,
        event_type=row.event_type,
        relevance_class=meta.get("relevance_class"),
        relevance_score=meta.get("relevance_score"),
        relevance_breakdown=meta.get("relevance_breakdown"),
        relevance_reason=meta.get("relevance_reason"),
    )


def edge_from_row(row: CausalEdgeRow) -> CausalEdge:
    from app.models.schemas import EdgeEvidence

    meta = getattr(row, "meta", None) or {}
    evidence_raw = meta.get("evidence") or []
    evidence = []
    for item in evidence_raw:
        if isinstance(item, dict):
            evidence.append(
                EdgeEvidence(
                    article_id=str(item.get("article_id") or item.get("articleId") or ""),
                    quote_or_snippet=str(item.get("quote_or_snippet") or item.get("quoteOrSnippet") or ""),
                    reason=str(item.get("reason") or ""),
                )
            )
    return CausalEdge(
        id=row.id,
        source_event_id=row.source_event_id,
        target_event_id=row.target_event_id,
        relation=row.relation,  # type: ignore[arg-type]
        confidence=row.confidence,
        evidence_score=row.evidence_score,
        reason=row.reason,
        supporting_article_ids=row.supporting_article_ids or [],
        status=row.status,  # type: ignore[arg-type]
        cross_border=row.cross_border,
        source_countries=row.source_countries or [],
        target_countries=row.target_countries or [],
        evidence=evidence,
        explanation=meta.get("explanation") or row.reason,
    )


def persist_analysis(
    db: Session,
    *,
    analysis_id: str,
    query: str,
    events: list[Event],
    edges: list[CausalEdge],
    articles: list[Article],
    data_mode: DataMode,
    degraded_reasons: list[str],
    cached_from: datetime | None = None,
    diagnostics: GraphDiagnostics | None = None,
) -> GraphPayload:
    for article in articles:
        persist_article(db, article)
    for event in events:
        persist_event(db, event)
    for edge in edges:
        persist_edge(db, edge)

    stats = {
        "articles": len(articles),
        "events": len(events),
        "connections": len(edges),
        "cross_border": sum(1 for edge in edges if edge.cross_border),
        "core_nodes": sum(1 for event in events if (event.relevance_class or "CORE") == "CORE"),
        "context_nodes": sum(1 for event in events if event.relevance_class == "CONTEXT"),
        "rejected_candidates": int(diagnostics.rejected_count if diagnostics else 0),
        "related_to_edges": sum(1 for edge in edges if edge.relation == "RELATED_TO"),
        "strong_causal_edges": sum(
            1
            for edge in edges
            if edge.relation in {"CAUSES", "CONTRIBUTES_TO", "ENABLES", "CONSTRAINS", "TRIGGERS"}
        ),
    }
    generated_at = datetime.utcnow()
    diagnostics_payload = diagnostics.model_dump(mode="json") if diagnostics else None
    row = db.get(AnalysisRow, analysis_id)
    if row is None:
        db.add(
            AnalysisRow(
                id=analysis_id,
                query=query,
                data_mode=data_mode,
                generated_at=generated_at,
                cached_from=cached_from,
                degraded_reasons=degraded_reasons,
                stats=stats,
                diagnostics=diagnostics_payload,
                success=True,
            )
        )
    else:
        row.query = query
        row.data_mode = data_mode
        row.generated_at = generated_at
        row.cached_from = cached_from
        row.degraded_reasons = degraded_reasons
        row.stats = stats
        row.diagnostics = diagnostics_payload
        row.success = True
        db.query(AnalysisEventRow).filter(AnalysisEventRow.analysis_id == analysis_id).delete()
        db.query(AnalysisEdgeRow).filter(AnalysisEdgeRow.analysis_id == analysis_id).delete()

    for event in events:
        db.add(AnalysisEventRow(analysis_id=analysis_id, event_id=event.id))
    for edge in edges:
        db.add(AnalysisEdgeRow(analysis_id=analysis_id, edge_id=edge.id))
    db.flush()
    return GraphPayload(
        analysis_id=analysis_id,
        query=query,
        data_mode=data_mode,
        cached_from=cached_from,
        generated_at=generated_at,
        degraded_reasons=degraded_reasons,
        stats=stats,
        events=events,
        edges=edges,
        articles=articles,
        diagnostics=diagnostics,
    )


def seed_demo_if_needed(db: Session) -> None:
    if db.get(AnalysisRow, PRIMARY_ANALYSIS_ID):
        return
    articles = seed_articles()
    events = seed_events(articles)
    edges = seed_edges(events, articles)
    persist_analysis(
        db,
        analysis_id=PRIMARY_ANALYSIS_ID,
        query="AI infrastructure in Southeast Asia",
        events=events,
        edges=edges,
        articles=articles,
        data_mode="CACHED",
        degraded_reasons=[],
        cached_from=datetime.utcnow(),
    )
    log_pipeline_event(db, "system", "demo_seeded", "Cached demo graph persisted for failover")
    db.commit()


def load_analysis(db: Session, analysis_id: str) -> GraphPayload:
    row = db.get(AnalysisRow, analysis_id)
    if row is None:
        raise AnalysisNotFound(f"Analysis {analysis_id} not found")
    event_ids = [
        link.event_id
        for link in db.query(AnalysisEventRow).filter(AnalysisEventRow.analysis_id == analysis_id).all()
    ]
    edge_ids = [
        link.edge_id
        for link in db.query(AnalysisEdgeRow).filter(AnalysisEdgeRow.analysis_id == analysis_id).all()
    ]
    events = [event_from_row(db.get(EventRow, event_id)) for event_id in event_ids if db.get(EventRow, event_id)]
    edges = [edge_from_row(db.get(CausalEdgeRow, edge_id)) for edge_id in edge_ids if db.get(CausalEdgeRow, edge_id)]
    article_ids: list[str] = []
    for event in events:
        article_ids.extend(event.source_article_ids)
    for edge in edges:
        article_ids.extend(edge.supporting_article_ids)
    articles = get_articles_by_ids(db, list(dict.fromkeys(article_ids)))
    diagnostics = None
    raw_diag = getattr(row, "diagnostics", None)
    if raw_diag:
        try:
            diagnostics = GraphDiagnostics.model_validate(raw_diag)
        except Exception:
            diagnostics = None
    return GraphPayload(
        analysis_id=row.id,
        query=row.query,
        data_mode=row.data_mode,  # type: ignore[arg-type]
        cached_from=row.cached_from,
        generated_at=row.generated_at,
        degraded_reasons=row.degraded_reasons or [],
        stats=row.stats or {},
        events=events,
        edges=edges,
        articles=articles,
        diagnostics=diagnostics,
    )


def latest_successful_analysis(db: Session) -> GraphPayload | None:
    row = (
        db.query(AnalysisRow)
        .filter(AnalysisRow.success.is_(True))
        .order_by(AnalysisRow.generated_at.desc())
        .first()
    )
    if row is None:
        return None
    return load_analysis(db, row.id)


def _analysis_id_for(query: str) -> str:
    return "an_" + hashlib.sha1(query.strip().lower().encode()).hexdigest()[:12]


def _public_articles(articles: list[Article]) -> list[Article]:
    # UI must not receive full bodies.
    slim: list[Article] = []
    for article in articles:
        slim.append(
            article.model_copy(
                update={
                    "body": "",
                    "raw": None,
                    "summary": article.summary or article.title,
                }
            )
        )
    return slim


def to_public_payload(payload: GraphPayload) -> dict:
    data = payload.model_dump(mode="json")
    data["articles"] = [article.model_dump(mode="json") for article in _public_articles(payload.articles)]
    return data


async def run_analysis(db: Session, query: str) -> GraphPayload:
    settings = get_settings()
    intent = parse_query_intent(query)
    degraded: list[str] = []
    data_mode: DataMode = "LIVE"
    gdelt_candidates = []
    try:
        gdelt_candidates = await GDELTClient().search_gdelt(query, settings.gdelt_max_records, db=db)
        log_pipeline_event(
            db,
            "gdelt",
            "search_ok",
            f"GDELT NGrams returned {len(gdelt_candidates)} ranked candidates",
        )
    except (GDELTUnavailable, CausaLensError) as exc:
        degraded.append(f"GDELT unavailable: {exc.message}")
        log_pipeline_event(db, "gdelt", "search_failed", exc.message)
        data_mode = "PARTIAL"

    curated = load_recent_articles(db, limit=40)
    fetched: list = []
    try:
        fetched = await fetch_configured_articles(gdelt_candidates, db)
        if fetched:
            log_pipeline_event(
                db,
                "gdelt",
                "brightdata_ok",
                f"Using {len(fetched)} CNA/Edge/VIR articles from GDELT (scraped or already in store)",
            )
    except CausaLensError as exc:
        degraded.append(f"Bright Data extraction of GDELT URLs failed: {exc.message}")
        data_mode = "PARTIAL"

    try:
        web_articles = await fetch_open_web_articles(
            gdelt_candidates,
            db,
            exclude_urls={canonicalize_url(article.url) for article in fetched},
        )
        if web_articles:
            log_pipeline_event(
                db,
                "gdelt",
                "web_extract_ok",
                f"Extracted {len(web_articles)} off-domain GDELT articles for relevance validation",
            )
            fetched = [*fetched, *web_articles]
    except CausaLensError as exc:
        degraded.append(f"GDELT article extraction failed: {exc.message}")
        data_mode = "PARTIAL"

    configured_candidates = [item for item in gdelt_candidates if source_for_url(item.url)]

    if fetched:
        pool = list(fetched)
        if len(pool) < 8 and _allows_demo_seed(query):
            seen = {canonicalize_url(article.url) for article in pool}
            for article in curated:
                if canonicalize_url(article.url) not in seen:
                    pool.append(article)
                    seen.add(canonicalize_url(article.url))
    elif configured_candidates:
        pool = list(curated)
        degraded.append(
            "GDELT routed CNA / The Edge / VIR URLs, but Bright Data did not return extractable article bodies."
        )
        data_mode = "PARTIAL"
    elif gdelt_candidates:
        pool = list(curated)
        degraded.append(
            f"GDELT found {len(gdelt_candidates)} candidates, but article extraction could not recover usable bodies."
        )
        data_mode = "PARTIAL"
    elif curated and _allows_demo_seed(query):
        pool = list(curated)
        data_mode = "PARTIAL"
    elif curated:
        pool = list(curated)
        data_mode = "PARTIAL"
    elif _allows_demo_seed(query):
        pool = seed_articles()
        for article in pool:
            persist_article(db, article)
        degraded.append("No live Bright Data articles in store; mixed in curated corpus.")
        data_mode = "PARTIAL"
    else:
        pool = []
        degraded.append("No live articles available; not filling the graph with unrelated context.")
        data_mode = "PARTIAL"

    curated, extra = merge_article_streams(pool, gdelt_candidates)
    routed = sum(1 for candidate in extra if source_for_url(candidate.url))
    if routed or fetched:
        log.info(
            "gdelt_routed_to_collectors",
            extra={
                "source": "gdelt",
                "article_count": len(fetched),
                "unfetched_configured": routed,
                "success": True,
            },
        )

    classified = classify_articles(intent, curated)
    eligible = select_eligible_articles(classified, max_articles=24)
    rejected_n = sum(1 for item in classified if item.result.classification == "REJECTED")
    log_pipeline_event(
        db,
        "relevance",
        "classified",
        f"Post-scrape relevance: {len(eligible)} eligible, {rejected_n} rejected of {len(classified)} candidates",
    )

    events: list[Event] = []
    edges: list[CausalEdge] = []
    live_extraction = False
    if llm_available() and eligible:
        try:
            extracted = await extract_events(eligible)
            core, context = assemble_events(intent, extracted, eligible, classified)
            if core:
                events = core + context
                raw_edges = await extract_causal_edges(events, eligible)
                edges = finalize_edges(events, raw_edges, eligible)
                live_extraction = True
        except LLMExtractionError as exc:
            degraded.append(f"LLM extraction failed: {exc.message}")

    if not live_extraction:
        if not settings.use_cached_demo_on_failure and not any(
            item.result.classification == "CORE" for item in classified
        ):
            raise LLMExtractionError("Live extraction failed and cached fallback is disabled")
        if _allows_demo_seed(query) and settings.use_cached_demo_on_failure:
            seed_articles_ = seed_articles()
            seed_events_ = events_for_query(query, seed_events(seed_articles_))
            seed_edges_ = edges_for_events(seed_edges(seed_events(seed_articles_), seed_articles_), seed_events_)
            url_map = {article.url: article for article in curated}
            merged_articles = []
            seen = set()
            for article in seed_articles_:
                live = url_map.get(article.url)
                merged_articles.append(live or article)
                seen.add(article.url)
            for article in curated:
                if article.url not in seen:
                    merged_articles.append(article)
                    seen.add(article.url)
            events, edges, classified, intent = _apply_intent_to_seed(
                query, merged_articles, seed_events_, seed_edges_
            )
            curated = merged_articles
            data_mode = "CACHED" if not llm_available() else "PARTIAL"
            if not any("cached" in item.lower() or "fallback" in item.lower() for item in degraded):
                degraded.append("Serving evidence-backed cached analysis after live extraction limits.")
        else:
            stubs = _stub_events_from_core(classified)
            core, context = assemble_events(intent, stubs, curated, classified)
            events = core + context
            edges = finalize_edges(events, [], curated)

    diagnostics = build_diagnostics(intent, classified, events, edges)
    log.info("graph_quality", extra={"source": "graph", "success": True, "query": query})
    log.info(format_diagnostics_text(diagnostics))

    analysis_id = _analysis_id_for(query)
    cached_from = datetime.utcnow() if data_mode != "LIVE" else None
    payload = persist_analysis(
        db,
        analysis_id=analysis_id,
        query=query,
        events=events,
        edges=edges,
        articles=curated,
        data_mode=data_mode,
        degraded_reasons=degraded,
        cached_from=cached_from,
        diagnostics=diagnostics,
    )
    db.commit()
    return payload


def graph_view(db: Session, analysis_id: str, event_id: str, mode: str) -> dict:
    payload = load_analysis(db, analysis_id)
    graph = build_graph(payload.events, payload.edges)
    if event_id not in {event.id for event in payload.events}:
        raise EventNotFound(f"Event {event_id} not found in analysis")
    if mode == "why":
        result = get_why(graph, event_id)
    elif mode == "next":
        result = get_what_next(graph, event_id)
    elif mode == "ripple":
        result = get_regional_ripple(graph, event_id)
    else:
        result = get_path(graph, event_id, event_id)
    result["analysis_id"] = analysis_id
    result["data_mode"] = payload.data_mode
    return result


def fallback_analysis_for_query(db: Session, query: str) -> GraphPayload:
    seed_demo_if_needed(db)
    articles = seed_articles()
    events = events_for_query(query, seed_events(articles))
    edges = edges_for_events(seed_edges(seed_events(articles), articles), events)
    events, edges, classified, intent = _apply_intent_to_seed(query, articles, events, edges)
    diagnostics = build_diagnostics(intent, classified, events, edges)
    analysis_id = _analysis_id_for(query)
    return persist_analysis(
        db,
        analysis_id=analysis_id,
        query=query,
        events=events,
        edges=edges,
        articles=articles,
        data_mode="CACHED",
        degraded_reasons=["Live pipeline unavailable; loaded last successful cached analysis."],
        cached_from=datetime.utcnow(),
        diagnostics=diagnostics,
    )
