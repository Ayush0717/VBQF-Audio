from __future__ import annotations

import math
import numpy as np
from extractors.base import BaseExtractor

EPSILON = 1e-10


# ── Shared FFT-based autocorrelation ─────────────────────────────────────────
# np.correlate(mode="full") is O(n²). FFT-based autocorrelation is O(n log n).
# For a 16kHz window of 1s that's 16000 samples — FFT is ~10x faster.

def _fft_autocorrelation(signal: np.ndarray) -> np.ndarray:
    """Compute the one-sided autocorrelation via FFT. Returns corr[0..N-1]."""
    n = signal.size
    # Pad to next power of 2 for efficient FFT (at least 2*n to avoid circular artifacts)
    fft_size = 1
    while fft_size < 2 * n:
        fft_size <<= 1
    spectrum = np.fft.rfft(signal, n=fft_size)
    power = spectrum * np.conj(spectrum)
    full_corr = np.fft.irfft(power, n=fft_size)
    # Return the one-sided autocorrelation (lags 0..N-1)
    return full_corr[:n].real


def _pitch_analysis(
    window: np.ndarray,
    sample_rate: int,
    min_hz: float = 75.0,
    max_hz: float = 500.0,
    confidence_threshold: float = 0.25,
) -> dict | None:
    """
    Shared pitch period detection used by Jitter, Shimmer, and HNR.
    Returns None if unvoiced/invalid, otherwise returns a dict with:
      - corr: one-sided autocorrelation
      - lag: pitch period in samples
      - confidence: normalized autocorrelation at the pitch lag
      - r_xx: corr[lag]/corr[0]
    """
    if window.size < 2 or float(np.max(np.abs(window))) == 0.0:
        return None

    centered = window - np.mean(window)
    corr = _fft_autocorrelation(centered)

    if corr.size == 0 or corr[0] <= 0:
        return None

    min_lag = max(1, int(sample_rate / max_hz))
    max_lag = min(corr.size - 1, int(sample_rate / min_hz))
    if max_lag <= min_lag:
        return None

    search = corr[min_lag:max_lag]
    lag = int(np.argmax(search) + min_lag)
    r_xx = float(corr[lag] / corr[0])

    if r_xx < confidence_threshold:
        return None

    if lag < 2:
        return None

    return {"corr": corr, "lag": lag, "confidence": r_xx, "r_xx": r_xx}


class JitterExtractor(BaseExtractor):
    name = "jitter"

    def __init__(self, min_hz: float = 75.0, max_hz: float = 500.0) -> None:
        self.min_hz = min_hz
        self.max_hz = max_hz

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, float | None]:
        analysis = _pitch_analysis(window, sample_rate, self.min_hz, self.max_hz)
        if analysis is None:
            return {"jitter_pct": None}

        pitch_period = analysis["lag"]

        # Find zero crossings or local peaks to divide into periods
        # For simplicity, we step through the window by the pitch period and find actual peaks
        peaks = []
        step = pitch_period
        for start in range(0, len(window) - step, step):
            segment = window[start : start + step]
            if segment.size > 0:
                peaks.append(start + np.argmax(np.abs(segment)))

        if len(peaks) < 3:
            return {"jitter_pct": 0.0}

        # Calculate cycle-to-cycle variation in period lengths (in samples)
        periods = np.diff(peaks)
        abs_diff = np.abs(np.diff(periods))
        mean_period = np.mean(periods)

        if mean_period <= EPSILON:
            return {"jitter_pct": 0.0}

        jitter = (np.mean(abs_diff) / mean_period) * 100.0
        return {"jitter_pct": float(max(0.0, min(100.0, jitter)))}


class ShimmerExtractor(BaseExtractor):
    name = "shimmer"

    def __init__(self, min_hz: float = 75.0, max_hz: float = 500.0) -> None:
        self.min_hz = min_hz
        self.max_hz = max_hz

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, float | None]:
        analysis = _pitch_analysis(window, sample_rate, self.min_hz, self.max_hz)
        if analysis is None:
            return {"shimmer_pct": None}

        pitch_period = analysis["lag"]

        # Find peak amplitudes of consecutive pitch periods
        amplitudes = []
        step = pitch_period
        for start in range(0, len(window) - step, step):
            segment = window[start : start + step]
            if segment.size > 0:
                amplitudes.append(float(np.max(np.abs(segment))))

        if len(amplitudes) < 3:
            return {"shimmer_pct": 0.0}

        mean_amp = np.mean(amplitudes)
        if mean_amp <= EPSILON:
            return {"shimmer_pct": 0.0}

        abs_diff = np.abs(np.diff(amplitudes))
        shimmer = (np.mean(abs_diff) / mean_amp) * 100.0
        return {"shimmer_pct": float(max(0.0, min(100.0, shimmer)))}


class HnrExtractor(BaseExtractor):
    name = "hnr"

    def __init__(self, min_hz: float = 75.0, max_hz: float = 500.0) -> None:
        self.min_hz = min_hz
        self.max_hz = max_hz

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, float | None]:
        analysis = _pitch_analysis(window, sample_rate, self.min_hz, self.max_hz)
        if analysis is None:
            return {"hnr_db": None}

        # Normalized autocorrelation coefficient
        r_xx = analysis["r_xx"]

        # Ensure r_xx stays in safe bounds (0.01 to 0.99) for HNR log ratio
        r_xx = max(0.01, min(0.99, r_xx))

        hnr_db = 10 * math.log10(r_xx / (1.0 - r_xx))
        return {"hnr_db": float(hnr_db)}


class SpeakingRateExtractor(BaseExtractor):
    name = "speaking_rate"

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, float]:
        """Estimates speaking rate (syllables per second) using energy envelope peak counts."""
        if window.size < 2 or float(np.max(np.abs(window))) == 0.0:
            return {"speaking_rate_sps": 0.0}

        # 1. Compute half-wave rectified audio or absolute amplitude
        rectified = np.abs(window)

        # 2. Simple rolling mean to act as low-pass envelope filter (e.g. ~100ms window size)
        # 100ms in samples: sample_rate * 0.1
        box_len = max(5, int(sample_rate * 0.1))
        box = np.ones(box_len) / box_len
        envelope = np.convolve(rectified, box, mode="same")

        # 3. Find peaks in the envelope (vectorized — no Python loop)
        mean_env = float(np.mean(envelope))
        std_env = float(np.std(envelope))
        threshold = mean_env + 0.3 * std_env

        # A peak: envelope[i] > envelope[i-1] AND envelope[i] > envelope[i+1] AND above threshold
        left_bigger = envelope[1:-1] > envelope[:-2]
        right_bigger = envelope[1:-1] > envelope[2:]
        above_threshold = envelope[1:-1] > threshold
        peaks = int(np.sum(left_bigger & right_bigger & above_threshold))

        # speaking rate = peaks / window duration (window size in seconds)
        duration_s = window.size / sample_rate
        speaking_rate_sps = peaks / duration_s if duration_s > 0 else 0.0

        return {"speaking_rate_sps": float(speaking_rate_sps)}

