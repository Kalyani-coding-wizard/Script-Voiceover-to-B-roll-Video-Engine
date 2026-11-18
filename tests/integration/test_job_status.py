"""
Integration tests for job status retrieval and error envelopes.
"""
import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_nonexistent_job_returns_404(client: AsyncClient):
    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/v1/jobs/{fake_id}")

    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "JOB_NOT_FOUND"
    assert data["error"]["retryable"] is False
    assert data["error"]["details"]["job_id"] == str(fake_id)


@pytest.mark.asyncio
async def test_create_and_fetch_job_status(client: AsyncClient):
    payload = {"script": "Checking status endpoint behavior."}
    key = f"status-check-{uuid.uuid4().hex[:6]}"
    resp = await client.post("/api/v1/broll/jobs", json=payload, headers={"Idempotency-Key": key})
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    status_resp = await client.get(f"/api/v1/jobs/{job_id}")
    assert status_resp.status_code == 200
    s_data = status_resp.json()
    assert s_data["job_id"] == job_id
    assert s_data["status"] in ("queued", "running", "succeeded")
    assert 0 <= s_data["progress"] <= 100
