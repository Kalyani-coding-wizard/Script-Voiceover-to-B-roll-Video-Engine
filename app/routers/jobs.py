"""
Jobs router: POST /api/v1/broll/jobs and POST /api/v1/jobs/{job_id}/swap-clip.
"""
from __future__ import annotations

import json
import uuid
import hashlib
from typing import Any, Dict, Optional

import structlog
from arq.connections import create_pool
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.dependencies import get_app_settings, get_db
from app.models.idempotency import IdempotencyRecord
from app.models.job import Job
from app.schemas.job_request import JobRequest
from app.schemas.job_response import JobAccepted

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Jobs"])


class SwapClipRequest(BaseModel):
    """Payload to swap footage for an existing scene."""

    scene_index: int = Field(..., ge=0, description="Index of the scene to swap")
    new_query: Optional[str] = Field(None, description="New search query to find alternate clip")
    new_clip_url: Optional[str] = Field(None, description="Explicit video URL to use instead")


@router.post(
    "/broll/jobs",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a new B-roll video generation job",
)
async def create_broll_job(
    request_data: JobRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> JobAccepted:
    """
    Submits a video generation job.
    - Safe retries: Sending the same request with the same Idempotency-Key
      returns the existing job and never does duplicate work.
    - Returns HTTP 202 with job_id immediately.
    """
    clean_key = idempotency_key.strip()
    if not clean_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "MISSING_INPUT",
                    "message": "Idempotency-Key header cannot be empty.",
                    "retryable": False,
                    "details": {"header": "Idempotency-Key"},
                }
            },
        )

    # 1. Check idempotency
    existing_stmt = select(Job).where(Job.idempotency_key == clean_key)
    result = await db.execute(existing_stmt)
    existing_job = result.scalar_one_or_none()

    if existing_job is not None:
        incoming_hash = hashlib.sha256(
            json.dumps(request_data.model_dump(), sort_keys=True, default=str).encode()
        ).hexdigest()
        existing_hash = hashlib.sha256(
            json.dumps(existing_job.request_payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        if incoming_hash != existing_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "IDEMPOTENCY_CONFLICT",
                        "message": "Idempotency-Key was already used with a different payload.",
                        "retryable": False,
                        "details": {"idempotency_key": clean_key},
                    }
                },
            )
        logger.info(
            "idempotent_request_matched",
            idempotency_key=clean_key,
            job_id=str(existing_job.id),
        )
        return JobAccepted(
            job_id=existing_job.id,
            status=existing_job.status,
            message="Existing job returned for this idempotency key.",
        )

    # 2. Create new Job
    new_job_id = uuid.uuid4()
    job = Job(
        id=new_job_id,
        idempotency_key=clean_key,
        status="queued",
        progress=0,
        request_payload=request_data.model_dump(),
        result=None,
        error=None,
    )
    db.add(job)

    # Record in idempotency_records as well
    idemp_record = IdempotencyRecord(key=clean_key, job_id=new_job_id)
    db.add(idemp_record)

    await db.commit()
    await db.refresh(job)

    logger.info(
        "job_created",
        job_id=str(new_job_id),
        idempotency_key=clean_key,
    )

    # 3. Enqueue job to ARQ / Redis
    if settings.mock_mode:
        import asyncio
        from worker.tasks.pipeline import run_pipeline_direct
        asyncio.create_task(run_pipeline_direct(str(new_job_id)))
    else:
        try:
            from arq.connections import RedisSettings
            redis_settings = RedisSettings.from_dsn(settings.redis_url, conn_timeout=1.0)
            arq_pool = await asyncio.wait_for(create_pool(redis_settings), timeout=1.5)
            await arq_pool.enqueue_job("run_pipeline", str(new_job_id))
            await arq_pool.close()
        except Exception as exc:
            logger.warning(
                "redis_enqueue_failed_falling_back_to_async",
                job_id=str(new_job_id),
                error=str(exc),
            )
            import asyncio
            from worker.tasks.pipeline import run_pipeline_direct
            asyncio.create_task(run_pipeline_direct(str(new_job_id)))

    return JobAccepted(
        job_id=job.id,
        status="queued",
        message="Job accepted and queued for processing.",
    )


@router.post(
    "/jobs/{job_id}/swap-clip",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Swap a clip in an existing job (Advanced level requirement)",
)
async def swap_scene_clip(
    job_id: uuid.UUID,
    swap_req: SwapClipRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> JobAccepted:
    """
    Replaces one scene's clip and re-renders only the affected part,
    taking clearly less time than a full render.
    """
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": f"Job {job_id} not found.",
                    "retryable": False,
                    "details": {"job_id": str(job_id)},
                }
            },
        )

    # Update job state for re-render
    job.status = "queued"
    job.progress = 50  # starts at re-render stage
    await db.commit()

    import asyncio
    from worker.tasks.pipeline import run_swap_clip_direct
    asyncio.create_task(
        run_swap_clip_direct(
            str(job_id),
            swap_req.scene_index,
            swap_req.new_query,
            swap_req.new_clip_url,
        )
    )

    return JobAccepted(
        job_id=job.id,
        status="queued",
        message=f"Swap clip queued for scene index {swap_req.scene_index}.",
    )


@router.get(
    "/download/{job_id}/{filename}",
    summary="Download job output artifacts (Integration Standard 7)",
)
async def download_output_file(job_id: uuid.UUID, filename: str):
    """Serves finished video, captions, timeline.json, or manifest.json files."""
    from pathlib import Path
    from fastapi.responses import FileResponse

    # Safe sanitization
    clean_name = Path(filename).name
    from app.storage import ArtifactStorage
    file_path = Path("outputs") / str(job_id) / clean_name

    storage = ArtifactStorage()
    try:
        storage.download_file(str(job_id), clean_name, file_path)
    except (FileNotFoundError, OSError):
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": f"Requested file '{clean_name}' does not exist for job {job_id}.",
                    "retryable": False,
                    "details": {"filename": clean_name},
                }
            },
        )

    # Media type detection
    media_type = "application/octet-stream"
    if clean_name.endswith(".mp4"):
        media_type = "video/mp4"
    elif clean_name.endswith(".json"):
        media_type = "application/json"
    elif clean_name.endswith(".srt"):
        media_type = "text/plain"

    return FileResponse(path=file_path, media_type=media_type, filename=clean_name)

