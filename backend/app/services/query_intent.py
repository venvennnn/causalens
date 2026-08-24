from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

from app.gdelt.topics import GEO_COUNTRY, SEA_GEO, normalize_text

ConceptStrength = Literal["required", "strong", "supporting", "weak"]
RelevanceClass = Literal["CORE", "CONTEXT", "REJECTED"]

STOPWORDS = {
    "about",
    "after",
    "around",
    "into",
    "near",
    "over",
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "in",
    "on",
    "of",
    "to",
    "a",
    "an",
    "vs",
}

EVENT_TYPE_LEXICONS: dict[str, list[str]] = {
    "investment": [
        "investment",
        "invests",
        "invested",
        "investing",
        "fdi",
        "foreign direct investment",
        "capital expenditure",
        "capex",
        "expansion",
        "expands",
        "expanded",
        "facility",
        "factory",
        "plant",
        "capacity",
        "funding",
        "capex",
        "greenfield",
    ],
    "regulation": [
        "regulation",
        "regulatory",
        "regulator",
        "policy",
        "ban",
        "law",
        "compliance",
        "rules",
        "guidelines",
    ],
    "disruption": [
        "disruption",
        "disrupted",
        "delay",
        "congestion",
        "strike",
        "blockade",
        "shortage",
        "halt",
    ],
    "constraint": [
        "constraint",
        "constraints",
        "tight",
        "tightens",
        "shortage",
        "power",
        "electricity",
        "grid",
        "rationing",
    ],
    "manufacturing": [
        "manufacturing",
        "production",
        "factory",
        "assembly",
        "output",
        "plant",
    ],
    "processing": [
        "processing",
        "refining",
        "smelting",
        "separation",
    ],
}

COUNTRY_ALIASES: dict[str, list[str]] = {
    "Malaysia": [
        "malaysia",
        "malaysian",
        "penang",
        "pulau pinang",
        "kulim",
        "kedah",
        "selangor",
        "johor",
        "johor bahru",
        "kuala lumpur",
        "cyberjaya",
        "malacca",
        "melaka",
        "sarawak",
        "sabah",
        "negeri sembilan",
        "perak",
        "ipoh",
        "bayan lepas",
        "bayan lepas",
        "klang",
        "putrajaya",
    ],
    "Singapore": ["singapore", "singaporean", "jurong", "tuas"],
    "Vietnam": [
        "vietnam",
        "vietnamese",
        "hanoi",
        "ha noi",
        "ho chi minh",
        "saigon",
        "bac ninh",
        "hai phong",
        "haiphong",
        "da nang",
        "dong nai",
    ],
    "Indonesia": [
        "indonesia",
        "indonesian",
        "jakarta",
        "batam",
        "bintan",
        "west java",
        "bekasi",
        "karawang",
        "bali",
        "surabaya",
    ],
    "Thailand": ["thailand", "thai", "bangkok", "rayong", "chachoengsao", "eastern economic corridor"],
    "Philippines": ["philippines", "philippine", "manila", "laguna", "cavite", "cebu"],
}

REGIONAL_GEO_TERMS = [
    "southeast asia",
    "south east asia",
    "asean",
    "sea region",
    "asia pacific",
    "asia-pacific",
]

SEA_COUNTRIES = tuple(COUNTRY_ALIASES.keys())

INDUSTRIAL_CONTEXT_TERMS = [
    "electricity",
    "power demand",
    "power grid",
    "grid",
    "utilities",
    "labour",
    "labor",
    "talent",
    "workforce",
    "supply chain",
    "logistics",
    "industrial park",
    "industrial corridor",
    "water",
    "land",
    "incentives",
    "tax break",
]


@dataclass(frozen=True)
class DomainPack:
    name: str
    triggers: tuple[str, ...]
    subject: str
    required: tuple[str, ...]
    strong: tuple[str, ...]
    supporting: tuple[str, ...]
    weak: tuple[str, ...]
    default_event_type: str | None = None


DOMAIN_PACKS: tuple[DomainPack, ...] = (
    DomainPack(
        name="semiconductor",
        triggers=("semiconductor", "chip manufacturing", "wafer", "foundry", "osat", "advanced packaging"),
        subject="semiconductor industry",
        required=(
            "semiconductor",
            "semiconductors",
            "chip manufacturing",
            "chip making",
            "chipmaker",
            "chipmakers",
            "chipmaking",
            "wafer",
            "wafers",
            "wafer fabrication",
            "wafer fab",
            "foundry",
            "foundries",
            "osat",
            "osats",
            "integrated circuit",
            "ic manufacturing",
            "ic packaging",
        ),
        strong=(
            "semiconductor plant",
            "semiconductor facility",
            "semiconductor packaging",
            "advanced packaging",
            "chip packaging",
            "fab expansion",
            "fab",
            "fabs",
            "fabrication",
            "chip",
            "chips",
            # SEA / global chip producers: company + primary geo is enough for CORE.
            "intel",
            "infineon",
            "micron",
            "tsmc",
            "amkor",
            "ase",
            "unisem",
            "inari",
            "silterra",
            "x-fab",
            "xfab",
            "globalfoundries",
            "global foundries",
            "stmicroelectronics",
            "stmicro",
            "nxp",
            "texas instruments",
            "umc",
            "asml",
            "on semiconductor",
            "onsemi",
        ),
        supporting=("investment", "fdi", "capacity", "expansion", "facility", "factory", "plant"),
        weak=("ai", "gpu", "nvidia", "electronics", "cloud", "data center", "data centre", "server", "technology"),
    ),
    DomainPack(
        name="data_center",
        triggers=("data center", "data centre", "datacenter", "hyperscale"),
        subject="data centre infrastructure",
        required=("data center", "data centre", "datacenter", "hyperscale"),
        strong=("cloud infrastructure", "server farm", "ai data center", "ai data centre", "colocation"),
        supporting=("power", "electricity", "grid", "capacity", "investment", "campus"),
        weak=("ai", "gpu", "semiconductor", "chip", "nvidia", "electronics"),
    ),
    DomainPack(
        name="ev_battery",
        triggers=("ev battery", "electric vehicle", "battery plant", "gigafactory", "nickel", "cathode"),
        subject="EV battery industry",
        required=("ev battery", "electric vehicle", "battery plant", "battery factory", "gigafactory", "cathode"),
        strong=("nickel", "lithium", "battery", "ev ecosystem"),
        supporting=("investment", "fdi", "capacity", "smelter", "refining"),
        weak=("ai", "cloud", "data center", "data centre", "semiconductor"),
    ),
    DomainPack(
        name="shipping",
        triggers=("shipping", "port congestion", "freight", "maritime", "container", "strait"),
        subject="shipping and logistics",
        required=("shipping", "port", "freight", "maritime", "container", "vessel", "strait"),
        strong=("port congestion", "supply chain disruption", "transshipment"),
        supporting=("disruption", "delay", "blockade", "reroute"),
        weak=("ai", "cloud", "data center", "semiconductor"),
    ),
    DomainPack(
        name="ai_regulation",
        triggers=("ai regulation", "artificial intelligence regulation", "ai act", "ai policy"),
        subject="AI regulation",
        required=("ai regulation", "artificial intelligence", "ai policy", "ai act"),
        strong=("regulator", "governance", "compliance"),
        supporting=("regulation", "policy", "law", "guidelines"),
        weak=("gpu", "data center", "semiconductor", "cloud"),
    ),
    DomainPack(
        name="rare_earth",
        triggers=("rare earth", "rare-earth", "lynas", "neodymium", "rare earths"),
        subject="rare earth processing",
        required=("rare earth", "rare earths", "rare-earth", "neodymium", "lynas"),
        strong=("processing", "refining", "separation", "cracking"),
        supporting=("investment", "permit", "license", "export"),
        weak=("ai", "semiconductor", "cloud", "data center"),
    ),
    DomainPack(
        name="electronics_manufacturing",
        triggers=("electronics manufacturing", "electronics assembly", "ems"),
        subject="electronics manufacturing",
        required=("electronics manufacturing", "electronics assembly", "electronics"),
        strong=("ems", "pcb", "component manufacturing", "assembly plant"),
        supporting=("fdi", "investment", "factory", "capacity"),
        weak=("ai", "cloud", "data center", "gpu"),
    ),
    DomainPack(
        name="ai_infrastructure",
        triggers=("ai infrastructure", "ai compute", "gpu cluster", "artificial intelligence infrastructure"),
        subject="AI infrastructure",
        required=("ai infrastructure", "artificial intelligence", "ai compute", "gpu cluster", "ai"),
        strong=("data center", "data centre", "hyperscale", "cloud infrastructure", "gpu", "cloud"),
        supporting=("investment", "capacity", "power", "campus"),
        weak=("gaming", "dlss", "consumer", "smartphone"),
    ),
)


@dataclass
class ConceptGroup:
    name: str
    strength: ConceptStrength
    terms: list[str] = field(default_factory=list)


@dataclass
class QueryIntent:
    raw_query: str
    subject: str
    event_type: str | None = None
    primary_geographies: list[str] = field(default_factory=list)
    context_geographies: list[str] = field(default_factory=list)
    primary_geo_terms: list[str] = field(default_factory=list)
    context_geo_terms: list[str] = field(default_factory=list)
    required_concept_groups: list[ConceptGroup] = field(default_factory=list)
    supporting_concept_groups: list[ConceptGroup] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    weak_context_terms: list[str] = field(default_factory=list)
    event_type_terms: list[str] = field(default_factory=list)
    domain: str = "generic"
    regional_query: bool = False

    def required_terms(self) -> list[str]:
        terms: list[str] = []
        for group in self.required_concept_groups:
            terms.extend(group.terms)
        return list(dict.fromkeys(terms))

    def strong_terms(self) -> list[str]:
        terms: list[str] = []
        for group in self.required_concept_groups + self.supporting_concept_groups:
            if group.strength in {"required", "strong"}:
                terms.extend(group.terms)
        return list(dict.fromkeys(terms))

    def supporting_terms(self) -> list[str]:
        terms: list[str] = []
        for group in self.supporting_concept_groups:
            terms.extend(group.terms)
        terms.extend(self.event_type_terms)
        return list(dict.fromkeys(terms))

    def all_subject_terms(self) -> list[str]:
        return list(dict.fromkeys([*self.required_terms(), *self.strong_terms()]))

    def to_dict(self) -> dict:
        payload = asdict(self)
        return payload


def _padded(text: str) -> str:
    return f" {normalize_text(text)} "


# Morphological endings only. Do not prefix-match intel→intelligence.
_MORPH_SUFFIXES = {
    "s",
    "es",
    "er",
    "ers",
    "ed",
    "ing",
    "ment",
    "maker",
    "makers",
    "making",
}


def phrase_in_text(phrase: str, text_n: str) -> bool:
    needle = normalize_text(phrase)
    if not needle:
        return False
    haystack = f" {text_n} "
    padded_needle = f" {needle} "
    if padded_needle in haystack:
        return True
    if " " in needle or len(needle) <= 3:
        return False
    for token in haystack.split():
        if token == needle:
            return True
        if token.startswith(needle) and token[len(needle) :] in _MORPH_SUFFIXES:
            return True
    return False


def any_phrase_in_text(phrases: list[str] | tuple[str, ...], text_n: str) -> list[str]:
    return [phrase for phrase in phrases if phrase_in_text(phrase, text_n)]


def _select_pack(query_n: str) -> DomainPack | None:
    scored: list[tuple[int, int, DomainPack]] = []
    for pack in DOMAIN_PACKS:
        hits = [trigger for trigger in pack.triggers if phrase_in_text(trigger, query_n)]
        if not hits:
            continue
        scored.append((len(hits), max(len(normalize_text(item)) for item in hits), pack))
    if not scored:
        # Single-token fallback: "semiconductor", "shipping", "battery"
        for pack in DOMAIN_PACKS:
            for trigger in pack.triggers:
                token = normalize_text(trigger).split()[0]
                if len(token) >= 6 and phrase_in_text(token, query_n):
                    return pack
        return None
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return scored[0][2]


def _detect_event_type(query_n: str) -> tuple[str | None, list[str]]:
    best_name = None
    best_hits: list[str] = []
    for name, terms in EVENT_TYPE_LEXICONS.items():
        hits = any_phrase_in_text(terms, query_n)
        if len(hits) > len(best_hits):
            best_name = name
            best_hits = hits
    return best_name, list(dict.fromkeys(best_hits + EVENT_TYPE_LEXICONS.get(best_name or "", [])))


def _detect_geographies(query_n: str) -> tuple[list[str], bool]:
    primary: list[str] = []
    for country, aliases in COUNTRY_ALIASES.items():
        if any_phrase_in_text(aliases, query_n):
            primary.append(country)
    regional = bool(any_phrase_in_text(REGIONAL_GEO_TERMS, query_n))
    if not primary and regional:
        primary = list(SEA_COUNTRIES)
    return primary, regional


def _geo_terms_for(countries: list[str]) -> list[str]:
    terms: list[str] = []
    for country in countries:
        terms.append(country.lower())
        terms.extend(COUNTRY_ALIASES.get(country, []))
    extra = [phrase for phrase, mapped in GEO_COUNTRY.items() if mapped in countries]
    terms.extend(extra)
    return list(dict.fromkeys(terms))


def _generic_subject_terms(query_n: str, primary_terms: list[str], event_terms: list[str]) -> list[str]:
    blocked = set(STOPWORDS)
    blocked.update(normalize_text(term) for term in primary_terms)
    blocked.update(normalize_text(term) for term in event_terms)
    blocked.update(normalize_text(term) for term in REGIONAL_GEO_TERMS)
    blocked.update(normalize_text(term) for term in SEA_GEO)
    tokens = [token for token in query_n.split() if token not in blocked and len(token) >= 4]
    phrases = [query_n] if query_n else []
    return list(dict.fromkeys(phrases + tokens))


def parse_query_intent(query: str) -> QueryIntent:
    raw = (query or "").strip()
    query_n = normalize_text(raw)
    pack = _select_pack(query_n)
    event_type, event_terms = _detect_event_type(query_n)
    primary, regional = _detect_geographies(query_n)
    if not primary:
        # Unspecified geography: CORE may be any SEA market.
        primary = list(SEA_COUNTRIES)
        regional = True
    context = [country for country in SEA_COUNTRIES if country not in primary]
    primary_terms = _geo_terms_for(primary)
    context_terms = _geo_terms_for(context)
    if regional:
        primary_terms = list(dict.fromkeys(primary_terms + REGIONAL_GEO_TERMS))
    if regional and set(primary) == set(SEA_COUNTRIES):
        context = []
        context_terms = []
    else:
        context_terms = list(dict.fromkeys(context_terms + REGIONAL_GEO_TERMS))

    if pack:
        required = ConceptGroup(name=pack.name, strength="required", terms=list(pack.required))
        strong = ConceptGroup(name=f"{pack.name}_strong", strength="strong", terms=list(pack.strong))
        supporting = ConceptGroup(
            name=f"{pack.name}_supporting",
            strength="supporting",
            terms=list(pack.supporting),
        )
        subject = pack.subject
        weak = list(pack.weak)
        domain = pack.name
        if pack.default_event_type and not event_type:
            event_type = pack.default_event_type
            event_terms = list(EVENT_TYPE_LEXICONS.get(event_type, event_terms))
    else:
        subject_terms = _generic_subject_terms(query_n, _geo_terms_for(primary), event_terms)
        required = ConceptGroup(name="query_subject", strength="required", terms=subject_terms or [query_n])
        strong = ConceptGroup(name="query_strong", strength="strong", terms=[])
        supporting = ConceptGroup(name="query_supporting", strength="supporting", terms=list(event_terms))
        subject = " ".join(subject_terms[:6]) or raw
        weak = ["technology", "ai", "cloud"]
        domain = "generic"

    if event_type and event_terms:
        supporting.terms = list(dict.fromkeys([*supporting.terms, *event_terms]))

    return QueryIntent(
        raw_query=raw,
        subject=subject,
        event_type=event_type,
        primary_geographies=primary,
        context_geographies=context,
        primary_geo_terms=primary_terms,
        context_geo_terms=context_terms,
        required_concept_groups=[required, strong],
        supporting_concept_groups=[supporting],
        weak_context_terms=weak,
        event_type_terms=event_terms,
        domain=domain,
        regional_query=regional,
    )
