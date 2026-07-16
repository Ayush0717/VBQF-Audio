from __future__ import annotations

import numpy as np

from extractors.base import BaseExtractor


class PitchExtractor(BaseExtractor):
    name = "pitch"

    def __init__(self, min_hz: float = 75.0, max_hz: float = 500.0) -> None:
        self.min_hz = min_hz
        self.max_hz = max_hz

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, float | None]:
        if window.size < 2 or float(np.max(np.abs(window))) == 0.0:
            return {"pitch_hz": None}

        centered = window - np.mean(window)
        corr = np.correlate(centered, centered, mode="full")[window.size - 1 :]
        if corr.size == 0 or corr[0] <= 0:
            return {"pitch_hz": None}

        min_lag = max(1, int(sample_rate / self.max_hz))
        max_lag = min(corr.size - 1, int(sample_rate / self.min_hz))
        if max_lag <= min_lag:
            return {"pitch_hz": None}

        search = corr[min_lag:max_lag]
        lag = int(np.argmax(search) + min_lag)
        confidence = float(corr[lag] / corr[0])
        if confidence < 0.25:
            return {"pitch_hz": None}

        return {"pitch_hz": float(sample_rate / lag)}
