"""
Unit tests for Pydantic request & response schemas.
"""
import pytest
from pydantic import ValidationError

from app.schemas.job_request import JobRequest, Scene
from app.schemas.job_response import ErrorDetail, ErrorResponse, JobAccepted, JobResponse


def test_requires_exactly_one_input():
    # 0 inputs -> invalid
    with pytest.raises(ValidationError):
        JobRequest()

    # Multiple inputs -> invalid
    with pytest.raises(ValidationError):
        JobRequest(
            audio_url="https://example.com/audio.mp3",
            script="Some script text",
        )

    # Exactly script -> valid
    req1 = JobRequest(script="Building financial discipline.")
    assert req1.script == "Building financial discipline."
    assert req1.audio_url is None
    assert req1.scenes is None

    # Exactly audio_url -> valid
    req2 = JobRequest(audio_url="https://example.com/speech.mp3")
    assert req2.audio_url == "https://example.com/speech.mp3"

    # Exactly scenes -> valid
    req3 = JobRequest(scenes=[Scene(text="Scene 1", visual_hint="Office workspace")])
    assert len(req3.scenes) == 1


def test_default_values():
    req = JobRequest(script="Hello world")
    assert req.voice == "en-IN-female"
    assert req.aspect_ratios == ["9:16"]
    assert req.captions.burn_in is True
    assert req.captions.srt is True
    assert req.avoid == []


def test_error_response_schema():
    err = ErrorDetail(
        code="INVALID_INPUT",
        message="Missing parameter",
        retryable=False,
        details={"field": "script"},
    )
    envelope = ErrorResponse(error=err)
    assert envelope.error.code == "INVALID_INPUT"
    assert envelope.error.retryable is False
