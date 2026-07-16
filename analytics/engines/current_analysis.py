from __future__ import annotations

from typing import Any
from analytics.engines.base import BaseAnalysisEngine
from analytics.models import AnalysisContext


class CurrentAnalysisEngine(BaseAnalysisEngine):
    """Level 1: Computes instantaneous window features at a specific master clock time t."""

    @classmethod
    def get_current_metrics(cls, context: AnalysisContext, t: float) -> dict[str, Any]:
        timeline = context.timeline
        events = context.events

        # 1. Retrieve current frame
        current_frame = None
        for row in timeline:
            if row["start_seconds"] <= t < row["end_seconds"]:
                current_frame = row
                break
        if not current_frame and timeline:
            if t < timeline[0]["start_seconds"]:
                current_frame = timeline[0]
            elif t >= timeline[-1]["end_seconds"]:
                current_frame = timeline[-1]

        # 2. Retrieve active speaker segment
        active_segment = None
        current_speaker = "Silence"
        for seg in context.diarization.get("segments", []):
            if seg["start"] <= t < seg["end"]:
                active_segment = seg
                current_speaker = seg["speaker"]
                break

        # 3. Determine status state
        # Priority: Dropout > Speaker Change (1.5s flash) > Pause > Speech > Idle
        status_state = "Idle"
        if current_frame:
            if current_frame.get("dropout", False):
                status_state = "Dropout"
            else:
                # Check for active speaker change flash in range [start_seconds, start_seconds + 1.5]
                for event in events:
                    if event["type"] == "speaker_change":
                        if event["start"] <= t <= event["start"] + 1.5:
                            status_state = "Speaker Change"
                            break
                if status_state == "Idle":
                    if current_frame.get("pause", False):
                        status_state = "Pause"
                    else:
                        derived = current_frame.get("derived") or {}
                        speech = derived.get("speech") or {}
                        if speech.get("active", False):
                            status_state = "Speech"

        # 4. Extract raw features safely
        raw = current_frame.get("raw", {}) if current_frame else {}
        acoustic = raw.get("acoustic", {})
        quality = raw.get("quality", {})
        prosody = raw.get("prosody", {})
        derived = current_frame.get("derived", {}) if current_frame else {}
        speech = derived.get("speech", {})

        return {
            "timestamp": t,
            "speaker": current_speaker,
            "status": status_state,
            "rms": acoustic.get("rms"),
            "energy": acoustic.get("energy"),
            "loudness_db": acoustic.get("loudness_db"),
            "spectral_centroid_hz": acoustic.get("spectral_centroid_hz"),
            "spectral_bandwidth_hz": acoustic.get("spectral_bandwidth_hz"),
            "spectral_rolloff_hz": acoustic.get("spectral_rolloff_hz"),
            "zero_crossing_rate": acoustic.get("zero_crossing_rate"),
            "snr_db": quality.get("snr_db"),
            "speech_quality_proxy": quality.get("speech_quality_proxy"),
            "hnr_db": quality.get("hnr_db"),
            "spectral_flux": quality.get("spectral_flux"),
            "formant_dispersion": quality.get("formant_dispersion"),
            "pitch_hz": prosody.get("pitch_hz"),
            "jitter_pct": prosody.get("jitter_pct"),
            "shimmer_pct": prosody.get("shimmer_pct"),
            "speaking_rate_sps": prosody.get("speaking_rate_sps"),
            "active_segment": active_segment,
        }
