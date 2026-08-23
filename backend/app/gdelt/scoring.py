from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from app.gdelt.matching import DocAccumulator
from app.gdelt.topics import GEO_COUNTRY, TopicConfig, normalize_text
from app.sources.adapters import canonicalize_url

AGGREGATOR_DOMAINS = {
    "newsnow.co.uk",
    "www.newsnow.co.uk",
    "newsnow.com",
    "www.newsnow.com",
    "news.google.com",
    "news.yahoo.com",
    "bing.com",
    "msn.com",
}

GENERIC_TITLES = {
    "latest news",
    "breaking news",
    "top stories",
    "technology news",
    "world news",
    "business news",
    "latest updates",
    "news",
}

STRONG_TITLE_TECH_SIGNALS = (
    "artificial intelligence",
    "data center",
    "data centre",
    "hyperscale",
    "infrastructure",
    "gpu cluster",
    "ai compute",
    "ai infrastructure",
    "cloud infrastructure",
    "server farm",
    "compute infrastructure",
    "investment",
    "server",
    "compute",
)

WEAK_TITLE_TECH_SIGNALS = (
    "ai",
    "nvidia",
    "gpu",
    "cloud",
    "semiconductor",
    "chip",
)

INDEX_TITLE_RE = re.compile(
    r"(latest news|breaking news|top stories|latest updates|news\s*\|\s*.*news)",
    re.IGNORECASE,
)


@dataclass
class ScoreBreakdown:
    tech: float = 0.0
    geography: float = 0.0
    entities: float = 0.0
    title: float = 0.0
    source: float = 0.0
    frequency: float = 0.0
    penalties: float = 0.0

    @property
    def total(self) -> float:
        return round(
            self.tech + self.geography + self.entities + self.title + self.source + self.frequency + self.penalties,
            2,
        )

    def as_dict(self) -> dict:
        return {
            "tech": round(self.tech, 2),
            "geography": round(self.geography, 2),
            "entities": round(self.entities, 2),
            "title": round(self.title, 2),
            "source": round(self.source, 2),
            "frequency": round(self.frequency, 2),
            "penalties": round(self.penalties, 2),
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> ScoreBreakdown:
        data = data or {}
        return cls(
            tech=float(data.get("tech") or 0),
            geography=float(data.get("geography") or 0),
            entities=float(data.get("entities") or 0),
            title=float(data.get("title") or 0),
            source=float(data.get("source") or 0),
            frequency=float(data.get("frequency") or 0),
            penalties=float(data.get("penalties") or 0),
        )


@dataclass
class RankedCandidate:
    snapshot_timestamp: str
    gdelt_doc_id: int
    title: str
    url: str
    domain: str
    published_at: str | None
    language: str
    image_url: str | None
    relevance_score: float
    breakdown: ScoreBreakdown
    matched_tech_terms: list[str]
    matched_geo_terms: list[str]
    matched_entities: list[str]
    matched_ngrams: list[str]
    is_aggregator: bool
    is_likely_article: bool
    country: str
    rejected: bool = False
    reject_reason: str | None = None
    extras: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source": "gdelt_ngrams",
            "snapshotTimestamp": self.snapshot_timestamp,
            "gdeltDocId": self.gdelt_doc_id,
            "title": self.title,
            "url": self.url,
            "domain": self.domain,
            "publishedAt": self.published_at,
            "language": self.language,
            "imageUrl": self.image_url,
            "relevanceScore": self.relevance_score,
            "scoreBreakdown": self.breakdown.as_dict(),
            "matchedTechTerms": self.matched_tech_terms,
            "matchedGeoTerms": self.matched_geo_terms,
            "matchedEntities": self.matched_entities,
            "matchedNgrams": self.matched_ngrams,
            "isLikelyArticle": self.is_likely_article,
            "isAggregator": self.is_aggregator,
            "country": self.country,
            "rejected": self.rejected,
            "rejectReason": self.reject_reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> RankedCandidate:
        breakdown = ScoreBreakdown.from_dict(data.get("scoreBreakdown") or data.get("breakdown"))
        return cls(
            snapshot_timestamp=str(data.get("snapshotTimestamp") or data.get("snapshot_timestamp") or ""),
            gdelt_doc_id=int(data.get("gdeltDocId") or data.get("gdelt_doc_id") or 0),
            title=str(data.get("title") or ""),
            url=str(data.get("url") or ""),
            domain=str(data.get("domain") or ""),
            published_at=data.get("publishedAt") or data.get("published_at"),
            language=str(data.get("language") or "en"),
            image_url=data.get("imageUrl") or data.get("image_url"),
            relevance_score=float(data.get("relevanceScore") or data.get("relevance_score") or breakdown.total),
            breakdown=breakdown,
            matched_tech_terms=list(data.get("matchedTechTerms") or data.get("matched_tech_terms") or []),
            matched_geo_terms=list(data.get("matchedGeoTerms") or data.get("matched_geo_terms") or []),
            matched_entities=list(data.get("matchedEntities") or data.get("matched_entities") or []),
            matched_ngrams=list(data.get("matchedNgrams") or data.get("matched_ngrams") or []),
            is_aggregator=bool(data.get("isAggregator") or data.get("is_aggregator")),
            is_likely_article=bool(data.get("isLikelyArticle", data.get("is_likely_article", True))),
            country=str(data.get("country") or "Unknown"),
            rejected=bool(data.get("rejected")),
            reject_reason=data.get("rejectReason") or data.get("reject_reason"),
        )


def domain_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def is_aggregator(url: str, domain: str | None = None) -> bool:
    host = (domain or domain_of(url)).lower().removeprefix("www.")
    return host in {item.removeprefix("www.") for item in AGGREGATOR_DOMAINS} or host.endswith(".newsnow.co.uk")


def url_looks_like_article(url: str) -> bool:
    path = (urlparse(url).path or "").rstrip("/")
    if not path or path == "/":
        return False
    last = path.split("/")[-1]
    if last.lower() in {"news", "category", "topics", "tag", "tags", "index", "reports", "latest"}:
        return False
    if re.search(r"\d{3,}", last):
        return True
    if last.lower().endswith((".html", ".htm", ".shtml")):
        return True
    slug = re.sub(r"[^a-z0-9]+", "-", last.lower()).strip("-")
    return slug.count("-") >= 3 or len(slug) >= 24


def is_likely_article_page(title: str, url: str) -> bool:
    title_n = normalize_text(title)
    domain = domain_of(url)
    if is_aggregator(url, domain):
        return False
    if not title_n:
        return False
    if title_n in GENERIC_TITLES:
        return url_looks_like_article(url)
    if INDEX_TITLE_RE.search(title) and not url_looks_like_article(url):
        return False
    if " | " in (title or "") and "news" in title_n and not url_looks_like_article(url):
        return False
    if "digitimes research" in title_n and not url_looks_like_article(url):
        return False
    return True


def _title_has_any(title_n: str, phrases: list[str]) -> bool:
    padded = f" {title_n} "
    return any(f" {phrase} " in padded for phrase in phrases if phrase)


def score_document(
    topic: TopicConfig,
    acc: DocAccumulator,
    *,
    title: str,
    url: str,
    language: str,
) -> RankedCandidate:
    domain = domain_of(url)
    breakdown = ScoreBreakdown()
    breakdown.tech = round(sum(acc.tech_terms.values()), 2)
    breakdown.geography = round(sum(acc.geo_terms.values()), 2)
    breakdown.entities = round(min(sum(acc.entity_terms.values()), 4.0), 2)
    breakdown.frequency = round(min(acc.total_match_frequency / 8.0, 2.5), 2)

    title_n = normalize_text(title)
    strong_in_title = _title_has_any(
        title_n, list(topic.strong_tech_terms) + list(STRONG_TITLE_TECH_SIGNALS)
    )
    weak_in_title = _title_has_any(title_n, list(topic.weak_tech_terms) + list(WEAK_TITLE_TECH_SIGNALS))
    geo_in_title = _title_has_any(title_n, list(acc.geo_terms) + list(topic.concept_groups.get("geography", {})))
    infra_in_title = _title_has_any(title_n, list(topic.infra_context_terms))
    if strong_in_title:
        breakdown.title += 3.0
    elif weak_in_title:
        breakdown.title += 0.5
    if geo_in_title:
        breakdown.title += 2.5
    if infra_in_title:
        breakdown.title += 2.0
    if not strong_in_title and not geo_in_title:
        breakdown.title -= 4.0

    likely_article = is_likely_article_page(title, url)
    aggregator = is_aggregator(url, domain)
    if aggregator:
        breakdown.source -= 4.0
        breakdown.penalties -= 3.0
    elif likely_article:
        breakdown.source += 1.0
    else:
        breakdown.source -= 1.5
        breakdown.penalties -= 6.0

    strong_hits = {phrase for phrase in acc.tech_terms if phrase in topic.strong_tech_terms}
    weak_only = bool(acc.tech_terms) and not strong_hits
    infra_context = bool(acc.tech_terms.keys() & topic.infra_context_terms) or infra_in_title
    matched_blob = normalize_text(" ".join(acc.matched_quadgrams + [title]))
    if _title_has_any(matched_blob, list(topic.infra_context_terms)):
        infra_context = True
    if weak_only and not infra_context:
        breakdown.tech = min(breakdown.tech, 1.5)
        breakdown.penalties -= 3.5

    rejected = False
    reason = None
    if not likely_article:
        rejected = True
        reason = "index_or_generic_page"
    if aggregator:
        rejected = True
        reason = "aggregator"

    country = "Unknown"
    for phrase in sorted(acc.geo_terms, key=lambda item: acc.geo_terms[item], reverse=True):
        if phrase in GEO_COUNTRY:
            country = GEO_COUNTRY[phrase]
            break

    canonical = canonicalize_url(url)
    candidate = RankedCandidate(
        snapshot_timestamp="",
        gdelt_doc_id=acc.doc_id,
        title=title,
        url=canonical or url,
        domain=domain,
        published_at=None,
        language=(language or "en")[:8],
        image_url=None,
        relevance_score=0.0,
        breakdown=breakdown,
        matched_tech_terms=sorted(acc.tech_terms),
        matched_geo_terms=sorted(acc.geo_terms),
        matched_entities=sorted(acc.entity_terms),
        matched_ngrams=list(acc.matched_quadgrams),
        is_aggregator=aggregator,
        is_likely_article=likely_article,
        country=country,
        rejected=rejected,
        reject_reason=reason,
    )
    candidate.relevance_score = breakdown.total
    return candidate
