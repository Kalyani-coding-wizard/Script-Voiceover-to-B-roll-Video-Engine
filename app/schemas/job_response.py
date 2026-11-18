"""Pydantic schemas for job responses."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class JobAccepted(BaseModel):
    """Returned immediately after POST /api/v1/broll/jobs (HTTP 202)."""

    job_id: UUID
    status: str = "queued"
    message: str = "Job accepted and queued for processing."


class ResultLinks(BaseModel):
    videos: Optional[Dict[str, str]] = Field(
        None, description="Aspect-ratio → presigned video URL."
    )
    captions_srt: Optional[str] = None
    timeline_url: Optional[str] = None
    manifest_url: Optional[str] = None


class ErrorDetail(BaseModel):
    code: str = Field(..., description="UPPER_SNAKE_CASE error code.")
    message: str
    retryable: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Standard error envelope used for all 4xx / 5xx responses."""

    error: ErrorDetail


class JobResponse(BaseModel):
    """Returned by GET /api/v1/jobs/{job_id}."""

    job_id: UUID
    status: str = Field(..., description="queued | running | succeeded | failed")
    progress: int = Field(0, ge=0, le=100)
    created_at: datetime
    updated_at: datetime
    result: Optional[ResultLinks] = None
    error: Optional[ErrorDetail] = None
