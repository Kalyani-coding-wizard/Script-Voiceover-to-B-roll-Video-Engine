"""Abstract base class for footage providers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Set


@dataclass
class FootageClip:
    url: str
    source: str                     # 'pexels', 'pixabay', 'fal_ai', 'mock'
    licence: str                    # provider or renderer licence name
    attribution: str                # human-readable credit
    is_ai_generated: bool
    relevance_score: float          # 0.0–1.0 cosine similarity
    reason: str                     # why this clip matches the scene
    licence_url: str = ""
    source_url: str = ""
    author: str = ""
    retrieved_at: Optional[str] = None
    clip_id: str = ""               # provider-specific ID for dedup
    duration_seconds: float = 0.0
    width: int = 1920
    height: int = 1080
    extra: dict = field(default_factory=dict)


class FootageProvider(ABC):
    """Abstract footage provider."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""

    @abstractmethod
    async def search(
        self,
        query: str,
        scene_text: str,
        orientation: str = "landscape",
        avoid: Optional[List[str]] = None,
        used_ids: Optional[Set[str]] = None,
        per_page: int = 5,
    ) -> List[FootageClip]:
        """
        Search for footage clips matching query.

        Args:
            query: Semantic keyword query (LLM-extracted).
            scene_text: Full scene narration text for scoring.
            orientation: 'landscape', 'portrait', or 'square'.
            avoid: Content terms to filter out.
            used_ids: Set of clip IDs already used in this job.
            per_page: Max results to fetch.

        Returns:
            List of FootageClip sorted by relevance_score descending.
        """

    async def is_available(self) -> bool:
        """Check whether this provider is configured and reachable."""
        return True
