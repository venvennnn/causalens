from __future__ import annotations

import hashlib
import json
from datetime import datetime

from pydantic import ValidationError

from app.clients.llm import complete_json_with_repair
from app.exceptions import LLMExtractionError
from app.logging import log
from app.models.schemas import Article, Entity, Event
from app.sources.adapters import parse_datetime

EVENT_SYSTEM = """You are the event extraction engine for CausaLens SEA.

You receive Southeast Asian business, technology, investment,
manufacturing, supply-chain and economic news articles.

Do not summarize articles.

Identify unique REAL-WORLD EVENTS.

Merge duplicates more aggressively when they share companies, location,
event type and a close date window even if headlines differ.

Do not create separate nodes merely because headlines differ.

Only extract events supported by supplied evidence.
Prefer events that directly match the user query when a query is provided.


Examples:

- company raises capital
- company expands factory
- manufacturing output changes
- commodity price changes
- supply disruption occurs
- company invests in another market
- new data center is announced
- acquisition occurs
- export demand rises or falls
- major partnership is announced

For every event return:

id
title
summary
event_date
countries
companies
industries
entities
source_article_ids
confidence
event_type

Never invent facts absent from the supplied articles.

Return JSON of the form:
{"events": [ ... ]}

event_type must be one of:
INVESTMENT, FUNDING, EXPANSION, PRICE_CHANGE, SUPPLY_DISRUPTION,
ACQUISITION, PARTNERSHIP, PRODUCTION_CHANGE, EXPORT_CHANGE,
MARKET_MOVE, TECHNOLOGY_LAUNCH, CORPORATE_ACTION

entities[].type must be one of:
COMPANY, COUNTRY, CITY, PERSON, INDUSTRY, COMMODITY, TECHNOLOGY, ORGANIZATION

source_article_ids must be drawn only from the provided article ids.
Keep titles concise and factual. confidence is 0-1.
"""


def _stable_event_id(title: str, event_type: str) -> str:
    slug = hashlib.sha1(f"{event_type}|{title.lower()}".encode("utf-8")).hexdigest()[:12]
    return f"evt_{slug}"


def _coerce_event(raw: dict, valid_article_ids: set[str]) -> Event | None:
    title = str(raw.get("title") or "").strip()
    summary = str(raw.get("summary") or "").strip()
    if not title or not summary:
        return None
    event_type = str(raw.get("event_type") or "MARKET_MOVE").upper()
    article_ids = [str(item) for item in raw.get("source_article_ids") or [] if str(item) in valid_article_ids]
    entities = []
    for entity in raw.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        name = str(entity.get("name") or "").strip()
        if not name:
            continue
        entities.append(
            Entity(
                id=str(entity.get("id") or hashlib.sha1(name.encode()).hexdigest()[:10]),
                name=name,
                type=str(entity.get("type") or "ORGANIZATION"),
                country=entity.get("country"),
            )
        )
    event_id = str(raw.get("id") or "").strip() or _stable_event_id(title, event_type)
    try:
        return Event(
            id=event_id,
            title=title,
            summary=summary,
            event_date=parse_datetime(raw.get("event_date")),
            countries=[str(c) for c in raw.get("countries") or [] if str(c).strip()],
            companies=[str(c) for c in raw.get("companies") or [] if str(c).strip()],
            industries=[str(c) for c in raw.get("industries") or [] if str(c).strip()],
            entities=entities,
            source_article_ids=article_ids,
            confidence=float(raw.get("confidence") or 0.6),
            event_type=event_type,
        )
    except ValidationError:
        return None


async def extract_events(articles: list[Article]) -> list[Event]:
    if not articles:
        return []
    payload = [
        {
            "id": article.id,
            "title": article.title,
            "source": article.source,
            "country": article.country,
            "published_at": article.published_at.isoformat() if article.published_at else None,
            "url": article.url,
            "body": article.body[:4000],
        }
        for article in articles
    ]
    user = (
        "Extract unique real-world events from these articles. "
        "Merge coverage of the same event.\n\n"
        f"{json.dumps(payload, default=str)}"
    )
    started = datetime.utcnow()
    try:
        result = await complete_json_with_repair(EVENT_SYSTEM, user)
    except LLMExtractionError:
        raise
    raw_events = result.get("events") if isinstance(result, dict) else result
    if not isinstance(raw_events, list):
        raise LLMExtractionError("Event extractor did not return an events list")
    valid_ids = {article.id for article in articles}
    events = []
    seen = set()
    for raw in raw_events:
        if not isinstance(raw, dict):
            continue
        event = _coerce_event(raw, valid_ids)
        if not event or event.id in seen:
            continue
        seen.add(event.id)
        events.append(event)
    duration_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
    log.info(
        "event_extraction_ok",
        extra={
            "source": "llm",
            "duration_ms": duration_ms,
            "success": True,
            "events_count": len(events),
            "article_count": len(articles),
        },
    )
    return events
