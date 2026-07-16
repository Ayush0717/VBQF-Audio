from __future__ import annotations

import logging
import os
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


def diarize_audio(
    audio_path: str | Path, num_speakers: int | None = None, hf_token: str | None = None
) -> list[dict[str, Any]]:
    """
    Performs speaker diarization directly on the source audio file using pyannote.audio.
    Returns a list of continuous speaker segments.
    """
    # Use provided token, or fall back to environment variable, or finally use a hardcoded default (for convenience in this session)
    token = hf_token or os.environ.get(
        "HF_TOKEN", "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"
    )

    if not token:
        raise ValueError(
            "A Hugging Face token is required to download the pyannote.audio model. Set HF_TOKEN environment variable."
        )

    LOGGER.info("Initializing Pyannote Speaker Diarization Pipeline...")
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
