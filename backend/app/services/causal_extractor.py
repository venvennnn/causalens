from __future__ import annotations

import hashlib
import json
from datetime import datetime

from pydantic import ValidationError

from app.clients.llm import complete_json_with_repair
from app.exceptions import LLMExtractionError
from app.logging import log
from app.models.schemas import Article, CausalEdge, Event
from app.services.evidence import annotate_cross_border, calculate_evidence_score

CAUSAL_SYSTEM = """You are the causal reasoning engine for CausaLens SEA.

Given a set of real-world events and their supporting article evidence,
identify causal relationships only when the supplied evidence supports
the relationship.

Allowed relationships:

CAUSES
CONTRIBUTES_TO
TRIGGERS
RESPONDS_TO
AFFECTS

Return JSON:
{"edges": [{
  "source_event_id": "...",
  "target_event_id": "...",
  "relation": "CAUSES",
  "confidence": 0.0,
  "reason": "...",
  "supporting_article_ids": ["..."],
  "status": "observed"
}]}

Rules:

Temporal precedence alone is NOT causality.

Two events occurring close together does NOT imply causation.

Prefer causal edges when:

1. an article explicitly describes causation;
2. an article describes a clear causal mechanism;
3. multiple sources independently support the connection;
4. the target is explicitly described as a response to the source.

"Observed" means directly evidenced.
"Inferred" means the evidence supports a reasonable mechanism but
causation is not explicitly stated.
"Predicted" is only for plausible future effects and must be shown
separately from observed facts.

Never fabricate supporting article IDs.
Only use event ids and article ids supplied in the request.
Do not create self-loops.
"""


def _edge_id(source: str, target: str, relation: str) -> str:
    return "edg_" + hashlib.sha1(f"{source}|{target}|{relation}".encode()).hexdigest()[:12]


async def extract_causal_edges(events: list[Event], articles: list[Article]) -> list[CausalEdge]:
    if len(events) < 2:
        return []
    article_map = {article.id: article for article in articles}
    event_payload = [
        {
            "id": event.id,
            "title": event.title,
            "summary": event.summary,
            "event_date": event.event_date.isoformat() if event.event_date else None,
            "countries": event.countries,
            "companies": event.companies,
            "industries": event.industries,
            "event_type": event.event_type,
            "source_article_ids": event.source_article_ids,
        }
        for event in events
    ]
    article_payload = [
        {
            "id": article.id,
            "title": article.title,
            "source": article.source,
            "country": article.country,
            "excerpt": (article.body or "")[:1200],
        }
        for article in articles
    ]
    user = json.dumps({"events": event_payload, "articles": article_payload}, default=str)
    started = datetime.utcnow()
    result = await complete_json_with_repair(CAUSAL_SYSTEM, user)
    raw_edges = result.get("edges") if isinstance(result, dict) else result
    if not isinstance(raw_edges, list):
        raise LLMExtractionError("Causal extractor did not return an edges list")

    event_ids = {event.id for event in events}
    valid_article_ids = set(article_map)
    events_by_id = {event.id: event for event in events}
    edges: list[CausalEdge] = []
    seen: set[tuple[str, str, str]] = set()
    for raw in raw_edges:
        if not isinstance(raw, dict):
            continue
        source_id = str(raw.get("source_event_id") or "")
        target_id = str(raw.get("target_event_id") or "")
        relation = str(raw.get("relation") or "AFFECTS").upper()
        if source_id not in event_ids or target_id not in event_ids or source_id == target_id:
            continue
        key = (source_id, target_id, relation)
        if key in seen:
            continue
        seen.add(key)
        supporting = [
            str(item)
            for item in raw.get("supporting_article_ids") or []
            if str(item) in valid_article_ids
        ]
        if not supporting:
            supporting = list(
                dict.fromkeys(
                    events_by_id[source_id].source_article_ids + events_by_id[target_id].source_article_ids
                )
            )[:4]
        try:
            edge = CausalEdge(
                id=_edge_id(source_id, target_id, relation),
                source_event_id=source_id,
                target_event_id=target_id,
                relation=relation,  # type: ignore[arg-type]
                confidence=float(raw.get("confidence") or 0.55),
                reason=str(raw.get("reason") or "").strip() or "Evidence-backed causal link.",
                supporting_article_ids=supporting,
                status=str(raw.get("status") or "observed").lower(),  # type: ignore[arg-type]
            )
        except ValidationError:
            continue
        edge = annotate_cross_border(edge, events_by_id)
        edge.evidence_score = calculate_evidence_score(edge, article_map)
        edges.append(edge)
    duration_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
    log.info(
        "causal_extraction_ok",
        extra={
            "source": "llm",
            "duration_ms": duration_ms,
            "success": True,
            "edges_count": len(edges),
            "events_count": len(events),
        },
    )
    return edges
