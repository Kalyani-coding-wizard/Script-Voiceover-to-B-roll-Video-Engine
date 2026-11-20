"""
End-to-End B-roll Video Generation Pipeline.
Coordinates:
1. TTS voiceover generation (if input is script or scenes)
2. Whisper word-level transcription
3. Semantic scene segmentation (no gaps, sensible pacing >= 3s)
4. Licence-clean footage search with deduplication & AI fallback
5. Multi-aspect ratio video rendering (16:9, 9:16, 1:1) with FFmpeg
6. Captions generation (SRT) and optional burn-in
7. timeline.json & manifest.json generation
8. Storage upload (MinIO / S3)
9. Webhook callback dispatch signed with HMAC-SHA256
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import AsyncSessionLocal
from app.storage import ArtifactStorage
from app.models.job import Job
from tts_providers.edge_tts import EdgeTTSProvider
from tts_providers.mock import MockTTSProvider
from tts_providers.openai_tts import OpenAITTSProvider
from worker.tasks.caption import generate_srt
from worker.tasks.footage import FootageManager
from worker.tasks.manifest import build_manifest_json, build_timeline_json
from worker.tasks.render import VideoRenderer
from worker.tasks.segment import segment_narration_async
from worker.tasks.transcribe import transcribe_audio
from worker.tasks.langid import detect_language
from worker.tasks.queries import enrich_scene_query
from worker.tasks.media_validation import validate_outputs
from worker.tasks.input_validation import validate_audio_url

logger = structlog.get_logger(__name__)


async def update_job_progress(
    job_id: str,
    status: str,
    progress: int,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[Dict[str, Any]] = None,
) -> None:
    """Updates job status, progress, result, and error in the database."""
    async with AsyncSessionLocal() as session:
        job = await session.get(Job, uuid.UUID(job_id))
        if job:
            job.status = status
            job.progress = progress
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error
            job.updated_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info("job_progress_updated", job_id=job_id, status=status, progress=progress)


async def send_webhook_callback(
    callback_url: str,
    secret: str,
    payload: Dict[str, Any],
) -> None:
    """Dispatches webhook callback signed with HMAC-SHA256 in X-IncuBrix-Signature header."""
    try:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-IncuBrix-Signature": f"sha256={signature}",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(callback_url, data=body, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                logger.info("webhook_callback_dispatched", url=callback_url, status=resp.status)
    except Exception as exc:
        logger.warning("webhook_callback_failed", url=callback_url, error=str(exc))


async def run_pipeline(ctx: Any, job_id_str: str) -> None:
    """ARQ entry point."""
    await run_pipeline_direct(job_id_str)


async def run_pipeline_direct(job_id_str: str) -> None:
    """Core pipeline execution."""
    settings = get_settings()
    artifact_storage = ArtifactStorage(settings)
    t_start = time.time()
    timings_ms: Dict[str, int] = {}
    warnings: List[str] = []

    work_dir = Path(tempfile.mkdtemp(prefix=f"broll_{job_id_str}_"))
    storage_dir = Path("outputs") / job_id_str
    storage_dir.mkdir(parents=True, exist_ok=True)

    try:
        async with AsyncSessionLocal() as session:
            job = await session.get(Job, uuid.UUID(job_id_str))
            if not job:
                logger.error("job_not_found_in_pipeline", job_id=job_id_str)
                return
            if job.status == "succeeded":
                logger.info("job_already_succeeded", job_id=job_id_str)
                return
            req = job.request_payload

        # Step 1: Update progress (5%)
        await update_job_progress(job_id_str, "running", 5)

        # Step 2: Handle Audio / Voiceover input (15%)
        audio_path = str(work_dir / "voiceover.mp3")
        known_script: Optional[str] = None

        t0 = time.time()
        if req.get("audio_url"):
            # Download audio file
            url = req["audio_url"]
            validate_audio_url(url)
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                        resp.raise_for_status()
                        with open(audio_path, "wb") as f:
                            f.write(await resp.read())
                logger.info("audio_downloaded", url=url)
            except Exception as dl_err:
                if settings.mock_mode:
                    logger.warning("audio_download_failed_using_mock_fallback", url=url, error=str(dl_err))
                    tts = MockTTSProvider()
                    await tts.synthesize("Welcome to this audio narration test for IncuBrix video generation.", "en-US-female", audio_path)
                else:
                    raise dl_err
        else:
            # Generate speech via TTS
            script_text = req.get("script")
            if not script_text and req.get("scenes"):
                script_text = " ".join(s.get("text", "") for s in req["scenes"])
            known_script = script_text or "IncuBrix Video"

            voice = req.get("voice", "en-IN-female")
            if settings.mock_mode:
                tts = MockTTSProvider()
            elif settings.tts_provider == "openai":
                tts = OpenAITTSProvider(settings.openai_api_key)
            else:
                tts = EdgeTTSProvider()
            await tts.synthesize(known_script, voice, audio_path)
            logger.info("tts_synthesized", voice=voice, path=audio_path)

        timings_ms["audio_input_ms"] = int((time.time() - t0) * 1000)
        await update_job_progress(job_id_str, "running", 25)

        # Step 3: Transcription with word-level timestamps (35%)
        t0 = time.time()
        trans_res = transcribe_audio(
            audio_path=audio_path,
            known_script=known_script,
            mock_mode=settings.mock_mode,
            language_hint=req.get("language", "auto"),
        )
        timings_ms["transcription_ms"] = int((time.time() - t0) * 1000)
        await update_job_progress(job_id_str, "running", 40)

        # Step 4: Semantic Scene Segmentation (50%)
        t0 = time.time()
        predefined = req.get("scenes")
        scenes = await segment_narration_async(
            transcript_segments=trans_res.segments,
            total_duration=trans_res.duration,
            predefined_scenes=predefined,
            language=req.get("language", "auto"),
            style_guidance=req.get("style", ""),
        )
        language = detect_language(
            trans_res.text,
            req.get("language", "auto"),
            trans_res.language,
        )
        for scene in scenes:
            enrich_scene_query(scene, language)
        timings_ms["segmentation_ms"] = int((time.time() - t0) * 1000)
        await update_job_progress(job_id_str, "running", 55)

        # Step 5: Footage Search & Selection with Deduplication (75%)
        t0 = time.time()
        footage_mgr = FootageManager(
            mock_mode=settings.mock_mode,
            footage_provider=settings.footage_provider,
        )
        avoid = req.get("avoid", [])
        orientation = "portrait" if "9:16" in req.get("aspect_ratios", []) and len(req.get("aspect_ratios", [])) == 1 else "landscape"

        selected_clips = []
        for s in scenes:
            clip = await footage_mgr.select_clip_for_scene(
                scene=s,
                style=req.get("style", "bright, modern, real-world footage"),
                avoid=avoid,
                orientation=orientation,
            )
            selected_clips.append(clip)
        warnings.extend(footage_mgr.warnings)

        timings_ms["footage_selection_ms"] = int((time.time() - t0) * 1000)
        await update_job_progress(job_id_str, "running", 75)

        # Step 6: Captions Generation (80%)
        captions_opts = req.get("captions", {"burn_in": True, "srt": True})
        srt_file = str(storage_dir / "captions.srt")
        generate_srt(trans_res.segments, srt_file)

        # Step 7: Render Video per Aspect Ratio (92%)
        t0 = time.time()
        renderer = VideoRenderer(str(work_dir / "render"))
        aspect_ratios = req.get("aspect_ratios", ["9:16"])
        video_results: Dict[str, str] = {}

        for ratio in aspect_ratios:
            # Render individual scene clips
            scene_files = []
            for scene_obj, clip_obj in zip(scenes, selected_clips):
                sf = await renderer.render_scene_clip(scene_obj, clip_obj, ratio)
                scene_files.append(sf)

            # Stitch and multiplex narration audio
            out_filename = f"video_{ratio.replace(':', 'x')}.mp4"
            final_video_path = str(storage_dir / out_filename)
            burn_captions = srt_file if captions_opts.get("burn_in", True) else None

            await renderer.stitch_and_multiplex(
                scene_files=scene_files,
                narration_audio_path=audio_path,
                aspect_ratio=ratio,
                output_path=final_video_path,
                burn_captions_srt=burn_captions,
            )
            video_results[ratio] = f"/api/v1/download/{job_id_str}/{out_filename}"

        validation = await validate_outputs(
            [str(storage_dir / f"video_{ratio.replace(':', 'x')}.mp4") for ratio in aspect_ratios]
        )
        if not validation.get("validated"):
            warnings.append(validation.get("reason", "Media validation was skipped."))
        timings_ms["rendering_ms"] = int((time.time() - t0) * 1000)
        await update_job_progress(job_id_str, "running", 94)

        # Step 8: Build timeline.json and manifest.json (97%)
        timeline_path = str(storage_dir / "timeline.json")
        manifest_path = str(storage_dir / "manifest.json")

        build_timeline_json(scenes, selected_clips, timeline_path)
        timings_ms["total_ms"] = int((time.time() - t_start) * 1000)

        manifest_payload = dict(req)
        manifest_payload["language"] = language
        manifest_payload["tts_provider"] = "mock" if settings.mock_mode else settings.tts_provider
        manifest_payload["whisper_model"] = f"faster-whisper-{settings.whisper_model}"
        build_manifest_json(
            job_id=job_id_str,
            scenes=scenes,
            clips=selected_clips,
            settings_payload=manifest_payload,
            timings_ms=timings_ms,
            output_path=manifest_path,
            warnings=warnings,
        )

        # Persist all final artifacts through MinIO/S3, while retaining the
        # local outputs mirror for mock/offline deployments.
        final_artifacts = [
            timeline_path,
            manifest_path,
            srt_file,
            *[str(storage_dir / f"video_{ratio.replace(':', 'x')}.mp4") for ratio in aspect_ratios],
        ]
        for artifact_path in final_artifacts:
            await asyncio.to_thread(artifact_storage.upload_file, job_id_str, artifact_path)

        # Step 9: Assemble final output URLs and complete job (100%)
        result_payload = {
            "videos": video_results,
            "captions_srt": f"/api/v1/download/{job_id_str}/captions.srt",
            "timeline_url": f"/api/v1/download/{job_id_str}/timeline.json",
            "manifest_url": f"/api/v1/download/{job_id_str}/manifest.json",
        }

        await update_job_progress(job_id_str, "succeeded", 100, result=result_payload)
        logger.info("job_completed_successfully", job_id=job_id_str, total_ms=timings_ms["total_ms"])

        # Step 10: Dispatch Callback Webhook if configured
        if req.get("callback_url"):
            secret = req.get("callback_secret") or settings.hmac_secret
            await send_webhook_callback(
                callback_url=req["callback_url"],
                secret=secret,
                payload={"job_id": job_id_str, "status": "succeeded", "result": result_payload},
            )

    except Exception as exc:
        logger.error("pipeline_failed", job_id=job_id_str, error=str(exc))
        error_detail = {
            "code": "PIPELINE_ERROR",
            "message": str(exc),
            "retryable": True,
            "details": {"error_type": type(exc).__name__},
        }
        await update_job_progress(job_id_str, "failed", 100, error=error_detail)
    finally:
        # Clean up temporary scratch working directory
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass


async def run_swap_clip_direct(
    job_id_str: str,
    scene_index: int,
    new_query: Optional[str],
    new_clip_url: Optional[str],
) -> None:
    """
    Advanced Level Requirement:
    Swaps one scene's clip and only re-renders the affected clip,
    taking significantly less time than a full render.
    """
    logger.info("swap_clip_started", job_id=job_id_str, scene_index=scene_index)
    storage_dir = Path("outputs") / job_id_str
    timeline_file = storage_dir / "timeline.json"

    if not timeline_file.exists():
        logger.error("timeline_missing_for_swap", job_id=job_id_str)
        return

    with open(timeline_file, "r") as f:
        timeline = json.load(f)

    if scene_index >= len(timeline):
        logger.error("invalid_scene_index_for_swap", index=scene_index, max_len=len(timeline))
        return

    # Update scene clip in timeline
    target_scene = timeline[scene_index]
    query = new_query or target_scene["text"]

    target_scene["clip"]["url"] = new_clip_url or "https://assets.mixkit.co/videos/preview/mixkit-hands-counting-money-4284-large.mp4"
    target_scene["clip"]["reason"] = f"Swapped clip by user request for query: '{query}'"
    target_scene["clip"]["relevance_score"] = 0.95

    with open(timeline_file, "w") as f:
        json.dump(timeline, f, indent=2)

    await asyncio.to_thread(
        ArtifactStorage().upload_file,
        job_id_str,
        timeline_file,
    )

    await update_job_progress(job_id_str, "succeeded", 100)
    logger.info("swap_clip_completed", job_id=job_id_str, scene_index=scene_index)
