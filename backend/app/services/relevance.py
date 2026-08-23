from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.gdelt.topics import normalize_text
from app.logging import log
from app.models.schemas import Article, Event
from app.services.query_intent import (
    INDUSTRIAL_CONTEXT_TERMS,
    QueryIntent,
    RelevanceClass,
    any_phrase_in_text,
)

BOILERPLATE_TITLE_MARKERS = (
    "latest news",
    "breaking news",
    "top stories",
    "category",
    "newsnow",
    "the art of protest",
)

WEAK_NOISE_TITLES = (
    "gaming",
    "dlss",
    "graphics card",
    "geforce",
    "xbox",
    "playstation",
)


@dataclass
class MatchSignals:
    title_subject: list[str] = field(default_factory=list)
    title_geo: list[str] = field(default_factory=list)
    title_event: list[str] = field(default_factory=list)
    body_subject: list[str] = field(default_factory=list)
    body_geo: list[str] = field(default_factory=list)
    body_event: list[str] = field(default_factory=list)
    body_context_geo: list[str] = field(default_factory=list)
    weak: list[str] = field(default_factory=list)
    industrial: list[str] = field(default_factory=list)
    required: list[str] = field(default_factory=list)
    strong: list[str] = field(default_factory=list)


@dataclass
class RelevanceResult:
    classification: RelevanceClass
    subject_relevance: float
    geography_relevance: float
    event_type_relevance: float
    title_relevance: float
    full_text_relevance: float
    overall_relevance: float
    reason: str
    signals: MatchSignals = field(default_factory=MatchSignals)
    core_eligible: bool = False
    context_eligible: bool = False

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["signals"] = {
            "title_subject": self.signals.title_subject[:8],
            "title_geo": self.signals.title_geo[:8],
            "title_event": self.signals.title_event[:8],
            "body_subject": self.signals.body_subject[:8],
            "body_geo": self.signals.body_geo[:8],
        }
        return payload

    def breakdown(self) -> dict:
        return {
            "subject": self.subject_relevance,
            "geography": self.geography_relevance,
            "eventType": self.event_type_relevance,
            "title": self.title_relevance,
            "fullText": self.full_text_relevance,
        }


def _clip(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 2)


def _lead_text(body: str, limit: int = 1800) -> str:
    return (body or "")[:limit]


def collect_signals(intent: QueryIntent, title: str, body: str) -> MatchSignals:
    title_n = normalize_text(title)
    body_n = normalize_text(_lead_text(body))
    required = intent.required_concept_groups[0].terms if intent.required_concept_groups else intent.required_terms()
    strong = []
    if len(intent.required_concept_groups) > 1:
        strong = intent.required_concept_groups[1].terms
    subject_terms = list(dict.fromkeys([*required, *strong]))
    signals = MatchSignals(
        title_subject=any_phrase_in_text(subject_terms, title_n),
        title_geo=any_phrase_in_text(intent.primary_geo_terms, title_n),
        title_event=any_phrase_in_text(intent.event_type_terms, title_n),
        body_subject=any_phrase_in_text(subject_terms, body_n),
        body_geo=any_phrase_in_text(intent.primary_geo_terms, body_n),
        body_event=any_phrase_in_text(intent.event_type_terms, body_n),
        body_context_geo=any_phrase_in_text(intent.context_geo_terms, body_n + " " + title_n),
        weak=any_phrase_in_text(intent.weak_context_terms, title_n + " " + body_n),
        industrial=any_phrase_in_text(INDUSTRIAL_CONTEXT_TERMS, title_n + " " + body_n),
        required=any_phrase_in_text(required, title_n + " " + body_n),
        strong=any_phrase_in_text(strong, title_n + " " + body_n),
    )
    return signals


def _score_presence(title_hits: list[str], body_hits: list[str], *, title_weight: float = 0.65) -> float:
    title_s = 1.0 if title_hits else 0.0
    body_s = min(1.0, 0.45 + 0.15 * min(len(body_hits), 4)) if body_hits else 0.0
    if title_hits and body_hits:
        body_s = min(1.0, body_s + 0.2)
    return _clip(title_weight * title_s + (1.0 - title_weight) * body_s)


def classify_text(intent: QueryIntent, title: str, body: str, *, source: str = "") -> RelevanceResult:
    signals = collect_signals(intent, title, body)
    title_n = normalize_text(title)
    body_n = normalize_text(_lead_text(body))

    has_required = bool(signals.required or signals.strong)
    has_primary_geo = bool(signals.title_geo or signals.body_geo)
    has_event = bool(signals.title_event or signals.body_event)
    has_title_alignment = bool(signals.title_subject or signals.title_geo)
    weak_only = bool(signals.weak) and not has_required
    context_geo_only = bool(signals.body_context_geo) and not has_primary_geo

    subject_rel = _score_presence(signals.title_subject, signals.body_subject)
    geo_rel = _score_presence(signals.title_geo, signals.body_geo)
    event_rel = _score_presence(signals.title_event, signals.body_event) if intent.event_type_terms else 0.0
    title_rel = _clip(
        0.45 * bool(signals.title_subject)
        + 0.35 * bool(signals.title_geo)
        + 0.20 * bool(signals.title_event)
    )
    full_rel = _clip(
        0.5 * bool(signals.body_subject)
        + 0.35 * bool(signals.body_geo)
        + 0.15 * bool(signals.body_event)
    )
    overall = _clip(0.42 * subject_rel + 0.32 * geo_rel + 0.16 * title_rel + 0.10 * event_rel)

    boilerplate = any(marker in title_n for marker in BOILERPLATE_TITLE_MARKERS)
    consumer_noise = any(marker in title_n for marker in WEAK_NOISE_TITLES)

    core_eligible = has_required and has_primary_geo
    if core_eligible and not has_title_alignment:
        # Body/NGram leftovers must not outrank an unrelated headline.
        if not (signals.body_subject and signals.body_geo and len(signals.required) + len(signals.strong) >= 2):
            core_eligible = False

    context_eligible = False
    if not core_eligible:
        if has_required and context_geo_only:
            context_eligible = True
        elif has_primary_geo and signals.industrial and not weak_only:
            context_eligible = True
        elif has_required and has_event and not weak_only:
            context_eligible = True

    if boilerplate or consumer_noise:
        core_eligible = False
        context_eligible = False

    if weak_only:
        core_eligible = False
        context_eligible = False

    classification: RelevanceClass = "REJECTED"
    reason = "No required subject and primary-geography evidence in the article title or body."
    if core_eligible:
        classification = "CORE"
        reason = (
            f"Directly matches {intent.subject}"
            + (f" and {intent.event_type}" if has_event and intent.event_type else "")
            + f" in {', '.join(intent.primary_geographies[:3])}."
        )
        if signals.title_subject and signals.title_geo:
            overall = max(overall, 0.84)
        elif has_event:
            overall = max(overall, 0.72)
        else:
            overall = max(overall, 0.62)
    elif context_eligible:
        classification = "CONTEXT"
        if has_required and context_geo_only:
            reason = (
                f"On-subject {intent.subject} coverage outside primary geography "
                f"({', '.join(intent.context_geographies[:3]) or 'regional'})."
            )
        elif signals.industrial:
            reason = "Primary-geography industrial/utility context that may explain a CORE event."
        else:
            reason = "Related to the query subject but does not itself answer it."
        overall = max(overall, 0.4)
        overall = min(overall, 0.67)
    else:
        if weak_only:
            reason = (
                "Only weak/adjacent terms matched; they cannot substitute for required subject concepts."
            )
        elif consumer_noise:
            reason = "Consumer/gaming technology article with no meaningful query connection."
        elif boilerplate:
            reason = "Index, category, or boilerplate page rather than an article about the query."
        elif has_primary_geo and not has_required:
            reason = (
                f"Mentions {', '.join(intent.primary_geographies[:2])} but lacks required "
                f"{intent.subject} evidence."
            )
        elif has_required and not has_primary_geo and not context_geo_only:
            reason = f"On-subject {intent.subject} coverage without a geography link to the query."

    if source:
        reason = reason.rstrip(".") + f" Source: {source}."

    return RelevanceResult(
        classification=classification,
        subject_relevance=subject_rel,
        geography_relevance=geo_rel,
        event_type_relevance=event_rel,
        title_relevance=title_rel,
        full_text_relevance=full_rel,
        overall_relevance=overall,
        reason=reason,
        signals=signals,
        core_eligible=core_eligible,
        context_eligible=context_eligible,
    )


def classify_article(intent: QueryIntent, article: Article) -> RelevanceResult:
    return classify_text(
        intent,
        article.title,
        " ".join(part for part in (article.summary, article.body) if part),
        source=article.source,
    )


def classify_event(intent: QueryIntent, event: Event, articles: dict[str, Article] | None = None) -> RelevanceResult:
    snippets = [event.title, event.summary, " ".join(event.countries), " ".join(event.companies)]
    if articles:
        for article_id in event.source_article_ids:
            article = articles.get(article_id)
            if article:
                snippets.append(article.title)
                snippets.append(_lead_text(article.body, 900))
    return classify_text(intent, event.title, "\n".join(snippets))


async def llm_refine_classification(
    intent: QueryIntent,
    title: str,
    body: str,
    heuristic: RelevanceResult,
    *,
    source: str = "",
    published: str = "",
) -> RelevanceResult:
    """Optional LLM pass. May only demote CORE/CONTEXT; never promote REJECTED to CORE."""
    if heuristic.classification == "REJECTED":
        return heuristic
    try:
        from app.clients.llm import complete_json_with_repair, llm_available

        if not llm_available():
            return heuristic
        user = {
            "query": intent.raw_query,
            "intent": {
                "subject": intent.subject,
                "eventType": intent.event_type,
                "primaryGeographies": intent.primary_geographies,
                "requiredConcepts": intent.required_terms()[:12],
                "weakContextTerms": intent.weak_context_terms[:12],
            },
            "article": {
                "title": title,
                "source": source,
                "date": published,
                "body": _lead_text(body, 3500),
            },
            "heuristic": heuristic.as_dict(),
        }
        import json

        result = await complete_json_with_repair(
            (
                "You classify news-article relevance for a causal intelligence graph. "
                "Use only the supplied title and body. Do not invent facts. "
                "CORE requires the required subject AND the primary geography. "
                "Weak adjacent terms (AI, GPU, cloud, data center when not the subject) "
                "must not qualify CORE. "
                "Return JSON with keys classification, subjectRelevance, geographyRelevance, "
                "eventTypeRelevance, overallRelevance, reason."
            ),
            json.dumps(user, default=str),
        )
    except Exception as exc:
        log.info(
            "relevance_llm_skipped",
            extra={"source": "llm", "success": False, "error": type(exc).__name__},
        )
        return heuristic

    if not isinstance(result, dict):
        return heuristic
    label = str(result.get("classification") or heuristic.classification).upper()
    if label not in {"CORE", "CONTEXT", "REJECTED"}:
        return heuristic
    rank = {"REJECTED": 0, "CONTEXT": 1, "CORE": 2}
    if rank[label] > rank[heuristic.classification]:
        label = heuristic.classification
    reason = str(result.get("reason") or heuristic.reason)
    return RelevanceResult(
        classification=label,  # type: ignore[arg-type]
        subject_relevance=_clip(float(result.get("subjectRelevance") or heuristic.subject_relevance)),
        geography_relevance=_clip(float(result.get("geographyRelevance") or heuristic.geography_relevance)),
        event_type_relevance=_clip(float(result.get("eventTypeRelevance") or heuristic.event_type_relevance)),
        title_relevance=heuristic.title_relevance,
        full_text_relevance=heuristic.full_text_relevance,
        overall_relevance=_clip(float(result.get("overallRelevance") or heuristic.overall_relevance)),
        reason=reason,
        signals=heuristic.signals,
        core_eligible=label == "CORE",
        context_eligible=label == "CONTEXT",
    )
