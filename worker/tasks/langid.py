"""Lightweight language detection used by the pipeline and manifest."""
from __future__ import annotations

import re
from typing import Optional


_SCRIPT_LANGUAGES = (
    ("te", re.compile(r"[\u0C00-\u0C7F]")),
    ("ta", re.compile(r"[\u0B80-\u0BFF]")),
    ("ml", re.compile(r"[\u0D00-\u0D7F]")),
    ("hi", re.compile(r"[\u0900-\u097F]")),
)


def detect_language(text: str, hint: str = "auto", detected: Optional[str] = None) -> str:
    """Return a stable language code without requiring a heavyweight model."""
    if hint and hint.lower() != "auto":
        return hint.lower()
    if detected:
        return detected.lower()
    for language, pattern in _SCRIPT_LANGUAGES:
        if pattern.search(text or ""):
            return language
    return "en"
