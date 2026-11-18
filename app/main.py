"""
FastAPI application entry point for IncuBrix Script to B-roll Video Engine.
"""
from __future__ import annotations

import logging
import sys
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import dependencies
from app.config import get_settings
from app.middleware.correlation import CorrelationIdMiddleware
from app.middleware.idempotency import IdempotencyKeyMiddleware
from app.models.job import Base
from app.routers import health, jobs, status as status_router

# ── Structured JSON Logging Setup ───────────────────────────────────────────
settings = get_settings()

logging.basicConfig(
    format="%(message)s",
    stream=sys.stdout,
    level=getattr(logging, settings.log_level, logging.INFO),
)

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger("broll_engine")


# ── Application Lifespan ────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown events."""
    logger.info("app_starting", version=settings.app_version)
    # Ensure database schema is initialized
    try:
        from app.models.job import Base, Job
        from app.models.idempotency import IdempotencyRecord
        if "sqlite" in str(dependencies.engine.url):
            sync_url = str(dependencies.engine.url).replace("+aiosqlite", "")
            from sqlalchemy import create_engine
            sync_eng = create_engine(sync_url)
            Base.metadata.create_all(sync_eng)
        else:
            async with dependencies.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        logger.info("database_tables_ready")
    except Exception as exc:
        logger.warning("database_init_skipped", reason=str(exc))
    yield
    logger.info("app_stopping")


# ── FastAPI App Instance ───────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="IncuBrix Script and Voiceover to B-roll Video Engine API.",
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Custom Middlewares ──────────────────────────────────────────────────────
# Note: IdempotencyKeyMiddleware runs inside CorrelationIdMiddleware
app.add_middleware(IdempotencyKeyMiddleware)
app.add_middleware(CorrelationIdMiddleware)


# ── Standardized JSON Error Handlers (Integration Standard 5) ───────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Format HTTPExceptions into standard JSON error envelope."""
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        content = exc.detail
    else:
        content = {
            "error": {
                "code": "HTTP_ERROR" if exc.status_code != 404 else "NOT_FOUND",
                "message": str(exc.detail),
                "retryable": exc.status_code >= 500,
                "details": {
                    "status_code": exc.status_code,
                    "path": request.url.path,
                },
            }
        }
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Format Pydantic schema validation errors into standard JSON."""
    raw_errors = exc.errors()
    clean_errors = []
    for err in raw_errors:
        clean_err = {
            "loc": [str(x) for x in err.get("loc", [])],
            "msg": str(err.get("msg", "")),
            "type": str(err.get("type", "")),
        }
        clean_errors.append(clean_err)
    error_msg = "; ".join(f"{e['loc']}: {e['msg']}" for e in clean_errors)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "INVALID_INPUT",
                "message": f"Input validation failed: {error_msg}",
                "retryable": False,
                "details": {"validation_errors": clean_errors},
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for internal server errors."""
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred processing your request.",
                "retryable": True,
                "details": {"error_type": type(exc).__name__, "error": str(exc)},
            }
        },
    )


# ── Mount Routers ───────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(jobs.router)
app.include_router(status_router.router)


@app.get("/", include_in_schema=False)
async def root_redirect():
    return {"message": "IncuBrix B-roll Engine API", "docs": "/docs", "health": "/health"}
