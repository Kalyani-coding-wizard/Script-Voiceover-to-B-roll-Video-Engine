"""
Unit tests for idempotency key handling and deduplication.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_missing_idempotency_key_returns_400(client: AsyncClient):
    payload = {"script": "Testing missing idempotency header."}
    resp = await client.post("/api/v1/broll/jobs", json=payload)
    assert resp.status_code == 400
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "MISSING_INPUT"


@pytest.mark.asyncio
async def test_idempotent_submissions_return_same_job(client: AsyncClient):
    payload = {"script": "Testing safe duplicate submissions."}
    key = "test-idemp-key-12345"
    headers = {"Idempotency-Key": key}

    # First submission
    resp1 = await client.post("/api/v1/broll/jobs", json=payload, headers=headers)
    assert resp1.status_code == 202
    job_id1 = resp1.json()["job_id"]

    # Second submission with identical key
    resp2 = await client.post("/api/v1/broll/jobs", json=payload, headers=headers)
    assert resp2.status_code == 202
    job_id2 = resp2.json()["job_id"]

    # Must return exact same job_id
    assert job_id1 == job_id2
