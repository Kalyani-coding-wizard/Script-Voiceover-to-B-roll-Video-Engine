"""
Unit tests for captions generation and SRT formatting.
"""
import tempfile
from pathlib import Path

from worker.tasks.caption import format_srt_timestamp, generate_srt


def test_format_srt_timestamp():
    assert format_srt_timestamp(0.0) == "00:00:00,000"
    assert format_srt_timestamp(3.5) == "00:00:03,500"
    assert format_srt_timestamp(65.123) == "00:01:05,123"
    assert format_srt_timestamp(3661.05) == "01:01:01,050"


def test_generate_srt_from_segments():
    segments = [
        {"start": 0.0, "end": 2.5, "text": "Building financial discipline."},
        {"start": 2.5, "end": 5.0, "text": "Start early and invest wisely."},
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        srt_path = Path(tmpdir) / "captions.srt"
        generate_srt(segments, str(srt_path))

        assert srt_path.exists()
        content = srt_path.read_text(encoding="utf-8")

        assert "1\n00:00:00,000 --> 00:00:02,500\nBuilding financial discipline." in content
        assert "2\n00:00:02,500 --> 00:00:05,000\nStart early and invest wisely." in content
