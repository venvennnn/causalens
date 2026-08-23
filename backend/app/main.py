from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import get_settings
from app.exceptions import CausaLensError
from app.logging import log
from app.models.db import get_session_factory, init_db
from app.services.analysis import seed_demo_if_needed
from app.services.pipeline import ensure_default_pipeline_rows

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    db = get_session_factory()()
    try:
        ensure_default_pipeline_rows(db)
        seed_demo_if_needed(db)
        db.commit()
        log.info("startup_ok", extra={"source": "api", "success": True})
    except Exception as exc:
        db.rollback()
        log.info("startup_seed_failed", extra={"source": "api", "success": False, "error": type(exc).__name__})
        raise
    finally:
        db.close()
    yield


app = FastAPI(
    title="CausaLens SEA",
    description="Live causal intelligence for Southeast Asian markets",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.exception_handler(CausaLensError)
async def causalens_error_handler(_: Request, exc: CausaLensError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())
