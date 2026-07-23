from __future__ import annotations

from typing import Any
import numpy as np
from analytics.models import AnalysisContext


def compute_engineered_features(context: AnalysisContext) -> dict[str, Any]:
    """Computes Layer 2 engineered features from an AnalysisContext instance."""
    timeline = context.timeline
    events = context.events
    diarization = context.diarization
    summary = context.summary
    duration = float(context.metadata.get("duration_seconds", 0.0))

    # Helper to retrieve nested values safely
    def get_timeline_vals(path: str) -> list[float]:
        parts = path.split(".")
        vals = []
        for w in timeline:
            v = w
            for p in parts:
                if isinstance(v, dict):
                    v = v.get(p)
                else:
                    v = None
                    break
            if isinstance(v, (int, float)):
                vals.append(float(v))
        return vals

    def format_ts(seconds: float) -> str:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m:02d}:{s:02d}"

    timeline_anomalies = {
        "audio_quality": {"dropouts": [], "clipping": [], "noise_spikes": []},
        "conversation_flow": {
            "interruptions": [],
            "response_delays": [],
            "awkward_pauses": [],
        },
        "conversation_balance": {"monologues": []},
        "voice_stability": {"voice_cracks": []},
        "interaction_integrity": {"abrupt_cutoff": []},
    }

    # 1. Gather all raw features lists (Acoustic and Quality are still timeline-based)
    pitches = get_timeline_vals("raw.prosody.pitch_hz")
    rmses = get_timeline_vals("raw.acoustic.rms")
    energies = get_timeline_vals("raw.acoustic.energy")
    loudnesses = get_timeline_vals("raw.acoustic.loudness_db")
    snrs = get_timeline_vals("raw.quality.snr_db")
    hnrs = get_timeline_vals("raw.quality.hnr_db")
    qualities = get_timeline_vals("raw.quality.speech_quality_proxy")
    clippings = get_timeline_vals("raw.quality.clipping_ratio")
    fluxes = get_timeline_vals("raw.quality.spectral_flux")
    bandwidths = get_timeline_vals("raw.acoustic.spectral_bandwidth_hz")
    rolloffs = get_timeline_vals("raw.acoustic.spectral_rolloff_hz")
    jitters = get_timeline_vals("raw.prosody.jitter_pct")
    shimmers = get_timeline_vals("raw.prosody.shimmer_pct")
    speaking_rates = get_timeline_vals("raw.prosody.speaking_rate_sps")

    # Pause & dropout events duration and count
    pause_events = [e for e in events if e.get("type") == "pause"]
    dropout_events = [e for e in events if e.get("type") == "dropout"]

    pause_durations = [float(e.get("duration", 0.0)) for e in pause_events]
    pause_count = len(pause_events)
    avg_pause = float(np.mean(pause_durations)) if pause_durations else 0.0
    longest_pause = float(np.max(pause_durations)) if pause_durations else 0.0
    pauses_per_min = (pause_count / (duration / 60.0)) if duration > 0 else 0.0

    dropout_durations = [float(e.get("duration", 0.0)) for e in dropout_events]
    dropout_count = len(dropout_events)
    total_dropout_duration = float(sum(dropout_durations))

    # Noise level: average loudness when speech is inactive
    silence_loudness = [
        w.get("raw", {}).get("acoustic", {}).get("loudness_db", -60.0)
        for w in timeline
        if w.get("derived", {}).get("speech", {}).get("active") is False
    ]
    silence_loudness = [l for l in silence_loudness if l is not None]
    noise_level = float(np.mean(silence_loudness)) if silence_loudness else -60.0

    clipping_percentage = round(float(np.mean(clippings)) * 100.0 if clippings else 0.0, 2)

    # 2. Compute Audio Quality metrics
    audio_quality = {
        "average_rms": round(float(np.mean(rmses)) if rmses else 0.0, 4),
        "average_energy": round(float(np.mean(energies)) if energies else 0.0, 4),
        "average_loudness": round(float(np.mean(loudnesses)) if loudnesses else 0.0, 2),
        "average_snr": round(float(np.mean(snrs)) if snrs else 0.0, 2),
        "noise_level": round(noise_level, 2),
        "recording_stability": round(float(np.std(snrs)) if snrs else 0.0, 2),
        "dropout_count": dropout_count,
        "dropout_duration": round(total_dropout_duration, 2),
        "clipping_percentage": clipping_percentage,
    }

    # 3. Compute Voice Stability metrics
    speaking_stability = float(np.std(speaking_rates)) if speaking_rates else 0.0

    voice_stability = {
        "pitch_stability": round(float(np.std(pitches)) if pitches else 0.0, 2),
        "pitch_variance": round(float(np.var(pitches)) if pitches else 0.0, 2),
        "energy_stability": round(float(np.std(energies)) if energies else 0.0, 4),
        "energy_variance": round(float(np.var(energies)) if energies else 0.0, 4),
        "loudness_stability": round(
            float(np.std(loudnesses)) if loudnesses else 0.0, 2
        ),
        "loudness_variance": round(float(np.var(loudnesses)) if loudnesses else 0.0, 2),
        "speaking_stability": round(speaking_stability, 2),
        "avg_jitter_pct": round(float(np.mean(jitters)) if jitters else 0.0, 2),
        "avg_shimmer_pct": round(float(np.mean(shimmers)) if shimmers else 0.0, 2),
        "stability_label": (
            "Stable"
            if (float(np.mean(jitters)) if jitters else 0.0) < 1.5
            else "Moderate"
        ),
    }

    # 4. Compute Speech Behaviour metrics
    # We now compute Speech % directly from the diarization segments instead of timeline grid!
    segments = diarization.get("segments", [])

    # Calculate union of all speech segments to get true speech percentage without double counting overlaps
    events_union = []
    if segments:
        sorted_segs = sorted(segments, key=lambda x: x["start"])
        current_start = sorted_segs[0]["start"]
        current_end = sorted_segs[0]["end"]
        for seg in sorted_segs[1:]:
            if seg["start"] <= current_end:
                current_end = max(current_end, seg["end"])
            else:
                events_union.append((current_start, current_end))
                current_start = seg["start"]
                current_end = seg["end"]
        events_union.append((current_start, current_end))

    total_speech_time = sum([end - start for start, end in events_union])
    speech_percent = (total_speech_time / duration * 100.0) if duration > 0 else 0.0
    silence_percent = 100.0 - speech_percent

    speech_behaviour = {
        "speech_percentage": round(speech_percent, 1),
        "silence_percentage": round(silence_percent, 1),
        "pause_count": pause_count,
        "average_pause_duration": round(avg_pause, 2),
        "longest_pause": round(longest_pause, 2),
        "pause_frequency": round(pauses_per_min, 2),
    }

    # 5. Compute Conversation Behaviour metrics entirely from Diarization
    stats = diarization.get("statistics", {})
    speaker_talk_time = stats.get("talk_times", {})
    speaker_count = stats.get("speaker_count", 0)

    speaker_talk_ratio = {
        spk: (t / total_speech_time * 100.0 if total_speech_time > 0 else 0.0)
        for spk, t in speaker_talk_time.items()
    }

    dominant_speaker = (
        max(speaker_talk_time, key=speaker_talk_time.get)
        if speaker_talk_time
        else "n/a"
    )

    # ── Robust Floor-Tracking Algorithm ──
    # Sort segments by start time
    sorted_segments = sorted(segments, key=lambda x: x["start"])
    
    latencies = []
    overlaps = []
    
    last_speaker = None
    last_start = 0
    last_end = 0
    
    floor_durations = []
    speaker_changes_count = 0

    for seg in sorted_segments:
        if last_speaker is None:
            last_speaker = seg["speaker"]
            last_start = seg["start"]
            last_end = seg["end"]
            continue
            
        if seg["speaker"] != last_speaker:
            gap = seg["start"] - last_end
            if gap > 0:
                # Floor is empty, new speaker takes it
                latencies.append(gap)
                if gap > 2.0:
                    timeline_anomalies["conversation_flow"]["response_delays"].append(
                        f"{format_ts(last_end)} - {format_ts(seg['start'])}"
                    )

                floor_durations.append(last_end - last_start)
                
                last_speaker = seg["speaker"]
                last_start = seg["start"]
                last_end = seg["end"]
                speaker_changes_count += 1
            else:
                # Overlap!
                overlap_time = min(last_end, seg["end"]) - seg["start"]
                if overlap_time > 0.2:  # Ignore micro-overlaps < 0.2s
                    overlaps.append(overlap_time)
                    if overlap_time > 1.0:
                        timeline_anomalies["conversation_flow"]["interruptions"].append(
                            format_ts(seg["start"])
                        )
                    
                # Does the new speaker take the floor?
                if seg["end"] > last_end:
                    floor_durations.append(last_end - last_start)
                    
                    last_speaker = seg["speaker"]
                    last_start = seg["start"]
                    last_end = seg["end"]
                    speaker_changes_count += 1
        else:
            # Same speaker continues (or overlaps with themselves, just extend)
            last_end = max(last_end, seg["end"])
            
    if last_speaker is not None:
        floor_durations.append(last_end - last_start)

    avg_latency = float(np.mean(latencies)) if latencies else 0.0
    longest_turn = float(np.max(floor_durations)) if floor_durations else 0.0
    turn_count = len(floor_durations)
    overlap_duration = float(sum(overlaps))
    overlap_count = len(overlaps)

    # Conversation balance score: talk percentage difference
    ratios_list = list(speaker_talk_ratio.values())
    if len(ratios_list) >= 2:
        ratios_list.sort(reverse=True)
        balance_val = abs(ratios_list[0] - ratios_list[1])
    else:
        balance_val = 100.0

    conversation_behaviour = {
        "speaker_talk_time": speaker_talk_time,
        "speaker_talk_ratio": speaker_talk_ratio,
        "speaker_count": speaker_count,
        "turn_count": turn_count,
        "speaker_change_count": speaker_changes_count,
        "average_turn_duration": round(
            float(np.mean(floor_durations)) if floor_durations else 0.0, 2
        ),
        "longest_turn": round(longest_turn, 2),
        "response_latency": round(avg_latency, 2),
        "conversation_balance": round(balance_val, 2),
    }

    # 6. Legacy / extra tabs support
    avg_snr = float(np.mean(snrs)) if snrs else 0.0
    avg_hnr = float(np.mean(hnrs)) if hnrs else 0.0
    avg_quality = float(np.mean(qualities)) if qualities else 0.0
    avg_flux = float(np.mean(fluxes)) if fluxes else 0.0

    voice_quality = {
        "avg_snr_db": round(avg_snr, 2),
        "avg_hnr_db": round(avg_hnr, 2),
        "avg_speech_quality": round(avg_quality, 2),
        "avg_spectral_flux": round(avg_flux, 3),
        "dropout_count": dropout_count,
        "dropout_duration": round(total_dropout_duration, 2),
        "clipping_percentage": clipping_percentage,
        "quality_label": (
            "Excellent" if avg_snr > 20.0 and avg_quality > 0.8 else "Good"
        ),
    }

    response_dynamics = {
        "avg_response_latency_seconds": round(avg_latency, 2),
        "total_overlap_seconds": round(overlap_duration, 2),
        "overlap_count": overlap_count,
        "overlap_frequency": round(overlap_count / (duration / 60.0), 2) if duration > 0 else 0.0,
    }

    # Emotion trend slopes
    def compute_slope(y_vals: list[float]) -> float:
        if len(y_vals) < 2:
            return 0.0
        x = np.arange(len(y_vals))
        slope, _ = np.polyfit(x, y_vals, 1)
        return float(slope)

    pitch_slope = compute_slope(pitches)
    loudness_slope = compute_slope(loudnesses)

    emotional_indicators = {
        "avg_speaking_rate_sps": round(
            float(np.mean(speaking_rates)) if speaking_rates else 0.0, 2
        ),
        "pitch_slope": round(pitch_slope, 4),
        "loudness_slope": round(loudness_slope, 4),
    }

    # 7. Interaction Integrity Features (Global Acoustic End-of-Call Analysis)
    # ─────────────────────────────────────────────────────────────────────────
    # Three objective, acoustically grounded structural features.
    # No psychoacoustic inference. No speaker intent assumptions.
    # Features: Abrupt Cutoff | Trailing Silence | Final Window Overlap
    # ─────────────────────────────────────────────────────────────────────────

    # Compute hop size from timeline frame spacing
    hop_size = (
        (timeline[1]["timestamp"] - timeline[0]["timestamp"])
        if len(timeline) >= 2
        else 0.5
    )

    base_median = summary.get("baseline_loudness_median", 0.0)
    base_mad = summary.get("baseline_loudness_mad", 1.0)

    # --- Feature 1: Abrupt Cutoff ---
    # Flag if speech is active in the final 3 frames with high energy and no trailing silence.
    final_frames = timeline[-3:] if len(timeline) >= 3 else timeline
    final_vad_flags = [
        1 if f.get("derived", {}).get("speech", {}).get("active") else 0
        for f in final_frames
    ]
    final_energies = [
        f.get("raw", {}).get("acoustic", {}).get("energy") or 0.0
        for f in final_frames
    ]
    active_count = sum(final_vad_flags)
    high_energy_count = sum(1 for e in final_energies if e > (base_median + base_mad))
    abrupt_cutoff = (active_count >= 2) and (high_energy_count >= 2)

    # --- Feature 2: Trailing Silence ---
    # Walk backwards from end of timeline counting consecutive silent frames.
    trailing_silence_count = 0
    for f in reversed(timeline):
        vad_active = f.get("derived", {}).get("speech", {}).get("active")
        if not vad_active:
            trailing_silence_count += 1
        else:
            break
    trailing_silence_seconds = round(trailing_silence_count * hop_size, 2)

    # --- Feature 3: Final Window Overlap ---
    # Count overlapping speech transitions in an adaptive end-of-call window.
    final_window_secs = min(30.0, 0.20 * duration)
    window_start_ts = duration - final_window_secs
    window_segments = sorted(
        [s for s in segments if s.get("end", 0.0) >= window_start_ts],
        key=lambda s: s["start"],
    )
    final_overlap_count = 0
    for idx in range(1, len(window_segments)):
        gap = window_segments[idx]["start"] - window_segments[idx - 1]["end"]
        if gap < -0.2:
            final_overlap_count += 1

    interaction_integrity_features = {
        "abrupt_cutoff": abrupt_cutoff,
        "trailing_silence_seconds": trailing_silence_seconds,
        "final_window_overlap_count": final_overlap_count,
    }

    # Populate Audio Quality Anomalies (Phase 1)
    for d in dropout_events:
        timeline_anomalies["audio_quality"]["dropouts"].append(
            format_ts(d.get("start", 0.0))
        )

    current_noise_start = None
    for f in timeline:
        ts_sec = float(f.get("timestamp", 0.0))
        snr = f.get("raw", {}).get("quality", {}).get("snr_db")
        if snr is not None and snr < 20.0:
            if current_noise_start is None:
                current_noise_start = ts_sec
        else:
            if current_noise_start is not None:
                if (ts_sec - current_noise_start) >= 1.0:  # Sustained noise spike > 1s
                    timeline_anomalies["audio_quality"]["noise_spikes"].append(
                        f"{format_ts(current_noise_start)} - {format_ts(ts_sec)}"
                    )
                current_noise_start = None

    # Phase 2: Conversation Flow and Balance
    for p in pause_events:
        if float(p.get("duration", 0.0)) > 3.0:
            timeline_anomalies["conversation_flow"]["awkward_pauses"].append(
                format_ts(float(p.get("start", 0.0)))
            )

    for s in segments:
        if s.get("duration", 0.0) > 30.0:
            timeline_anomalies["conversation_balance"]["monologues"].append(
                f"{format_ts(s.get('start', 0.0))} - {format_ts(s.get('end', 0.0))}"
            )

    # Phase 3: Voice Stability and Collection Confidence
    current_crack_start = None
    for f in timeline:
        ts_sec = float(f.get("timestamp", 0.0))
        jit = f.get("raw", {}).get("prosody", {}).get("jitter_pct")
        shim = f.get("raw", {}).get("prosody", {}).get("shimmer_pct")
        if (jit is not None and jit > 3.0) or (shim is not None and shim > 10.0):
            if current_crack_start is None:
                current_crack_start = ts_sec
        else:
            if current_crack_start is not None:
                if (ts_sec - current_crack_start) >= 0.5:  # Sustained crack > 0.5s
                    timeline_anomalies["voice_stability"]["voice_cracks"].append(
                        f"{format_ts(current_crack_start)} - {format_ts(ts_sec)}"
                    )
                current_crack_start = None

    if interaction_integrity_features.get("abrupt_cutoff"):
        timeline_anomalies["interaction_integrity"]["abrupt_cutoff"].append(
            format_ts(duration)
        )

    return {
        "audio_quality": audio_quality,
        "voice_stability": voice_stability,
        "speech_behaviour": speech_behaviour,
        "conversation_behaviour": conversation_behaviour,
        "voice_quality": voice_quality,
        "response_dynamics": response_dynamics,
        "emotional_indicators": emotional_indicators,
        "interaction_integrity": interaction_integrity_features,
        "timeline_anomalies": timeline_anomalies,
    }
