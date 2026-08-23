from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


EntityType = Literal[
    "COMPANY",
    "COUNTRY",
    "CITY",
    "PERSON",
    "INDUSTRY",
    "COMMODITY",
    "TECHNOLOGY",
    "ORGANIZATION",
]

EventType = Literal[
    "INVESTMENT",
    "FUNDING",
    "EXPANSION",
    "PRICE_CHANGE",
    "SUPPLY_DISRUPTION",
    "ACQUISITION",
    "PARTNERSHIP",
    "PRODUCTION_CHANGE",
    "EXPORT_CHANGE",
    "MARKET_MOVE",
    "TECHNOLOGY_LAUNCH",
    "CORPORATE_ACTION",
]

RelationType = Literal[
    "CAUSES",
    "CONTRIBUTES_TO",
    "TRIGGERS",
    "RESPONDS_TO",
    "AFFECTS",
]

EdgeStatus = Literal["observed", "inferred", "predicted"]
HealthStatus = Literal["HEALTHY", "DEGRADED", "FAILED", "HEALED"]
DataMode = Literal["LIVE", "CACHED", "PARTIAL"]


class Entity(BaseModel):
    id: str
    name: str
    type: str
    country: str | None = None


class ArticleCandidate(BaseModel):
    id: str
    title: str
    url: str
    source: str
    country: str
    published_at: datetime | None = None
    category: list[str] = Field(default_factory=list)
    summary: str | None = None
    image_url: str | None = None
    raw: dict | None = None


class Article(BaseModel):
    id: str
    title: str
    url: str
    source: str
    country: str
    language: str = "en"
    published_at: datetime | None = None
    author: str | None = None
    category: list[str] = Field(default_factory=list)
    summary: str | None = None
    body: str
    image_url: str | None = None
    ingested_at: datetime
    raw: dict | None = None

    @field_validator("category", mode="before")
    @classmethod
    def split_categories(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value


class Event(BaseModel):
    id: str
    title: str
    summary: str
    event_date: datetime | None = None
    countries: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    source_article_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    event_type: str = "MARKET_MOVE"

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, value: float) -> float:
        return max(0.0, min(1.0, value))


class CausalEdge(BaseModel):
    id: str
    source_event_id: str
    target_event_id: str
    relation: RelationType
    confidence: float
    evidence_score: float = 0.0
    reason: str
    supporting_article_ids: list[str] = Field(default_factory=list)
    status: EdgeStatus = "observed"
    cross_border: bool = False
    source_countries: list[str] = Field(default_factory=list)
    target_countries: list[str] = Field(default_factory=list)

    @field_validator("confidence", "evidence_score")
    @classmethod
    def clamp_scores(cls, value: float) -> float:
        return max(0.0, min(1.0, value))


class ValidationResult(BaseModel):
    healthy: bool
    failures: list[str] = Field(default_factory=list)


class PipelineSourceStatus(BaseModel):
    source: str
    display_name: str
    country: str
    discovery_status: str
    article_status: str
    last_success: datetime | None = None
    last_failure: datetime | None = None
    articles_discovered: int = 0
    articles_extracted: int = 0
    validation_failures: int = 0
    collector_id: str
    article_collector_id: str
    health: HealthStatus = "HEALTHY"


class PipelineLogEvent(BaseModel):
    id: str
    source: str
    collector_id: str | None = None
    kind: str
    message: str
    created_at: datetime


class GraphPayload(BaseModel):
    analysis_id: str
    query: str
    data_mode: DataMode
    cached_from: datetime | None = None
    generated_at: datetime
    degraded_reasons: list[str] = Field(default_factory=list)
    stats: dict[str, int] = Field(default_factory=dict)
    events: list[Event]
    edges: list[CausalEdge]
    articles: list[Article]


class AnalyzeRequest(BaseModel):
    query: str = Field(min_length=3, max_length=240)


class HealingEventRequest(BaseModel):
    source: str
    collector_id: str
    message: str

    @model_validator(mode="after")
    def normalize_source(self) -> "HealingEventRequest":
        self.source = self.source.strip().lower()
        return self


class RefreshResponse(BaseModel):
    sources: int
    articles_discovered: int
    articles_extracted: int
    articles_valid: int
    data_mode: DataMode = "LIVE"
    degraded_reasons: list[str] = Field(default_factory=list)
