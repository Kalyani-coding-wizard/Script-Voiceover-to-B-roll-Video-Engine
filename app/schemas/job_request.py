"""Pydantic schemas for job requests."""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator


class CaptionOptions(BaseModel):
    burn_in: bool = True
    srt: bool = True


class Scene(BaseModel):
    text: str = Field(..., min_length=1)
    visual_hint: Optional[str] = None


class JobRequest(BaseModel):
    # ── Input (exactly one required) ────────────────────────────────────────
    audio_url: Optional[str] = Field(
        None,
        description="URL of an existing voiceover audio file (mp3/wav/m4a).",
    )
    script: Optional[str] = Field(
        None,
        description="Plain-text script. TTS will generate audio.",
    )
    scenes: Optional[List[Scene]] = Field(
        None,
        description="Pre-segmented scenes with optional visual hints.",
    )

    # ── Voice (TTS only) ────────────────────────────────────────────────────
    voice: str = Field("en-IN-female", description="TTS voice identifier.")
    language: str = Field(
        "auto",
        description="Input language hint (auto, en, hi, te, ta, ml, or another Whisper language code).",
    )

    # ── Output options ──────────────────────────────────────────────────────
    aspect_ratios: List[str] = Field(
        default_factory=lambda: ["9:16"],
        description="Desired output aspect ratios.",
    )
    style: str = Field(
        "bright, modern, real-world footage",
        description="Visual style guidance for footage search.",
    )
    avoid: List[str] = Field(
        default_factory=list,
        description="Topics / elements to avoid in footage.",
    )
    captions: CaptionOptions = Field(default_factory=CaptionOptions)

    # ── Callback ────────────────────────────────────────────────────────────
    callback_url: Optional[str] = Field(
        None, description="Webhook URL to call on job completion."
    )
    callback_secret: Optional[str] = Field(
        None, description="Secret used to sign the callback payload (HMAC-SHA256)."
    )

    @field_validator("aspect_ratios")
    @classmethod
    def _validate_aspect_ratios(cls, value: List[str]) -> List[str]:
        allowed = {"9:16", "16:9", "1:1"}
        if not value or any(r not in allowed for r in value):
            raise ValueError("aspect_ratios must contain only 9:16, 16:9, or 1:1.")
        return list(dict.fromkeys(value))

    @field_validator("language")
    @classmethod
    def _validate_language(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized or len(normalized) > 16:
            raise ValueError("language must be 'auto' or a valid language code.")
        return normalized

    @model_validator(mode="after")
    def _exactly_one_input(self) -> "JobRequest":
        provided = [
            x
            for x in (self.audio_url, self.script, self.scenes)
            if x is not None and x != []
        ]
        if len(provided) == 0:
            raise ValueError(
                "Exactly one of 'audio_url', 'script', or 'scenes' must be provided."
            )
        if len(provided) > 1:
            raise ValueError(
                "Only one of 'audio_url', 'script', or 'scenes' may be provided."
            )
        return self

    model_config = {"json_schema_extra": {
        "examples": [
            {
                "script": "Welcome to our product demo. Today we explore...",
                "voice": "en-IN-female",
                "aspect_ratios": ["16:9", "9:16"],
                "style": "bright, modern, real-world footage",
                "avoid": ["people's faces", "alcohol"],
                "captions": {"burn_in": True, "srt": True},
                "callback_url": None,
                "callback_secret": None,
            }
        ]
    }}
