from __future__ import annotations

import numpy as np

from extractors.base import BaseExtractor


class VadExtractor(BaseExtractor):
    name = "vad"

    def __init__(self, rms_threshold: float = 0.015) -> None:
        self.rms_threshold = rms_threshold

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, bool]:
        rms = float(np.sqrt(np.mean(np.square(window)))) if window.size else 0.0
        zcr = (
            float(np.count_nonzero(np.diff(np.signbit(window))) / (window.size - 1))
            if window.size > 1
            else 0.0
        )
        return {"speech": bool(rms >= self.rms_threshold and zcr < 0.35)}


class PauseExtractor(BaseExtractor):
    name = "pause"

    def __init__(self, rms_threshold: float = 0.015) -> None:
        self.rms_threshold = rms_threshold

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, bool]:
        rms = float(np.sqrt(np.mean(np.square(window)))) if window.size else 0.0
        return {"pause": bool(rms < self.rms_threshold)}


class DropoutExtractor(BaseExtractor):
    name = "dropout"

    def __init__(self, rms_threshold: float = 0.003) -> None:
        self.rms_threshold = rms_threshold

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, bool]:
        peak = float(np.max(np.abs(window))) if window.size else 0.0
        rms = float(np.sqrt(np.mean(np.square(window)))) if window.size else 0.0
        return {"dropout": bool(peak < self.rms_threshold and rms < self.rms_threshold)}
