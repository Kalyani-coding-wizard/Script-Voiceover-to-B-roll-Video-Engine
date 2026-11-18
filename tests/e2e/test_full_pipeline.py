"""
End-to-End Test: Full pipeline from request submission to final video outputs.
Executes in MOCK_MODE with no external API keys required.
"""
import asyncio
import json
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from worker.tasks.pipeline import run_pipeline_direct


@pytest.mark.asyncio
async def test_end_to_end_pipeline(client: AsyncClient):
    payload = {
        "script": "Building financial discipline is the cornerstone of long-term independence. Start early and watch your future flourish.",
        "voice": "en-IN-female",
        "aspect_ratios": ["16:9"],
        "style": "bright, modern, real-world footage",
        "avoid": ["people's faces"],
        "captions": {"burn_in": True, "srt": True},
    }
    idempotency_key = f"e2e-test-{uuid.uuid4().hex[:8]}"

    # 1. Submit Job
    resp = await client.post(
        "/api/v1/broll/jobs",
        json=payload,
        headers={"Idempotency-Key": idempotency_key},
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    # 2. Wait for background task to complete (or poll status)
    job_data = None
    for _ in range(50):
        status_resp = await client.get(f"/api/v1/jobs/{job_id}")
        assert status_resp.status_code == 200
        job_data = status_resp.json()
        if job_data["status"] in ("succeeded", "failed"):
            break
        await asyncio.sleep(0.1)

    assert job_data is not None
    assert job_data["status"] == "succeeded"
    assert job_data["progress"] == 100
    assert job_data["result"] is not None

    res = job_data["result"]
    assert "16:9" in res["videos"]
    assert res["captions_srt"] is not None
    assert res["timeline_url"] is not None
    assert res["manifest_url"] is not None

    # 4. Check generated output files on disk
    out_dir = Path("outputs") / job_id
    assert out_dir.exists()

    timeline_file = out_dir / "timeline.json"
    manifest_file = out_dir / "manifest.json"
    srt_file = out_dir / "captions.srt"

    assert timeline_file.exists()
    assert manifest_file.exists()
    assert srt_file.exists()

    # 5. Validate timeline.json contents
    with open(timeline_file, "r") as f:
        timeline = json.load(f)

    assert len(timeline) >= 1
    used_clip_ids = set()
    for scene in timeline:
        clip = scene["clip"]
        assert "licence" in clip
        assert "attribution" in clip
        assert "is_ai_generated" in clip
        assert "relevance_score" in clip
        assert "reason" in clip
        # Ensure no repeat clips
        assert clip["clip_id"] not in used_clip_ids
        used_clip_ids.add(clip["clip_id"])

    # 6. Validate manifest.json contents
    with open(manifest_file, "r") as f:
        manifest = json.load(f)

    assert manifest["job_id"] == job_id
    assert "production_numbers" in manifest
    assert "licence_and_rights" in manifest
    assert manifest["licence_and_rights"]["commercial_use_allowed"] is True
