from __future__ import annotations

import math

import numpy as np

from extractors.base import BaseExtractor

EPSILON = 1e-10


class RmsExtractor(BaseExtractor):
    name = "rms"

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, float]:
        return {"rms": float(np.sqrt(np.mean(np.square(window))))}


class EnergyExtractor(BaseExtractor):
    name = "energy"

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, float]:
        return {"energy": float(np.mean(np.square(window)))}


class LoudnessExtractor(BaseExtractor):
    name = "loudness"

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, float]:
        rms = float(np.sqrt(np.mean(np.square(window))))
        return {"loudness_db": float(20 * math.log10(max(rms, EPSILON)))}


class ZeroCrossingRateExtractor(BaseExtractor):
    name = "zero_crossing_rate"

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, float]:
        if window.size < 2:
            return {"zero_crossing_rate": 0.0}
        crossings = np.count_nonzero(np.diff(np.signbit(window)))
        return {"zero_crossing_rate": float(crossings / (window.size - 1))}


class SpectralCentroidExtractor(BaseExtractor):
    name = "spectral_centroid"

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, float | None]:
        magnitude = np.abs(np.fft.rfft(window))
        total = float(np.sum(magnitude))
        if total <= EPSILON:
            return {"spectral_centroid_hz": None}

        frequencies = np.fft.rfftfreq(window.size, d=1.0 / sample_rate)
        centroid = float(np.sum(frequencies * magnitude) / total)
        return {"spectral_centroid_hz": centroid}
