"""Application configuration via pydantic-settings (reads from env vars / .env)."""
from __future__ import annotations

import os
import sys

# Ensure Windows finds native DLLs (e.g. SQLite3, FFmpeg) when using embedded/QGIS Python
if sys.platform == "win32":
    qgis_bin = r"C:\Program Files\QGIS 3.40.1\bin"
    if os.path.exists(qgis_bin) and hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(qgis_bin)
        except Exception:
            pass

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://broll:broll@postgres:5432/broll"

    # ── Redis / ARQ ─────────────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"

    # ── Object storage (MinIO / S3) ─────────────────────────────────────────
    s3_endpoint: str = "http://minio:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "broll-outputs"
    storage_mode: Literal["local", "s3"] = "local"
    s3_region: str = "us-east-1"
    artifact_backend: Literal["auto", "local", "s3"] = "auto"

    # ── External API keys ───────────────────────────────────────────────────
    pexels_api_key: str = ""
    pixabay_api_key: str = ""
    fal_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""

    # ── Provider selection ──────────────────────────────────────────────────
    tts_provider: Literal["edge", "openai"] = "edge"
    llm_provider: Literal["gemini", "openai"] = "gemini"
    footage_provider: Literal["pexels", "pixabay", "fal"] = "fal"

    # ── Feature flags ───────────────────────────────────────────────────────
    mock_mode: bool = False

    # ── Logging ─────────────────────────────────────────────────────────────
    log_level: str = "INFO"

    # ── Business limits ─────────────────────────────────────────────────────
    max_audio_duration: int = 600  # seconds
    worker_concurrency: int = 2
    whisper_model: str = "small"
    whisper_compute_type: str = "int8"

    # ── Security ────────────────────────────────────────────────────────────
    hmac_secret: str = "change-me-in-production"

    # ── App metadata ────────────────────────────────────────────────────────
    app_name: str = "IncuBrix B-roll Video Engine"
    app_version: str = "1.0.0"
    debug: bool = False

    @field_validator("log_level")
    @classmethod
    def _normalise_log_level(cls, v: str) -> str:
        return v.upper()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
