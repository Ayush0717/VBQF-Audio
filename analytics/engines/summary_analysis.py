from __future__ import annotations

from typing import Any
import numpy as np
from analytics.engines.base import BaseAnalysisEngine
from analytics.models import AnalysisContext


class SummaryAnalysisEngine(BaseAnalysisEngine):
    """Level 3: Computes whole-call metadata summaries from the timeline and events."""

    @classmethod
    def compute_summary(
        cls,
        timeline: list[dict[str, Any]],
        speaker_segments: list[dict[str, Any]],
        events: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Calculates call-level summaries."""
        duration = float(metadata.get("duration_seconds", 0.0))

        # Calculate speaker stats from segments
        from extractors.speaker.statistics import compute_speaker_statistics

        stats_and_dominant = compute_speaker_statistics(speaker_segments, duration)

        # Calculate average SNR, Pitch, Loudness
        pitches = cls.extract_nested_values(timeline, "raw.prosody.pitch_hz")
        rmses = cls.extract_nested_values(timeline, "raw.acoustic.rms")
        energies = cls.extract_nested_values(timeline, "raw.acoustic.energy")
        loudnesses = cls.extract_nested_values(timeline, "raw.acoustic.loudness_db")
        snrs = cls.extract_nested_values(timeline, "raw.quality.snr_db")

        avg_snr = float(np.mean(snrs)) if snrs else 0.0
        avg_pitch = float(np.mean(pitches)) if pitches else 0.0
        avg_rms = float(np.mean(rmses)) if rmses else 0.0
        avg_energy = float(np.mean(energies)) if energies else 0.0
        avg_loudness = float(np.mean(loudnesses)) if loudnesses else 0.0

        # Calculate pauses and dropouts
        pause_events = [e for e in events if e["type"] == "pause"]
        dropout_events = [e for e in events if e["type"] == "dropout"]

        total_pause_duration = float(sum(e["duration"] for e in pause_events))
        longest_pause = float(max((e["duration"] for e in pause_events), default=0.0))
        total_pause_count = len(pause_events)
        total_dropouts = len(dropout_events)

        # Calculate speech and silence time
        speech_frames = sum(
            1
            for w in timeline
            if w.get("derived", {}).get("speech", {}).get("active") is True
        )
        total_frames = len(timeline)
        speech_ratio = (speech_frames / total_frames) if total_frames > 0 else 0.0

        total_speech_time = round(duration * speech_ratio, 2)
        total_silence_time = round(duration * (1.0 - speech_ratio), 2)

        return {
            "duration_seconds": duration,
            "speaker_count": len(stats_and_dominant.get("speaker_statistics", {})),
            "dominant_speaker": stats_and_dominant.get("dominant_speaker"),
            "total_speech_time_seconds": total_speech_time,
            "total_silence_time_seconds": total_silence_time,
            "average_snr_db": round(avg_snr, 2),
            "average_pitch_hz": round(avg_pitch, 2),
            "average_rms": round(avg_rms, 4),
            "average_energy": round(avg_energy, 4),
            "average_loudness_db": round(avg_loudness, 2),
            "total_pause_count": total_pause_count,
            "total_pause_duration_seconds": round(total_pause_duration, 2),
            "longest_pause_seconds": round(longest_pause, 2),
            "total_dropouts": total_dropouts,
            "speaker_statistics": stats_and_dominant.get("speaker_statistics", {}),
        }
