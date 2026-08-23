from __future__ import annotations

from rapidfuzz import fuzz

from app.models.schemas import Article, ArticleCandidate
from app.sources.adapters import canonicalize_url


def normalize_title(title: str) -> str:
    return " ".join((title or "").lower().split())


def titles_similar(a: str, b: str, threshold: int = 90) -> bool:
    if not a or not b:
        return False
    return fuzz.token_set_ratio(normalize_title(a), normalize_title(b)) >= threshold


def dedupe_candidates(items: list[ArticleCandidate], threshold: int = 90) -> list[ArticleCandidate]:
    unique: list[ArticleCandidate] = []
    seen_urls: set[str] = set()
    for item in sorted(items, key=lambda c: c.published_at or __import__("datetime").datetime.min, reverse=True):
        url = canonicalize_url(item.url)
        if url in seen_urls:
            continue
        if any(titles_similar(item.title, existing.title, threshold) for existing in unique):
            continue
        seen_urls.add(url)
        unique.append(item)
    return unique


def merge_article_streams(
    curated: list[Article],
    discovered: list[ArticleCandidate],
    threshold: int = 90,
) -> tuple[list[Article], list[ArticleCandidate]]:
    curated_urls = {canonicalize_url(article.url) for article in curated}
    extra: list[ArticleCandidate] = []
    for item in discovered:
        url = canonicalize_url(item.url)
        if url in curated_urls:
            continue
        if any(titles_similar(item.title, article.title, threshold) for article in curated):
            continue
        if any(titles_similar(item.title, other.title, threshold) for other in extra):
            continue
        extra.append(item)
    return curated, extra
