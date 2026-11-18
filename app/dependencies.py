"""FastAPI dependencies: DB session, Redis pool, settings."""
from __future__ import annotations

import os
from typing import AsyncGenerator, Optional

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, get_settings

_settings: Settings = get_settings()

# Default to SQLite if asyncpg is missing or MOCK_MODE is enabled
_db_url = _settings.database_url
if _settings.mock_mode or "sqlite" in _db_url:
    _db_url = "sqlite+aiosqlite:///./test.db"
else:
    try:
        import asyncpg  # noqa: F401
    except ImportError:
        _db_url = "sqlite+aiosqlite:///./test.db"

_engine_kwargs: dict = {"echo": _settings.debug}
if not _db_url.startswith("sqlite"):
    _engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
    })

engine = create_async_engine(_db_url, **_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

_redis_pool: Optional[aioredis.Redis] = None


def get_redis_client(s: Settings) -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            s.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_pool


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async SQLAlchemy session, rolling back on exception."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_redis() -> aioredis.Redis:
    """Return the shared async Redis client."""
    return get_redis_client(get_settings())


def get_app_settings() -> Settings:
    return get_settings()
