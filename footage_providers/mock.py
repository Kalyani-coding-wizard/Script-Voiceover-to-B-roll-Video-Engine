"""
Mock Footage Provider — produces licence-clean, deterministic mock clips.
No external API calls or keys required. Ideal for unit tests, offline dev, and fallbacks.
"""
from __future__ import annotations

import hashlib
from typing import List, Optional, Set

from footage_providers.base import FootageClip, FootageProvider

_MOCK_VIDEOS = [
    {
        "clip_id": "mock_pexels_101",
        "url": "https://assets.mixkit.co/videos/preview/mixkit-hands-counting-money-4284-large.mp4",
        "source": "mock_stock",
        "licence": "Mock Footage Licence",
        "licence_url": "https://example.com/mock-footage-licence",
        "attribution": "Mock Stock Library",
        "is_ai_generated": False,
        "base_keywords": ["money", "finance", "savings", "cash", "bank", "wealth", "investment"],
        "description": "Close up of hands counting currency banknotes on an office desk",
    },
    {
        "clip_id": "mock_pexels_102",
        "url": "https://assets.mixkit.co/videos/preview/mixkit-business-team-in-a-meeting-working-together-4256-large.mp4",
        "source": "mock_stock",
        "licence": "Mock Footage Licence",
        "attribution": "Mock Stock Library",
        "is_ai_generated": False,
        "base_keywords": ["team", "meeting", "office", "collaboration", "work", "business", "corporate"],
        "description": "Diverse team collaborating around conference table discussing charts",
    },
    {
        "clip_id": "mock_pexels_103",
        "url": "https://assets.mixkit.co/videos/preview/mixkit-software-developer-working-on-code-4258-large.mp4",
        "source": "mock_stock",
        "licence": "Mock Footage Licence",
        "attribution": "Mock Stock Library",
        "is_ai_generated": False,
        "base_keywords": ["code", "developer", "technology", "programming", "software", "computer", "cloud", "python"],
        "description": "Programmer typing code on a dual monitor workstation in low light",
    },
    {
        "clip_id": "mock_pexels_104",
        "url": "https://assets.mixkit.co/videos/preview/mixkit-data-center-server-racks-4290-large.mp4",
        "source": "mock_stock",
        "licence": "Mock Footage Licence",
        "attribution": "Mock Stock Library",
        "is_ai_generated": False,
        "base_keywords": ["server", "cloud computing", "datacenter", "infrastructure", "network", "hardware"],
        "description": "Blinking lights in modern enterprise data center server room",
    },
    {
        "clip_id": "mock_pexels_105",
        "url": "https://assets.mixkit.co/videos/preview/mixkit-growth-chart-graph-on-screen-4299-large.mp4",
        "source": "mock_stock",
        "licence": "Mock Footage Licence",
        "attribution": "Mock Stock Library",
        "is_ai_generated": False,
        "base_keywords": ["growth", "chart", "statistics", "sales", "analytics", "market", "metrics"],
        "description": "Financial stock market upward trending graph showing 40 percent growth",
    },
    {
        "clip_id": "mock_pexels_106",
        "url": "https://assets.mixkit.co/videos/preview/mixkit-handshake-between-business-partners-4259-large.mp4",
        "source": "mock_stock",
        "licence": "Mock Footage Licence",
        "attribution": "Mock Stock Library",
        "is_ai_generated": False,
        "base_keywords": ["trust", "handshake", "agreement", "partnership", "deal", "contract", "value"],
        "description": "Two business executives shaking hands sealing long term trust and partnership",
    },
    {
        "clip_id": "mock_pexels_107",
        "url": "https://assets.mixkit.co/videos/preview/mixkit-person-walking-in-peaceful-forest-4288-large.mp4",
        "source": "mock_stock",
        "licence": "Mock Footage Licence",
        "attribution": "Mock Stock Library",
        "is_ai_generated": False,
        "base_keywords": ["calm", "nature", "peace", "forest", "reflection", "sensitive", "story", "quiet"],
        "description": "Quiet reflective walk through tranquil morning woods with soft ambient lighting",
    },
    {
        "clip_id": "mock_pexels_108",
        "url": "https://assets.mixkit.co/videos/preview/mixkit-smartphone-user-scrolling-feed-4295-large.mp4",
        "source": "mock_stock",
        "licence": "Mock Footage Licence",
        "attribution": "Mock Stock Library",
        "is_ai_generated": False,
        "base_keywords": ["mobile", "phone", "app", "social", "scroll", "screen", "digital", "mouse"],
        "description": "Close up of finger navigating sleek user interface on modern smartphone",
    },
    {
        "clip_id": "mock_pexels_109",
        "url": "https://assets.mixkit.co/videos/preview/mixkit-modern-city-skyline-time-lapse-4282-large.mp4",
        "source": "mock_stock",
        "licence": "Mock Footage Licence",
        "attribution": "Mock Stock Library",
        "is_ai_generated": False,
        "base_keywords": ["city", "skyline", "urban", "architecture", "future", "modern", "global"],
        "description": "Cinematic timelapse of metropolitan skyline with flowing traffic and dusk lighting",
    },
    {
        "clip_id": "mock_pexels_110",
        "url": "https://assets.mixkit.co/videos/preview/mixkit-hands-holding-coffee-cup-4291-large.mp4",
        "source": "mock_stock",
        "licence": "Mock Footage Licence",
        "attribution": "Mock Stock Library",
        "is_ai_generated": False,
        "base_keywords": ["coffee", "morning", "routine", "lifestyle", "warmth", "break"],
        "description": "Holding a warm ceramic mug on a wooden table during a morning break",
    },
    {
        "clip_id": "mock_pexels_111",
        "url": "https://assets.mixkit.co/videos/preview/mixkit-doctor-with-stethoscope-listening-4265-large.mp4",
        "source": "mock_stock",
        "licence": "Mock Footage Licence",
        "attribution": "Mock Stock Library",
        "is_ai_generated": False,
        "base_keywords": ["health", "medical", "doctor", "hospital", "care", "wellness", "science"],
        "description": "Medical professional examining patient in modern bright healthcare clinic",
    },
    {
        "clip_id": "mock_pexels_112",
        "url": "https://assets.mixkit.co/videos/preview/mixkit-students-studying-together-in-library-4272-large.mp4",
        "source": "mock_stock",
        "licence": "Mock Footage Licence",
        "attribution": "Mock Stock Library",
        "is_ai_generated": False,
        "base_keywords": ["education", "study", "learning", "books", "university", "tutorial", "knowledge"],
        "description": "Focused students reading books and laptops together in quiet study hall",
    },
]

for _record in _MOCK_VIDEOS:
    _record["licence"] = "Mock Footage Licence"
    _record["licence_url"] = "https://example.com/mock-footage-licence"
    _record["attribution"] = "Mock Stock Library"


class MockFootageProvider(FootageProvider):
    """Mock footage provider returning deterministic licence-recorded clips."""

    @property
    def name(self) -> str:
        return "mock"

    async def is_available(self) -> bool:
        return True

    async def search(
        self,
        query: str,
        scene_text: str,
        orientation: str = "landscape",
        avoid: Optional[List[str]] = None,
        used_ids: Optional[Set[str]] = None,
        per_page: int = 5,
    ) -> List[FootageClip]:
        used_ids = used_ids or set()
        avoid_terms = [a.lower().strip() for a in (avoid or [])]
        query_words = set(query.lower().replace(",", " ").split())
        scene_words = set(scene_text.lower().replace(",", " ").split())

        candidates: List[tuple[float, dict]] = []

        for item in _MOCK_VIDEOS:
            cid = item["clip_id"]
            if cid in used_ids:
                continue

            # Check avoid terms
            desc_lower = item["description"].lower()
            keywords_lower = " ".join(item["base_keywords"]).lower()
            combined_text = f"{desc_lower} {keywords_lower}"

            if any(term in combined_text for term in avoid_terms if term):
                continue

            # Semantic match score calculation
            overlap_q = sum(1 for w in query_words if w in combined_text)
            overlap_s = sum(1 for w in scene_words if w in combined_text)
            
            # Baseline score plus semantic match boost
            score = 0.5 + (0.35 * min(1.0, (overlap_q * 2 + overlap_s) / max(1, len(query_words) + 2)))
            score = min(0.98, max(0.40, score))

            candidates.append((score, item))

        # Sort descending by relevance score
        candidates.sort(key=lambda x: x[0], reverse=True)

        # Fallback if all avoided or used: generate dynamic clean candidate
        if not candidates:
            # Deterministic hash ID to avoid repeat
            hash_id = f"mock_synth_{hashlib.md5(scene_text.encode()).hexdigest()[:8]}"
            if hash_id in used_ids:
                hash_id = f"{hash_id}_{len(used_ids)}"
            
            return [
                FootageClip(
                    url="https://assets.mixkit.co/videos/preview/mixkit-modern-city-skyline-time-lapse-4282-large.mp4",
                    source="mock_stock",
                    licence="Mock Footage Licence",
                    licence_url="https://example.com/mock-footage-licence",
                    source_url="https://assets.mixkit.co/videos/preview/mixkit-modern-city-skyline-time-lapse-4282-large.mp4",
                    author="Mock Stock Library",
                    retrieved_at="",
                    attribution="Mock Stock Library",
                    is_ai_generated=False,
                    relevance_score=0.75,
                    reason=f"Synthesized fallback matching scene semantic intent: '{query}'",
                    clip_id=hash_id,
                    duration_seconds=10.0,
                    width=1920,
                    height=1080,
                )
            ]

        results: List[FootageClip] = []
        for score, item in candidates[:per_page]:
            reason = (
                f"Selected for '{query}' - visual elements ({item['description'][:60]}...) "
                f"semantically align with scene narration (relevance: {score:.2f})."
            )
            results.append(
                FootageClip(
                    url=item["url"],
                    source="mock_stock",
                    licence="Mock Footage Licence",
                    licence_url=item.get("licence_url", "https://example.com/mock-footage-licence"),
                    source_url=item["url"],
                    author="Mock Stock Library",
                    retrieved_at="",
                    attribution="Mock Stock Library",
                    is_ai_generated=item["is_ai_generated"],
                    relevance_score=round(score, 2),
                    reason=reason,
                    clip_id=item["clip_id"],
                    duration_seconds=12.0,
                    width=1920,
                    height=1080,
                    extra={"description": item["description"]},
                )
            )
        return results
