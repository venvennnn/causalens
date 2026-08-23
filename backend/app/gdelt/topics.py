from __future__ import annotations

import re
from dataclasses import dataclass, field


def normalize_text(value: str) -> str:
    text = (value or "").lower().replace("\u00a0", " ")
    text = text.replace("-", " ").replace("_", " ")
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


AI_INFRA_TECH = {
    "ai infrastructure": 5.0,
    "artificial intelligence infrastructure": 5.0,
    "ai data center": 5.0,
    "ai data centre": 5.0,
    "data center": 2.5,
    "data centre": 2.5,
    "gpu cluster": 4.0,
    "gpu infrastructure": 4.0,
    "gpu data center": 5.0,
    "gpu data centre": 5.0,
    "ai cloud": 4.0,
    "cloud infrastructure": 2.0,
    "cloud computing": 1.5,
    "hyperscale data center": 4.0,
    "hyperscale data centre": 4.0,
    "ai compute": 4.0,
    "compute infrastructure": 3.0,
    "semiconductor": 1.0,
    "chip manufacturing": 2.0,
    "server farm": 2.0,
    "data center investment": 4.0,
    "data centre investment": 4.0,
    # Weak standalone tokens: can help qualify with geography, but must not dominate.
    "nvidia": 1.0,
    "gpu": 1.0,
}

SEA_GEO = {
    "singapore": 3.0,
    "malaysia": 3.0,
    "vietnam": 3.0,
    "indonesia": 3.0,
    "thailand": 3.0,
    "philippines": 3.0,
    "southeast asia": 4.0,
    "south east asia": 4.0,
    "asean": 4.0,
    "johor": 4.0,
    "johor bahru": 5.0,
    "kuala lumpur": 3.0,
    "penang": 4.0,
    "pulau pinang": 4.0,
    "kulim": 4.5,
    "kedah": 3.5,
    "selangor": 3.0,
    "bayan lepas": 4.5,
    "cyberjaya": 3.5,
    "bangkok": 3.0,
    "jakarta": 3.0,
    "manila": 3.0,
    "ho chi minh": 3.0,
    "hanoi": 3.0,
    "bac ninh": 3.5,
    "hai phong": 3.0,
    "haiphong": 3.0,
}

INFRA_ENTITIES = {
    "nvidia": 2.0,
    "microsoft": 1.5,
    "google": 1.5,
    "amazon": 1.0,
    "aws": 1.5,
    "oracle": 1.5,
    "meta": 1.0,
    "bytedance": 2.0,
    "alibaba": 1.5,
    "tencent": 1.5,
    "ytl": 2.0,
    "singtel": 2.0,
    "telekom malaysia": 2.0,
    "keppel": 2.0,
    "sinar mas": 1.5,
    "blackstone": 1.5,
    "kkr": 1.5,
    "brookfield": 1.5,
}

STRONG_TECH_TERMS = {
    "ai infrastructure",
    "artificial intelligence infrastructure",
    "ai data center",
    "ai data centre",
    "gpu cluster",
    "gpu infrastructure",
    "gpu data center",
    "gpu data centre",
    "ai cloud",
    "hyperscale data center",
    "hyperscale data centre",
    "ai compute",
    "compute infrastructure",
    "server farm",
    "data center investment",
    "data centre investment",
    "data center",
    "data centre",
    "cloud infrastructure",
}

WEAK_TECH_TERMS = {
    "cloud computing",
    "semiconductor",
    "chip manufacturing",
    "nvidia",
    "gpu",
}

INFRA_CONTEXT_TERMS = {
    "data center",
    "data centre",
    "infrastructure",
    "compute infrastructure",
    "gpu cluster",
    "ai compute",
    "hyperscale",
    "cloud infrastructure",
    "server farm",
    "investment",
    "capacity",
    "construction",
    "facility",
}

EV_TECH = {
    "ev battery": 5.0,
    "electric vehicle": 3.0,
    "battery plant": 4.5,
    "battery factory": 4.5,
    "nickel": 2.5,
    "lithium": 2.0,
    "supply chain": 2.0,
    "gigafactory": 5.0,
    "cathode": 3.0,
    "ev ecosystem": 4.0,
}

SEMI_TECH = {
    "semiconductor": 3.0,
    "chip manufacturing": 4.0,
    "chipmaker": 4.0,
    "chipmakers": 4.0,
    "wafer": 3.0,
    "foundry": 4.0,
    "osat": 4.0,
    "advanced packaging": 4.0,
    "chip supply chain": 4.5,
    "intel": 3.2,
    "infineon": 3.5,
    "micron": 3.2,
}

MANUFACTURING_TECH = {
    "manufacturing": 2.5,
    "factory expansion": 4.0,
    "fdi": 3.0,
    "industrial park": 3.5,
    "production capacity": 3.5,
    "electronics manufacturing": 4.0,
    "supply chain": 2.0,
}


GEO_COUNTRY = {
    "singapore": "Singapore",
    "malaysia": "Malaysia",
    "vietnam": "Vietnam",
    "indonesia": "Indonesia",
    "thailand": "Thailand",
    "philippines": "Philippines",
    "johor": "Malaysia",
    "johor bahru": "Malaysia",
    "kuala lumpur": "Malaysia",
    "penang": "Malaysia",
    "pulau pinang": "Malaysia",
    "kulim": "Malaysia",
    "kedah": "Malaysia",
    "selangor": "Malaysia",
    "bayan lepas": "Malaysia",
    "cyberjaya": "Malaysia",
    "bangkok": "Thailand",
    "jakarta": "Indonesia",
    "manila": "Philippines",
    "ho chi minh": "Vietnam",
    "hanoi": "Vietnam",
    "bac ninh": "Vietnam",
    "hai phong": "Vietnam",
    "haiphong": "Vietnam",
    "southeast asia": "Southeast Asia",
    "south east asia": "Southeast Asia",
    "asean": "Southeast Asia",
}


@dataclass
class TopicConfig:
    name: str
    concept_groups: dict[str, dict[str, float]]
    boost_terms: dict[str, float] = field(default_factory=dict)
    strong_tech_terms: set[str] = field(default_factory=set)
    weak_tech_terms: set[str] = field(default_factory=set)
    infra_context_terms: set[str] = field(default_factory=set)
    required_groups: tuple[str, ...] = ("technology", "geography")

    def all_phrases(self) -> list[tuple[str, str, float]]:
        phrases: list[tuple[str, str, float]] = []
        for group, terms in self.concept_groups.items():
            for phrase, weight in terms.items():
                phrases.append((normalize_text(phrase), group, float(weight)))
        for phrase, weight in self.boost_terms.items():
            phrases.append((normalize_text(phrase), "entity", float(weight)))
        phrases.sort(key=lambda item: len(item[0]), reverse=True)
        return phrases


def _topic(
    name: str,
    tech: dict[str, float],
    *,
    strong: set[str] | None = None,
    weak: set[str] | None = None,
) -> TopicConfig:
    strong = strong or {k for k, v in tech.items() if v >= 2.5 or k in STRONG_TECH_TERMS}
    weak = weak or {k for k in tech if k in WEAK_TECH_TERMS or tech[k] <= 1.5}
    return TopicConfig(
        name=name,
        concept_groups={"technology": dict(tech), "geography": dict(SEA_GEO)},
        boost_terms=dict(INFRA_ENTITIES),
        strong_tech_terms={normalize_text(item) for item in strong},
        weak_tech_terms={normalize_text(item) for item in weak},
        infra_context_terms={normalize_text(item) for item in INFRA_CONTEXT_TERMS},
    )


def topic_from_intent(intent) -> TopicConfig:
    tech: dict[str, float] = {}
    for term in intent.required_terms():
        tech[term] = 4.0
    for group in intent.required_concept_groups:
        weight = 4.0 if group.strength == "required" else 3.2
        for term in group.terms:
            tech.setdefault(term, weight)
    for group in intent.supporting_concept_groups:
        for term in group.terms:
            tech.setdefault(term, 2.2)
    # Query remainder can boost recall but must not become a required weak substitute.
    q = normalize_text(intent.raw_query)
    if q:
        tech.setdefault(q, 1.2)

    strong = {normalize_text(term) for term in intent.strong_terms() or intent.required_terms()}
    weak = {normalize_text(term) for term in intent.weak_context_terms}
    boost = {term: 1.0 for term in intent.weak_context_terms}
    for entity in intent.entities:
        boost[entity] = 1.5
    geo = dict(SEA_GEO)
    for term in [*intent.primary_geo_terms, *intent.context_geo_terms]:
        normalized = normalize_text(term)
        if normalized:
            geo.setdefault(normalized, 3.5)
    # Keep GDELT geography SEA-wide for recall; precision is applied after Bright Data.
    return TopicConfig(
        name=intent.domain or "query",
        concept_groups={"technology": tech, "geography": geo},
        boost_terms={**INFRA_ENTITIES, **boost},
        strong_tech_terms=strong,
        weak_tech_terms=weak,
        infra_context_terms={normalize_text(item) for item in intent.supporting_terms()[:24]},
    )


def topic_from_query(query: str) -> TopicConfig:
    from app.services.query_intent import parse_query_intent

    q = normalize_text(query)
    if q in {"ai infrastructure in southeast asia", ""}:
        return _topic("ai_infrastructure_sea", AI_INFRA_TECH)
    return topic_from_intent(parse_query_intent(query))
