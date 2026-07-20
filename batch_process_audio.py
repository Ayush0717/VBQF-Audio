import logging
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import argparse
import time
import os

from config import DEFAULT_CONFIG
from utils.logging import configure_logging


def _process_single_file(audio_path_str: str, output_path_str: str) -> dict:
    """
    Worker function executed in each subprocess.
    Each subprocess loads its own cached pipeline singleton (once per process)
    and pre-builds extractors (once per process).
    Returns a result dict with status, timing, and error info.
    """
    from app import process_audio
    from config import DEFAULT_CONFIG
    from extractors import build_extractors

    audio_path = Path(audio_path_str)
    output_path = Path(output_path_str)
    result = {"file": audio_path.name, "status": "success", "elapsed": 0.0, "error": None}

    # Build extractors once per process (cached in local scope across calls
    # within the same process due to module-level import caching)
    extractors = build_extractors(DEFAULT_CONFIG)

    start_time = time.perf_counter()
    try:
        process_audio(
            audio_path,
            output_path=output_path,
            config=DEFAULT_CONFIG,
            extractors=extractors,
        )
        result["elapsed"] = time.perf_counter() - start_time
    except Exception as e:
        result["elapsed"] = time.perf_counter() - start_time
        result["status"] = "failed"
        result["error"] = f"{type(e).__name__}: {e}"

    return result


def main():
    parser = argparse.ArgumentParser(description="Batch process audio files.")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of parallel workers. Defaults to min(6, file_count). "
             "Each worker loads its own pyannote model (~2-3 GB RAM).",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    args = parser.parse_args()

    configure_logging(args.verbose)

    # Find all wav files in data/audio
    audio_dir = Path("data/audio")
    audio_files = sorted(audio_dir.glob("*.wav"))

    if not audio_files:
        print(f"No .wav files found in {audio_dir.absolute()}")
        return

    print(f"Found {len(audio_files)} audio files to process.")

    output_dir = Path("data/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Determine worker count ────────────────────────────────────────────────
    # VM specs: 16 vCPUs (8 cores × 2 threads), 64 GiB RAM
    # Each pyannote worker needs ~2-3 GB RAM → safe limit ~6 workers (~18 GB)
    # Leave headroom for OS + other processes
    max_workers = args.workers or min(6, len(audio_files))
    print(f"Using {max_workers} parallel worker(s).")

    # ── Build work items ──────────────────────────────────────────────────────
    work_items = []
    for audio_path in audio_files:
        output_path = output_dir / f"{audio_path.stem}_features.json"
        work_items.append((str(audio_path), str(output_path)))

    # ── Process in parallel ───────────────────────────────────────────────────
    batch_start = time.perf_counter()
    success_count = 0
    fail_count = 0
    results = []

    if max_workers == 1:
        # Sequential mode — no subprocess overhead
        # Warm up diarization pipeline once in this process
        print("\n⏳ Warming up diarization pipeline (one-time load)...")
        warmup_start = time.perf_counter()
        try:
            from extractors.speaker.diarizer import warmup_pipeline
            warmup_pipeline()
            print(f"✅ Pipeline ready in {time.perf_counter() - warmup_start:.1f}s\n")
        except Exception as e:
            print(f"⚠️  Pipeline warmup failed: {e} (will retry per file)\n")

        from app import process_audio
        from extractors import build_extractors
        extractors = build_extractors(DEFAULT_CONFIG)

        for i, (audio_str, output_str) in enumerate(work_items, 1):
            audio_name = Path(audio_str).name
            print(f"[{i}/{len(work_items)}] Processing {audio_name}...")
            start_time = time.perf_counter()
            try:
                process_audio(
                    audio_str,
                    output_path=output_str,
                    config=DEFAULT_CONFIG,
                    extractors=extractors,
                )
                elapsed = time.perf_counter() - start_time
                print(f"  ✅ Done in {elapsed:.1f}s → {Path(output_str).name}")
                success_count += 1
                results.append({"file": audio_name, "elapsed": elapsed, "status": "success"})
            except Exception as e:
                elapsed = time.perf_counter() - start_time
                print(f"  ❌ Failed in {elapsed:.1f}s — {e}")
                traceback.print_exc()
                fail_count += 1
                results.append({"file": audio_name, "elapsed": elapsed, "status": "failed"})
    else:
        # Parallel mode — each subprocess loads its own pipeline singleton
        print(f"\n🚀 Launching {max_workers} workers (each loads pipeline once)...\n")

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {}
            for audio_str, output_str in work_items:
                future = executor.submit(_process_single_file, audio_str, output_str)
                future_to_file[future] = Path(audio_str).name

            completed = 0
            for future in as_completed(future_to_file):
                completed += 1
                file_name = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)
                    if result["status"] == "success":
                        success_count += 1
                        print(f"  [{completed}/{len(work_items)}] ✅ {result['file']} — {result['elapsed']:.1f}s")
                    else:
                        fail_count += 1
                        print(f"  [{completed}/{len(work_items)}] ❌ {result['file']} — {result['elapsed']:.1f}s — {result['error']}")
                except Exception as e:
                    fail_count += 1
                    print(f"  [{completed}/{len(work_items)}] ❌ {file_name} — Worker crashed: {e}")
                    results.append({"file": file_name, "elapsed": 0, "status": "failed"})

    batch_elapsed = time.perf_counter() - batch_start

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  BATCH PROCESSING COMPLETE")
    print("=" * 60)
    print(f"  Total files:        {len(audio_files)}")
    print(f"  Successful:         {success_count}")
    print(f"  Failed:             {fail_count}")
    print(f"  Workers used:       {max_workers}")
    print(f"  Total wall time:    {batch_elapsed:.1f}s")
    if results:
        times = [r["elapsed"] for r in results if r["status"] == "success"]
        if times:
            sum_time = sum(times)
            print(f"  Sum of file times:  {sum_time:.1f}s")
            print(f"  Avg per file:       {sum_time / len(times):.1f}s")
            print(f"  Speedup (parallel): {sum_time / batch_elapsed:.1f}x")
    print("=" * 60)

    # ── Generate consolidated CSV ─────────────────────────────────────────────
    try:
        from analytics.batch_csv_export import generate_batch_csv
        print("\nGenerating batch CSV report...")
        out_csv = generate_batch_csv()
        print(f"✅ Master CSV created: {out_csv}")
    except Exception as e:
        print(f"❌ Failed to generate master CSV: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()

