"""DRISHTI FastAPI application entry point.

Start locally:
    cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api import router
from .config import get_settings
from .database import SessionLocal, init_db
from .seed.seed_demo import ensure_live_test_watch, seed
from .services import auth as auth_service
from .services import scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("drishti")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db()
    if settings.seed_demo_data:
        with SessionLocal() as db:
            seed(db)
        logger.info("Demo dataset ready - Demo Mode: AI Regulation India, 01-14 Sep 2026.")
    with SessionLocal() as db:
        auth_service.bootstrap_admin(db)
    with SessionLocal() as db:
        if ensure_live_test_watch(db):
            logger.info("Telegram configured - live test watch created.")
    scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()



app = FastAPI(
    title="DRISHTI Narrative Intelligence API",
    description=(
        "Backend for DRISHTI (SIH 2026, PS 26152). Demo Mode is always available; "
        "live platform adapters activate only when credentials are configured server-side."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# OpenAPI grouping for http://localhost:8000/docs
app.openapi_tags = [
    {"name": "Auth", "description": "Local JWT authentication and roles."},
    {"name": "Watches", "description": "Watch lifecycle and provenance."},
    {"name": "Timeline", "description": "Shared-clock analytical state."},
    {"name": "Assistant", "description": "Grounded analyst assistant with citation validation."},
    {"name": "Connectors", "description": "Platform connector status, tests and ingestion."},
    {"name": "System", "description": "Health, audit log and diagnostics."},
]


@app.get("/")
def root() -> dict:
    return {"service": "DRISHTI", "version": __version__, "docs": "/docs", "api": "/api"}
