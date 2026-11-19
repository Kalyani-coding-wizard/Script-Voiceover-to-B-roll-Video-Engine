"""OpenAI text-to-speech provider."""

from __future__ import annotations

import asyncio
import os
from typing import Optional

import aiohttp

from tts_providers.base import TTSProvider, TTSResult


class OpenAITTSProvider(TTSProvider):
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = os.getenv("OPENAI_TTS_MODEL", "tts-1")

    @property
    def name(self) -> str:
        return "openai"

    async def synthesize(
        self,
        text: str,
        voice: str,
        output_path: str,
    ) -> TTSResult:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        openai_voice = voice if voice in {
            "alloy", "echo", "fable", "onyx", "nova", "shimmer",
        } else "nova"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "voice": openai_voice,
                    "input": text,
                    "response_format": "mp3",
                },
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                response.raise_for_status()
                with open(output_path, "wb") as output:
                    output.write(await response.read())

        duration = await self._get_duration(output_path)
        return TTSResult(
            audio_path=output_path,
            duration_seconds=duration,
            provider=self.name,
        )

    @staticmethod
    async def _get_duration(path: str) -> float:
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            import json
            return float(json.loads(stdout)["format"]["duration"])
        except Exception:
            return 5.0
