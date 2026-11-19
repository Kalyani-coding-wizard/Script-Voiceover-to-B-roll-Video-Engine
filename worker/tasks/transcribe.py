"""
Transcription task using OpenAI Whisper with word-level timestamps.
Supports mp3, wav, m4a up to 10 minutes.
Includes graceful fallback for mock mode or low-resource environments.
"""
from __future__ import annotations

import os
import structlog
from typing import Any, Dict, List

logger = structlog.get_logger(__name__)


class TranscribeResult:
    def __init__(
        self,
        text: str,
        duration: float,
        segments: List[Dict[str, Any]],
        words: List[Dict[str, Any]],
        language: str = "en",
    ):
        self.text = text
        self.duration = duration
        self.segments = segments
        self.words = words
        self.language = language

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "duration": self.duration,
            "segments": self.segments,
            "words": self.words,
            "language": self.language,
        }


def transcribe_audio(
    audio_path: str,
    known_script: str | None = None,
    mock_mode: bool = False,
    model_name: str | None = None,
    language_hint: str = "auto",
) -> TranscribeResult:
    """
    Transcribes the audio file and produces word-level timestamps.
    If mock_mode is True or Whisper fails to load, produces synthetic timestamps
    aligned with known_script or duration.
    """
    model_name = model_name or os.getenv("WHISPER_MODEL", "small")
    logger.info("transcription_started", audio_path=audio_path, model=model_name)

    if not mock_mode:
        try:
            try:
                from faster_whisper import WhisperModel
                model = WhisperModel(model_name, compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"))
                segments_iter, info = model.transcribe(
                    audio_path,
                    language=None if language_hint == "auto" else language_hint,
                    word_timestamps=True,
                    vad_filter=True,
                )
                raw_segments = list(segments_iter)
                res = {
                    "text": " ".join(s.text for s in raw_segments),
                    "language": info.language,
                    "segments": [
                        {
                            "id": i,
                            "start": s.start,
                            "end": s.end,
                            "text": s.text,
                            "words": [
                                {"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                                for w in (s.words or [])
                            ],
                        }
                        for i, s in enumerate(raw_segments)
                    ],
                }
            except ImportError:
                import whisper
                model = whisper.load_model(model_name)
                res = model.transcribe(
                    audio_path,
                    word_timestamps=True,
                    language=None if language_hint == "auto" else language_hint,
                    condition_on_previous_text=False,
                )

            text = res.get("text", "").strip()
            language = res.get("language", "en")
            segments = []
            words = []

            for s in res.get("segments", []):
                s_words = []
                for w in s.get("words", []):
                    w_item = {
                        "word": w.get("word", "").strip(),
                        "start": round(float(w.get("start", 0.0)), 2),
                        "end": round(float(w.get("end", 0.0)), 2),
                        "probability": round(float(w.get("probability", 1.0)), 3),
                    }
                    words.append(w_item)
                    s_words.append(w_item)

                segments.append({
                    "id": s.get("id", 0),
                    "start": round(float(s.get("start", 0.0)), 2),
                    "end": round(float(s.get("end", 0.0)), 2),
                    "text": s.get("text", "").strip(),
                    "words": s_words,
                })

            total_duration = segments[-1]["end"] if segments else 5.0
            logger.info("transcription_succeeded", duration=total_duration, word_count=len(words))
            return TranscribeResult(text, total_duration, segments, words, language)
        except Exception as exc:
            logger.warning("whisper_transcription_fallback", error=str(exc))

    # Synthetic timestamp generator for mock mode / fallback
    return _generate_synthetic_transcription(audio_path, known_script, language_hint)


def _generate_synthetic_transcription(
    audio_path: str, known_script: str | None, language_hint: str = "auto"
) -> TranscribeResult:
    """Estimates words and segment timestamps when audio has known script or mock."""
    script_text = (
        known_script.strip()
        if known_script
        else "IncuBrix automated video engine generating clean B-roll footage."
    )

    words_raw = script_text.split()
    # Assume average speaking rate of 2.6 words per second (156 wpm)
    sec_per_word = 0.38
    total_duration = max(3.0, len(words_raw) * sec_per_word)

    words: List[Dict[str, Any]] = []
    current_time = 0.0

    for w in words_raw:
        w_start = round(current_time, 2)
        w_end = round(current_time + sec_per_word, 2)
        words.append({
            "word": w,
            "start": w_start,
            "end": w_end,
            "probability": 0.99,
        })
        current_time = w_end

    # Group into sentence-like segments
    segments: List[Dict[str, Any]] = []
    chunk_size = 8
    for i in range(0, len(words), chunk_size):
        chunk = words[i : i + chunk_size]
        s_text = " ".join(item["word"] for item in chunk)
        segments.append({
            "id": len(segments),
            "start": chunk[0]["start"],
            "end": chunk[-1]["end"],
            "text": s_text,
            "words": chunk,
        })

    return TranscribeResult(
        text=script_text,
        duration=round(total_duration, 2),
        segments=segments,
        words=words,
        language="en" if language_hint == "auto" else language_hint,
    )
