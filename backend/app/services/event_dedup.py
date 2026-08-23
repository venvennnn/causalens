from __future__ import annotations

from datetime import datetime, timedelta

from rapidfuzz import fuzz

from app.models.schemas import Event
from app.services.dedupe import normalize_title, titles_similar


def _norm_set(values: list[str]) -> set[str]:
    return {item.strip().lower() for item in values if item and item.strip()}


def _date_close(a: datetime | None, b: datetime | None, days: int = 21) -> bool:
    if a is None or b is None:
        return True
    return abs((a - b).total_seconds()) <= timedelta(days=days).total_seconds()


def events_are_duplicates(left: Event, right: Event) -> bool:
    if left.id == right.id:
        return True
    if titles_similar(left.title, right.title, threshold=84):
        return True
    companies = _norm_set(left.companies) & _norm_set(right.companies)
    countries = _norm_set(left.countries) & _norm_set(right.countries)
    same_type = (left.event_type or "").upper() == (right.event_type or "").upper()
    token_ratio = fuzz.token_set_ratio(normalize_title(left.title), normalize_title(right.title))
    partial = fuzz.partial_ratio(normalize_title(left.title), normalize_title(right.title))
    if companies and countries and same_type and _date_close(left.event_date, right.event_date) and max(token_ratio, partial) >= 55:
        return True
    if companies and max(token_ratio, partial) >= 80 and _date_close(left.event_date, right.event_date, days=45):
        return True
    return False


def merge_events(keeper: Event, other: Event) -> Event:
    article_ids = list(dict.fromkeys([*keeper.source_article_ids, *other.source_article_ids]))
    companies = list(dict.fromkeys([*keeper.companies, *other.companies]))
    countries = list(dict.fromkeys([*keeper.countries, *other.countries]))
    industries = list(dict.fromkeys([*keeper.industries, *other.industries]))
    entities = list(keeper.entities)
    seen = {(ent.name.lower(), ent.type) for ent in entities}
    for ent in other.entities:
        key = (ent.name.lower(), ent.type)
        if key not in seen:
            entities.append(ent)
            seen.add(key)
    title = keeper.title if len(keeper.title) >= len(other.title) else other.title
    summary = keeper.summary if len(keeper.summary) >= len(other.summary) else other.summary
    confidence = max(keeper.confidence, other.confidence)
    relevance = keeper.relevance_score or 0
    other_rel = other.relevance_score or 0
    if other.relevance_class == "CORE" and keeper.relevance_class != "CORE":
        keeper.relevance_class = "CORE"
        keeper.relevance_breakdown = other.relevance_breakdown
        relevance = max(relevance, other_rel)
    keeper.title = title
    keeper.summary = summary
    keeper.companies = companies
    keeper.countries = countries
    keeper.industries = industries
    keeper.entities = entities
    keeper.source_article_ids = article_ids
    keeper.confidence = min(1.0, confidence + 0.04 * max(0, len(article_ids) - 1))
    keeper.relevance_score = max(relevance, other_rel)
    if keeper.event_date is None:
        keeper.event_date = other.event_date
    return keeper


def dedupe_events(events: list[Event]) -> list[Event]:
    unique: list[Event] = []
    for event in events:
        matched = None
        for existing in unique:
            if events_are_duplicates(existing, event):
                matched = existing
                break
        if matched is None:
            unique.append(event)
        else:
            merge_events(matched, event)
    return unique
