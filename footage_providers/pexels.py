"""
Pexels footage provider.
Docs: https://www.pexels.com/api/documentation/
"""
import logging
import os
from typing import List, Optional, Set

import aiohttp
import numpy as np

from footage_providers.base import FootageClip, FootageProvider

logger = logging.getLogger(__name__)

PEXELS_API_BASE = "https://api.pexels.com/videos/search"


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def _build_avoid_filter(avoid: Optional[List[str]]) -> str:
    if not avoid:
        return ""
    return " -" + " -".join(avoid)


class PexelsProvider(FootageProvider):
    """Pexels video search provider."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or os.getenv("PEXELS_API_KEY", "")
        self._embedder = None  # lazy-loaded

    @property
    def name(self) -> str:
        return "pexels"

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
            logger.warning("Pexels API key not configured")
            return []

        used_ids = used_ids or set()
        avoid_str = _build_avoid_filter(avoid)
        full_query = f"{query}{avoid_str}"

        headers = {"Authorization": self._api_key}
        params = {
            "query": full_query,
            "per_page": per_page,
            "orientation": orientation,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    PEXELS_API_BASE,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
        except Exception as exc:
            logger.error("Pexels search failed: %s", exc)
            return []

        videos = data.get("videos", [])
        if not videos:
            return []

        # Semantic scoring
        embedder = self._get_embedder()
        scene_emb = embedder.encode(scene_text, convert_to_numpy=True)

        clips: List[FootageClip] = []
        for v in videos:
            clip_id = str(v.get("id", ""))
            if clip_id in used_ids:
                continue

            # Pick best video file (HD preferred)
            files = sorted(
                v.get("video_files", []),
                key=lambda f: f.get("width", 0),
                reverse=True,
            )
            if not files:
                continue
            best_file = files[0]
            clip_url = best_file.get("link", "")
            if not clip_url:
                continue

            # Score clip against scene text using its tags/query
            clip_desc = " ".join(
                [v.get("url", ""), query] +
                [t.get("title", "") for t in v.get("tags", [])]
            )
            clip_emb = embedder.encode(clip_desc, convert_to_numpy=True)
            score = _cosine_similarity(scene_emb, clip_emb)

            photographer = v.get("user", {}).get("name", "Unknown")
            clips.append(
                FootageClip(
                    url=clip_url,
                    source="pexels",
                    licence="Pexels Licence",
                    attribution=f"Video by {photographer} on Pexels",
                    is_ai_generated=False,
                    relevance_score=round(score, 4),
                    reason=f"Pexels clip matching '{query}'",
                    clip_id=clip_id,
                    duration_seconds=float(v.get("duration", 0)),
                    width=best_file.get("width", 1920),
                    height=best_file.get("height", 1080),
                )
            )

        clips.sort(key=lambda c: c.relevance_score, reverse=True)
        return clips
