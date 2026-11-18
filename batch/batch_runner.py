"""
Batch Runner CLI Tool (Integration Standard Point 10).
Runs a folder or file of test inputs against the IncuBrix B-roll API
and writes all resulting artifacts and a summary.json report to a target folder.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

import httpx


async def run_single_job(
    client: httpx.AsyncClient,
    base_url: str,
    input_file: Path,
    output_dir: Path,
    poll_interval: float = 2.0,
    timeout: float = 300.0,
) -> Dict[str, Any]:
    """Processes a single input JSON file through the B-roll API."""
    print(f"\n[+] Processing: {input_file.name}")
    t0 = time.time()

    with open(input_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    idempotency_key = f"batch_{input_file.stem}_{uuid.uuid4().hex[:8]}"
    headers = {
        "Idempotency-Key": idempotency_key,
        "Content-Type": "application/json",
    }

    # 1. Submit Job
    post_url = f"{base_url.rstrip('/')}/api/v1/broll/jobs"
    try:
        resp = await client.post(post_url, json=payload, headers=headers, timeout=30.0)
    except Exception as exc:
        print(f"[-] Submission failed for {input_file.name}: {exc}")
        return {
            "file": input_file.name,
            "status": "failed",
            "error": str(exc),
            "duration_seconds": round(time.time() - t0, 2),
        }

    if resp.status_code not in (200, 202):
        print(f"[-] API error ({resp.status_code}): {resp.text}")
        return {
            "file": input_file.name,
            "status": "failed",
            "http_status": resp.status_code,
            "error": resp.text,
            "duration_seconds": round(time.time() - t0, 2),
        }

    job_data = resp.json()
    job_id = job_data.get("job_id")
    print(f"    Job ID: {job_id} (queued)")

    # 2. Poll until completion or timeout
    status_url = f"{base_url.rstrip('/')}/api/v1/jobs/{job_id}"
    final_status = "unknown"
    job_result: Dict[str, Any] = {}
    job_error: Any = None

    start_poll = time.time()
    while time.time() - start_poll < timeout:
        await asyncio.sleep(poll_interval)
        try:
            status_resp = await client.get(status_url, timeout=10.0)
            if status_resp.status_code == 200:
                s_data = status_resp.json()
                final_status = s_data.get("status")
                progress = s_data.get("progress", 0)
                print(f"    Status: {final_status} ({progress}%)", end="\r")

                if final_status in ("succeeded", "failed"):
                    job_result = s_data.get("result") or {}
                    job_error = s_data.get("error")
                    break
        except Exception as exc:
            print(f"\n    Polling warning: {exc}")

    print()  # newline after \r
    elapsed = round(time.time() - t0, 2)

    if final_status != "succeeded":
        print(f"[-] Job {job_id} did not succeed. Final status: {final_status}")
        return {
            "file": input_file.name,
            "job_id": job_id,
            "status": final_status,
            "error": job_error,
            "duration_seconds": elapsed,
        }

    # 3. Download results to output folder
    job_output_dir = output_dir / f"job_{job_id}"
    job_output_dir.mkdir(parents=True, exist_ok=True)

    downloaded_files: List[str] = []
    download_targets = []

    # Collect video downloads
    for ratio, v_url in (job_result.get("videos") or {}).items():
        download_targets.append((f"video_{ratio.replace(':', 'x')}.mp4", v_url))

    if job_result.get("captions_srt"):
        download_targets.append(("captions.srt", job_result["captions_srt"]))
    if job_result.get("timeline_url"):
        download_targets.append(("timeline.json", job_result["timeline_url"]))
    if job_result.get("manifest_url"):
        download_targets.append(("manifest.json", job_result["manifest_url"]))

    for fname, rel_url in download_targets:
        full_url = f"{base_url.rstrip('/')}{rel_url}" if rel_url.startswith("/") else rel_url
        try:
            dl_resp = await client.get(full_url, timeout=30.0)
            if dl_resp.status_code == 200:
                out_file_path = job_output_dir / fname
                with open(out_file_path, "wb") as f:
                    f.write(dl_resp.content)
                downloaded_files.append(fname)
        except Exception as exc:
            print(f"    Warning: failed to download {fname}: {exc}")

    print(f"[✓] Completed {input_file.name} in {elapsed}s (saved {len(downloaded_files)} files to {job_output_dir.name})")

    return {
        "file": input_file.name,
        "job_id": job_id,
        "status": "succeeded",
        "duration_seconds": elapsed,
        "artifacts_downloaded": downloaded_files,
        "output_directory": str(job_output_dir),
    }


async def main_async(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    if input_path.is_file():
        input_files = [input_path]
    elif input_path.is_dir():
        input_files = sorted(list(input_path.glob("*.json")))
    else:
        print(f"Error: input path '{args.input}' does not exist.")
        return 1

    if not input_files:
        print(f"No JSON input files found in '{args.input}'.")
        return 1

    print(f"==================================================")
    print(f" IncuBrix Batch Runner — Processing {len(input_files)} inputs")
    print(f" Base URL: {args.base_url}")
    print(f" Output Folder: {output_path.resolve()}")
    print(f"==================================================")

    results: List[Dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        for f in input_files:
            res = await run_single_job(
                client=client,
                base_url=args.base_url,
                input_file=f,
                output_dir=output_path,
                poll_interval=args.poll_interval,
                timeout=args.timeout,
            )
            results.append(res)

    # Save summary report
    summary_path = output_path / "summary.json"
    summary_report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_inputs": len(input_files),
        "succeeded": sum(1 for r in results if r.get("status") == "succeeded"),
        "failed": sum(1 for r in results if r.get("status") != "succeeded"),
        "results": results,
    }

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_report, f, indent=2)

    print(f"\n==================================================")
    print(f" Batch Complete: {summary_report['succeeded']}/{len(input_files)} succeeded.")
    print(f" Summary saved to: {summary_path}")
    print(f"==================================================")

    return 0 if summary_report["failed"] == 0 else 1


def main():
    parser = argparse.ArgumentParser(description="IncuBrix B-roll Engine Batch Runner")
    parser.add_argument("--input", "-i", required=True, help="Input file or directory of JSON test files")
    parser.add_argument("--output", "-o", default="./batch_results", help="Directory to save output artifacts")
    parser.add_argument("--base-url", "-u", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Status polling interval in seconds")
    parser.add_argument("--timeout", type=float, default=300.0, help="Per-job timeout in seconds")

    args = parser.parse_args()
    sys.exit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
