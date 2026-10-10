from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from sovereign_workbench.config import get_settings
from sovereign_workbench.db.base import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        settings.ensure_dirs()
        connect_args = {"check_same_thread": False}
        _engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
        if settings.database_url.startswith("sqlite"):
            event.listen(_engine, "connect", _enable_sqlite_features)
    return _engine


def _enable_sqlite_features(dbapi_connection: object, _: object) -> None:
    """Enable SQLite behaviour required by the cascade relationships and concurrency."""
    connection = dbapi_connection
    cursor = connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def _get_sessionmaker() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine(), autoflush=False, expire_on_commit=False)
    return _SessionLocal


def init_db() -> None:
    from sovereign_workbench.db import models  # noqa: F401  (register tables)

    engine = _get_engine()
    Base.metadata.create_all(bind=engine)
    _migrate_tasks(engine)


def _migrate_tasks(engine: Engine) -> None:
    """Apply the small additive migration needed by databases created by 0.1.0."""
    columns = {column["name"] for column in inspect(engine).get_columns("tasks")}
    if "attachments" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE tasks ADD COLUMN attachments TEXT DEFAULT '[]'"))


@contextmanager
def session_scope() -> Iterator[Session]:
    session = _get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    session = _get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
