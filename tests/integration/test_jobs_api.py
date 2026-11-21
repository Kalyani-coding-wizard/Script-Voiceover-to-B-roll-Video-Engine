"""
Integration tests for the Jobs API endpoints.
"""
import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoints(client: AsyncClient):
    # Liveness probe
    h_resp = await client.get("/health")
    assert h_resp.status_code == 200
    assert h_resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_web_ui_served(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Script to B-roll" in response.text


@pytest.mark.asyncio
async def test_create_job_text_script(client: AsyncClient):
    payload = {
        "script": "Building financial discipline is the cornerstone of long-term independence.",
        "voice": "en-IN-female",
        "aspect_ratios": ["16:9"],
        "style": "bright, modern, real-world footage",
        "avoid": ["people's faces"],
        "captions": {"burn_in": True, "srt": True},
    }
    headers = {"Idempotency-Key": f"integ-text-{uuid.uuid4().hex[:6]}"}
    resp = await client.post("/api/v1/broll/jobs", json=payload, headers=headers)

    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_create_job_scenes_list(client: AsyncClient):
    payload = {
        "scenes": [
            {"text": "Intro line", "visual_hint": "Tech office"},
            {"text": "Key feature", "visual_hint": "Mobile app"},
        ],
        "aspect_ratios": ["16:9", "9:16"],
    }
    headers = {"Idempotency-Key": f"integ-scenes-{uuid.uuid4().hex[:6]}"}
    resp = await client.post("/api/v1/broll/jobs", json=payload, headers=headers)

    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data


@pytest.mark.asyncio
async def test_invalid_input_no_script_or_audio(client: AsyncClient):
    payload = {
        "aspect_ratios": ["16:9"],
    }
    headers = {"Idempotency-Key": f"integ-invalid-{uuid.uuid4().hex[:6]}"}
    resp = await client.post("/api/v1/broll/jobs", json=payload, headers=headers)

    assert resp.status_code == 422
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_INPUT"
    assert "retryable" in data["error"]
