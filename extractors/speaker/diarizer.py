from __future__ import annotations

import logging
import os
import time
import torch
from typing import Any
from pathlib import Path

# Try to import pyannote.audio
try:
    from pyannote.audio import Pipeline
except ImportError as exc:
    raise ImportError(
        "pyannote.audio is required for speaker diarization. Please install it first: pip install pyannote.audio"
    ) from exc

LOGGER = logging.getLogger(__name__)

# ── Singleton pipeline cache ─────────────────────────────────────────────────
# The pyannote model is ~500MB and takes 10-30s to load. By caching it as a
# module-level singleton we pay the cost ONCE per process, not once per file.
_CACHED_PIPELINE: Pipeline | None = None


def _get_pipeline(hf_token: str | None = None) -> Pipeline:
    """Return the cached pyannote pipeline, loading it on first call."""
    global _CACHED_PIPELINE

    if _CACHED_PIPELINE is not None:
        return _CACHED_PIPELINE

    token = hf_token or os.environ.get(
        "HF_TOKEN", "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"
    )

    if not token:
        raise ValueError(
            "A Hugging Face token is required to download the pyannote.audio model. Set HF_TOKEN environment variable."
        )

    LOGGER.info("Initializing Pyannote Speaker Diarization Pipeline (one-time load)...")
    load_start = time.perf_counter()
    try:
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1", use_auth_token=token
        )
    except Exception as e:
        LOGGER.error(
            "Failed to load pyannote pipeline. Make sure your Hugging Face token is valid and you have accepted the user conditions for pyannote/speaker-diarization-3.1 and pyannote/segmentation-3.0 on huggingface.co."
        )
        raise e

    # Send pipeline to GPU if available
    if torch.cuda.is_available():
        pipeline.to(torch.device("cuda"))
    elif torch.backends.mps.is_available():
        pipeline.to(torch.device("mps"))

    load_elapsed = time.perf_counter() - load_start
    LOGGER.info("Pyannote pipeline loaded in %.1fs (cached for reuse)", load_elapsed)

    _CACHED_PIPELINE = pipeline
    return _CACHED_PIPELINE


def warmup_pipeline(hf_token: str | None = None) -> None:
    """Pre-load the diarization pipeline so the first file doesn't pay the cost.
    Call this once before starting a batch loop."""
    _get_pipeline(hf_token)


def diarize_audio(
    audio_path: str | Path, num_speakers: int | None = None, hf_token: str | None = None
) -> list[dict[str, Any]]:
    """
    Performs speaker diarization directly on the source audio file using pyannote.audio.
    Returns a list of continuous speaker segments.
    """
    pipeline = _get_pipeline(hf_token)

    if num_speakers is not None:
        LOGGER.info(
            f"Running diarization on {audio_path} (expecting exactly {num_speakers} speakers)..."
        )
        diarization = pipeline(str(audio_path), num_speakers=num_speakers)
    else:
        LOGGER.info(
            f"Running diarization on {audio_path} (auto-detecting speaker count)..."
        )
        diarization = pipeline(str(audio_path))

    segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        duration = turn.end - turn.start
        # Map SPEAKER_00 to Speaker 0, etc.
        clean_speaker = str(speaker).replace("SPEAKER_", "Speaker ")
        if clean_speaker.startswith("Speaker ") and clean_speaker[8:].isdigit():
            clean_speaker = f"Speaker {int(clean_speaker[8:])}"

        segments.append(
            {
                "speaker": clean_speaker,
                "start": round(turn.start, 3),
                "end": round(turn.end, 3),
                "duration": round(duration, 3),
            }
        )

    LOGGER.info(f"Successfully extracted {len(segments)} continuous speaker segments.")
    return segments
