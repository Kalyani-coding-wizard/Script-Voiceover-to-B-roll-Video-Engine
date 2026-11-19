"""Validation for remote audio inputs."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse


SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a"}


def validate_audio_url(url: str) -> None:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix and suffix not in SUPPORTED_AUDIO_EXTENSIONS:
        raise ValueError("UNSUPPORTED_FORMAT: audio_url must point to mp3, wav, or m4a.")
