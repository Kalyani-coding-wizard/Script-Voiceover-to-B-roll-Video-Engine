"""Optional ffprobe validation for rendered media consistency."""
from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable


async def probe_media(path: str) -> Dict[str, Any]:
    """Return ffprobe JSON, raising a useful error when media is invalid."""
    if not shutil.which("ffprobe"):
        return {}
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode:
        raise ValueError(f"ffprobe failed for {path}: {stderr.decode().strip()}")
    return json.loads(stdout.decode())


async def validate_outputs(paths: Iterable[str]) -> Dict[str, Any]:
    """Validate codec, frame rate, resolution, and audio presence across outputs."""
    reports = [await probe_media(path) for path in paths]
    reports = [report for report in reports if report]
    if len(reports) < 2:
        return {"validated": False, "reason": "ffprobe unavailable or fewer than two outputs"}

    signatures = []
    for report in reports:
        video = next((s for s in report.get("streams", []) if s.get("codec_type") == "video"), None)
        audio = next((s for s in report.get("streams", []) if s.get("codec_type") == "audio"), None)
        if not video or not audio:
            raise ValueError("Rendered output must contain both video and audio streams.")
        signatures.append({
            "codec": video.get("codec_name"),
            "fps": video.get("r_frame_rate"),
            "width": video.get("width"),
            "height": video.get("height"),
            "audio_codec": audio.get("codec_name"),
        })
    if len({json.dumps(item, sort_keys=True) for item in signatures}) != 1:
        raise ValueError("Rendered outputs are not codec/fps/resolution consistent.")
    return {"validated": True, "signature": signatures[0]}
