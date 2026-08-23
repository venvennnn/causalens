from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.exceptions import CausaLensError
from app.models.db import get_db
from app.models.schemas import AnalyzeRequest, HealingEventRequest, RefreshResponse
from app.services.analysis import (
    fallback_analysis_for_query,
    graph_view,
    load_analysis,
    run_analysis,
    to_public_payload,
)
from app.services.ingest import ingest_all_sources
from app.services.pipeline import list_pipeline_events, list_pipeline_status, record_healing_event
from app.sources.registry import SOURCE_REGISTRY

router = APIRouter()


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "causalens-sea",
        "brightdata_transport": settings.effective_brightdata_transport,
        "sources": list(SOURCE_REGISTRY),
    }


@router.post("/ingest/refresh", response_model=RefreshResponse)
async def refresh_ingest(db: Session = Depends(get_db)) -> RefreshResponse:
    settings = get_settings()
    try:
        result = await ingest_all_sources(db)
        db.commit()
        data_mode = "LIVE"
        reasons: list[str] = []
        if result["articles_valid"] == 0:
            data_mode = "CACHED"
            reasons.append("No live articles validated; UI should keep cached corpus.")
        elif any(item.get("health") == "FAILED" for item in result["results"]):
            data_mode = "PARTIAL"
            reasons.append("One or more Bright Data sources failed during refresh.")
        return RefreshResponse(
            sources=result["sources"],
            articles_discovered=result["articles_discovered"],
            articles_extracted=result["articles_extracted"],
            articles_valid=result["articles_valid"],
            data_mode=data_mode,  # type: ignore[arg-type]
            degraded_reasons=reasons,
        )
    except CausaLensError as exc:
        if settings.use_cached_demo_on_failure:
            return RefreshResponse(
                sources=len(SOURCE_REGISTRY),
                articles_discovered=0,
                articles_extracted=0,
                articles_valid=0,
                data_mode="CACHED",
                degraded_reasons=[exc.message],
            )
        raise HTTPException(status_code=exc.status_code, detail=exc.to_dict()) from exc


@router.post("/analyze")
async def analyze(body: AnalyzeRequest, db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    try:
        payload = await run_analysis(db, body.query.strip())
        return to_public_payload(payload)
    except CausaLensError as exc:
        if settings.use_cached_demo_on_failure:
            payload = fallback_analysis_for_query(db, body.query.strip())
            db.commit()
            data = to_public_payload(payload)
            data["degraded_reasons"] = list(dict.fromkeys([*payload.degraded_reasons, exc.message]))
            return data
        raise HTTPException(status_code=exc.status_code, detail=exc.to_dict()) from exc


@router.get("/analysis/{analysis_id}")
def get_analysis(analysis_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return to_public_payload(load_analysis(db, analysis_id))
    except CausaLensError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_dict()) from exc


@router.get("/events/{event_id}/why")
def why(event_id: str, analysis_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return graph_view(db, analysis_id, event_id, "why")
    except CausaLensError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_dict()) from exc


@router.get("/events/{event_id}/next")
def what_next(event_id: str, analysis_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return graph_view(db, analysis_id, event_id, "next")
    except CausaLensError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_dict()) from exc


@router.get("/events/{event_id}/ripple")
def ripple(event_id: str, analysis_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return graph_view(db, analysis_id, event_id, "ripple")
    except CausaLensError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_dict()) from exc


@router.get("/pipeline/status")
def pipeline_status(db: Session = Depends(get_db)) -> dict:
    sources = [item.model_dump(mode="json") for item in list_pipeline_status(db)]
    gdelt = {
        "source": "gdelt",
        "display_name": "GDELT",
        "health": "HEALTHY",
        "discovery_status": "live",
    }
    return {"sources": sources, "gdelt": gdelt}


@router.get("/pipeline/events")
def pipeline_events(db: Session = Depends(get_db)) -> dict:
    return {"events": [item.model_dump(mode="json") for item in list_pipeline_events(db)]}


@router.post("/pipeline/healing-event")
def healing_event(body: HealingEventRequest, db: Session = Depends(get_db)) -> dict:
    event = record_healing_event(db, body.source, body.collector_id, body.message)
    db.commit()
    return event.model_dump(mode="json")
