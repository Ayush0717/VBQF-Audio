from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np


@dataclass(frozen=True)
class AudioWindow:
    index: int
    start_seconds: float
    end_seconds: float
    samples: np.ndarray


def generate_windows(
    samples: np.ndarray,
    sample_rate: int,
    window_seconds: float,
    hop_seconds: float,
) -> Iterator[AudioWindow]:
    if window_seconds <= 0 or hop_seconds <= 0:
        raise ValueError("window_seconds and hop_seconds must be positive.")

    window_size = max(1, int(round(window_seconds * sample_rate)))
    hop_size = max(1, int(round(hop_seconds * sample_rate)))

    if samples.size == 0:
        return

    index = 0
    for start in range(0, samples.size, hop_size):
        end = start + window_size
        window = samples[start:end]
        if window.size < window_size:
            window = np.pad(window, (0, window_size - window.size))

        start_seconds = start / sample_rate
        end_seconds = min(end, samples.size) / sample_rate
        yield AudioWindow(
            index=index,
            start_seconds=float(start_seconds),
            end_seconds=float(end_seconds),
            samples=window.astype(np.float32, copy=False),
        )
        index += 1

        if end >= samples.size:
            break
