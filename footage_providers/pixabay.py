"""
Pixabay footage provider.
Docs: https://pixabay.com/api/docs/
"""
import logging
import os
from typing import List, Optional, Set

import aiohttp
import numpy as np

from footage_providers.base import FootageClip, FootageProvider

logger = logging.getLogger(__name__)

PIXABAY_API_BASE = "https://pixabay.com/api/videos/"


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


class PixabayProvider(FootageProvider):
    """Pixabay video search provider."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or os.getenv("PIXABAY_API_KEY", "")
        self._embedder = None

    @property
    def name(self) -> str:
        return "pixabay"

    def _get_embedder(self):
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
        return self._embedder

    async def is_available(self) -> bool:
        return bool(self._api_key)

    async def search(
        self,
        query: str,
        scene_text: str,
        orientation: str = "landscape",
        avoid: Optional[List[str]] = None,
        used_ids: Optional[Set[str]] = None,
        per_page: int = 5,
    ) -> List[FootageClip]:
        if not self._api_key:
            logger.warning("Pixabay API key not configured")
            return []

        used_ids = used_ids or set()

        # Pixabay doesn't support negative terms natively; we apply a post-filter
        params = {
            "key": self._api_key,
            "q": query,
            "per_page": per_page,
            "video_type": "film",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    PIXABAY_API_BASE,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
        except Exception as exc:
            logger.error("Pixabay search failed: %s", exc)
            return []

        hits = data.get("hits", [])
        if not hits:
            return []

        embedder = self._get_embedder()
        scene_emb = embedder.encode(scene_text, convert_to_numpy=True)

        clips: List[FootageClip] = []
        for hit in hits:
            clip_id = str(hit.get("id", ""))
            if clip_id in used_ids:
                continue

            # Pixabay video sizes: large > medium > small
            videos_info = hit.get("videos", {})
            best = (
                videos_info.get("large")
                or videos_info.get("medium")
                or videos_info.get("small")
            )
            if not best:
                continue
            clip_url = best.get("url", "")
            if not clip_url:
                continue

            # Content safety: skip hits matching avoid terms
            tags = hit.get("tags", "")
            if avoid and any(t.strip().lower() in tags.lower() for t in avoid):
                continue

            # Score
            clip_desc = f"{query} {tags}"
            clip_emb = embedder.encode(clip_desc, convert_to_numpy=True)
            score = _cosine_similarity(scene_emb, clip_emb)

            user = hit.get("user", "Unknown")
            clips.append(
                FootageClip(
                    url=clip_url,
                    source="pixabay",
                    licence="Pixabay Licence",
                    attribution=f"Video by {user} on Pixabay",
                    is_ai_generated=False,
                    relevance_score=round(score, 4),
                    reason=f"Pixabay clip matching '{query}'",
                    clip_id=clip_id,
                    duration_seconds=float(hit.get("duration", 0)),
                    width=best.get("width", 1920),
                    height=best.get("height", 1080),
                )
            )

        clips.sort(key=lambda c: c.relevance_score, reverse=True)
        return clips
