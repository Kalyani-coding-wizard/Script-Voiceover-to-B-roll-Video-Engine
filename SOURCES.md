# SOURCES.md — External Models, APIs, Libraries, and Media Sources

All models, libraries, APIs, and media sources utilized in the default execution path are licensed for commercial use.

---

## 1. Machine Learning Models & Speech Synthesis

| Asset | Source / Provider | License | Commercial Usability | Purpose |
|---|---|---|---|---|
| **Whisper (base)** | OpenAI (`openai-whisper`) | MIT License | Permitted | Local audio transcription and word-level timestamp generation |
| **Edge TTS (Neural)** | Microsoft (`edge-tts`) | MIT License / Public Neural API | Permitted | Neural voiceover generation across English, Hindi, and Tamil |
| **all-MiniLM-L6-v2** | Hugging Face (`sentence-transformers`) | Apache 2.0 | Permitted | Semantic embedding generation and cosine similarity calculation |
| **Fast SVD / Stable Video** | fal.ai | Commercial API License | Permitted | Generative AI video fallback for abstract conceptual scenes |

---

## 2. Media & Stock Footage Sources

| Source | API / Platform | License | Commercial Usability | Purpose |
|---|---|---|---|---|
| **Pexels Video API** | Pexels GmbH | Pexels License (Commercial Use Allowed, No Attribution Required) | Permitted | Primary HD stock B-roll footage |
| **Pixabay Video API** | Pixabay GmbH / Canva | Pixabay Content License (Commercial Safe) | Permitted | Secondary stock B-roll footage failover |
| **Mixkit Curated Library** | Envato Elements Pty Ltd | Mixkit Stock Video Free License (Commercial) | Permitted | Mock and fallback clean video clips |

---

## 3. Core Software Libraries & Frameworks

| Library / Tool | Version | License | Purpose |
|---|---|---|---|
| **FastAPI** | >= 0.110.0 | MIT License | Asynchronous HTTP REST framework |
| **Uvicorn** | >= 0.29.0 | BSD-3-Clause | ASGI production web server |
| **FFmpeg** | 6.x / 7.x | LGPL 2.1+ | Video scaling, cropping, normalization, and audio multiplexing |
| **SQLAlchemy** | >= 2.0.0 | MIT License | Async relational database ORM |
| **ARQ** | >= 0.25.0 | MIT License | Async Redis task queue |
| **Redis** | 7.x | BSD-3-Clause | High-speed cache and task broker |
| **PostgreSQL** | 16.x | PostgreSQL License | ACID persistent database for job records |
| **MinIO** | RELEASE.2024+ | AGPL-3.0 (Server) / Apache 2.0 (SDK) | S3-compatible local/cloud object storage |
| **Structlog** | >= 24.1.0 | Apache 2.0 / MIT | Structured JSON logging with contextvars |
| **HTTPX** | >= 0.27.0 | BSD-3-Clause | Async HTTP client for external requests and testing |
| **Pytest** | >= 8.1.0 | MIT License | Automated unit, integration, and E2E test harness |

---

## 4. Rights & Compliance Statement

- No research-only or non-commercial data (e.g., CC BY-NC) is present in the default pipeline.
- No copyrighted, watermarked, or unlicensed media is outputted.
- All AI-generated clips are explicitly tagged with `"is_ai_generated": true` in both `timeline.json` and `manifest.json`.
