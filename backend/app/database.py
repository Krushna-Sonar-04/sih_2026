"""SQLAlchemy engine/session management.

PostgreSQL is the PRIMARY database (see docker-compose.yml). When DATABASE_URL
points at PostgreSQL and the server is unreachable, the application fails
clearly — it never silently falls back to SQLite. SQLite remains an explicit
development fallback only, chosen by setting DATABASE_URL to a sqlite:// URL.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

logger = logging.getLogger("drishti.database")

settings = get_settings()

IS_SQLITE = settings.database_url.startswith("sqlite")
IS_POSTGRES = settings.database_url.startswith(("postgresql", "postgres://"))

connect_args = {"check_same_thread": False} if IS_SQLITE else {"connect_timeout": 10}
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def safe_url() -> str:
    """Connection description with the password removed — safe to log or display."""
    try:
        return engine.url.render_as_string(hide_password=True)
    except Exception:  # pragma: no cover - defensive
        return engine.dialect.name


def require_connection() -> None:
    """Fail loudly when the configured database cannot be reached.

    PostgreSQL is the intended target; an unreachable PostgreSQL is a
    configuration error, not a reason to quietly use another database.
    """
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception as exc:
        raise RuntimeError(
            f"Database unreachable at {safe_url()}. "
            "Start PostgreSQL (docker compose up -d db) or set DATABASE_URL to an explicit "
            f"sqlite:// development fallback. Original error: {str(exc)[:200]}"
        ) from exc


def run_migrations() -> str:
    """Bring the schema to head using Alembic (the versioned migration path)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")
    return current_revision()


def current_revision() -> str:
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).first()
            return str(row[0]) if row else "none"
    except Exception:
        return "none"


def init_db() -> None:
    """Startup schema management: migrations only, never a blind create_all."""
    from . import models  # noqa: F401  (register mappings)

    require_connection()
    revision = run_migrations()
    logger.info("Schema at migration revision %s (%s).", revision, safe_url())


def database_status() -> dict:
    """Real connectivity probe: latency, server version, dialect. No credentials."""
    started = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
            version = ""
            if IS_POSTGRES:
                row = conn.execute(text("SHOW server_version")).first()
                version = f"PostgreSQL {row[0]}" if row else "PostgreSQL"
            else:
                version = f"SQLite (development fallback) {engine.dialect.server_version_info or ''}".strip()
        latency = round((time.perf_counter() - started) * 1000, 1)
        return {
            "status": "Connected",
            "detail": f"{version} · {latency} ms · revision {current_revision()}",
            "latency_ms": latency,
            "version": version,
            "dialect": engine.dialect.name,
        }
    except Exception as exc:
        return {
            "status": "Unavailable",
            "detail": f"Database unreachable ({engine.dialect.name}): {str(exc)[:180]}",
            "latency_ms": None,
            "version": "",
            "dialect": engine.dialect.name,
        }
