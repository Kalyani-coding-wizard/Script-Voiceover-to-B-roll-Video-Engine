"""Root conftest.py – shared fixtures for all test layers.

Sets MOCK_MODE=true and uses an in-memory SQLite database so no
real infrastructure (Postgres, Redis, MinIO) is required during tests.
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import AsyncGenerator

# Ensure Windows finds DLLs if using embedded/QGIS Python
if sys.platform == "win32":
    qgis_bin = r"C:\Program Files\QGIS 3.40.1\bin"
    if os.path.exists(qgis_bin) and hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(qgis_bin)
        except Exception:
            pass

# Force test environment BEFORE any app code is imported
os.environ["MOCK_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["S3_ENDPOINT"] = "http://localhost:9000"
os.environ["HMAC_SECRET"] = "test-secret"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_URL = "sqlite+aiosqlite:///./test.db"
SYNC_DB_URL = "sqlite:///./test.db"

# Sync table creation once at startup so no async loop issues occur
from app.models.job import Base, Job
from app.models.idempotency import IdempotencyRecord

sync_engine = create_engine(SYNC_DB_URL, echo=False)
Base.metadata.create_all(sync_engine)

_engine = create_async_engine(TEST_DB_URL, echo=False)
_session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)

import app.dependencies as deps
deps.engine = _engine
deps.AsyncSessionLocal = _session_factory


@pytest.fixture
def app():
    """Return the FastAPI application instance with DB dependency override."""
    from app.main import app as _app

    async def _test_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with _session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    _app.dependency_overrides[deps.get_db] = _test_get_db
    return _app


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client wired directly to the ASGI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """DB session fixture for direct DB tests."""
    async with _session_factory() as session:
        yield session
        await session.rollback()
