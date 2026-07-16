from __future__ import annotations

import numpy as np
from extractors.base import BaseExtractor

EPSILON = 1e-10


class SpectralFluxExtractor(BaseExtractor):
    name = "spectral_flux"

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, float]:
        """Calculates frame-to-frame spectral flux within the window."""
        if window.size < 512:
            return {"spectral_flux": 0.0}

        # Divide the window into short frames (e.g., 256 samples, ~16ms hop)
        frame_size = 512
        hop_size = 256

        frames = []
        for start in range(0, len(window) - frame_size + 1, hop_size):
            frames.append(window[start : start + frame_size])

        if len(frames) < 2:
            return {"spectral_flux": 0.0}

        # Compute FFT magnitudes for all frames
        magnitudes = []
        for f in frames:
            mag = np.abs(np.fft.rfft(f * np.hanning(f.size)))
            # Normalize magnitude
            total = np.sum(mag)
            if total > EPSILON:
                mag /= total
            magnitudes.append(mag)

        # Calculate L2 distance between consecutive normalized frames
        flux_values = []
        for i in range(1, len(magnitudes)):
            diff = magnitudes[i] - magnitudes[i - 1]
            flux = float(np.sqrt(np.sum(np.square(diff))))
            flux_values.append(flux)

        return {"spectral_flux": float(np.mean(flux_values)) if flux_values else 0.0}


class FormantDispersionExtractor(BaseExtractor):
    name = "formant_dispersion"

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, float | None]:
        """Calculates the dispersion (average frequency separation) between the first two formant peaks."""
        if window.size < 512 or float(np.max(np.abs(window))) == 0.0:
            return {"formant_dispersion": None}

        # Compute spectrum using Hanning window
        mag = np.abs(np.fft.rfft(window * np.hanning(window.size)))
        freqs = np.fft.rfftfreq(window.size, d=1.0 / sample_rate)

        # Focus search on typical vowel formant regions:
        # F1 generally in [300, 1000] Hz
        # F2 generally in [1000, 3000] Hz
        f1_mask = (freqs >= 300) & (freqs <= 1000)
        f2_mask = (freqs >= 1000) & (freqs <= 3000)

        if not np.any(f1_mask) or not np.any(f2_mask):
            return {"formant_dispersion": None}

        # Find absolute peak in F1 band
        f1_idx = np.argmax(mag[f1_mask])
        f1_hz = freqs[f1_mask][f1_idx]

        # Find absolute peak in F2 band
        f2_idx = np.argmax(mag[f2_mask])
        f2_hz = freqs[f2_mask][f2_idx]

        # Dispersion is the distance between F2 and F1
        dispersion = f2_hz - f1_hz
        if dispersion <= 0:
            return {"formant_dispersion": None}

        return {"formant_dispersion": float(dispersion)}
