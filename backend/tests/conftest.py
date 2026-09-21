"""Shared test configuration.

Tests never need live credentials. By default they run against a throwaway
SQLite file; set DRISHTI_TEST_DATABASE_URL to a PostgreSQL URL to exercise the
identical suite against the primary database, for example:

    DRISHTI_TEST_DATABASE_URL=postgresql+psycopg://drishti@127.0.0.1:5432/drishti_test pytest tests -q
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

TEST_DATABASE_URL = os.environ.get("DRISHTI_TEST_DATABASE_URL", "sqlite:///./test_drishti.db")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("SEED_DEMO_DATA", "false")
os.environ.setdefault("INGESTION_ENABLED", "false")
# Telegram/X credentials stay empty: no test may ever reach a live platform.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "")
os.environ.setdefault("X_BEARER_TOKEN", "")
os.environ.setdefault("LIVE_CONNECTOR_TEST", "false")


@pytest.fixture(scope="session")
def database_url() -> str:
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def migrated_database(database_url: str):
    """Fresh schema created through the real Alembic migration path."""
    from app.database import Base, engine, run_migrations

    if database_url.startswith("sqlite"):
        path = Path(database_url.split("///")[-1])
        if path.exists():
            path.unlink()
    else:
        Base.metadata.drop_all(bind=engine)
        with engine.begin() as conn:
            conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    revision = run_migrations()
    yield revision


@pytest.fixture()
def db(migrated_database):
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
