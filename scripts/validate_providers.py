"""Non-secret live readiness check for fal.ai and Gemini configuration."""
from __future__ import annotations

import os
import sys

import aiohttp


async def main() -> int:
    fal_key = os.getenv("FAL_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    mock_mode = os.getenv("MOCK_MODE", "false").lower() == "true"

    print(f"Mock mode: {'enabled' if mock_mode else 'disabled'}")
    print(f"fal.ai key: {'configured' if fal_key else 'missing'}")
    print(f"Gemini key: {'configured' if gemini_key else 'missing'}")

    if mock_mode:
        print("Live provider checks skipped while MOCK_MODE=true")
        return 0

    failures = []
    async with aiohttp.ClientSession() as session:
        if gemini_key:
            model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            try:
                async with session.post(
                    url,
                    headers={"x-goog-api-key": gemini_key, "Content-Type": "application/json"},
                    json={"contents": [{"parts": [{"text": "Reply with OK"}]}]},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    print(f"Gemini: HTTP {response.status}")
                    if response.status not in (200,):
                        failures.append("Gemini")
            except Exception as exc:
                print(f"Gemini: failed ({type(exc).__name__})")
                failures.append("Gemini")

    return 1 if failures else 0


if __name__ == "__main__":
    import asyncio

    sys.exit(asyncio.run(main()))
