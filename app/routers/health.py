"""Health & readiness endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.dependencies import get_db, get_redis
from app.config import get_settings

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Liveness probe")
async def health() -> dict:
    """Returns 200 OK when the process is alive."""
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe")
async def ready(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    """
    Checks DB and Redis connectivity.
    Returns 200 when both are reachable, 503 otherwise.
    """
    checks: dict = {}
    settings = get_settings()

    # PostgreSQL
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    # Redis
    import os
    if os.getenv("MOCK_MODE", "false").lower() == "true":
        checks["redis"] = "ok"
    else:
        try:
            import asyncio
            await asyncio.wait_for(redis.ping(), timeout=1.0)
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {exc}"

    all_ok = all(v == "ok" for v in checks.values())
    checks["storage"] = "configured" if settings.artifact_backend in {"auto", "s3"} else "local"
    checks["fal"] = "configured" if settings.fal_api_key else "missing"
    checks["gemini"] = "configured" if settings.gemini_api_key else "missing"
    checks["openai"] = "configured" if settings.openai_api_key else "missing"
    checks["mock_mode"] = "enabled" if settings.mock_mode else "disabled"
    if not all_ok:
        raise HTTPException(status_code=503, detail={"status": "degraded", "checks": checks})

    return {"status": "ok", "checks": checks}
