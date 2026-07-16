from __future__ import annotations

from typing import Any
import numpy as np
from analytics.models import AnalysisContext


class BaseAnalysisEngine:
    """Base class for all Phase 1 analysis engines containing common timeline and event helpers."""

    @staticmethod
    def get_windows_in_range(
        timeline: list[dict[str, Any]], start: float, end: float
    ) -> list[dict[str, Any]]:
        """Filters the timeline windows that overlap with [start, end]."""
        return [
            w for w in timeline if w["start_seconds"] < end and w["end_seconds"] > start
        ]

    @staticmethod
    def get_events_in_range(
        events: list[dict[str, Any]], start: float, end: float
    ) -> list[dict[str, Any]]:
        """Filters the event records occurring within the interval [start, end]."""
        return [
            e
            for e in events
            if e["start"] < end and (e.get("end") or e["start"]) > start
        ]

    @staticmethod
    def compute_stats(values: list[float]) -> dict[str, float]:
        """Calculates standard descriptive statistics for a list of values."""
        if not values:
            return {"min": 0.0, "max": 0.0, "mean": 0.0, "std": 0.0}
        return {
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "mean": float(np.mean(values)),
            "std": float(np.std(values)),
        }

    @staticmethod
    def extract_nested_values(windows: list[dict[str, Any]], path: str) -> list[float]:
        """Traverses nested dictionary keys to collect numeric values."""
        parts = path.split(".")
        results = []
        for w in windows:
            val = w
            for p in parts:
                if isinstance(val, dict):
                    val = val.get(p)
                else:
                    val = None
                    break
            if isinstance(val, (int, float)):
                results.append(float(val))
        return results
