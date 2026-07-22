# import logging
# import traceback
# from concurrent.futures import ProcessPoolExecutor, as_completed
# from pathlib import Path
# import argparse
# import time
# import os


# import os
# import ssl

# # 1. Force Python, requests, and httpx to use your VM's secure system certificate store
# os.environ["REQUESTS_CA_BUNDLE"] = "/etc/ssl/certs/ca-certificates.crt"
# os.environ["SSL_CERT_FILE"] = "/etc/ssl/certs/ca-certificates.crt"
# os.environ["CURL_CA_BUNDLE"] = "/etc/ssl/certs/ca-certificates.crt"

# # 2. Inject the system trust store into the global SSL context
# try:
#     ssl._create_default_https_context = lambda: ssl.create_default_context(cafile="/etc/ssl/certs/ca-certificates.crt")
# except Exception:
#     pass

# # 3. Force standard HTTP traffic to bypass buggy Xet client roadblocks
# os.environ["HF_HUB_DISABLE_XET"] = "1"

# # 4. Embed your Hugging Face token permanently
# os.environ["HF_TOKEN"] = "YOUR_HF_TOKEN_HERE"


# # --- PYTORCH SECURITY OVERRIDE ---
# import torch
# # Force weights_only=False to allow loading legacy metadata structures from Pyannote
# original_torch_load = torch.load
# def patched_torch_load(*args, **kwargs):
#     if "weights_only" in kwargs:
#         kwargs["weights_only"] = False
#     return original_torch_load(*args, **kwargs)
# torch.load = patched_torch_load
# # ----------------------------------


# # --- TORCHAUDIO BACKEND MONKEYPATCH (BYPASS TORCHCODEC / FFMPEG) ---
# import torchaudio
# import soundfile as sf

# # 1. Custom load function using soundfile
# def patched_torchaudio_load(uri, frame_offset=0, num_frames=-1, normalize=True, channels_first=True, **kwargs):
#     start = frame_offset if frame_offset > 0 else 0
#     stop = start + num_frames if num_frames > 0 else None
#     dtype = 'float32' if normalize else 'int16'
    
#     data, samplerate = sf.read(uri, start=start, stop=stop, dtype=dtype)
#     tensor = torch.from_numpy(data)
    
#     if tensor.ndim == 1:
#         # Mono file, shape [frames] -> [frames, 1]
#         tensor = tensor.unsqueeze(1)
#     if channels_first:
#         # Transpose from soundfile [frames, channels] to torchaudio [channels, frames]
#         tensor = tensor.T
        
#     return tensor, samplerate

# # 2. Custom metadata class matching torchaudio standard
# class PatchedAudioMetaData:
#     def __init__(self, sample_rate, num_frames, num_channels, bits_per_sample, encoding):
#         self.sample_rate = sample_rate
#         self.num_frames = num_frames
#         self.num_channels = num_channels
#         self.bits_per_sample = bits_per_sample
#         self.encoding = encoding

# # 3. Custom info function using soundfile
# def patched_torchaudio_info(filepath, **kwargs):
#     sf_info = sf.info(filepath)
    
#     subtype = sf_info.subtype
#     bits_per_sample = 16
#     if "16" in subtype:
#         bits_per_sample = 16
#     elif "24" in subtype:
#         bits_per_sample = 24
#     elif "32" in subtype:
#         bits_per_sample = 32
#     elif "FLOAT" in subtype or "DOUBLE" in subtype:
#         bits_per_sample = 32
        
#     return PatchedAudioMetaData(
#         sample_rate=sf_info.samplerate,
#         num_frames=sf_info.frames,
#         num_channels=sf_info.channels,
#         bits_per_sample=bits_per_sample,
#         encoding=sf_info.subtype
#     )

# # Apply TorchAudio bypass
# torchaudio.load = patched_torchaudio_load
# torchaudio.info = patched_torchaudio_info
# torchaudio.AudioMetaData = PatchedAudioMetaData

# if not hasattr(torchaudio, "list_audio_backends"):
#     torchaudio.list_audio_backends = lambda: ["soundfile"]
# # ------------------------------------------------------------------


# import huggingface_hub
# import huggingface_hub.file_download

# # 5. Hugging Face patch for modern huggingface_hub compatibility
# def _patch_hf_download(module):
#     if hasattr(module, "hf_hub_download"):
#         orig_download = module.hf_hub_download
#         def patched_download(*args, **kwargs):
#             if "use_auth_token" in kwargs:
#                 kwargs["token"] = kwargs.pop("use_auth_token")
#             elif "token" not in kwargs:
#                 kwargs["token"] = os.environ.get("HF_TOKEN")
#             return orig_download(*args, **kwargs)
#         module.hf_hub_download = patched_download

# _patch_hf_download(huggingface_hub)
# _patch_hf_download(huggingface_hub.file_download)



# from config import DEFAULT_CONFIG
# from utils.logging import configure_logging


# def _process_single_file(audio_path_str: str, output_path_str: str) -> dict:
#     """
#     Worker function executed in each subprocess.
#     Each subprocess loads its own cached pipeline singleton (once per process)
#     and pre-builds extractors (once per process).
#     Returns a result dict with status, timing, and error info.
#     """
#     from app import process_audio
#     from config import DEFAULT_CONFIG
#     from extractors import build_extractors

#     audio_path = Path(audio_path_str)
#     output_path = Path(output_path_str)
#     result = {"file": audio_path.name, "status": "success", "elapsed": 0.0, "error": None}

#     # Build extractors once per process (cached in local scope across calls
#     # within the same process due to module-level import caching)
#     extractors = build_extractors(DEFAULT_CONFIG)

#     start_time = time.perf_counter()
#     try:
#         process_audio(
#             audio_path,
#             output_path=output_path,
#             config=DEFAULT_CONFIG,
#             extractors=extractors,
#         )
#         result["elapsed"] = time.perf_counter() - start_time
#     except Exception as e:
#         result["elapsed"] = time.perf_counter() - start_time
#         result["status"] = "failed"
#         result["error"] = f"{type(e).__name__}: {e}"

#     return result


# def main():
#     parser = argparse.ArgumentParser(description="Batch process audio files.")
#     parser.add_argument(
#         "--workers",
#         type=int,
#         default=None,
#         help="Number of parallel workers. Defaults to min(6, file_count). "
#              "Each worker loads its own pyannote model (~2-3 GB RAM).",
#     )
#     parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
#     args = parser.parse_args()

#     configure_logging(args.verbose)

#     # Find all wav files in data/audio
#     audio_dir = Path("data/audio")
#     audio_files = sorted(audio_dir.glob("*.wav"))

#     if not audio_files:
#         print(f"No .wav files found in {audio_dir.absolute()}")
#         return

#     print(f"Found {len(audio_files)} audio files to process.")

#     output_dir = Path("data/outputs")
#     output_dir.mkdir(parents=True, exist_ok=True)

#     # ── Determine worker count ────────────────────────────────────────────────
#     # VM specs: 16 vCPUs (8 cores × 2 threads), 64 GiB RAM
#     # Each pyannote worker needs ~2-3 GB RAM → safe limit ~6 workers (~18 GB)
#     # Leave headroom for OS + other processes
#     max_workers = args.workers or min(6, len(audio_files))
#     print(f"Using {max_workers} parallel worker(s).")

#     # ── Build work items ──────────────────────────────────────────────────────
#     work_items = []
#     for audio_path in audio_files:
#         output_path = output_dir / f"{audio_path.stem}_features.json"
#         work_items.append((str(audio_path), str(output_path)))

#     # ── Process in parallel ───────────────────────────────────────────────────
#     batch_start = time.perf_counter()
#     success_count = 0
#     fail_count = 0
#     results = []

#     if max_workers == 1:
#         # Sequential mode — no subprocess overhead
#         # Warm up diarization pipeline once in this process
#         print("\n⏳ Warming up diarization pipeline (one-time load)...")
#         warmup_start = time.perf_counter()
#         try:
#             from extractors.speaker.diarizer import warmup_pipeline
#             warmup_pipeline()
#             print(f"✅ Pipeline ready in {time.perf_counter() - warmup_start:.1f}s\n")
#         except Exception as e:
#             print(f"⚠️  Pipeline warmup failed: {e} (will retry per file)\n")

#         from app import process_audio
#         from extractors import build_extractors
#         extractors = build_extractors(DEFAULT_CONFIG)

#         for i, (audio_str, output_str) in enumerate(work_items, 1):
#             audio_name = Path(audio_str).name
#             print(f"[{i}/{len(work_items)}] Processing {audio_name}...")
#             start_time = time.perf_counter()
#             try:
#                 process_audio(
#                     audio_str,
#                     output_path=output_str,
#                     config=DEFAULT_CONFIG,
#                     extractors=extractors,
#                 )
#                 elapsed = time.perf_counter() - start_time
#                 print(f"  ✅ Done in {elapsed:.1f}s → {Path(output_str).name}")
#                 success_count += 1
#                 results.append({"file": audio_name, "elapsed": elapsed, "status": "success"})
#             except Exception as e:
#                 elapsed = time.perf_counter() - start_time
#                 print(f"  ❌ Failed in {elapsed:.1f}s — {e}")
#                 traceback.print_exc()
#                 fail_count += 1
#                 results.append({"file": audio_name, "elapsed": elapsed, "status": "failed"})
#     else:
#         # Parallel mode — each subprocess loads its own pipeline singleton
#         print(f"\n🚀 Launching {max_workers} workers (each loads pipeline once)...\n")

#         with ProcessPoolExecutor(max_workers=max_workers) as executor:
#             future_to_file = {}
#             for audio_str, output_str in work_items:
#                 future = executor.submit(_process_single_file, audio_str, output_str)
#                 future_to_file[future] = Path(audio_str).name

#             completed = 0
#             for future in as_completed(future_to_file):
#                 completed += 1
#                 file_name = future_to_file[future]
#                 try:
#                     result = future.result()
#                     results.append(result)
#                     if result["status"] == "success":
#                         success_count += 1
#                         print(f"  [{completed}/{len(work_items)}] ✅ {result['file']} — {result['elapsed']:.1f}s")
#                     else:
#                         fail_count += 1
#                         print(f"  [{completed}/{len(work_items)}] ❌ {result['file']} — {result['elapsed']:.1f}s — {result['error']}")
#                 except Exception as e:
#                     fail_count += 1
#                     print(f"  [{completed}/{len(work_items)}] ❌ {file_name} — Worker crashed: {e}")
#                     results.append({"file": file_name, "elapsed": 0, "status": "failed"})

#     batch_elapsed = time.perf_counter() - batch_start

#     # ── Summary ───────────────────────────────────────────────────────────────
#     print("\n" + "=" * 60)
#     print("  BATCH PROCESSING COMPLETE")
#     print("=" * 60)
#     print(f"  Total files:        {len(audio_files)}")
#     print(f"  Successful:         {success_count}")
#     print(f"  Failed:             {fail_count}")
#     print(f"  Workers used:       {max_workers}")
#     print(f"  Total wall time:    {batch_elapsed:.1f}s")
#     if results:
#         times = [r["elapsed"] for r in results if r["status"] == "success"]
#         if times:
#             sum_time = sum(times)
#             print(f"  Sum of file times:  {sum_time:.1f}s")
#             print(f"  Avg per file:       {sum_time / len(times):.1f}s")
#             print(f"  Speedup (parallel): {sum_time / batch_elapsed:.1f}x")
#     print("=" * 60)

#     # ── Generate consolidated CSV ─────────────────────────────────────────────
#     try:
#         from analytics.batch_csv_export import generate_batch_csv
#         print("\nGenerating batch CSV report...")
#         out_csv = generate_batch_csv()
#         print(f"✅ Master CSV created: {out_csv}")
#     except Exception as e:
#         print(f"❌ Failed to generate master CSV: {e}")
#         traceback.print_exc()


# if __name__ == "__main__":
#     main()

import os

# ── CPU Thread Control ────────────────────────────────────────────────────────
# CRITICAL: These MUST be set BEFORE torch/numpy are imported.
# VM: 16 vCPUs, 6 workers → 16 / 6 ≈ 2 threads per worker.
# Without this, every worker tries to use all 16 cores:
#   6 workers × 16 threads = 96 threads fighting for 16 cores → massive slowdown.
# With this, each worker cleanly owns 2 cores → 6 × 2 = 12 cores used, 4 for OS.
_THREADS_PER_WORKER = "2"
os.environ.setdefault("OMP_NUM_THREADS", _THREADS_PER_WORKER)
os.environ.setdefault("MKL_NUM_THREADS", _THREADS_PER_WORKER)
os.environ.setdefault("OPENBLAS_NUM_THREADS", _THREADS_PER_WORKER)
os.environ.setdefault("NUMEXPR_NUM_THREADS", _THREADS_PER_WORKER)
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", _THREADS_PER_WORKER)
# ─────────────────────────────────────────────────────────────────────────────

import argparse
import logging
import ssl
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


def apply_global_patches():
    """
    Applies environment configuration, PyTorch safety overrides,
    Audio backend bypasses, and Hugging Face API compatibility patches.
    MUST run in both the main process AND every subprocess worker.
    """
    # 1. Force Python, requests, and httpx to use VM secure system certificate store
    os.environ["REQUESTS_CA_BUNDLE"] = "/etc/ssl/certs/ca-certificates.crt"
    os.environ["SSL_CERT_FILE"] = "/etc/ssl/certs/ca-certificates.crt"
    os.environ["CURL_CA_BUNDLE"] = "/etc/ssl/certs/ca-certificates.crt"

    try:
        ssl._create_default_https_context = lambda: ssl.create_default_context(
            cafile="/etc/ssl/certs/ca-certificates.crt"
        )
    except Exception:
        pass

    # 2. Force standard HTTP traffic to bypass buggy Xet client roadblocks
    os.environ["HF_HUB_DISABLE_XET"] = "1"

    # 3. Embed your Hugging Face token (Ensure this is set or exported in your ENV)
    if "HF_TOKEN" not in os.environ:
        os.environ["HF_TOKEN"] = "YOUR_HF_TOKEN_HERE"

    # 4. PyTorch Security Override + Thread Control
    import torch

    # Belt-and-suspenders thread limit (in case env vars were set after torch import)
    torch.set_num_threads(int(_THREADS_PER_WORKER))
    torch.set_num_interop_threads(int(_THREADS_PER_WORKER))

    if not hasattr(torch, "_is_patched"):
        original_torch_load = torch.load

        def patched_torch_load(*args, **kwargs):
            if "weights_only" in kwargs:
                kwargs["weights_only"] = False
            return original_torch_load(*args, **kwargs)

        torch.load = patched_torch_load
        torch._is_patched = True

    # 5. Torchaudio Backend Bypass (uses soundfile to replace torchcodec/ffmpeg)
    import soundfile as sf
    import torchaudio

    def patched_torchaudio_load(
        uri, frame_offset=0, num_frames=-1, normalize=True, channels_first=True, **kwargs
    ):
        start = frame_offset if frame_offset > 0 else 0
        stop = start + num_frames if num_frames > 0 else None
        dtype = "float32" if normalize else "int16"

        data, samplerate = sf.read(uri, start=start, stop=stop, dtype=dtype)
        tensor = torch.from_numpy(data)

        if tensor.ndim == 1:
            tensor = tensor.unsqueeze(1)
        if channels_first:
            tensor = tensor.T

        return tensor, samplerate

    class PatchedAudioMetaData:
        def __init__(self, sample_rate, num_frames, num_channels, bits_per_sample, encoding):
            self.sample_rate = sample_rate
            self.num_frames = num_frames
            self.num_channels = num_channels
            self.bits_per_sample = bits_per_sample
            self.encoding = encoding

    def patched_torchaudio_info(filepath, **kwargs):
        sf_info = sf.info(filepath)
        subtype = sf_info.subtype
        bits_per_sample = 16
        if "16" in subtype:
            bits_per_sample = 16
        elif "24" in subtype:
            bits_per_sample = 24
        elif "32" in subtype:
            bits_per_sample = 32
        elif "FLOAT" in subtype or "DOUBLE" in subtype:
            bits_per_sample = 32

        return PatchedAudioMetaData(
            sample_rate=sf_info.samplerate,
            num_frames=sf_info.frames,
            num_channels=sf_info.channels,
            bits_per_sample=bits_per_sample,
            encoding=sf_info.subtype,
        )

    torchaudio.load = patched_torchaudio_load
    torchaudio.info = patched_torchaudio_info
    torchaudio.AudioMetaData = PatchedAudioMetaData

    if not hasattr(torchaudio, "list_audio_backends"):
        torchaudio.list_audio_backends = lambda: ["soundfile"]

    # 6. Hugging Face compatibility patch (Handles 'use_auth_token' vs 'token' API changes)
    import huggingface_hub
    import huggingface_hub.file_download

    def _patch_hf_download(module):
        if hasattr(module, "hf_hub_download"):
            orig_download = module.hf_hub_download

            def patched_download(*args, **kwargs):
                if "use_auth_token" in kwargs:
                    kwargs["token"] = kwargs.pop("use_auth_token")
                elif "token" not in kwargs:
                    kwargs["token"] = os.environ.get("HF_TOKEN")
                return orig_download(*args, **kwargs)

            module.hf_hub_download = patched_download

    _patch_hf_download(huggingface_hub)
    _patch_hf_download(huggingface_hub.file_download)


# Apply patches immediately for the main process
apply_global_patches()


def _worker_init():
    """Initializer function called when a new subprocess starts."""
    apply_global_patches()


# ── Per-worker extractor cache ───────────────────────────────────────────────
# build_extractors() creates 18 extractor objects. We cache them at module level
# so each worker process builds them exactly once across all files it processes.
_WORKER_EXTRACTORS = None


def _process_single_file(audio_path_str: str, output_path_str: str) -> dict:
    """Worker function executed in each subprocess."""
    global _WORKER_EXTRACTORS
    from app import process_audio
    from config import DEFAULT_CONFIG
    from extractors import build_extractors

    # Build extractors once per worker process (reused for all files this worker handles)
    if _WORKER_EXTRACTORS is None:
        _WORKER_EXTRACTORS = build_extractors(DEFAULT_CONFIG)

    audio_path = Path(audio_path_str)
    output_path = Path(output_path_str)
    result = {"file": audio_path.name, "status": "success", "elapsed": 0.0, "error": None}

    start_time = time.perf_counter()
    try:
        process_audio(
            audio_path,
            output_path=output_path,
            config=DEFAULT_CONFIG,
            extractors=_WORKER_EXTRACTORS,
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
        help="Number of parallel workers. Defaults to min(6, file_count).",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    args = parser.parse_args()

    from config import DEFAULT_CONFIG
    from utils.logging import configure_logging

    configure_logging(args.verbose)

    audio_dir = Path("data/audio")
    audio_files = sorted(audio_dir.glob("*.wav"))

    if not audio_files:
        print(f"No .wav files found in {audio_dir.absolute()}")
        return

    print(f"Found {len(audio_files)} audio files to process.")

    output_dir = Path("data/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)

    max_workers = args.workers or min(6, len(audio_files))
    print(f"Using {max_workers} parallel worker(s).")

    work_items = [
        (str(audio_path), str(output_dir / f"{audio_path.stem}_features.json"))
        for audio_path in audio_files
    ]

    batch_start = time.perf_counter()
    success_count = 0
    fail_count = 0
    results = []

    if max_workers == 1:
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
        print(f"\n🚀 Launching {max_workers} workers (each loads pipeline once)...\n")

        # Key Fix: Pass initializer=_worker_init to load patches in all workers
        with ProcessPoolExecutor(max_workers=max_workers, initializer=_worker_init) as executor:
            future_to_file = {
                executor.submit(_process_single_file, audio_str, output_str): Path(
                    audio_str
                ).name
                for audio_str, output_str in work_items
            }

            completed = 0
            for future in as_completed(future_to_file):
                completed += 1
                file_name = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)
                    if result["status"] == "success":
                        success_count += 1
                        print(
                            f"  [{completed}/{len(work_items)}] ✅ {result['file']} — {result['elapsed']:.1f}s"
                        )
                    else:
                        fail_count += 1
                        print(
                            f"  [{completed}/{len(work_items)}] ❌ {result['file']} — {result['elapsed']:.1f}s — {result['error']}"
                        )
                except Exception as e:
                    fail_count += 1
                    print(
                        f"  [{completed}/{len(work_items)}] ❌ {file_name} — Worker crashed: {e}"
                    )
                    results.append({"file": file_name, "elapsed": 0, "status": "failed"})

    batch_elapsed = time.perf_counter() - batch_start

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