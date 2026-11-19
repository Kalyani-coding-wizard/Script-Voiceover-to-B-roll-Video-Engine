"""Content, intellectual-property, and search safety gates."""
from __future__ import annotations

import re
from dataclasses import dataclass


BLOCKED_TERMS = {
    "porn", "xxx", "explicit", "sexual", "nude", "nudity",
    "gore", "graphic violence", "rape",
}
IP_TERMS = {
    "movie", "film scene", "anime", "celebrity", "actor", "actress",
    "netflix", "disney", "marvel", "pokemon", "pubg", "free fire",
}


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    query: str
    warning: str | None = None
    requires_fallback: bool = False


def gate_query(text: str, query: str) -> SafetyDecision:
    combined = f"{text} {query}".lower()
    if any(term in combined for term in BLOCKED_TERMS):
        return SafetyDecision(False, "abstract safe motion graphic", "Unsafe content query blocked.", True)
    if any(re.search(rf"\b{re.escape(term)}\b", combined) for term in IP_TERMS):
        return SafetyDecision(
            False,
            "abstract cinematic motion graphic",
            "IP-protected or niche footage request routed to fallback.",
            True,
        )
    return SafetyDecision(True, query)
