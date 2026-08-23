"""GDELT discovery client.

Default path is Web NGrams + TOC (high-traffic, not DOC 2.0 rate limits).
DOC 2.0 remains an optional fallback when ``gdelt_doc_fallback`` is enabled
or ``gdelt_discovery_mode=doc``.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.exceptions import GDELTUnavailable
from app.gdelt.pipeline import discover_ngrams
from app.logging import log
from app.models.schemas import ArticleCandidate
from app.sources.adapters import article_id_for, canonicalize_url, parse_datetime

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

SEA_HINT = (
    '(Singapore OR Malaysia OR Vietnam OR Indonesia OR Thailand OR Philippines '
    'OR "Southeast Asia" OR ASEAN OR Johor)'
)


class GDELTClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def search_gdelt(
        self,
        query: str,
        max_records: int = 30,
        db: Session | None = None,
    ) -> list[ArticleCandidate]:
        mode = (self.settings.gdelt_discovery_mode or "ngrams").lower()
        if mode == "doc":
            return await self.search_gdelt_doc(query, max_records)
        try:
            result = await discover_ngrams(query, db=db)
            candidates = result.candidates[: max(max_records, 0)]
            log.info(
                "gdelt_search_ok",
                extra={
                    "source": "gdelt",
                    "query": query,
                    "success": True,
                    "article_count": len(candidates),
                    "snapshots": ",".join(result.snapshots),
                    "provider": "gdelt_ngrams",
                },
            )
            return candidates
        except Exception as exc:
            log.info(
                "gdelt_ngrams_failed",
                extra={
                    "source": "gdelt",
                    "query": query,
                    "success": False,
                    "error": type(exc).__name__,
                },
            )
            if self.settings.gdelt_doc_fallback:
                log.info("Falling back to GDELT DOC 2.0 API", extra={"source": "gdelt"})
                return await self.search_gdelt_doc(query, max_records)
            if isinstance(exc, GDELTUnavailable):
                raise
            raise GDELTUnavailable(f"GDELT NGrams discovery failed: {exc}") from exc

    async def search_gdelt_doc(self, query: str, max_records: int = 30) -> list[ArticleCandidate]:
        """Optional GDELT DOC 2.0 ArtList (rate-limited; not the default)."""
        started = datetime.utcnow()
        records = await self._fetch_doc(query, max_records)
        candidates: list[ArticleCandidate] = []
        for item in records:
            url = canonicalize_url(item.get("url") or "")
            title = (item.get("title") or "").strip()
            if not url or not title:
                continue
            domain = (item.get("domain") or urlparse(url).hostname or "").lower()
            country = (item.get("sourcecountry") or "").strip() or None
            language = (item.get("language") or "English").strip()
            published = parse_datetime(item.get("seendate") or item.get("date"))
            candidates.append(
                ArticleCandidate(
                    id=article_id_for(url),
                    title=title,
                    url=url,
                    source=domain or "GDELT",
                    country=country or "Unknown",
                    published_at=published,
                    category=[],
                    summary=None,
                    image_url=item.get("socialimage"),
                    raw={
                        "provider": "gdelt_doc",
                        "domain": domain,
                        "language": language,
                        "sourcecountry": country,
                        **item,
                    },
                )
            )
        duration_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        log.info(
            "gdelt_doc_search_ok",
            extra={
                "source": "gdelt",
                "query": query,
                "duration_ms": duration_ms,
                "success": True,
                "article_count": len(candidates),
                "provider": "gdelt_doc",
            },
        )
        return candidates

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException, GDELTUnavailable)),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _fetch_doc(self, query: str, max_records: int) -> list[dict]:
        combined_query = f"({query}) {SEA_HINT}"
        params = {
            "query": combined_query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": str(min(max(max_records, 1), 75)),
            "sort": "DateDesc",
            "timespan": "14d",
        }
        timeout = httpx.Timeout(self.settings.gdelt_timeout_s)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(GDELT_DOC_URL, params=params)
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            raise GDELTUnavailable("GDELT document API is unreachable") from exc
        if response.status_code >= 400:
            raise GDELTUnavailable(f"GDELT returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise GDELTUnavailable("GDELT returned a non-JSON payload") from exc
        articles = payload.get("articles") if isinstance(payload, dict) else payload
        if not isinstance(articles, list):
            return []
        return [item for item in articles if isinstance(item, dict)]
