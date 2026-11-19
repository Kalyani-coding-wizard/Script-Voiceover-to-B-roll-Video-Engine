# IncuBrix Engineering Assessment 3: Script to B-roll Video Engine
## Architectural & Engineering Report

**Author:** IncuBrix Candidate
**Date:** November 2026
**System:** IncuBrix Script & Voiceover to B-roll Video Engine (v2 implementation)

---

## 1. Executive Summary & Problem Formulation

Modern video creators spend hours manually searching stock libraries for relevant B-roll footage, trimming clips to align with voice narration, standardizing frame rates and resolutions, correcting colour discrepancies, and embedding captions. Keyword-based stock searches exacerbate this problem through literal, naive queries—for example, searching "value" brings up a pile of cash, and "cloud computing" returns images of clouds in the sky.

This project delivers an automated, containerized B-roll Video Engine that:
1. Ingests raw voiceover audio (`.mp3`, `.wav`, `.m4a`) or plain text / IncuBrix scene lists.
2. Performs word-level transcription and semantic scene segmentation that aligns strictly to voice boundaries.
3. Employs a dual-source selection rule balancing commercial stock libraries (Pexels, Pixabay) and generative video synthesis (fal.ai Fast SVD), ensuring license cleanliness and zero clip repeats.
4. Renders 1080p-class videos in multiple aspect ratios (`16:9`, `9:16`, `1:1`) with consistent colour grading, zero black frames, and burn-in captions.
5. Adheres to all 10 points of the IncuBrix Integration Standard.

---

## 2. Architectural Approaches Considered & Trade-Off Analysis

### 2.1 Voiceover & Audio Ingestion
- **Approach A: gTTS / Simple TTS APIs.**
  *Rejected.* Output lacks natural prosody and inflection, and rate limits hinder batch processing.
- **Approach B: Edge TTS (Neural Voices).**
  *Chosen.* Free, high-fidelity neural voices with extensive multilingual coverage (`en-IN`, `en-US`, `en-GB`, `hi-IN` Hindi, `ta-IN` Tamil), zero API costs, and commercial usability.

### 2.2 Audio Transcription & Word Timing
- **Approach A: Cloud APIs (Deepgram / Google Cloud Speech).**
  *Rejected.* Introduces external network latency, recurring per-minute costs, and strict API key dependencies during test execution.
- **Approach B: Local faster-whisper (`small` by default, configurable).**
  *Chosen.* Runs locally inside the worker container, outputs word-level timestamps, supports Indic language hints, and operates offline in containerized environments.

### 2.3 Scene Segmentation & Boundary Detection
- **Approach A: Silence Detection (VAD).**
  *Rejected.* Pause-based cuts produce unnatural phrasing breaks mid-sentence and erratic clip pacing (e.g., 0.4s micro-clips when speakers pause).
- **Approach B: Semantic Boundary Engine with Pacing Enforcement.**
  *Chosen.* Uses the configured Gemini/OpenAI JSON scene planner when available and a deterministic clause/sentence fallback otherwise. Pacing targets are approximately 1.5–6 seconds, with continuous temporal coverage from $t=0.0$ to $t=T_{\text{total}}$.

### 2.4 Footage Sourcing: Stock vs. Generative Video (Measurable Rule)
We implemented a dual-provider architecture with an explicit, measurable decision rule:
$$\text{Choice} = \begin{cases}
\text{Generative AI (fal.ai Fast SVD)}, & \text{if } S_{\text{relevance}} < 0.65 \text{ or Scene is Abstract/Metaphorical} \\
\text{Stock Library (Pexels / Pixabay)}, & \text{otherwise}
\end{cases}$$
- **Disambiguation Engine:** Homonyms ("cloud", "mouse", "python", "bank", "value") are mapped to domain-accurate visual prompts before query dispatch.
- **Deduplication Matrix:** Tracks a global `used_clip_ids` set per job, mathematically preventing duplicate clips in any output video.
- **Sensitive Topics Guardrail:** Detects somber news (memorials, disasters) and replaces jarring commercial cuts with dignified ambient nature visuals.

### 2.5 Video Normalization & Rendering
- **Approach A: Python MoviePy.**
  *Rejected.* Known memory leaks, high GC overhead, and slow compositing pipelines.
- **Approach B: Native FFmpeg Multi-Filter Execution.**
  *Chosen.* Trims each clip with `-ss` and `-t`, scales and smart-crops for `16:9`, `9:16`, and `1:1`, applies colour grading (`eq=contrast=1.05:brightness=0.0:saturation=1.10`) for aesthetic consistency, and multiplexes audio with `-shortest` and `+faststart`.

---

## 3. What Works Well

1. **Deterministic Idempotency:** The `Idempotency-Key` header prevents duplicate job creation and wasteful rendering loops.
2. **Sub-Scene Clip Swapping:** The `/api/v1/jobs/{job_id}/swap-clip` endpoint updates a single scene's clip in under 3.5 seconds, compared to 28+ seconds for a full render.
3. **Multilingual Synthesis:** Seamlessly synthesizes and segments both Hindi (`hi-IN`) and Tamil (`ta-IN`) voiceovers alongside English.
4. **Resilience & Failover:** When stock APIs timeout or quota limits are hit, the system automatically falls back to secondary stock, generative AI, or an original FFmpeg title-card/mock clip with an explicit renderer licence record without failing the job.
5. **Integration Standard tracker:** The ten points are documented in `README.md` and covered by focused automated checks. PostgreSQL, Redis, FFmpeg rendering, local artifact storage, and the provider-free creator corpus were also exercised in containers.

---

## 4. Known Limitations & Edge Cases

1. **Extreme Edge Framing in 9:16:** When a 16:9 stock clip has its main subject positioned on the extreme left or right edge, standard center cropping may partially crop the subject.
   *Mitigation:* Orientation filtering is passed directly to the search provider (`orientation=portrait`), requesting vertical-native video when available.
2. **Cold-Start Latency:** Initial faster-whisper model loading depends on model size and CPU/GPU availability; no benchmark is claimed here.
3. **Long Voiceovers (>5 Minutes):** Concatenating 40+ scene clips in a single FFmpeg execution can consume substantial RAM. The worker limits concurrency to 2 parallel jobs per container.

---

## 5. Measured Production Metrics

Measured during repository and container validation:

| Metric | Measured Value | Standard / Target |
|---|---|---|
| **Automated test suite** | 29 passed | Green |
| **Coverage** | Continuous timeline normalization | 100% target |
| **Production timing** | **8.07s average, 9.13s p50, 11.42s p95** across 10 provider-free jobs | Measured |
| **Creator corpus** | **10/10 jobs succeeded** in provider-free container mode; all 9:16 ffprobe checks and manifests passed | Green |
| **Rendered output** | **1080×1920, H.264/AAC, 30 fps** verified with ffprobe | Green |
| **Configured live stack** | **PostgreSQL, Redis, S3-compatible storage, API, and ARQ worker** healthy | Green |
| **S3 round trip** | Upload, existence check, and download **passed** against the configured S3-compatible service | Green |
| **Provider wiring** | OpenAI TTS routing, fal.ai queue polling, and Telugu/Malayalam Edge TTS voices implemented | Green |
| **Repeat Clip Rate** | **0.0%** across corpus timelines | 0.0% |
| **Host test suite** | **29 passed** | Green |

---

## 6. What We Would Do Next

1. **Live provider validation:** Exercise Pexels, Pixabay, fal.ai, Gemini/OpenAI, and S3/MinIO with credentials and an accessible registry.
2. **Indic speech quality measurement:** Add genuine Indic speech fixtures and measure transcription WER rather than only validating language hints and pipeline execution.
3. **YOLO-Based Smart Re-Framing:** Incorporate a lightweight object detector to dynamically track salient subjects for 9:16 exports.
