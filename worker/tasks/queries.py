"""Creator-oriented search query generation.

Queries are deliberately concrete and English-friendly so stock providers can
search them consistently even when narration is Indic or code-mixed.
"""
from __future__ import annotations

import re
from typing import Any

from worker.tasks.segment import DISAMBIGUATION_MAP, SegmentedScene


FIGURATIVE_REWRITES = {
    "grind never stops": "person working late at desk",
    "sky is the limit": "person climbing toward a bright horizon",
    "watch your future flourish": "young professional planning goals with upward growth chart",
    "break the ice": "friendly people starting a conversation",
}


def build_search_query(scene: SegmentedScene, language: str = "en") -> str:
    """Build a concrete English query while preserving original scene text."""
    text = scene.visual_hint or scene.text
    lower = text.lower()
    for phrase, replacement in FIGURATIVE_REWRITES.items():
        if phrase in lower:
            return replacement
    for key, replacement in DISAMBIGUATION_MAP.items():
        if re.search(rf"\b{re.escape(key)}\b", lower):
            return replacement
    # Existing hints are preferred; otherwise retain useful Latin/code-mixed terms.
    words = re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", text)
    if words:
        return " ".join(words[:8])
    return "abstract cinematic motion graphic"


def enrich_scene_query(scene: SegmentedScene, language: str = "en") -> SegmentedScene:
    scene.search_query = build_search_query(scene, language)
    return scene
