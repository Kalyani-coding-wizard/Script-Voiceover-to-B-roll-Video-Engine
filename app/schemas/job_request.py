"""Pydantic schemas for job requests."""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import AnyHttpUrl, BaseModel, Field, model_validator


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

    # ── Output options ──────────────────────────────────────────────────────
    aspect_ratios: List[str] = Field(
        default=["16:9"],
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
