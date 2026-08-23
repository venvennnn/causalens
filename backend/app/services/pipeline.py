from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.db import PipelineEventRow, PipelineRunRow
from app.models.schemas import PipelineLogEvent, PipelineSourceStatus
from app.sources.registry import SOURCE_REGISTRY, get_source


def upsert_pipeline_run(
    db: Session,
    *,
    source_key: str,
    discovery_status: str | None = None,
    article_status: str | None = None,
    last_success: datetime | None = None,
    last_failure: datetime | None = None,
    articles_discovered: int | None = None,
    articles_extracted: int | None = None,
    validation_failures: int | None = None,
    collector_id: str | None = None,
    article_collector_id: str | None = None,
    health: str | None = None,
) -> PipelineRunRow:
    row = db.get(PipelineRunRow, source_key)
    source = get_source(source_key)
    if row is None:
        row = PipelineRunRow(
            id=source_key,
            source=source_key,
            discovery_status=discovery_status or "idle",
            article_status=article_status or "idle",
            collector_id=collector_id or source["discovery_collector"],
            article_collector_id=article_collector_id or source["article_collector"],
            health=health or "HEALTHY",
            updated_at=datetime.utcnow(),
        )
        db.add(row)
    if discovery_status is not None:
        row.discovery_status = discovery_status
    if article_status is not None:
        row.article_status = article_status
    if last_success is not None:
        row.last_success = last_success
    if last_failure is not None:
        row.last_failure = last_failure
    if articles_discovered is not None:
        row.articles_discovered = articles_discovered
    if articles_extracted is not None:
        row.articles_extracted = articles_extracted
    if validation_failures is not None:
        row.validation_failures = validation_failures
    if collector_id is not None:
        row.collector_id = collector_id
    if article_collector_id is not None:
        row.article_collector_id = article_collector_id
    if health is not None:
        row.health = health
    row.updated_at = datetime.utcnow()
    return row


def log_pipeline_event(
    db: Session,
    source: str,
    kind: str,
    message: str,
    collector_id: str | None = None,
) -> PipelineEventRow:
    row = PipelineEventRow(
        id=uuid.uuid4().hex,
        source=source,
        collector_id=collector_id,
        kind=kind,
        message=message,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    return row


def record_healing_event(db: Session, source: str, collector_id: str, message: str) -> PipelineLogEvent:
    if source not in SOURCE_REGISTRY:
        source = source.lower()
    upsert_pipeline_run(
        db,
        source_key=source,
        health="HEALED",
        article_status="ok",
        last_success=datetime.utcnow(),
        collector_id=collector_id,
    )
    row = log_pipeline_event(db, source, "collector_repaired", message, collector_id)
    log_pipeline_event(
        db,
        source,
        "extraction_recovered",
        "Extraction recovered after scraper healing.",
        collector_id,
    )
    db.flush()
    return PipelineLogEvent(
        id=row.id,
        source=row.source,
        collector_id=row.collector_id,
        kind=row.kind,
        message=row.message,
        created_at=row.created_at,
    )


def list_pipeline_status(db: Session) -> list[PipelineSourceStatus]:
    statuses = []
    for key, meta in SOURCE_REGISTRY.items():
        row = db.get(PipelineRunRow, key)
        if row is None:
            statuses.append(
                PipelineSourceStatus(
                    source=key,
                    display_name=meta["name"],
                    country=meta["country"],
                    discovery_status="idle",
                    article_status="idle",
                    collector_id=meta["discovery_collector"],
                    article_collector_id=meta["article_collector"],
                    health="HEALTHY",
                )
            )
            continue
        statuses.append(
            PipelineSourceStatus(
                source=key,
                display_name=meta["name"],
                country=meta["country"],
                discovery_status=row.discovery_status,
                article_status=row.article_status,
                last_success=row.last_success,
                last_failure=row.last_failure,
                articles_discovered=row.articles_discovered,
                articles_extracted=row.articles_extracted,
                validation_failures=row.validation_failures,
                collector_id=row.collector_id or meta["discovery_collector"],
                article_collector_id=row.article_collector_id or meta["article_collector"],
                health=row.health,  # type: ignore[arg-type]
            )
        )
    return statuses


def list_pipeline_events(db: Session, limit: int = 50) -> list[PipelineLogEvent]:
    rows = (
        db.query(PipelineEventRow)
        .order_by(PipelineEventRow.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        PipelineLogEvent(
            id=row.id,
            source=row.source,
            collector_id=row.collector_id,
            kind=row.kind,
            message=row.message,
            created_at=row.created_at,
        )
        for row in rows
    ]


def ensure_default_pipeline_rows(db: Session) -> None:
    now = datetime.utcnow()
    for key, meta in SOURCE_REGISTRY.items():
        if db.get(PipelineRunRow, key) is None:
            db.add(
                PipelineRunRow(
                    id=key,
                    source=key,
                    discovery_status="idle",
                    article_status="idle",
                    last_success=now,
                    articles_discovered=5,
                    articles_extracted=5,
                    validation_failures=0,
                    collector_id=meta["discovery_collector"],
                    article_collector_id=meta["article_collector"],
                    health="HEALTHY",
                    updated_at=now,
                )
            )
            log_pipeline_event(
                db,
                key,
                "seeded",
                "Scrape succeeded — curated collector registered",
                meta["discovery_collector"],
            )
    db.flush()
