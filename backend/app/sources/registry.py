from __future__ import annotations

from app.config import get_settings

settings = get_settings()

SOURCE_REGISTRY: dict[str, dict] = {
    "cna": {
        "name": "CNA",
        "country": "Singapore",
        "region": "Southeast Asia",
        "discovery_url": "https://www.channelnewsasia.com/business",
        "discovery_collector": settings.cna_discovery_collector,
        "article_collector": settings.cna_article_collector,
        "domains": ["channelnewsasia.com", "www.channelnewsasia.com"],
    },
    "edge": {
        "name": "The Edge Malaysia",
        "country": "Malaysia",
        "region": "Southeast Asia",
        "discovery_url": "https://theedgemalaysia.com/",
        "discovery_collector": settings.edge_discovery_collector,
        "article_collector": settings.edge_article_collector,
        "domains": ["theedgemalaysia.com"],
    },
    "vir": {
        "name": "Vietnam Investment Review",
        "country": "Vietnam",
        "region": "Southeast Asia",
        "discovery_url": "https://vir.com.vn/",
        "discovery_collector": settings.vir_discovery_collector,
        "article_collector": settings.vir_article_collector,
        "domains": ["vir.com.vn"],
    },
}

DOMAIN_TO_SOURCE: dict[str, str] = {}
for key, meta in SOURCE_REGISTRY.items():
    for domain in meta["domains"]:
        DOMAIN_TO_SOURCE[domain.lower()] = key


def get_source(source_key: str) -> dict:
    if source_key not in SOURCE_REGISTRY:
        raise KeyError(source_key)
    return SOURCE_REGISTRY[source_key]


def source_for_url(url: str) -> str | None:
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host_bare = host[4:]
    else:
        host_bare = host
    return DOMAIN_TO_SOURCE.get(host) or DOMAIN_TO_SOURCE.get(host_bare)
