from __future__ import annotations

import math
import numpy as np
from extractors.base import BaseExtractor

EPSILON = 1e-10


class JitterExtractor(BaseExtractor):
    name = "jitter"

    def __init__(self, min_hz: float = 75.0, max_hz: float = 500.0) -> None:
        self.min_hz = min_hz
        self.max_hz = max_hz

    def extract(self, window: np.ndarray, sample_rate: int) -> dict[str, float | None]:
        if window.size < 2 or float(np.max(np.abs(window))) == 0.0:
            return {"jitter_pct": None}

        # Demean
        centered = window - np.mean(window)
        corr = np.correlate(centered, centered, mode="full")[window.size - 1 :]
        if corr.size == 0 or corr[0] <= 0:
            return {"jitter_pct": None}

        min_lag = max(1, int(sample_rate / self.max_hz))
        max_lag = min(corr.size - 1, int(sample_rate / self.min_hz))
        if max_lag <= min_lag:
            return {"jitter_pct": None}

        search = corr[min_lag:max_lag]
        lag = int(np.argmax(search) + min_lag)
        confidence = float(corr[lag] / corr[0])

        # Unvoiced/silence guard
        if confidence < 0.25:
            return {"jitter_pct": None}

        # Pitch period T in samples
        pitch_period = lag
        if pitch_period < 2:
            return {"jitter_pct": None}

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
        if window.size < 2 or float(np.max(np.abs(window))) == 0.0:
            return {"shimmer_pct": None}

        centered = window - np.mean(window)
        corr = np.correlate(centered, centered, mode="full")[window.size - 1 :]
        if corr.size == 0 or corr[0] <= 0:
            return {"shimmer_pct": None}

        min_lag = max(1, int(sample_rate / self.max_hz))
        max_lag = min(corr.size - 1, int(sample_rate / self.min_hz))
        if max_lag <= min_lag:
            return {"shimmer_pct": None}

        search = corr[min_lag:max_lag]
        lag = int(np.argmax(search) + min_lag)
        confidence = float(corr[lag] / corr[0])

        if confidence < 0.25:
            return {"shimmer_pct": None}

        pitch_period = lag
        if pitch_period < 2:
            return {"shimmer_pct": None}

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
        if window.size < 2 or float(np.max(np.abs(window))) == 0.0:
            return {"hnr_db": None}

        centered = window - np.mean(window)
        corr = np.correlate(centered, centered, mode="full")[window.size - 1 :]
        if corr.size == 0 or corr[0] <= 0:
            return {"hnr_db": None}

        min_lag = max(1, int(sample_rate / self.max_hz))
        max_lag = min(corr.size - 1, int(sample_rate / self.min_hz))
        if max_lag <= min_lag:
            return {"hnr_db": None}

        search = corr[min_lag:max_lag]
        lag = int(np.argmax(search) + min_lag)

        # Normalized autocorrelation coefficient
        r_xx = float(corr[lag] / corr[0])

        # Ensure r_xx stays in a safe bounds (0.01 to 0.99) for HNR log ratio
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

        # 3. Find peaks in the envelope
        # A point is a peak if it is greater than its neighbors and above a threshold
        mean_env = float(np.mean(envelope))
        std_env = float(np.std(envelope))
        threshold = mean_env + 0.3 * std_env

        peaks = 0
        for i in range(1, len(envelope) - 1):
            if envelope[i] > envelope[i - 1] and envelope[i] > envelope[i + 1]:
                if envelope[i] > threshold:
                    peaks += 1

        # speaking rate = peaks / window duration (window size in seconds)
        duration_s = window.size / sample_rate
        speaking_rate_sps = peaks / duration_s if duration_s > 0 else 0.0

        return {"speaking_rate_sps": float(speaking_rate_sps)}
