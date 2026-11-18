"""
Kokoro TTS Provider — Local MIT-licensed TTS model.
Provides offline text-to-speech with no API costs.
Requires the kokoro-tts package to be installed.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import structlog

from tts_providers.base import TTSProvider

logger = structlog.get_logger(__name__)


class KokoroTTSProvider(TTSProvider):
    """
    Kokoro TTS (MIT License): local offline text-to-speech.
    Falls back to MockTTSProvider if kokoro is not installed.
    """

    VOICE_MAP = {
        "en-US-female": "af_heart",
        "en-US-male": "am_adam",
        "en-IN-female": "af_heart",
        "en-IN-male": "am_adam",
        "en-GB-female": "bf_emma",
        "en-GB-male": "bm_george",
    }

    def __init__(self, model_id: str = "hexgrad/Kokoro-82M"):
        self.model_id = model_id
        self._pipeline = None

    def _load_pipeline(self):
        if self._pipeline is not None:
            return
        try:
            from kokoro import KPipeline
            lang_code = "a"  # American English default
            self._pipeline = KPipeline(lang_code=lang_code)
            logger.info("kokoro_tts_loaded", model=self.model_id)
        except ImportError:
            logger.warning("kokoro_not_installed_falling_back_to_mock")
            self._pipeline = None

    async def synthesize(
        self,
        text: str,
        voice: str = "en-US-female",
        output_path: str = "voiceover.mp3",
    ) -> str:
        self._load_pipeline()

        if self._pipeline is None:
            from tts_providers.mock import MockTTSProvider
            mock = MockTTSProvider()
            return await mock.synthesize(text, voice, output_path)

        kokoro_voice = self.VOICE_MAP.get(voice, "af_heart")

        try:
            import soundfile as sf
            import numpy as np
            generator = self._pipeline(text, voice=kokoro_voice, speed=1.0)
            all_audio = []
            for _, _, audio_chunk in generator:
                all_audio.append(audio_chunk)

            if all_audio:
                combined = np.concatenate(all_audio)
                sf.write(output_path, combined, 24000)
                logger.info("kokoro_tts_synthesized", voice=kokoro_voice, path=output_path)
            else:
                raise RuntimeError("Kokoro returned no audio")

        except Exception as exc:
            logger.warning("kokoro_synthesis_failed", error=str(exc))
            from tts_providers.mock import MockTTSProvider
            mock = MockTTSProvider()
            return await mock.synthesize(text, voice, output_path)

        return output_path

    async def is_available(self) -> bool:
        try:
            import kokoro
            return True
        except ImportError:
            return False
