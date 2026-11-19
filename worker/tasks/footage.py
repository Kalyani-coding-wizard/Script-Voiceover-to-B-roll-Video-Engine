"""
Footage Search and Selection Orchestrator.
Coordinates:
- Stock libraries (Pexels, Pixabay)
- Generative AI video models (fal.ai Fast SVD)
- Licence-clean mock provider for tests / offline
- Measurable selection rule between stock vs generative AI
- Deduplication: guarantees no clip is reused within the same video
- Content safety filtering: avoid terms, sensitive news, real persons / brands
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Set

import structlog

from footage_providers.base import FootageClip, FootageProvider
from footage_providers.fal_ai import FalAIFootageProvider
from footage_providers.mock import MockFootageProvider
from footage_providers.pexels import PexelsProvider
from footage_providers.pixabay import PixabayProvider
from worker.tasks.segment import SegmentedScene
from worker.tasks.cards import make_title_card_clip
from worker.tasks.safety import gate_query

logger = structlog.get_logger(__name__)

# Minimum relevance score to accept a stock clip before triggering generative fallback
STOCK_RELEVANCE_THRESHOLD = 0.65

# Abstract topics that trigger AI video generation rule
ABSTRACT_KEYWORDS = {
    "trust", "mindset", "future", "philosophy", "infinite",
    "imagination", "abstract", "metaphor", "wisdom", "concept",
    "dream", "subconscious", "paradigm", "essence",
}

# Sensitive news / tragedy keywords requiring respectful neutral visuals
SENSITIVE_KEYWORDS = {
    "sad", "tragedy", "died", "grief", "disaster", "funeral",
    "accident", "loss", "mourning", "victim", "crisis"
}


class FootageManager:
    """Manages multi-provider footage retrieval, fallback hierarchy, and deduplication."""

    def __init__(self, mock_mode: bool = False):
        self.mock_mode = mock_mode
        self.used_clip_ids: Set[str] = set()
        self.warnings: List[str] = []

        # Initialize providers
        self.mock_provider = MockFootageProvider()
        self.pexels = PexelsProvider()
        self.pixabay = PixabayProvider()
        self.fal_ai = FalAIFootageProvider()

    def _is_abstract_concept(self, text: str, query: str) -> bool:
        """Measurable rule: checks whether the scene is abstract/metaphorical."""
        combined = f"{text} {query}".lower().split()
        return any(w in ABSTRACT_KEYWORDS for w in combined)

    def _is_sensitive_topic(self, text: str) -> bool:
        """Detects sensitive/sad news requiring dignified respectful footage."""
        combined = text.lower().split()
        return any(w in SENSITIVE_KEYWORDS for w in combined)

    async def select_clip_for_scene(
        self,
        scene: SegmentedScene,
        style: str = "bright, modern, real-world footage",
        avoid: Optional[List[str]] = None,
        orientation: str = "landscape",
    ) -> FootageClip:
        """
        Picks the best licence-clean clip for a scene using the written measurable rule:
        1. Check sensitive topics -> use calm, respectful nature/ambient visuals.
        2. Check abstract topics or low stock relevance -> use generative AI (fal.ai).
        3. Real-world topics -> use Pexels / Pixabay stock libraries.
        4. Resilient fallback -> if one provider is down, seamless switch to next.
        """
        avoid = avoid or []
        avoid_clean = list(avoid)
        safety = gate_query(scene.text, scene.search_query)
        if safety.requires_fallback:
            self.warnings.append(safety.warning or "Scene routed to a safe fallback.")
            clip = make_title_card_clip(scene.text, safety.query, safety.warning or "Safe fallback selected.")
            self.used_clip_ids.add(clip.clip_id)
            return clip

        # Content Safety: ensure named persons/brands don't produce unauthorized realistic faces
        avoid_clean.extend(["celebrity face", "trademark logo", "violent content"])

        # Check sensitive topic handling
        if self._is_sensitive_topic(scene.text):
            query = "peaceful calm nature morning forest sunlight"
            reason = "Sensitive/somber topic detected: selected dignified, respectful ambient visuals."
            clip = await self._search_with_fallback(
                query=query,
                scene_text=scene.text,
                orientation=orientation,
                avoid=avoid_clean,
                override_reason=reason,
            )
            return clip

        # Measurable Rule: Abstract vs Concrete
        is_abstract = self._is_abstract_concept(scene.text, scene.search_query)

        if is_abstract and not self.mock_mode:
            # Rule: When concept is abstract/metaphorical, generative AI video produces superior semantic fit
            fal_clips = await self.fal_ai.search(
                query=scene.visual_hint or scene.search_query,
                scene_text=scene.text,
                orientation=orientation,
                avoid=avoid_clean,
                used_ids=self.used_clip_ids,
            )
            if fal_clips:
                clip = fal_clips[0]
                self.used_clip_ids.add(clip.clip_id)
                clip.reason = (
                    f"Selected Generative AI (fal.ai) per Measurable Rule: scene expresses abstract concept "
                    f"('{scene.search_query}') where stock footage would produce literal or mismatched cliches."
                )
                return clip

        # Concrete / Real-World Footage: Try Stock Library First
        clip = await self._search_with_fallback(
            query=scene.search_query,
            scene_text=scene.text,
            orientation=orientation,
            avoid=avoid_clean,
        )

        # If stock relevance score is below threshold, trigger generative AI model
        if clip.relevance_score < STOCK_RELEVANCE_THRESHOLD and not self.mock_mode:
            fal_clips = await self.fal_ai.search(
                query=scene.visual_hint or scene.search_query,
                scene_text=scene.text,
                orientation=orientation,
                avoid=avoid_clean,
                used_ids=self.used_clip_ids,
            )
            if fal_clips:
                clip = fal_clips[0]
                self.used_clip_ids.add(clip.clip_id)
                clip.reason = (
                    f"Switched from stock to Generative AI (fal.ai) per Measurable Rule: stock relevance "
                    f"score was below threshold (<0.65). Generative video synthesized for: '{scene.search_query}'."
                )
                return clip
            fallback = make_title_card_clip(
                scene.text,
                scene.search_query,
                "Stock relevance was below threshold and AI footage was unavailable.",
            )
            self.used_clip_ids.add(fallback.clip_id)
            self.warnings.append("Stock relevance below threshold; title-card fallback used.")
            return fallback

        return clip

    async def _search_with_fallback(
        self,
        query: str,
        scene_text: str,
        orientation: str,
        avoid: List[str],
        override_reason: Optional[str] = None,
    ) -> FootageClip:
        """Searches across providers with automatic failover."""
        # Provider 1: Pexels
        if not self.mock_mode and await self.pexels.is_available():
            try:
                clips = await self.pexels.search(
                    query=query,
                    scene_text=scene_text,
                    orientation=orientation,
                    avoid=avoid,
                    used_ids=self.used_clip_ids,
                    per_page=5,
                )
                if clips:
                    best = clips[0]
                    self.used_clip_ids.add(best.clip_id)
                    if override_reason:
                        best.reason = override_reason
                    else:
                        best.reason = (
                            f"Selected Stock (Pexels) per Measurable Rule: concrete real-world topic "
                            f"'{query}' (relevance: {best.relevance_score:.2f})."
                        )
                    return best
            except Exception as exc:
                logger.warning("pexels_search_failed_fallback_to_pixabay", error=str(exc))

        # Provider 2: Pixabay
        if not self.mock_mode and await self.pixabay.is_available():
            try:
                clips = await self.pixabay.search(
                    query=query,
                    scene_text=scene_text,
                    orientation=orientation,
                    avoid=avoid,
                    used_ids=self.used_clip_ids,
                    per_page=5,
                )
                if clips:
                    best = clips[0]
                    self.used_clip_ids.add(best.clip_id)
                    if override_reason:
                        best.reason = override_reason
                    else:
                        best.reason = (
                            f"Selected Stock (Pixabay) via provider failover: matched '{query}' "
                            f"(relevance: {best.relevance_score:.2f})."
                        )
                    return best
            except Exception as exc:
                logger.warning("pixabay_search_failed_fallback_to_mock", error=str(exc))

        if not self.mock_mode:
            fallback = make_title_card_clip(
                scene_text,
                query,
                "No licence-clean provider returned a usable clip; original title card generated.",
            )
            self.used_clip_ids.add(fallback.clip_id)
            self.warnings.append("All footage providers unavailable; original title-card fallback used.")
            return fallback

        # Provider 3: deterministic mock provider (always available offline)
        mock_clips = await self.mock_provider.search(
            query=query,
            scene_text=scene_text,
            orientation=orientation,
            avoid=avoid,
            used_ids=self.used_clip_ids,
            per_page=5,
        )
        best = mock_clips[0]
        self.used_clip_ids.add(best.clip_id)
        if override_reason:
            best.reason = override_reason
        return best
