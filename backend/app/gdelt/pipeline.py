from __future__ import annotations

import gzip
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.exceptions import GDELTUnavailable
from app.gdelt.matching import DocAccumulator, TermMatcher, parse_ngram_line
from app.gdelt.scoring import RankedCandidate, is_likely_article_page, score_document
from app.gdelt.snapshots import SnapshotFetcher, candidate_stamps, open_gzip
from app.gdelt.topics import TopicConfig, topic_from_query
from app.logging import log
from app.models.db import ArticleRow, GdeltSnapshotRow
from app.models.schemas import ArticleCandidate
from app.sources.adapters import article_id_for, canonicalize_url, parse_datetime

_GZIP_ERRORS: tuple[type[BaseException], ...] = (OSError, EOFError, gzip.BadGzipFile)


@dataclass
class DiscoveryStats:
    snapshot: str
    ngram_rows: int = 0
    relevant_docids: int = 0
    tech_docids: int = 0
    geo_docids: int = 0
    qualified_candidates: int = 0
    rejected_index_pages: int = 0
    rejected_low_relevance: int = 0
    rejected_language: int = 0
    from_cache: bool = False

    def as_dict(self) -> dict:
        return {
            "snapshot": self.snapshot,
            "ngram_rows": self.ngram_rows,
            "relevant_docids": self.relevant_docids,
            "tech_docids": self.tech_docids,
            "geo_docids": self.geo_docids,
            "qualified_candidates": self.qualified_candidates,
            "rejected_index_pages": self.rejected_index_pages,
            "rejected_low_relevance": self.rejected_low_relevance,
            "rejected_language": self.rejected_language,
            "from_cache": self.from_cache,
        }


@dataclass
class DiscoveryResult:
    candidates: list[ArticleCandidate] = field(default_factory=list)
    ranked: list[RankedCandidate] = field(default_factory=list)
    stats: list[DiscoveryStats] = field(default_factory=list)
    snapshots: list[str] = field(default_factory=list)
    topic: str = ""


def _get_or_create_snapshot(db: Session | None, stamp: str) -> GdeltSnapshotRow | None:
    if db is None:
        return None
    row = db.get(GdeltSnapshotRow, stamp)
    if row is None:
        row = GdeltSnapshotRow(
            snapshot_timestamp=stamp,
            status="pending",
            downloaded_at=None,
            processed_at=None,
            ngram_rows=0,
            article_count=0,
            candidate_count=0,
        )
        db.add(row)
        db.flush()
    return row


def last_processed_snapshot(db: Session | None) -> str | None:
    if db is None:
        return None
    row = (
        db.query(GdeltSnapshotRow)
        .filter(GdeltSnapshotRow.status == "ok")
        .order_by(GdeltSnapshotRow.snapshot_timestamp.desc())
        .first()
    )
    return row.snapshot_timestamp if row else None


def gdelt_discovery_status(db: Session) -> dict:
    last = last_processed_snapshot(db)
    latest = (
        db.query(GdeltSnapshotRow)
        .order_by(GdeltSnapshotRow.snapshot_timestamp.desc())
        .first()
    )
    ok_count = db.query(GdeltSnapshotRow).filter(GdeltSnapshotRow.status == "ok").count()
    health = "HEALTHY"
    if latest is not None and latest.status in {"failed", "corrupt"}:
        health = "DEGRADED"
    elif ok_count == 0 and latest is None:
        health = "HEALTHY"
    return {
        "source": "gdelt",
        "display_name": "GDELT Web NGrams",
        "health": health,
        "discovery_status": "ngrams",
        "last_snapshot": last,
        "snapshots_ok": ok_count,
        "latest_status": latest.status if latest else "idle",
    }


def _scan_ngrams(path: Path, matcher: TermMatcher) -> tuple[dict[int, DocAccumulator], int]:
    docs: dict[int, DocAccumulator] = {}
    rows = 0
    with open_gzip(path) as handle:
        for line in handle:
            parsed = parse_ngram_line(line)
            if parsed is None:
                continue
            rows += 1
            doc_id, ngram, count = parsed
            hits = matcher.match_ngram(ngram, count)
            if not hits:
                continue
            acc = docs.get(doc_id)
            if acc is None:
                acc = DocAccumulator(doc_id=doc_id)
                docs[doc_id] = acc
            for hit in hits:
                acc.add(hit)
    return docs, rows


def load_toc(path: Path, wanted: set[int] | None = None) -> dict[int, dict]:
    found: dict[int, dict] = {}
    with open_gzip(path) as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                continue
            doc_id = item.get("ID", item.get("id"))
            try:
                doc_id = int(doc_id)
            except (TypeError, ValueError):
                continue
            if wanted is not None and doc_id not in wanted:
                continue
            found[doc_id] = item
            if wanted is not None and len(found) == len(wanted):
                break
    return found


def process_snapshot_files(
    stamp: str,
    ngram_path: Path,
    toc_path: Path,
    matcher: TermMatcher,
    topic: TopicConfig,
    *,
    min_score: float,
    english_only: bool = True,
    known_urls: set[str] | None = None,
) -> tuple[list[RankedCandidate], DiscoveryStats]:
    known_urls = known_urls if known_urls is not None else set()
    docs, ngram_rows = _scan_ngrams(ngram_path, matcher)
    qualified = [acc for acc in docs.values() if acc.qualifies(topic.required_groups)]
    toc = load_toc(toc_path, {acc.doc_id for acc in qualified})
    stats = DiscoveryStats(
        snapshot=stamp,
        ngram_rows=ngram_rows,
        relevant_docids=len(docs),
        tech_docids=sum(1 for acc in docs.values() if acc.tech_terms),
        geo_docids=sum(1 for acc in docs.values() if acc.geo_terms),
    )
    ranked: list[RankedCandidate] = []
    for acc in qualified:
        meta = toc.get(acc.doc_id) or {}
        title = str(meta.get("title") or "").strip()
        url = str(meta.get("url") or "").strip()
        if not title or not url:
            continue
        language = str(meta.get("lang") or meta.get("language") or "en")
        if english_only and language.lower()[:2] not in {"en", ""}:
            stats.rejected_language += 1
            continue
        item = score_document(topic, acc, title=title, url=url, language=language)
        item.snapshot_timestamp = stamp
        item.published_at = str(meta.get("date") or "") or None
        item.image_url = meta.get("img") or meta.get("image")
        canonical = canonicalize_url(item.url)
        if canonical in known_urls:
            continue
        if item.rejected or not is_likely_article_page(item.title, item.url):
            stats.rejected_index_pages += 1
            continue
        if item.relevance_score < min_score:
            stats.rejected_low_relevance += 1
            continue
        ranked.append(item)
        known_urls.add(canonical)
    stats.qualified_candidates = len(ranked)
    return ranked, stats


def ranked_to_candidate(item: RankedCandidate) -> ArticleCandidate:
    return ArticleCandidate(
        id=article_id_for(item.url),
        title=item.title,
        url=item.url,
        source=item.domain or "GDELT",
        country=item.country,
        published_at=parse_datetime(item.published_at),
        category=["GDELT"],
        summary=None,
        image_url=item.image_url,
        raw={
            "provider": "gdelt_ngrams",
            "snapshot_timestamp": item.snapshot_timestamp,
            "gdelt_doc_id": item.gdelt_doc_id,
            "language": item.language,
            "domain": item.domain,
            "is_aggregator": item.is_aggregator,
            "is_likely_article": item.is_likely_article,
            "relevance_score": item.relevance_score,
            "score_breakdown": item.breakdown.as_dict(),
            "matched_tech_terms": item.matched_tech_terms,
            "matched_geo_terms": item.matched_geo_terms,
            "matched_entities": item.matched_entities,
            "matched_ngrams": item.matched_ngrams,
        },
    )


def _existing_urls(db: Session | None) -> set[str]:
    if db is None:
        return set()
    rows = db.query(ArticleRow.canonical_url).all()
    return {row[0] for row in rows if row[0]}


def _write_ranked_cache(path: Path, ranked: list[RankedCandidate], stats: DiscoveryStats) -> None:
    payload = {
        "stats": stats.as_dict(),
        "candidates": [item.to_dict() for item in ranked],
    }
    tmp = path.with_suffix(path.suffix + ".partial")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)


def _read_ranked_cache(path: Path) -> tuple[list[RankedCandidate], DiscoveryStats] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    items = [RankedCandidate.from_dict(row) for row in payload.get("candidates") or []]
    stats = DiscoveryStats(
        snapshot=str((payload.get("stats") or {}).get("snapshot") or path.name.split(".")[0]),
        ngram_rows=int((payload.get("stats") or {}).get("ngram_rows") or 0),
        relevant_docids=int((payload.get("stats") or {}).get("relevant_docids") or 0),
        tech_docids=int((payload.get("stats") or {}).get("tech_docids") or 0),
        geo_docids=int((payload.get("stats") or {}).get("geo_docids") or 0),
        qualified_candidates=len(items),
        rejected_index_pages=int((payload.get("stats") or {}).get("rejected_index_pages") or 0),
        rejected_low_relevance=int((payload.get("stats") or {}).get("rejected_low_relevance") or 0),
        rejected_language=int((payload.get("stats") or {}).get("rejected_language") or 0),
        from_cache=True,
    )
    return items, stats


async def discover_ngrams(
    query: str,
    *,
    db: Session | None = None,
    max_snapshots: int | None = None,
    min_score: float | None = None,
    force_rescan: bool = False,
) -> DiscoveryResult:
    settings = get_settings()
    topic = topic_from_query(query)
    matcher = TermMatcher(topic)
    fetcher = SnapshotFetcher()
    stamps = candidate_stamps(
        lag_minutes=settings.gdelt_ngram_lag_minutes,
        lookback_hours=settings.gdelt_ngram_lookback_hours,
        max_probes=settings.gdelt_ngram_max_probe_minutes,
        stride_minutes=settings.gdelt_ngram_snapshot_stride_minutes,
    )
    limit = max_snapshots or settings.gdelt_ngram_max_snapshots
    min_score = settings.gdelt_ngram_min_relevance_score if min_score is None else min_score
    english_only = settings.gdelt_ngram_english_only
    known_urls = _existing_urls(db)
    ranked: list[RankedCandidate] = []
    stats: list[DiscoveryStats] = []
    used: list[str] = []

    timeout = httpx.Timeout(settings.gdelt_timeout_s, connect=15.0)
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "CausaLens-SEA/1.0"},
        ) as client:
            found = 0
            for stamp in stamps:
                if found >= limit:
                    break
                row = _get_or_create_snapshot(db, stamp)
                if row and row.status == "missing":
                    continue
                cache_path = fetcher.ranked_cache_path(stamp, topic.name)
                use_cache = (
                    not force_rescan
                    and row is not None
                    and row.status == "ok"
                    and cache_path.exists()
                ) or (not force_rescan and cache_path.exists() and fetcher.files_cached(stamp))
                if use_cache and cache_path.exists():
                    cached = _read_ranked_cache(cache_path)
                    if cached is not None:
                        cached_items, snap_stats = cached
                        kept = 0
                        for item in cached_items:
                            canonical = canonicalize_url(item.url)
                            if canonical in known_urls:
                                continue
                            ranked.append(item)
                            known_urls.add(canonical)
                            kept += 1
                        snap_stats.qualified_candidates = kept
                        snap_stats.from_cache = True
                        stats.append(snap_stats)
                        used.append(stamp)
                        found += 1
                        log.info(
                            f"[GDELT] snapshot={stamp} ngram_rows={snap_stats.ngram_rows} "
                            f"relevant_docids={snap_stats.relevant_docids} qualified_candidates={kept} "
                            f"from_cache=1",
                            extra={
                                "source": "gdelt",
                                "snapshot": stamp,
                                "qualified_candidates": kept,
                                "success": True,
                            },
                        )
                        continue
                try:
                    status = await fetcher.snapshot_available(client, stamp)
                except (httpx.TransportError, httpx.TimeoutException) as exc:
                    if row:
                        row.status = "failed"
                        row.error = type(exc).__name__
                    log.info(
                        f"[GDELT] snapshot={stamp} timeout",
                        extra={"source": "gdelt", "snapshot": stamp, "success": False},
                    )
                    continue
                if status == "missing":
                    if row:
                        row.status = "missing"
                    continue
                if status == "missing_toc":
                    if row:
                        row.status = "missing_toc"
                    continue
                if row and row.downloaded_at is None:
                    row.downloaded_at = datetime.now(timezone.utc).replace(tzinfo=None)
                try:
                    items, snap_stats = process_snapshot_files(
                        stamp,
                        fetcher.ngram_path(stamp),
                        fetcher.toc_path(stamp),
                        matcher,
                        topic,
                        min_score=min_score,
                        english_only=english_only,
                        known_urls=known_urls,
                    )
                except _GZIP_ERRORS as exc:
                    if row:
                        row.status = "corrupt"
                        row.error = type(exc).__name__
                    log.info(
                        f"[GDELT] snapshot={stamp} corrupt_gzip",
                        extra={
                            "source": "gdelt",
                            "snapshot": stamp,
                            "success": False,
                            "error": type(exc).__name__,
                        },
                    )
                    continue

                ranked.extend(items)
                stats.append(snap_stats)
                used.append(stamp)
                found += 1
                _write_ranked_cache(cache_path, items, snap_stats)
                if row:
                    row.status = "ok"
                    row.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    row.ngram_rows = snap_stats.ngram_rows
                    row.article_count = snap_stats.relevant_docids
                    row.candidate_count = snap_stats.qualified_candidates
                    row.topic = topic.name
                    row.error = None
                log.info(
                    f"[GDELT] snapshot={stamp} ngram_rows={snap_stats.ngram_rows} "
                    f"relevant_docids={snap_stats.relevant_docids} "
                    f"tech_docids={snap_stats.tech_docids} geo_docids={snap_stats.geo_docids} "
                    f"qualified_candidates={snap_stats.qualified_candidates} "
                    f"rejected_index_pages={snap_stats.rejected_index_pages} "
                    f"rejected_low_relevance={snap_stats.rejected_low_relevance}",
                    extra={
                        "source": "gdelt",
                        "snapshot": stamp,
                        "ngram_rows": snap_stats.ngram_rows,
                        "relevant_docids": snap_stats.relevant_docids,
                        "qualified_candidates": snap_stats.qualified_candidates,
                        "rejected_index_pages": snap_stats.rejected_index_pages,
                        "rejected_low_relevance": snap_stats.rejected_low_relevance,
                        "success": True,
                    },
                )
    except (httpx.TransportError, httpx.TimeoutException) as exc:
        raise GDELTUnavailable("GDELT Web NGrams is unreachable") from exc

    if db is not None:
        db.flush()

    ranked.sort(key=lambda item: item.relevance_score, reverse=True)
    candidates = [ranked_to_candidate(item) for item in ranked]
    return DiscoveryResult(
        candidates=candidates,
        ranked=ranked,
        stats=stats,
        snapshots=used,
        topic=topic.name,
    )


def serialize_ranked(items: Iterable[RankedCandidate], limit: int = 25) -> list[dict]:
    return [item.to_dict() for item in list(items)[:limit]]
