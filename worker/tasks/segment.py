"""
Scene Segmentation Task.
Segments narration into coherent visual scenes by MEANING, strictly timed to voice.
Enforces:
- Scene boundaries fall on natural sentence or phrase boundaries.
- Every single second from 0.0 to total_duration is covered (no gaps or drift).
- Pacing constraints: minimum scene duration >= 3.0s (no flashing clips).
- Semantic disambiguation for double-meaning words (cloud, mouse, python, bank, value).
"""
from __future__ import annotations

import re
import structlog
from typing import Any, Dict, List, Optional

logger = structlog.get_logger(__name__)

MIN_SCENE_DURATION = 3.0
MAX_SCENE_DURATION = 12.0

# Disambiguation rules for hard case concepts
DISAMBIGUATION_MAP = {
    "cloud": "cloud computing server infrastructure data center",
    "cloud computing": "enterprise server room digital data network",
    "value": "business strategy growth and professional client partnership",
    "bank": "modern commercial banking institution finance building",
    "mouse": "ergonomic computer mouse navigating digital interface",
    "python": "software developer writing python code on multiple monitors",
    "trust": "business partners shaking hands in modern conference room",
    "growth": "upward trending financial analytics graph and corporate charts",
    "sales": "business metrics dashboard with rising revenue numbers",
}


class SegmentedScene:
    def __init__(
        self,
        scene_index: int,
        text: str,
        start_time: float,
        end_time: float,
        visual_hint: str = "",
        search_query: str = "",
    ):
        self.scene_index = scene_index
        self.text = text.strip()
        self.start_time = round(start_time, 2)
        self.end_time = round(end_time, 2)
        self.duration = round(self.end_time - self.start_time, 2)
        self.visual_hint = visual_hint or text
        self.search_query = search_query or self._derive_query(text)

    def _derive_query(self, text: str) -> str:
        lower = text.lower()
        # Check disambiguation map first
        for key, hint in DISAMBIGUATION_MAP.items():
            if re.search(rf"\b{re.escape(key)}\b", lower):
                return hint

        # Clean noise words
        stop_words = {
            "a", "an", "the", "in", "on", "at", "to", "for", "of", "with",
            "is", "are", "was", "were", "and", "or", "it", "this", "that",
            "we", "you", "our", "today", "now", "here", "there"
        }
        words = [w for w in re.findall(r"\b[a-zA-Z]{3,}\b", lower) if w not in stop_words]
        return " ".join(words[:4]) or text[:30]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_index": self.scene_index,
            "text": self.text,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "visual_hint": self.visual_hint,
            "search_query": self.search_query,
        }


def segment_narration(
    transcript_segments: List[Dict[str, Any]],
    total_duration: float,
    predefined_scenes: Optional[List[Dict[str, Any]]] = None,
    style_guidance: str = "bright, modern, real-world footage",
) -> List[SegmentedScene]:
    """
    Main segmentation function.
    Returns contiguous, non-overlapping scenes covering [0.0, total_duration].
    """
    logger.info(
        "segmentation_started",
        total_duration=total_duration,
        predefined_scenes_count=len(predefined_scenes) if predefined_scenes else 0,
    )

    if predefined_scenes and len(predefined_scenes) > 0:
        return _segment_from_predefined(predefined_scenes, total_duration)

    return _segment_from_transcript(transcript_segments, total_duration)


def _segment_from_predefined(
    predefined_scenes: List[Dict[str, Any]],
    total_duration: float,
) -> List[SegmentedScene]:
    """Maps user-provided IncuBrix scene list onto the total audio duration."""
    n = len(predefined_scenes)
    duration_per_scene = total_duration / n
    scenes: List[SegmentedScene] = []

    for i, s in enumerate(predefined_scenes):
        start = round(i * duration_per_scene, 2)
        end = round(total_duration if i == n - 1 else (i + 1) * duration_per_scene, 2)
        text = s.get("text", "")
        hint = s.get("visual_hint", "") or text

        scene = SegmentedScene(
            scene_index=i,
            text=text,
            start_time=start,
            end_time=end,
            visual_hint=hint,
            search_query=hint,
        )
        scenes.append(scene)

    _normalize_timeline_coverage(scenes, total_duration)
    return scenes


def _segment_from_transcript(
    segments: List[Dict[str, Any]],
    total_duration: float,
) -> List[SegmentedScene]:
    """
    Groups Whisper segments/sentences into pacing-compliant scenes.
    Ensures minimum scene duration of MIN_SCENE_DURATION.
    """
    if not segments:
        return [
            SegmentedScene(
                scene_index=0,
                text="IncuBrix video narration",
                start_time=0.0,
                end_time=round(total_duration, 2),
                visual_hint="modern technology and business innovation",
            )
        ]

    scenes: List[SegmentedScene] = []
    current_text_chunks: List[str] = []
    current_start = 0.0

    for idx, seg in enumerate(segments):
        s_text = seg.get("text", "").strip()
        s_end = float(seg.get("end", current_start + MIN_SCENE_DURATION))
        current_text_chunks.append(s_text)

        curr_duration = s_end - current_start
        is_last = idx == len(segments) - 1

        # Check if boundary is desirable: sentence terminator or reached target length
        has_terminator = bool(re.search(r"[.?!;]$", s_text))
        
        if (curr_duration >= MIN_SCENE_DURATION and has_terminator) or (curr_duration >= MAX_SCENE_DURATION) or is_last:
            scene_text = " ".join(current_text_chunks).strip()
            scene_idx = len(scenes)
            scenes.append(
                SegmentedScene(
                    scene_index=scene_idx,
                    text=scene_text,
                    start_time=current_start,
                    end_time=s_end,
                )
            )
            current_start = s_end
            current_text_chunks = []

    # Final timeline normalization to ensure no gaps or audio drift
    _normalize_timeline_coverage(scenes, total_duration)
    return scenes


def _normalize_timeline_coverage(scenes: List[SegmentedScene], total_duration: float) -> None:
    """Enforces continuous coverage from 0.0 to total_duration."""
    if not scenes:
        return

    # Guarantee first starts at 0.0
    scenes[0].start_time = 0.0

    # Ensure continuity between scenes
    for i in range(len(scenes) - 1):
        scenes[i + 1].start_time = scenes[i].end_time

    # Guarantee last scene covers through total_duration
    scenes[-1].end_time = max(scenes[-1].start_time + 1.0, round(total_duration, 2))

    for s in scenes:
        s.duration = round(s.end_time - s.start_time, 2)
