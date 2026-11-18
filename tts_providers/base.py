"""Abstract base class for TTS providers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TTSResult:
    audio_path: str          # local path to output mp3/wav
    duration_seconds: float  # duration of produced audio
    provider: str            # name of provider used


class TTSProvider(ABC):
    """Abstract TTS provider."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: str,
        output_path: str,
    ) -> TTSResult:
        """
        Convert text to speech and save to output_path.

        Args:
            text: Narration text to synthesize.
            voice: Voice identifier (e.g. 'en-IN-female').
            output_path: Absolute path where the audio file should be saved.

        Returns:
            TTSResult with path, duration, and provider name.
        """
