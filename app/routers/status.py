"""Job status router: GET /api/v1/jobs/{job_id}."""
from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.job import Job
from app.schemas.job_response import ErrorDetail, JobResponse, ResultLinks

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Jobs"])


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
    summary="Get job status",
)
async def get_job_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Return current status, progress, result links, and any error for a job."""
    job: Job | None = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": f"No job with id '{job_id}' was found.",
                    "retryable": False,
                    "details": {"job_id": str(job_id)},
                }
            },
        )

    logger.info("job_status_fetched", job_id=str(job_id), status=job.status)

    result: ResultLinks | None = None
    if job.result:
        result = ResultLinks(**job.result)

    error: ErrorDetail | None = None
    if job.error:
        error = ErrorDetail(**job.error)

    return JobResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        created_at=job.created_at,
        updated_at=job.updated_at,
        result=result,
        error=error,
    )
