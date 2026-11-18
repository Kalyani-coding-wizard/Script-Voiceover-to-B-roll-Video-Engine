"""
Mock TTS provider — returns a 5-second silent MP3.
Useful for testing without any external service.
"""
import asyncio
import os
import struct

from tts_providers.base import TTSProvider, TTSResult

# Minimal valid silent MP3 frame (128kbps, 44100 Hz, stereo, ~26ms)
_SILENT_MP3_FRAME = bytes([
    0xFF, 0xFB, 0x90, 0x00,  # MPEG1 Layer3 header 128kbps 44100Hz stereo
]) + bytes(413)              # payload zeros


def _write_silent_mp3(path: str, duration_seconds: float = 5.0) -> None:
    """Write a silent MP3 of approximately `duration_seconds` length."""
    # Each frame ≈ 26 ms at 128kbps/44100Hz
    num_frames = int(duration_seconds / 0.026) + 1
    with open(path, "wb") as f:
        for _ in range(num_frames):
            f.write(_SILENT_MP3_FRAME)


class MockTTSProvider(TTSProvider):
    """Mock TTS — produces a 5-second silent MP3, no external calls."""

    DURATION = 5.0

    @property
    def name(self) -> str:
        return "mock"

    async def synthesize(
        self,
        text: str,
        voice: str,
        output_path: str,
    ) -> TTSResult:
        await asyncio.to_thread(_write_silent_mp3, output_path, self.DURATION)
        return TTSResult(
            audio_path=output_path,
            duration_seconds=self.DURATION,
            provider=self.name,
        )
