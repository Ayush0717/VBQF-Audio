from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class AudioData:
    samples: np.ndarray
    sample_rate: int
    duration_seconds: float


def load_audio(
    path: str | Path,
    target_sample_rate: int = 16_000,
    normalize: bool = True,
) -> AudioData:
    """Load WAV/MP3, convert to mono, resample, and optionally peak-normalize."""
    audio_path = Path(path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    try:
        import librosa
    except ImportError as exc:
        raise ImportError(
            "librosa is required for audio loading. Install requirements.txt first."
        ) from exc

    samples, sample_rate = librosa.load(
        str(audio_path),
        sr=target_sample_rate,
        mono=True,
    )
    samples = np.asarray(samples, dtype=np.float32)

    if normalize and samples.size:
        peak = float(np.max(np.abs(samples)))
        if peak > 0:
            samples = samples / peak

    duration = float(samples.size / target_sample_rate) if target_sample_rate else 0.0
    return AudioData(
        samples=samples, sample_rate=target_sample_rate, duration_seconds=duration
    )
