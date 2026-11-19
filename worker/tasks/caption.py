"""
Caption generator: produces compliant captions.srt from Whisper word/segment timestamps.
"""
from __future__ import annotations

from typing import Any, Dict, List


def format_srt_timestamp(seconds: float) -> str:
    """Converts seconds (float) to SRT format: HH:MM:SS,mmm"""
    ms = int(round((seconds - int(seconds)) * 1000))
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt(
    words_or_segments: List[Dict[str, Any]],
    output_path: str,
    max_words_per_cue: int = 5,
) -> str:
    """
    Constructs well-formed captions.srt with natural line breaks
    and exact voice synchronization.
    """
    cues: List[Dict[str, Any]] = []

    # Check if we have fine-grained word timestamps
    has_words = any("words" in item and item["words"] for item in words_or_segments)

    if has_words:
        all_words: List[Dict[str, Any]] = []
        for item in words_or_segments:
            if "words" in item:
                all_words.extend(item["words"])
            elif "word" in item:
                all_words.append(item)

        # Group words into subtitle cues
        for i in range(0, len(all_words), max_words_per_cue):
            group = all_words[i : i + max_words_per_cue]
            if not group:
                continue
            text = " ".join(w.get("word", "").strip() for w in group)
            start_t = float(group[0].get("start", 0.0))
            end_t = float(group[-1].get("end", start_t + 2.0))
            cues.append({
                "start": start_t,
                "end": max(end_t, start_t + 1.0),
                "text": text,
            })
    else:
        # Fall back to segments directly
        for s in words_or_segments:
            start_t = float(s.get("start", 0.0))
            end_t = float(s.get("end", start_t + 2.0))
            text = s.get("text", "").strip()
            cues.append({
                "start": start_t,
                "end": max(end_t, start_t + 1.0),
                "text": text,
            })

    # Render SRT file
    with open(output_path, "w", encoding="utf-8") as f:
        for idx, cue in enumerate(cues, 1):
            start_str = format_srt_timestamp(cue["start"])
            end_str = format_srt_timestamp(cue["end"])
            f.write(f"{idx}\n")
            f.write(f"{start_str} --> {end_str}\n")
            f.write(f"{cue['text']}\n\n")

    return output_path
