from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.clients.brightdata import BrightDataClient
from app.config import get_settings
from app.exceptions import CausaLensError, SourceNotFound
from app.logging import log
from app.models.db import ArticleRow
from app.models.schemas import Article, ArticleCandidate
from app.services.dedupe import dedupe_candidates
from app.services.health import validate_article
from app.services.pipeline import log_pipeline_event, upsert_pipeline_run
from app.sources.adapters import canonicalize_url, normalize_article, normalize_discovery
from app.sources.registry import SOURCE_REGISTRY, get_source, source_for_url


def _article_row(article: Article, valid: bool) -> ArticleRow:
    return ArticleRow(
        id=article.id,
        title=article.title,
        url=article.url,
        canonical_url=canonicalize_url(article.url),
        source=article.source,
        country=article.country,
        language=article.language,
        published_at=article.published_at,
        author=article.author,
        category=article.category,
        summary=article.summary,
        body=article.body,
        image_url=article.image_url,
        ingested_at=article.ingested_at,
        raw=article.raw,
        valid=valid,
    )


async def ingest_source(
    source_key: str,
    db: Session,
    max_articles: int | None = None,
    client: BrightDataClient | None = None,
) -> dict:
    if source_key not in SOURCE_REGISTRY:
        raise SourceNotFound(f"Unknown source {source_key}")
    settings = get_settings()
    source = get_source(source_key)
    max_articles = max_articles or settings.max_articles_per_source
    client = client or BrightDataClient()
    run_id = uuid.uuid4().hex[:12]
    discovered = 0
    extracted = 0
    valid_count = 0
    failures = 0

    upsert_pipeline_run(
        db,
        source_key=source_key,
        discovery_status="running",
        article_status="idle",
        collector_id=source["discovery_collector"],
        article_collector_id=source["article_collector"],
    )
    log_pipeline_event(db, source_key, "discovery_started", "Discovery collector started", source["discovery_collector"])

    try:
        records = await client.run_collector(source["discovery_collector"], source["discovery_url"])
    except CausaLensError as exc:
        upsert_pipeline_run(
            db,
            source_key=source_key,
            discovery_status="failed",
            article_status="skipped",
            health="FAILED",
            last_failure=datetime.utcnow(),
            collector_id=source["discovery_collector"],
            article_collector_id=source["article_collector"],
        )
        log_pipeline_event(db, source_key, "discovery_failed", exc.message, source["discovery_collector"])
        raise

    candidates: list[ArticleCandidate] = []
    for record in records:
        candidate = normalize_discovery(source_key, record)
        if candidate:
            candidates.append(candidate)
    candidates = dedupe_candidates(candidates)
    candidates = sorted(
        candidates,
        key=lambda item: item.published_at or datetime.min,
        reverse=True,
    )[:max_articles]
    discovered = len(candidates)
    upsert_pipeline_run(
        db,
        source_key=source_key,
        discovery_status="ok",
        article_status="running",
        articles_discovered=discovered,
        collector_id=source["discovery_collector"],
        article_collector_id=source["article_collector"],
    )
    log_pipeline_event(
        db,
        source_key,
        "discovery_ok",
        f"Scrape succeeded — {discovered} article URLs discovered",
        source["discovery_collector"],
    )

    semaphore = asyncio.Semaphore(settings.article_concurrency)

    async def fetch_one(candidate: ArticleCandidate) -> Article | None:
        async with semaphore:
            try:
                rows = await client.run_collector(source["article_collector"], candidate.url)
            except CausaLensError as exc:
                log.info(
                    "article_extract_failed",
                    extra={
                        "source": source_key,
                        "collector": source["article_collector"],
                        "url": candidate.url,
                        "success": False,
                        "error": type(exc).__name__,
                    },
                )
                return None
            record = rows[0] if rows else {}
            return normalize_article(source_key, record, url=candidate.url, candidate=candidate)

    articles = [item for item in await asyncio.gather(*(fetch_one(c) for c in candidates)) if item]
    extracted = len(articles)
    valid_articles: list[Article] = []
    for article in articles:
        result = validate_article(article)
        row = _article_row(article, result.healthy)
        existing = db.get(ArticleRow, article.id)
        if existing:
            for field in (
                "title",
                "url",
                "canonical_url",
                "source",
                "country",
                "language",
                "published_at",
                "author",
                "category",
                "summary",
                "body",
                "image_url",
                "ingested_at",
                "raw",
                "valid",
            ):
                setattr(existing, field, getattr(row, field))
        else:
            db.add(row)
        if result.healthy:
            valid_articles.append(article)
            valid_count += 1
        else:
            failures += 1
            log.info(
                "article_validation_failed",
                extra={
                    "source": source_key,
                    "url": article.url,
                    "validation_failures": result.failures,
                    "success": False,
                },
            )

    health = "HEALTHY"
    if failures and valid_count:
        health = "DEGRADED"
        log_pipeline_event(
            db,
            source_key,
            "validation_degraded",
            f"Validation degraded — {failures} article(s) failed quality checks",
            source["article_collector"],
        )
    elif not valid_count:
        health = "FAILED"
        log_pipeline_event(
            db,
            source_key,
            "extraction_failed",
            "No valid articles extracted",
            source["article_collector"],
        )
    else:
        log_pipeline_event(
            db,
            source_key,
            "extraction_ok",
            f"Extraction recovered — {valid_count} valid articles persisted",
            source["article_collector"],
        )

    upsert_pipeline_run(
        db,
        source_key=source_key,
        discovery_status="ok",
        article_status="ok" if valid_count else "failed",
        articles_discovered=discovered,
        articles_extracted=extracted,
        validation_failures=failures,
        last_success=datetime.utcnow() if valid_count else None,
        last_failure=datetime.utcnow() if not valid_count else None,
        health=health,
        collector_id=source["discovery_collector"],
        article_collector_id=source["article_collector"],
    )
    db.flush()
    log.info(
        "ingest_source_complete",
        extra={
            "source": source_key,
            "collector": source["discovery_collector"],
            "run_id": run_id,
            "success": valid_count > 0,
            "article_count": valid_count,
            "articles_discovered": discovered,
            "articles_extracted": extracted,
            "validation_failures": failures,
        },
    )
    return {
        "source": source_key,
        "articles_discovered": discovered,
        "articles_extracted": extracted,
        "articles_valid": valid_count,
        "validation_failures": failures,
        "health": health,
    }


async def ingest_all_sources(db: Session, max_articles: int | None = None) -> dict:
    client = BrightDataClient()

    async def run(source_key: str) -> dict:
        try:
            return await ingest_source(source_key, db, max_articles=max_articles, client=client)
        except Exception as exc:
            return {
                "source": source_key,
                "articles_discovered": 0,
                "articles_extracted": 0,
                "articles_valid": 0,
                "validation_failures": 0,
                "health": "FAILED",
                "error": str(exc),
            }

    results = await asyncio.gather(*(run(key) for key in SOURCE_REGISTRY))
    return {
        "sources": len(SOURCE_REGISTRY),
        "articles_discovered": sum(item["articles_discovered"] for item in results),
        "articles_extracted": sum(item["articles_extracted"] for item in results),
        "articles_valid": sum(item["articles_valid"] for item in results),
        "results": results,
    }


def _candidate_relevance(candidate: ArticleCandidate) -> float | None:
    raw = candidate.raw or {}
    score = raw.get("relevance_score")
    if score is None:
        return None
    try:
        return float(score)
    except (TypeError, ValueError):
        return None


def _upsert_article_row(db: Session, article: Article, valid: bool) -> None:
    row = _article_row(article, valid)
    existing = db.get(ArticleRow, article.id)
    if existing:
        for field in (
            "title",
            "url",
            "canonical_url",
            "source",
            "country",
            "language",
            "published_at",
            "author",
            "category",
            "summary",
            "body",
            "image_url",
            "ingested_at",
            "raw",
            "valid",
        ):
            setattr(existing, field, getattr(row, field))
        return
    db.add(row)


def load_articles_by_canonical_urls(db: Session, urls: list[str]) -> list[Article]:
    canonicals = [canonicalize_url(url) for url in urls if url]
    if not canonicals:
        return []
    rows = (
        db.query(ArticleRow)
        .filter(ArticleRow.valid.is_(True), ArticleRow.canonical_url.in_(canonicals))
        .all()
    )
    by_url = {row.canonical_url: article_from_row(row) for row in rows}
    ordered: list[Article] = []
    seen: set[str] = set()
    for url in canonicals:
        article = by_url.get(url)
        if article is None or article.id in seen:
            continue
        seen.add(article.id)
        ordered.append(article)
    return ordered


async def fetch_configured_articles(
    candidates: list[ArticleCandidate],
    db: Session,
    *,
    client: BrightDataClient | None = None,
    min_score: float | None = None,
    force: bool = False,
) -> list[Article]:
    """Fetch full text via Bright Data article collectors for CNA / Edge / VIR URLs only.

    URLs already in the article store are reused and still returned as live hits.
    """
    settings = get_settings()
    min_score = settings.min_brightdata_relevance_score if min_score is None else min_score
    client = client or BrightDataClient()
    existing_rows = {
        row.canonical_url: row
        for row in db.query(ArticleRow).filter(ArticleRow.valid.is_(True)).all()
        if row.canonical_url
    }

    to_scrape: list[tuple[ArticleCandidate, str]] = []
    reuse_urls: list[str] = []
    seen: set[str] = set()
    ranked: list[tuple[ArticleCandidate, str]] = []
    for candidate in candidates:
        source_key = source_for_url(candidate.url)
        if not source_key:
            continue
        canonical = canonicalize_url(candidate.url)
        if canonical in seen:
            continue
        score = _candidate_relevance(candidate)
        provider = (candidate.raw or {}).get("provider")
        if provider == "gdelt_ngrams" and score is not None and score < min_score:
            continue
        seen.add(canonical)
        ranked.append((candidate, source_key))

    ranked.sort(key=lambda item: _candidate_relevance(item[0]) or 0.0, reverse=True)
    ranked = ranked[: settings.gdelt_brightdata_max_urls]

    for candidate, source_key in ranked:
        canonical = canonicalize_url(candidate.url)
        if not force and canonical in existing_rows:
            reuse_urls.append(canonical)
            continue
        to_scrape.append((candidate, source_key))

    log.info(
        f"[GDELT] sent_to_brightdata={len(to_scrape)} reused_from_store={len(reuse_urls)}",
        extra={
            "source": "gdelt",
            "article_count": len(to_scrape) + len(reuse_urls),
            "success": True,
        },
    )

    stored_articles = load_articles_by_canonical_urls(db, reuse_urls)
    if not to_scrape:
        return stored_articles

    semaphore = asyncio.Semaphore(settings.article_concurrency)

    async def fetch_one(candidate: ArticleCandidate, source_key: str) -> Article | None:
        source = get_source(source_key)
        async with semaphore:
            try:
                rows = await client.run_collector(source["article_collector"], candidate.url)
            except CausaLensError as exc:
                log.info(
                    "gdelt_brightdata_extract_failed",
                    extra={
                        "source": source_key,
                        "collector": source["article_collector"],
                        "url": candidate.url,
                        "success": False,
                        "error": type(exc).__name__,
                    },
                )
                return None
            record = rows[0] if rows else {}
            return normalize_article(source_key, record, url=candidate.url, candidate=candidate)

    extracted = [
        item
        for item in await asyncio.gather(*(fetch_one(c, key) for c, key in to_scrape))
        if item
    ]
    valid_articles: list[Article] = []
    for article in extracted:
        result = validate_article(article)
        _upsert_article_row(db, article, result.healthy)
        if result.healthy:
            valid_articles.append(article)
    db.flush()
    log_pipeline_event(
        db,
        "gdelt",
        "brightdata_extract",
        f"Bright Data extracted {len(valid_articles)}/{len(to_scrape)} GDELT-routed articles; reused {len(stored_articles)} from store",
    )
    by_canonical = {canonicalize_url(article.url): article for article in [*stored_articles, *valid_articles]}
    ordered: list[Article] = []
    for candidate, _source_key in ranked:
        article = by_canonical.get(canonicalize_url(candidate.url))
        if article and article.id not in {item.id for item in ordered}:
            ordered.append(article)
    return ordered


def load_recent_articles(db: Session, limit: int = 40) -> list[Article]:
    rows = (
        db.query(ArticleRow)
        .filter(ArticleRow.valid.is_(True))
        .order_by(ArticleRow.ingested_at.desc())
        .limit(limit)
        .all()
    )
    return [article_from_row(row) for row in rows]


def article_from_row(row: ArticleRow) -> Article:
    return Article(
        id=row.id,
        title=row.title,
        url=row.url,
        source=row.source,
        country=row.country,
        language=row.language,
        published_at=row.published_at,
        author=row.author,
        category=row.category or [],
        summary=row.summary,
        body=row.body,
        image_url=row.image_url,
        ingested_at=row.ingested_at,
        raw=row.raw,
    )


def get_articles_by_ids(db: Session, ids: list[str]) -> list[Article]:
    if not ids:
        return []
    rows = db.query(ArticleRow).filter(ArticleRow.id.in_(ids)).all()
    by_id = {row.id: article_from_row(row) for row in rows}
    return [by_id[item] for item in ids if item in by_id]
