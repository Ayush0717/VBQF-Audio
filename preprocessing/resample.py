from __future__ import annotations

import numpy as np


def resample_audio(
    samples: np.ndarray, original_rate: int, target_rate: int
) -> np.ndarray:
    if original_rate == target_rate:
        return samples.astype(np.float32, copy=False)

    try:
        import librosa
    except ImportError as exc:
        raise ImportError("librosa is required for resampling.") from exc

    return librosa.resample(
        samples.astype(np.float32, copy=False),
        orig_sr=original_rate,
        target_sr=target_rate,
    ).astype(np.float32, copy=False)
