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
from app.services.relations import normalize_relation_label

CAUSAL_SYSTEM = """You are the relation extractor for CausaLens SEA.

Identify relationships between events ONLY when the supplied article evidence
supports the relationship. Do not invent facts or article IDs.

Allowed relationships:

CAUSES
CONTRIBUTES_TO
TRIGGERS
RESPONDS_TO
AFFECTS
ENABLES
CONSTRAINS
PART_OF
RELATED_TO

Default to RELATED_TO whenever two events are about the same topic,
share entities, or are only semantically similar.

Do NOT convert similarity into causality.

CAUSES requires the source text to assert that the source event produced
the target event, using explicit causal language such as because, due to,
as a result, led to, driven by, caused, prompted, forced, triggered.

CONTRIBUTES_TO is weaker than CAUSES: the source is described as one
contributing factor, not the sole cause.

AFFECTS is for a stated impact that is not clearly causal.

ENABLES / CONSTRAINS / RESPONDS_TO / PART_OF only when the article
states that mechanism.

Directionality matters. Identify source → relation → target explicitly.
Do not infer direction from chronology or graph layout.
Event A happening before Event B is NOT causal proof.

If two events come from different articles and no article links them,
use RELATED_TO. Never invent a cross-article CAUSES claim.

Temporal ordering may be mentioned as supporting context only.

Return JSON:
{"edges": [{
  "source_event_id": "...",
  "target_event_id": "...",
  "relation": "RELATED_TO",
  "confidence": 0.0,
  "reason": "short evidence-based explanation",
  "supporting_article_ids": ["..."],
  "status": "observed"
}]}

"Observed" means directly evidenced in an article.
"Inferred" means a reasonable mechanism is described but not explicit.
"Predicted" is only for plausible future effects.

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
            "relevance_class": event.relevance_class or "CORE",
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
        relation = normalize_relation_label(str(raw.get("relation") or "RELATED_TO"))
        if source_id not in event_ids or target_id not in event_ids or source_id == target_id:
            continue
        key = (source_id, target_id, relation)
        if key in seen:
            continue
        seen.add(key)
        source_event = events_by_id[source_id]
        target_event = events_by_id[target_id]
        supporting = [
            str(item)
            for item in raw.get("supporting_article_ids") or []
            if str(item) in valid_article_ids
        ]
        shared = set(source_event.source_article_ids) & set(target_event.source_article_ids)
        if relation != "RELATED_TO":
            # Causal claims must keep provenance from overlapping evidence, not a union of both events.
            if shared:
                supporting = [item for item in supporting if item in shared] or list(shared)[:4]
            elif not supporting:
                relation = "RELATED_TO"
        if not supporting:
            supporting = list(
                dict.fromkeys(source_event.source_article_ids + target_event.source_article_ids)
            )[:4]
            relation = "RELATED_TO"
        try:
            edge = CausalEdge(
                id=_edge_id(source_id, target_id, relation),
                source_event_id=source_id,
                target_event_id=target_id,
                relation=relation,  # type: ignore[arg-type]
                confidence=float(raw.get("confidence") or 0.5),
                reason=str(raw.get("reason") or "").strip() or "Evidence-backed relationship.",
                supporting_article_ids=supporting,
                status=str(raw.get("status") or "observed").lower(),  # type: ignore[arg-type]
                explanation=str(raw.get("reason") or "").strip() or None,
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
