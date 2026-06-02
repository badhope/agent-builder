"""Database access layer.

Provides:
* ``Base`` — declarative base for ORM models.
* ``async_engine`` and ``sync_engine`` — engines (sync used for Alembic only).
* ``async_session_factory`` — async session factory.
* ``get_db`` / ``db_session`` — FastAPI dependencies that yield a session
  inside a transaction with proper rollback semantics.
* ``healthcheck`` — async ping used by /healthz and readiness probes.

Engines are lazily initialised and rebuilt on settings change (cache busted
in tests via ``reset_engine_cache()``).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from app.settings import get_settings
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass


class Base(DeclarativeBase, MappedAsDataclass, kw_only=True):
    """Declarative base class for all ORM models.

    Subclassing :class:`MappedAsDataclass` with ``kw_only=True`` lets
    columns declare defaults (e.g. ``default=uuid.uuid4``,
    ``default=dict``) anywhere in the class body without tripping
    Python's "non-default argument follows default argument" dataclass
    check. All model construction must use keyword arguments.
    """

    __mapper_args__ = {"eager_defaults": True}


# ---- Engine factories -------------------------------------------------------

_async_engine: AsyncEngine | None = None
_async_sessionmaker: async_sessionmaker[AsyncSession] | None = None
_engine_lock = asyncio.Lock()


def _build_async_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.db.url,
        pool_size=settings.db.pool_size,
        max_overflow=settings.db.max_overflow,
        pool_recycle=settings.db.pool_recycle_s,
        pool_pre_ping=True,
        echo=settings.db.echo,
        future=True,
    )


def get_engine() -> AsyncEngine:
    """Get (or build) the global async engine."""
    global _async_engine
    if _async_engine is None:
        _async_engine = _build_async_engine()
    return _async_engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Get (or build) the global async session factory."""
    global _async_sessionmaker
    if _async_sessionmaker is None:
        _async_sessionmaker = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _async_sessionmaker


async def dispose_engine() -> None:
    """Dispose the global engine (call on shutdown)."""
    global _async_engine, _async_sessionmaker
    if _async_engine is not None:
        await _async_engine.dispose()
    _async_engine = None
    _async_sessionmaker = None


def reset_engine_cache() -> None:
    """Force the engine to be rebuilt on next access (used in tests)."""
    global _async_engine, _async_sessionmaker
    _async_engine = None
    _async_sessionmaker = None


# ---- Session context managers / dependencies -------------------------------


@asynccontextmanager
async def db_session() -> AsyncIterator[AsyncSession]:
    """Yield a session inside a transaction.

    Commits on clean exit, rolls back on exception, always closes.
    """
    sm = get_sessionmaker()
    session = sm()
    try:
        async with session.begin():
            yield session
    except SQLAlchemyError:
        # session.begin() already rolled back, just re-raise
        raise
    finally:
        await session.close()


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a transactional session."""
    async with db_session() as session:
        yield session


# ---- Healthcheck ------------------------------------------------------------


async def healthcheck() -> dict[str, Any]:
    """Probe the database and return status info."""
    from sqlalchemy import text

    engine = get_engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


__all__ = [
    "Base",
    "db_session",
    "dispose_engine",
    "get_db",
    "get_engine",
    "get_sessionmaker",
    "healthcheck",
    "reset_engine_cache",
]
