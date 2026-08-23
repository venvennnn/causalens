from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


class ArticleRow(Base):
    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    canonical_url: Mapped[str] = mapped_column(String, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String, index=True, nullable=False)
    country: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, default="en")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    valid: Mapped[bool] = mapped_column(Boolean, default=True)


class EventRow(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    event_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    countries: Mapped[list] = mapped_column(JSON, default=list)
    companies: Mapped[list] = mapped_column(JSON, default=list)
    industries: Mapped[list] = mapped_column(JSON, default=list)
    entities: Mapped[list] = mapped_column(JSON, default=list)
    source_article_ids: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    event_type: Mapped[str] = mapped_column(String, default="MARKET_MOVE")


class CausalEdgeRow(Base):
    __tablename__ = "causal_edges"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_event_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    target_event_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    relation: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_article_ids: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, default="observed")
    cross_border: Mapped[bool] = mapped_column(Boolean, default=False)
    source_countries: Mapped[list] = mapped_column(JSON, default=list)
    target_countries: Mapped[list] = mapped_column(JSON, default=list)


class AnalysisRow(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    query: Mapped[str] = mapped_column(String, index=True, nullable=False)
    data_mode: Mapped[str] = mapped_column(String, default="LIVE")
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cached_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    degraded_reasons: Mapped[list] = mapped_column(JSON, default=list)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    success: Mapped[bool] = mapped_column(Boolean, default=True)


class AnalysisEventRow(Base):
    __tablename__ = "analysis_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), index=True)
    event_id: Mapped[str] = mapped_column(String, index=True)


class AnalysisEdgeRow(Base):
    __tablename__ = "analysis_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), index=True)
    edge_id: Mapped[str] = mapped_column(String, index=True)


class PipelineRunRow(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String, index=True, nullable=False)
    discovery_status: Mapped[str] = mapped_column(String, default="idle")
    article_status: Mapped[str] = mapped_column(String, default="idle")
    last_success: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_failure: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    articles_discovered: Mapped[int] = mapped_column(Integer, default=0)
    articles_extracted: Mapped[int] = mapped_column(Integer, default=0)
    validation_failures: Mapped[int] = mapped_column(Integer, default=0)
    collector_id: Mapped[str] = mapped_column(String, default="")
    article_collector_id: Mapped[str] = mapped_column(String, default="")
    health: Mapped[str] = mapped_column(String, default="HEALTHY")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class PipelineEventRow(Base):
    __tablename__ = "pipeline_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String, index=True, nullable=False)
    collector_id: Mapped[str | None] = mapped_column(String, nullable=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class GdeltSnapshotRow(Base):
    """Processed GDELT Web NGrams snapshot. DOCIDs are unique only within a snapshot."""

    __tablename__ = "gdelt_snapshots"

    snapshot_timestamp: Mapped[str] = mapped_column(String, primary_key=True)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ngram_rows: Mapped[int] = mapped_column(Integer, default=0)
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic: Mapped[str | None] = mapped_column(String, nullable=True)


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
        _engine = create_engine(settings.database_url, future=True, connect_args=connect_args)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)
    return _SessionLocal


def init_db() -> None:
    Base.metadata.create_all(get_engine())


def get_db():
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
