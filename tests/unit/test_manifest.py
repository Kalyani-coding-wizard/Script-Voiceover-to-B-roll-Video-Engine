"""
Unit tests for manifest.json and timeline.json builder.
"""
import json
import tempfile
from pathlib import Path

from footage_providers.base import FootageClip
from worker.tasks.manifest import build_manifest_json, build_timeline_json
from worker.tasks.segment import SegmentedScene


def test_manifest_and_timeline():
    scenes = [
        SegmentedScene(0, "Introduction to financial growth", 0.0, 5.0, "modern bank office"),
        SegmentedScene(1, "Investing in high growth companies", 5.0, 10.0, "software code"),
    ]
    clips = [
        FootageClip(
            url="https://example.com/clip1.mp4",
            source="mock_stock",
            licence="CC0",
            attribution="Mock Library",
            is_ai_generated=False,
            relevance_score=0.91,
            reason="Matches finance topic",
            clip_id="c1",
        ),
        FootageClip(
            url="https://example.com/clip2.mp4",
            source="fal_ai",
            licence="Commercial-AI-Generated",
            attribution="fal.ai Fast SVD",
            is_ai_generated=True,
            relevance_score=0.88,
            reason="Generative video for abstract topic",
            clip_id="c2",
        ),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        t_path = Path(tmpdir) / "timeline.json"
        m_path = Path(tmpdir) / "manifest.json"

        timeline = build_timeline_json(scenes, clips, str(t_path))
        manifest = build_manifest_json(
            job_id="test-job-uuid",
            scenes=scenes,
            clips=clips,
            settings_payload={"aspect_ratios": ["16:9"]},
            timings_ms={"total_ms": 1500},
            output_path=str(m_path),
        )

        assert t_path.exists()
        assert m_path.exists()

        # Check timeline requirements
        assert len(timeline) == 2
        assert timeline[0]["clip"]["licence"] == "CC0"
        assert timeline[0]["clip"]["is_ai_generated"] is False
        assert timeline[1]["clip"]["is_ai_generated"] is True
        assert "independent_vlm_score" in timeline[0]["clip"]

        # Check manifest requirements
        assert manifest["job_id"] == "test-job-uuid"
        assert "production_numbers" in manifest
        assert manifest["production_numbers"]["turnaround_seconds"] == 1.5
        assert "licence_and_rights" in manifest
        assert manifest["licence_and_rights"]["commercial_use_allowed"] is True
