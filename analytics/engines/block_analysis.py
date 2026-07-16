from __future__ import annotations

import math
from typing import Any
import numpy as np
from analytics.engines.base import BaseAnalysisEngine
from analytics.models import AnalysisContext


class BlockAnalysisEngine(BaseAnalysisEngine):
    """Level 2: Computes block-level stats dynamically on demand, with caching for performance."""

    # Internal cache of computed blocks. Key: (block_size_seconds, block_index), Value: result dict
    _cache: dict[tuple[float, int], dict[str, Any]] = {}

    @classmethod
    def clear_cache(cls) -> None:
        """Clears the computed block cache."""
        cls._cache.clear()

    @classmethod
    def get_block_metrics(
        cls,
        context: AnalysisContext,
        current_time: float,
        block_size: float,
        config: Any,
    ) -> dict[str, Any]:
        """
        Computes statistics for the block covering the current playback position.
        Uses cached result if available.
        """
        block_index = int(current_time // block_size)
        cache_key = (block_size, block_index)

        if cache_key in cls._cache:
            return cls._cache[cache_key]

        # Calculate block time boundaries
        block_start = block_index * block_size
        block_end = block_start + block_size

        # 1. Gather overlapping timeline windows
        block_windows = cls.get_windows_in_range(
            context.timeline, block_start, block_end
        )

        # 2. Extract numeric lists for acoustic/prosodic/quality parameters
        pitches = cls.extract_nested_values(block_windows, "raw.prosody.pitch_hz")
        rmses = cls.extract_nested_values(block_windows, "raw.acoustic.rms")
        energies = cls.extract_nested_values(block_windows, "raw.acoustic.energy")
        loudnesses = cls.extract_nested_values(
            block_windows, "raw.acoustic.loudness_db"
        )
        snrs = cls.extract_nested_values(block_windows, "raw.quality.snr_db")
        centroids = cls.extract_nested_values(
            block_windows, "raw.acoustic.spectral_centroid_hz"
        )
        bandwidths = cls.extract_nested_values(
            block_windows, "raw.acoustic.spectral_bandwidth_hz"
        )
        rolloffs = cls.extract_nested_values(
            block_windows, "raw.acoustic.spectral_rolloff_hz"
        )
        jitters = cls.extract_nested_values(block_windows, "raw.prosody.jitter_pct")
        shimmers = cls.extract_nested_values(block_windows, "raw.prosody.shimmer_pct")
        speech_qualities = cls.extract_nested_values(
            block_windows, "raw.quality.speech_quality_proxy"
        )
        fluxes = cls.extract_nested_values(block_windows, "raw.quality.spectral_flux")

        # 3. Acoustic/Prosody descriptive statistics
        stats = {
            "pitch": cls.compute_stats(pitches),
            "rms": cls.compute_stats(rmses),
            "energy": cls.compute_stats(energies),
            "loudness": cls.compute_stats(loudnesses),
            "snr": cls.compute_stats(snrs),
            "spectral_centroid": cls.compute_stats(centroids),
            "spectral_bandwidth": cls.compute_stats(bandwidths),
            "spectral_rolloff": cls.compute_stats(rolloffs),
        }

        # 4. Event statistics
        # Gather overlapping events
        block_events = cls.get_events_in_range(context.events, block_start, block_end)

        pause_events = [e for e in block_events if e["type"] == "pause"]
        dropout_events = [e for e in block_events if e["type"] == "dropout"]
        speaker_changes = [e for e in block_events if e["type"] == "speaker_change"]

        # Sum overlap durations inside block
        def sum_event_durations(events_list: list[dict[str, Any]]) -> float:
            total_dur = 0.0
            for e in events_list:
                e_start = e["start"]
                e_end = e.get("end") or e_start
                overlap_s = max(e_start, block_start)
                overlap_e = min(e_end, block_end)
                total_dur += max(0.0, overlap_e - overlap_s)
            return total_dur

        pause_duration = sum_event_durations(pause_events)
        dropout_duration = sum_event_durations(dropout_events)

        longest_pause = 0.0
        for e in pause_events:
            e_start = e["start"]
            e_end = e.get("end") or e_start
            overlap_dur = max(0.0, min(e_end, block_end) - max(e_start, block_start))
            if overlap_dur > longest_pause:
                longest_pause = overlap_dur

        # Speech active frame percentage
        speech_frames = sum(
            1
            for w in block_windows
            if w.get("derived", {}).get("speech", {}).get("active") is True
        )
        total_frames = len(block_windows)
        speech_percent = (
            (speech_frames / total_frames * 100.0) if total_frames > 0 else 0.0
        )
        silence_percent = 100.0 - speech_percent

        # Speaker ratios & talk times inside this block
        # Calculate from overlapping speaker segments
        block_segments = [
            seg
            for seg in context.diarization.get("segments", [])
            if seg["start"] < block_end and seg["end"] > block_start
        ]

        speaker_durations: dict[str, float] = {}
        for seg in block_segments:
            overlap_s = max(seg["start"], block_start)
            overlap_e = min(seg["end"], block_end)
            duration = max(0.0, overlap_e - overlap_s)
            spk = seg["speaker"]
            speaker_durations[spk] = speaker_durations.get(spk, 0.0) + duration

        total_speak_time = sum(speaker_durations.values())
        speaker_ratios: dict[str, float] = {}
        if total_speak_time > 0.0:
            for spk, dur in speaker_durations.items():
                speaker_ratios[spk] = (dur / total_speak_time) * 100.0

        # Turn Count and Response Latency inside this block
        turn_count = len(block_segments)

        latencies = []
        for j in range(1, len(block_segments)):
            prev_seg = block_segments[j - 1]
            curr_seg = block_segments[j]
            gap = curr_seg["start"] - prev_seg["end"]
            if gap > 0:
                latencies.append(gap)
        avg_latency = float(np.mean(latencies)) if latencies else 0.0

        # Assemble event analytics block
        events_stats = {
            "speech_percent": speech_percent,
            "silence_percent": silence_percent,
            "pause_count": len(pause_events),
            "pause_duration": pause_duration,
            "longest_pause": longest_pause,
            "dropout_count": len(dropout_events),
            "dropout_duration": dropout_duration,
            "speaker_ratios": speaker_ratios,
            "speaker_durations": speaker_durations,
            "turn_count": turn_count,
            "speaker_changes": len(speaker_changes),
            "avg_latency": avg_latency,
        }

        # 5. Dynamically calculate block scores using formulas aligned to the configuration weights
        block_scores = cls._calculate_block_scores(
            stats, events_stats, jitters, shimmers, speech_qualities, fluxes
        )

        result = {
            "block_index": block_index,
            "start_seconds": block_start,
            "end_seconds": block_end,
            "stats": stats,
            "events": events_stats,
            "scores": block_scores,
        }

        # Save to cache
        cls._cache[cache_key] = result
        return result

    @classmethod
    def _calculate_block_scores(
        cls,
        stats: dict[str, Any],
        events: dict[str, Any],
        jitters: list[float],
        shimmers: list[float],
        speech_qualities: list[float],
        fluxes: list[float],
    ) -> dict[str, int]:
        """Calculates Layer 3 scorecard values specifically scoped to the block's timeline."""
        # 1. Audio Quality Score
        avg_quality = float(np.mean(speech_qualities)) if speech_qualities else 0.0
        avg_snr = stats["snr"]["mean"]
        dropout_count = events["dropout_count"]

        avg_flux = float(np.mean(fluxes)) if fluxes else 0.0
        flux_penalty = 15.0 * max(0.0, avg_flux - 0.15)

        aq_base = 100.0 * avg_quality
        aq_snr_modifier = (avg_snr - 15.0) if avg_snr > 15.0 else 0.0
        aq_score = aq_base + aq_snr_modifier - (5.0 * dropout_count) - flux_penalty
        aq_score = max(0, min(100, int(round(aq_score))))

        # 2. Voice Stability Score
        pitch_std = stats["pitch"]["std"]
        loudness_std = stats["loudness"]["std"]
        energy_std = stats["energy"]["std"]
        avg_jitter = float(np.mean(jitters)) if jitters else 0.0
        avg_shimmer = float(np.mean(shimmers)) if shimmers else 0.0

        vs_score = (
            100.0
            - (0.4 * pitch_std)
            - (3.0 * loudness_std)
            - (500.0 * energy_std)
            - (6.0 * avg_jitter)
            - (2.5 * avg_shimmer)
        )
        vs_score = max(0, min(100, int(round(vs_score))))

        # 3. Conversation Flow Score
        # pauses per minute in this block
        block_duration_min = 10.0 / 60.0  # assume block size duration
        pauses_per_min = (
            events["pause_count"] / block_duration_min
            if block_duration_min > 0
            else 0.0
        )
        avg_latency = events["avg_latency"]

        flow_score = (
            100.0
            - (8.0 * pauses_per_min)
            - (12.0 * events["dropout_count"])
            - (4.0 * max(0.0, avg_latency - 1.5))
        )
        flow_score += min(15.0, 1.2 * events["speaker_changes"])
        flow_score = max(0, min(100, int(round(flow_score))))

        # 4. Conversation Balance Score
        # Deviation of dominant speaker from 50%
        dominant_share = 50.0
        ratios = events["speaker_ratios"]
        if ratios:
            dominant_share = max(ratios.values())
        balance_deviation = abs(dominant_share - 50.0)
        balance_score = max(0, min(100, int(round(100.0 - 2.0 * balance_deviation))))

        # 5. Speech Activity Score
        sa_score = events["speech_percent"] + (100.0 - events["silence_percent"])
        sa_score = max(0, min(100, int(round(sa_score / 2.0))))

        return {
            "audio_quality": aq_score,
            "voice_stability": vs_score,
            "conversation_flow": flow_score,
            "conversation_balance": balance_score,
            "speech_activity": sa_score,
        }
