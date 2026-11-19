"""
Generative Video Provider via fal.ai (Fast SDV / Stable Video Diffusion / Kling / Luma).
Used when:
1. Stock libraries fail to find relevant footage (relevance_score < 0.65)
2. Abstract metaphors or rare conceptual scenes where realistic stock is absent
3. Explicit AI generation requested in style settings
"""
from __future__ import annotations

import hashlib
import os
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Set

import aiohttp
import structlog

from footage_providers.base import FootageClip, FootageProvider

logger = structlog.get_logger(__name__)


class FalAIFootageProvider(FootageProvider):
    """Generative AI video provider using fal.ai text-to-video APIs."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FAL_API_KEY", "")
        self.api_url = "https://queue.fal.run/fal-ai/fast-svd/text-to-video"

    @property
    def name(self) -> str:
        return "fal_ai"

    async def is_available(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("mock_"))

    async def search(
        self,
        query: str,
        scene_text: str,
        orientation: str = "landscape",
        avoid: Optional[List[str]] = None,
        used_ids: Optional[Set[str]] = None,
        per_page: int = 1,
    ) -> List[FootageClip]:
        used_ids = used_ids or set()
        clean_query = query.strip()
        clip_hash = hashlib.md5(f"fal_{clean_query}".encode()).hexdigest()[:10]
        clip_id = f"fal_gen_{clip_hash}"

        # If API key is available, execute remote inference
        if await self.is_available():
            try:
                headers = {
                    "Authorization": f"Key {self.api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "prompt": f"Cinematic B-roll video: {clean_query}, high quality, 4k, photorealistic",
                    "aspect_ratio": "16:9" if orientation == "landscape" else "9:16",
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.api_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=60)
                    ) as resp:
                        if resp.status in (200, 201):
                            data = await resp.json()
                            video_url = data.get("video", {}).get("url") or data.get("url")
                            if not video_url:
                                response_url = data.get("response_url")
                                status_url = data.get("status_url")
                                if status_url or response_url:
                                    poll_url = status_url or response_url
                                    for _ in range(30):
                                        await asyncio.sleep(2)
                                        async with session.get(
                                            poll_url,
                                            headers=headers,
                                            timeout=aiohttp.ClientTimeout(total=30),
                                        ) as poll:
                                            poll.raise_for_status()
                                            poll_data = await poll.json()
                                        state = str(poll_data.get("status", "")).upper()
                                        if state in {"COMPLETED", "SUCCEEDED"}:
                                            final_url = response_url if response_url else poll_url
                                            if final_url != poll_url:
                                                async with session.get(
                                                    final_url,
                                                    headers=headers,
                                                    timeout=aiohttp.ClientTimeout(total=30),
                                                ) as final:
                                                    final.raise_for_status()
                                                    poll_data = await final.json()
                                            video_url = (
                                                poll_data.get("video", {}).get("url")
                                                or poll_data.get("url")
                                            )
                                            break
                                        if state in {"FAILED", "ERROR"}:
                                            raise RuntimeError(poll_data.get("error", "fal.ai generation failed"))
                            if video_url:
                                return [
                                    FootageClip(
                                        url=video_url,
                                        source=self.name,
                                        licence="Commercial-AI-Generated",
                                        licence_url="https://fal.ai/terms",
                                        source_url=video_url,
                                        author="fal.ai",
                                        retrieved_at=datetime.now(timezone.utc).isoformat(),
                                        attribution="Generated via fal.ai text-to-video model",
                                        is_ai_generated=True,
                                        relevance_score=0.92,
                                        reason=f"Generatively rendered for abstract scene: '{clean_query}'",
                                        clip_id=clip_id,
                                        duration_seconds=5.0,
                                        width=1920,
                                        height=1080,
                                    )
                                ]
            except Exception as exc:
                logger.warning("fal_ai_generation_failed", error=str(exc), query=clean_query)

        return []
