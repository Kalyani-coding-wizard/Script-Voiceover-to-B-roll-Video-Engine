"""
Microsoft Edge TTS provider (free, no API key required).
Uses the edge-tts library.
"""
import asyncio
import os
import tempfile
from typing import Optional

try:
    import edge_tts
except ImportError:
    edge_tts = None

from tts_providers.base import TTSProvider, TTSResult

# Mapping from generic voice specs to Edge TTS voice names
VOICE_MAP = {
    # English
    "en-IN-female": "en-IN-NeerjaNeural",
    "en-IN-male": "en-IN-PrabhatNeural",
    "en-US-female": "en-US-JennyNeural",
    "en-US-male": "en-US-GuyNeural",
    "en-GB-female": "en-GB-SoniaNeural",
    "en-GB-male": "en-GB-RyanNeural",
    "en-AU-female": "en-AU-NatashaNeural",
    "en-AU-male": "en-AU-WilliamNeural",
    # Hindi (Multilingual Support - Outstanding Level)
    "hi-IN-female": "hi-IN-SwaraNeural",
    "hi-IN-male": "hi-IN-MadhurNeural",
    "hi-female": "hi-IN-SwaraNeural",
    "hi-male": "hi-IN-MadhurNeural",
    # Tamil (Multilingual Support - Outstanding Level)
    "ta-IN-female": "ta-IN-PallaviNeural",
    "ta-IN-male": "ta-IN-ValluvarNeural",
    "ta-female": "ta-IN-PallaviNeural",
    "ta-male": "ta-IN-ValluvarNeural",
}

DEFAULT_VOICE = "en-US-JennyNeural"


class EdgeTTSProvider(TTSProvider):
    """Microsoft Edge TTS (free, neural voices)."""

    @property
    def name(self) -> str:
        return "edge-tts"

    def _resolve_voice(self, voice: str) -> str:
        """Map generic voice spec → Edge TTS voice name."""
        if voice in VOICE_MAP:
            return VOICE_MAP[voice]
        # Accept raw Edge TTS names directly
        if "Neural" in voice or voice.startswith("en-"):
            return VOICE_MAP.get(voice, DEFAULT_VOICE)
        return DEFAULT_VOICE

    async def synthesize(
        self,
        text: str,
        voice: str,
        output_path: str,
    ) -> TTSResult:
        edge_voice = self._resolve_voice(voice)
        communicate = edge_tts.Communicate(text, edge_voice)
        await communicate.save(output_path)

        # Measure duration via ffprobe
        duration = await self._get_duration(output_path)
        return TTSResult(
            audio_path=output_path,
            duration_seconds=duration,
            provider=self.name,
        )

    @staticmethod
    async def _get_duration(path: str) -> float:
        """Use ffprobe to get audio duration."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            import json
            data = json.loads(stdout)
            return float(data["format"]["duration"])
        except Exception:
            return 5.0  # fallback estimate
