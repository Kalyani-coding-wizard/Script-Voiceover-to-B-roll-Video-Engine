# AI_USE.md — AI Coding Assistants & Model Usage Disclosure

In compliance with the IncuBrix Assessment guidelines, all AI tools and models utilized during system design, implementation, and testing are disclosed below.

---

## 1. AI Coding Assistants & Tools

| Tool / Assistant | Provider | Scope of Application |
|---|---|---|
| **Google Antigravity & Claude Sonnet 4.6 (Thinking)** | Google DeepMind / Anthropic | Initial architectural design, schema drafting, and task planning |
| **Gemini 3.8 Flash** | Google DeepMind | End-to-end code implementation, FFmpeg filter pipeline, test suites, and documentation |

---

## 2. Details of AI-Assisted Tasks

1. **System Architecture & Interface Design:**
   - Designed OpenAPI 3.1 specification for `/api/v1/broll/jobs` and `/api/v1/jobs/{job_id}`.
   - Structured the async database models using SQLAlchemy 2.0 with PostgreSQL and SQLite compatibility.

2. **Core Algorithm & Pipeline Implementation:**
   - Implemented the measurable rule logic for routing between stock footage and generative AI video.
   - Developed the temporal segmentation engine ensuring strict clause alignment without audio drift or sub-3-second micro-clips.
   - Created the FFmpeg normalisation and smart-cropping pipeline for `16:9`, `9:16`, and `1:1` video outputs.

3. **Test Suite & Tooling:**
   - Authored pytest test suites covering unit, integration, and end-to-end execution with 100% mock support (no API keys required).
   - Built the CLI batch runner (`batch/batch_runner.py`) for automated folder-based submission and verification.

---

## 3. Human Review & Verification Statement

All code, schemas, mathematical formulas, and Docker configurations generated with AI assistance were reviewed, verified, and debugged to guarantee full functionality, performance, and compliance with the IncuBrix Engineering Assessment specification.
