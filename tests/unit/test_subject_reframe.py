from pathlib import Path

import pytest

from worker.tasks.render import VideoRenderer


@pytest.mark.asyncio
async def test_subject_detection_falls_back_to_center(tmp_path: Path):
    renderer = VideoRenderer(str(tmp_path))
    subject_x = await renderer._detect_subject_x(tmp_path / "missing.mp4")
    assert subject_x == 0.5
