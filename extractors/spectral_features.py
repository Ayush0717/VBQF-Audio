from __future__ import annotations

import numpy as np
from extractors.base import BaseExtractor

EPSILON = 1e-10


class SpectralBandwidthExtractor(BaseExtractor):
    name = "spectral_bandwidth"

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, float | None]:
        """Calculates spectral bandwidth (spread around the spectral centroid) within the window."""
        if window.size < 2 or float(np.max(np.abs(window))) == 0.0:
            return {"spectral_bandwidth_hz": None}

        mag = np.abs(np.fft.rfft(window * np.hanning(window.size)))
        total = float(np.sum(mag))
        if total <= EPSILON:
            return {"spectral_bandwidth_hz": None}

        freqs = np.fft.rfftfreq(window.size, d=1.0 / sample_rate)
        centroid = float(np.sum(freqs * mag) / total)

        # Calculate second central moment (standard deviation)
        variance = float(np.sum(np.square(freqs - centroid) * mag) / total)
        bandwidth = float(np.sqrt(variance))
        return {"spectral_bandwidth_hz": bandwidth}


class SpectralRolloffExtractor(BaseExtractor):
    name = "spectral_roll_off"

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, float | None]:
        """Calculates spectral roll-off frequency (the frequency below which 85% of magnitude energy lies)."""
        if window.size < 2 or float(np.max(np.abs(window))) == 0.0:
            return {"spectral_rolloff_hz": None}

        mag = np.abs(np.fft.rfft(window * np.hanning(window.size)))
        total = float(np.sum(mag))
        if total <= EPSILON:
            return {"spectral_rolloff_hz": None}

        freqs = np.fft.rfftfreq(window.size, d=1.0 / sample_rate)
        cum_sum = np.cumsum(mag)
        threshold = 0.85 * total

        idx = np.searchsorted(cum_sum, threshold)
        if idx >= len(freqs):
            idx = len(freqs) - 1

        return {"spectral_rolloff_hz": float(freqs[idx])}
