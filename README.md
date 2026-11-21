# IncuBrix Assessment 3 — Script-to-B-roll Video Engine

A containerised FastAPI service that converts a voiceover audio file, plain-text script, or structured scene list into polished B-roll videos with captions — in multiple aspect ratios (16:9, 9:16, 1:1) — in a single API call. It transcribes audio with Whisper, segments the transcript into scenes using an LLM, fetches royalty-free stock footage from Pexels/Pixabay (falling back to AI-generated video via fal.ai), and renders the final MP4 with burned-in captions using FFmpeg.

The creator-first defaults are **9:16 output**, captions enabled, and `language=auto`. Telugu, Tamil, Malayalam, Hindi, and code-mixed inputs are retained in scene text while search queries are normalized to concrete English visuals. Every timeline clip carries its provider licence, licence URL, source URL, author, and retrieval timestamp. Movie, anime, celebrity, gaming-IP, and unsafe requests are routed to an original FFmpeg title-card fallback rather than scraped footage.

---

## Architecture

```mermaid
flowchart LR
    Client -->|POST /api/v1/broll/jobs| API["FastAPI\n(port 8000)"]
    API -->|enqueue job| Redis
    Redis --> Worker["ARQ Worker"]
    Worker -->|audio| Whisper["Whisper\ntranscription"]
    Worker -->|transcript| LLM["Gemini Flash /\nOpenAI scene split"]
    Worker -->|keywords| Pexels["Pexels / Pixabay\nstock footage"]
    Pexels -->|no clip found| FalAI["fal.ai SVD\nAI fallback"]
    Worker -->|text input| EdgeTTS["Edge TTS\nvoiceover"]
    Worker -->|clips + audio + captions| FFmpeg["FFmpeg\nrender"]
    FFmpeg -->|mp4 / srt / json| MinIO["MinIO\n(S3-compatible)"]
    API -->|GET /api/v1/jobs/:id| DB[(PostgreSQL\njob state)]
    Worker --- DB
```

---

## Quick Start (≤ 10 commands)

```bash
git clone <repo> && cd broll-engine
cp .env.example .env
# Edit .env to add your API keys (or set MOCK_MODE=true for no-key mode)
docker compose up -d
docker compose run --rm api alembic upgrade head
# Service is ready at http://localhost:8000
# Optional: open MinIO console at http://localhost:9001
```

> **No API keys?** Set `MOCK_MODE=true` in `.env` — the engine returns synthetic clips so you can validate the full pipeline end-to-end without spending money.

---

## Running Tests

```bash
make test
```

Runs the full pytest suite (unit + integration) inside the `api` container. Test output is printed to stdout; exit code 0 = all pass.

---

## Batch Runner

```bash
make batch input=./tests/inputs output=./results
```

Submits every file in `input/` as a separate job, polls until all jobs finish, then downloads all outputs into `output/`. Useful for benchmarking the 8 hard cases at once.

## Integration Standard tracker

| Point | Proof |
|---|---|
| 1. Accept text/scenes | `tests/integration/test_jobs_api.py` |
| 2. Accept audio URL | `worker/tasks/input_validation.py` and E2E pipeline |
| 3. Async 202 + polling | `tests/e2e/test_full_pipeline.py` |
| 4. Semantic, timed scenes | `tests/unit/test_segmenter.py` |
| 5. Licence metadata per clip | `tests/unit/test_manifest.py` |
| 6. Captions/SRT output | `tests/unit/test_caption.py` |
| 7. Downloadable artifacts | `tests/e2e/test_full_pipeline.py` |
| 8. Provider failover/fallback | `worker/tasks/footage.py` and title-card fallback |
| 9. Idempotency and conflict handling | `tests/unit/test_idempotency.py` |
| 10. Batchable creator corpus | `tests/fixtures/creator_scripts/` and `make corpus` |

---

## Environment Variables

| Variable | Default | Required | Description |
|---|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://broll:broll@postgres:5432/broll` | ✅ | Async PostgreSQL DSN for job state |
| `REDIS_URL` | `redis://redis:6379/0` | ✅ | ARQ job queue and idempotency cache |
| `S3_ENDPOINT` | `http://minio:9000` | ✅ | MinIO / S3 endpoint for output storage |
| `ARTIFACT_BACKEND` | `auto` | — | `auto`, `local`, or `s3`; S3 failures fall back to local artifacts |
| `S3_ACCESS_KEY` | `minioadmin` | ✅ | S3 access key |
| `S3_SECRET_KEY` | `minioadmin` | ✅ | S3 secret key |
| `S3_BUCKET` | `broll-outputs` | ✅ | Bucket name for rendered video outputs |
| `PEXELS_API_KEY` | _(empty)_ | ⚠️ | Pexels API key — required unless `MOCK_MODE=true` |
| `PIXABAY_API_KEY` | _(empty)_ | ⚠️ | Pixabay API key — optional second footage source |
| `FAL_API_KEY` | _(empty)_ | ⚠️ | fal.ai key for AI-generated video fallback |
| `OPENAI_API_KEY` | _(empty)_ | ⚠️ | OpenAI key when `LLM_PROVIDER=openai` |
| `GEMINI_API_KEY` | _(empty)_ | ⚠️ | Gemini Flash key when `LLM_PROVIDER=gemini` |
| `LLM_PROVIDER` | `gemini` | ✅ | Scene segmentation LLM: `gemini` or `openai` |
| `FOOTAGE_PROVIDER` | `fal` | ✅ | Primary provider: `pexels`, `pixabay`, or `fal` |
| `WHISPER_MODEL` | `small` | — | faster-whisper model; use `large-v3-turbo` for higher Indic quality |
| `WHISPER_COMPUTE_TYPE` | `int8` | — | CPU-friendly faster-whisper compute type |
| `TTS_PROVIDER` | `edge` | ✅ | Text-to-speech engine: `edge` (Edge TTS) |
| `MOCK_MODE` | `false` | — | `true` → skip all external APIs, return mock clips |
| `LOG_LEVEL` | `INFO` | — | Structured log verbosity: `DEBUG`, `INFO`, `WARNING` |
| `MAX_AUDIO_DURATION` | `600` | — | Maximum accepted audio length in seconds (10 min) |
| `WORKER_CONCURRENCY` | `2` | — | Number of parallel ARQ workers per container |
| `HMAC_SECRET` | `change-me-in-production` | ✅ | Secret used to sign HMAC-SHA256 callback payloads |
| `CORS_ORIGINS` | `http://localhost:8000` | ✅ | Comma-separated browser origins allowed by the API |

---

## API Quick Reference

### Submit a Job

```
POST /api/v1/broll/jobs
Idempotency-Key: <uuid>          # required
Content-Type: application/json
```

**Body** — supply exactly **one** of `audio_url`, `script`, or `scenes`:

```jsonc
{
  "audio_url": "https://example.com/voiceover.mp3",   // OR
  "script": "Welcome to our product...",               // OR
  "scenes": [{"text": "...", "visual_hint": "..."}],

  "voice": "en-IN-female",        // TTS voice when input is text
  "aspect_ratios": ["16:9", "9:16"],
  "style": "bright, modern, real-world footage",
  "avoid": ["people's faces", "alcohol"],
  "captions": {"burn_in": true, "srt": true},
  "callback_url": "https://your-server.com/webhook"
}
```

**Response** `202 Accepted`:
```json
{ "job_id": "550e8400-e29b-41d4-a716-446655440000" }
```

---

### Poll Job Status

```
GET /api/v1/jobs/{job_id}
```

**Response** `200 OK`:
```jsonc
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "succeeded",           // queued | running | succeeded | failed
  "progress": 100,
  "result": {
    "videos": {
      "16:9": "/api/v1/download/550e8400-e29b-41d4-a716-446655440000/video_16x9.mp4",
      "9:16": "/api/v1/download/550e8400-e29b-41d4-a716-446655440000/video_9x16.mp4"
    },
    "captions_srt": "/api/v1/download/550e8400-e29b-41d4-a716-446655440000/captions.srt",
    "timeline_url": "/api/v1/download/550e8400-e29b-41d4-a716-446655440000/timeline.json",
    "manifest_url": "/api/v1/download/550e8400-e29b-41d4-a716-446655440000/manifest.json"
  },
  "error": null
}
```

---

### Swap a Clip (Advanced Level Requirement)

```
POST /api/v1/jobs/{job_id}/swap-clip
Content-Type: application/json

{
  "scene_index": 1,
  "new_query": "software developer typing code"
}
```
Re-renders only the affected scene clip in clearly less time than a full render.

---

## Error Codes

| Code | HTTP | Retryable | Meaning |
|---|---|---|---|
| `INVALID_INPUT` | 422 | ❌ | Malformed request body or missing required field |
| `MULTIPLE_INPUTS` | 422 | ❌ | More than one of `audio_url`/`script`/`scenes` provided |
| `AUDIO_TOO_LONG` | 422 | ❌ | Audio exceeds `MAX_AUDIO_DURATION` seconds |
| `UNSUPPORTED_FORMAT` | 415 | ❌ | Audio format not mp3/wav/m4a |
| `JOB_NOT_FOUND` | 404 | ❌ | `job_id` does not exist in the database |
| `TRANSCRIPTION_FAILED` | 500 | ✅ | Whisper could not transcribe the audio |
| `FOOTAGE_UNAVAILABLE` | 500 | ✅ | No stock clips found and fal.ai fallback failed |
| `RENDER_FAILED` | 500 | ✅ | FFmpeg exited with non-zero status |
| `UPSTREAM_RATE_LIMIT` | 429 | ✅ | Pexels/Pixabay/LLM rate limit hit; job will retry |
| `STORAGE_ERROR` | 500 | ✅ | MinIO upload failed |
| `IDEMPOTENCY_CONFLICT` | 409 | ❌ | Same `Idempotency-Key` used with different payload |

All error responses follow the envelope:
```json
{
  "error": {
    "code": "JOB_NOT_FOUND",
    "message": "No job with id '...' found.",
    "retryable": false,
    "details": {}
  }
}
```

---

## Hard Cases

The engine explicitly handles the following edge cases from the IncuBrix brief:

| # | Hard Case | How the Engine Handles It |
|---|---|---|
| 1 | **Very short scene (< 2 s)** | Scene is padded with a freeze-frame of the last clip frame; captions still display correctly |
| 2 | **Very long scene (> 30 s)** | Scene is split into sub-segments of ≤ 15 s, each getting its own B-roll clip, to avoid a single looping clip |
| 3 | **No matching stock footage** | Falls back to fal.ai Stable Video Diffusion generation using the scene's keyword prompt; if that also fails the placeholder "no footage" card is used |
| 4 | **Non-English audio** | Whisper auto-detects language; LLM keyword extraction prompt is language-aware; footage search uses English-translated keywords |
| 5 | **Audio with music / noise** | Whisper `--condition_on_previous_text False` and VAD filter reduce hallucination on noisy audio |
| 6 | **Script with no natural scene breaks** | LLM is prompted to split on semantic topic shifts, not punctuation alone; minimum scene duration enforced |
| 7 | **Multiple aspect ratios requested** | FFmpeg renders each ratio in a separate pass from the same source clips; captions are re-positioned per ratio |
| 8 | **Duplicate job submission** | `Idempotency-Key` header is checked against Redis; identical key returns the original `job_id` without re-processing |

---

## Notes

### Cold-Start Time
The first request after `docker compose up` may take longer while faster-whisper downloads the configured model. Subsequent requests reuse the cached model. For higher Indic quality, set `WHISPER_MODEL=large-v3-turbo` and provide a GPU-enabled deployment.

### Rate Limits
| Service | Free Tier Limit | Engine Behaviour |
|---|---|---|
| Pexels API | 200 req/hour | Automatic retry with exponential back-off; falls back to Pixabay |
| Pixabay API | 100 req/min | Same retry/fallback strategy |
| Gemini Flash | 60 req/min (free) | Retry with jitter; switch to `LLM_PROVIDER=openai` for higher limits |
| fal.ai | Per-API-key quota | Failure logs `FOOTAGE_UNAVAILABLE`; placeholder card inserted |
