"""SQLAlchemy engine, session factory and the declarative Base."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def _create_engine(url: str) -> Engine:
    is_sqlite = url.startswith("sqlite")
    # FastAPI may use the session from a worker thread, so SQLite's
    # same-thread check has to be disabled.
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    new_engine = create_engine(url, connect_args=connect_args)

    if is_sqlite:
        @event.listens_for(new_engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record) -> None:
            # SQLite ignores FOREIGN KEY constraints unless this is enabled
            # for every new connection.
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return new_engine


engine = _create_engine(get_settings().database_url)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables that do not exist yet."""
    import app.models  # noqa: F401  - registers the models on Base.metadata

    Base.metadata.create_all(bind=engine)


def close_db() -> None:
    """Close every pooled connection (called on shutdown and after tests).

    Without this, idle SQLite connections are only closed by the garbage
    collector, which Python 3.13+ reports as a ResourceWarning.
    """
    engine.dispose()
