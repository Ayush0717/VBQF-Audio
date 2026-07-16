from __future__ import annotations

import math

import numpy as np

from extractors.base import BaseExtractor

EPSILON = 1e-10


class SnrExtractor(BaseExtractor):
    name = "snr"

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, float | None]:
        if window.size == 0:
            return {"snr_db": None}

        power = np.square(window)
        signal = float(np.percentile(power, 95))
        noise = float(np.percentile(power, 10))
        if signal <= EPSILON:
            return {"snr_db": None}

        snr = 10 * math.log10(max(signal, EPSILON) / max(noise, EPSILON))
        return {"snr_db": float(snr)}


class SpeechQualityExtractor(BaseExtractor):
    name = "speech_quality"

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, float | None]:
        rms = float(np.sqrt(np.mean(np.square(window)))) if window.size else 0.0
        if rms <= EPSILON:
            return {"speech_quality_proxy": 0.0}

        clipping_ratio = float(np.mean(np.abs(window) > 0.98))
        noise_floor = float(np.percentile(np.abs(window), 10))
        score = 1.0 - min(1.0, clipping_ratio * 8.0 + noise_floor * 0.5)
        return {
            "speech_quality_proxy": float(max(0.0, min(1.0, score))),
            "clipping_ratio": float(clipping_ratio)
        }


class SilenceRatioExtractor(BaseExtractor):
    name = "silence_ratio"

    def __init__(self, threshold: float = 0.015) -> None:
        self.threshold = threshold

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, float]:
        return {"silence_ratio": float(np.mean(np.abs(window) < self.threshold))}
