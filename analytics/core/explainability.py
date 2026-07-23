from __future__ import annotations

from typing import Any
from analytics.models import ScoreResult


class ExplainabilityEngine:
    """Layer 3: Evaluates score values into qualitative grades and lists positive/negative contributing factors."""

    @classmethod
    def get_grade(cls, value: float, config: Any) -> str:
        """Determines the grade based on ScoreConfig thresholds."""
        thresholds = config.thresholds
        if value >= thresholds.get("Excellent", 90.0):
            return "Excellent"
        elif value >= thresholds.get("Good", 75.0):
            return "Good"
        elif value >= thresholds.get("Fair", 60.0):
            return "Fair"
        else:
            return "Poor"

    @classmethod
    def explain_audio_quality(
        cls, score_val: float, engineered: dict[str, Any], config: Any
    ) -> ScoreResult:
        aq = engineered.get("audio_quality", {})
        anomalies = engineered.get("timeline_anomalies", {}).get("audio_quality", {})
        pos = []
        neg = []

        # Check SNR & Noise Spikes
        snr = aq.get("average_snr", 0.0)
        noise_spikes = anomalies.get("noise_spikes", [])
        if snr >= 22.0 and not noise_spikes:
            pos.append("High Signal-to-Noise Ratio (SNR)")
        elif noise_spikes:
            neg.append(
                f"Loud background noise detected at {', '.join(noise_spikes[:3])}"
                + ("..." if len(noise_spikes) > 3 else "")
            )
        elif snr < 15.0:
            neg.append("Low Signal-to-Noise Ratio (SNR) - background noise present")

        # Check Noise Level
        noise = aq.get("noise_level", -60.0)
        if noise <= -48.0:
            pos.append("Quiet noise floor during silent intervals")
        elif noise > -42.0 and not noise_spikes:
            neg.append("Elevated background hum/noise floor")

        # Check Dropouts
        dropouts = anomalies.get("dropouts", [])
        if not dropouts:
            pos.append("Clean signal transmission with zero dropouts")
        else:
            neg.append(
                f"Audio transmission dropout(s) at {', '.join(dropouts[:3])}"
                + ("..." if len(dropouts) > 3 else "")
            )

        # Check Speech Quality Proxy
        speech_qual = aq.get("average_speech_quality", 1.0)
        if speech_qual >= 0.85:
            pos.append("Consistent voice signal clarity")
        elif speech_qual < 0.65:
            neg.append("Degraded vocal signal quality")

        return ScoreResult(
            name="Audio Quality Score",
            value=score_val,
            grade=cls.get_grade(score_val, config),
            positives=pos,
            negatives=neg,
        )

    @classmethod
    def explain_recording_reliability(
        cls, score_val: float, engineered: dict[str, Any], config: Any
    ) -> ScoreResult:
        aq = engineered.get("audio_quality", {})
        pos = []
        neg = []

        # Check Dropouts and signal loss
        dropouts = aq.get("dropout_count", 0)
        dropout_dur = aq.get("dropout_duration", 0.0)
        if dropouts == 0:
            pos.append("Continuous signal stream (no dropouts)")
        else:
            neg.append(
                f"Signal stream dropouts: {dropouts} occurrences ({dropout_dur:.1f}s total)"
            )

        # Check clipping
        clipping = aq.get("clipping_percentage", 0.0)
        if clipping < 0.2:
            pos.append("Zero signal amplitude clipping/distortion")
        else:
            neg.append(f"Audio clipping detected: {clipping:.2f}% of samples clipped")

        # Check noise stability
        stability = aq.get("recording_stability", 100.0)
        if stability >= 85.0:
            pos.append("Highly stable signal strength")
        else:
            neg.append("Unstable channel signal strength")

        return ScoreResult(
            name="Recording Reliability Score",
            value=score_val,
            grade=cls.get_grade(score_val, config),
            positives=pos,
            negatives=neg,
        )

    @classmethod
    def explain_voice_stability(
        cls, score_val: float, engineered: dict[str, Any], config: Any
    ) -> ScoreResult:
        vs = engineered.get("voice_stability", {})
        anomalies = engineered.get("timeline_anomalies", {}).get("voice_stability", {})
        pos = []
        neg = []

        # Pitch variation
        pitch_std = vs.get("pitch_stability", 0.0)
        if pitch_std < 12.0:
            pos.append("Highly stable fundamental pitch (monotone or calm)")
        elif pitch_std > 28.0:
            neg.append(
                "High pitch fluctuations (suggests emotional shaking or agitation)"
            )

        # Jitter and shimmer
        jitter = vs.get("avg_jitter_pct", 0.0)
        shimmer = vs.get("avg_shimmer_pct", 0.0)
        voice_cracks = anomalies.get("voice_cracks", [])

        if jitter < 1.5 and shimmer < 3.0 and not voice_cracks:
            pos.append("Stable vocal chords (low jitter/shimmer)")
        else:
            if voice_cracks:
                neg.append(
                    f"Severe voice distortion/crack(s) at {', '.join(voice_cracks[:3])}"
                    + ("..." if len(voice_cracks) > 3 else "")
                )
            elif jitter >= 2.5:
                neg.append("Micro-frequency tremors detected (high jitter)")
            elif shimmer >= 5.0:
                neg.append("Micro-amplitude breathing variations (high shimmer)")

        # Rhythmic stability
        speak_std = vs.get("speaking_stability", 0.0)
        if speak_std < 1.0:
            pos.append("Consistent speaking tempo and cadence")
        elif speak_std > 2.5:
            neg.append("Uneven speech rate (rushed or halting tempo)")

        return ScoreResult(
            name="Voice Stability Score",
            value=score_val,
            grade=cls.get_grade(score_val, config),
            positives=pos,
            negatives=neg,
        )

    @classmethod
    def explain_conversation_flow(
        cls, score_val: float, engineered: dict[str, Any], config: Any
    ) -> ScoreResult:
        flow = engineered.get("conversation_behaviour", {})
        sb = engineered.get("speech_behaviour", {})
        rd = engineered.get("response_dynamics", {})
        anomalies = engineered.get("timeline_anomalies", {}).get(
            "conversation_flow", {}
        )
        pos = []
        neg = []

        # Latency & Delays
        latency = flow.get("response_latency", 0.0)
        delays = anomalies.get("response_delays", [])
        if latency < 1.3 and not delays:
            pos.append("Fast conversational response latency")
        elif delays:
            neg.append(
                f"Awkward response delay(s) at {', '.join(delays[:3])}"
                + ("..." if len(delays) > 3 else "")
            )
        elif latency > 2.2:
            neg.append("Delayed response gaps (indicates hesitation or confusion)")

        # Overlaps & Interruptions
        overlaps = rd.get("overlap_count", 0)
        interruptions = anomalies.get("interruptions", [])
        if overlaps == 0:
            pos.append("Clean turn-taking with no double-talk")
        elif interruptions:
            neg.append(
                f"Severe interruption(s) at {', '.join(interruptions[:3])}"
                + ("..." if len(interruptions) > 3 else "")
            )
        elif overlaps > 4:
            neg.append(f"Frequent minor speaker overlaps: {overlaps} occurrences")

        # Speaker changes
        changes = flow.get("speaker_change_count", 0)
        if changes >= 15:
            pos.append("Active back-and-forth flow")
        elif changes < 6:
            neg.append("Stagnant turn exchange (long monologue chunks)")

        # Silence Behaviour
        awkward_pauses = anomalies.get("awkward_pauses", [])
        if awkward_pauses:
            neg.append(
                f"Awkward mid-turn pause(s) at {', '.join(awkward_pauses[:3])}"
                + ("..." if len(awkward_pauses) > 3 else "")
            )
        else:
            silence_pct = sb.get("silence_percentage", 0.0)
            if silence_pct > 35.0:
                neg.append(
                    f"Excessive general silence during the call ({silence_pct:.1f}%)"
                )

        return ScoreResult(
            name="Conversation Flow Score",
            value=score_val,
            grade=cls.get_grade(score_val, config),
            positives=pos,
            negatives=neg,
        )

    @classmethod
    def explain_conversation_balance(
        cls, score_val: float, engineered: dict[str, Any], config: Any
    ) -> ScoreResult:
        flow = engineered.get("conversation_behaviour", {})
        anomalies = engineered.get("timeline_anomalies", {}).get(
            "conversation_balance", {}
        )
        pos = []
        neg = []

        balance = flow.get("conversation_balance", 0.0)
        monologues = anomalies.get("monologues", [])

        if balance <= 15.0 and not monologues:
            pos.append("Perfect conversational balance between participants")
        elif monologues:
            neg.append(
                f"Prolonged monologue(s) detected at {', '.join(monologues[:2])}"
                + ("..." if len(monologues) > 2 else "")
            )
        elif balance > 50.0:
            neg.append(
                f"Highly dominated conversation: speaker imbalance of {balance:.1f}%"
            )

        turns = flow.get("turn_count", 0)
        if turns >= 18:
            pos.append("High turn parity (both speakers engaged)")
        elif turns < 8:
            neg.append("Low turn parity (one-sided monologue)")

        return ScoreResult(
            name="Conversation Balance Score",
            value=score_val,
            grade=cls.get_grade(score_val, config),
            positives=pos,
            negatives=neg,
        )

    @classmethod
    def explain_interaction_integrity(
        cls, score_val: float, engineered: dict[str, Any], config: Any
    ) -> ScoreResult:
        anomalies = engineered.get("timeline_anomalies", {}).get(
            "interaction_integrity", {}
        )
        ii = engineered.get("interaction_integrity", {})
        pos = []
        neg = []

        abrupt_cutoff = anomalies.get("abrupt_cutoff", [])
        if abrupt_cutoff:
            neg.append(
                f"Recording ended while speech was still active — "
                f"no trailing silence detected (at {abrupt_cutoff[0]})"
            )
        else:
            pos.append("Clean call termination with natural trailing silence")

        trailing = ii.get("trailing_silence_seconds", 0.0)
        if trailing < 0.5:
            neg.append(
                f"Only {int(trailing * 1000)}ms of silence before call ended "
                f"— expected ≥ 2 seconds for a clean termination"
            )
        elif trailing >= 1.5:
            pos.append(f"Natural conversation decay ({trailing:.1f}s trailing silence)")

        final_overlaps = ii.get("final_overlap_count", 0)
        if final_overlaps > 0:
            neg.append(
                f"{final_overlaps} overlapping speech event(s) detected "
                f"near the end of the call"
            )
        else:
            pos.append("Clean turn-taking in the final window of the call")

        return ScoreResult(
            name="Interaction Integrity Score",
            value=score_val,
            grade=cls.get_grade(score_val, config),
            positives=pos,
            negatives=neg,
        )


    @classmethod
    def explain_speech_activity(
        cls, score_val: float, engineered: dict[str, Any], config: Any
    ) -> ScoreResult:
        sb = engineered.get("speech_behaviour", {})
        pos = []
        neg = []

        speech_pct = sb.get("speech_percentage", 0.0)
        if speech_pct >= 70.0:
            pos.append("High active speech density (low dead air)")
        elif speech_pct < 50.0:
            neg.append(
                f"High amount of silence/non-speech intervals ({100.0 - speech_pct:.1f}%)"
            )

        # Pause behaviour
        pauses_min = sb.get("pause_frequency", 0.0)
        if pauses_min < 5.0:
            pos.append("Continuous fluent speech delivery")
        elif pauses_min > 12.0:
            neg.append("Frequent brief pauses breaking speaking flow")

        return ScoreResult(
            name="Speech Activity Score",
            value=score_val,
            grade=cls.get_grade(score_val, config),
            positives=pos,
            negatives=neg,
        )

    @classmethod
    def explain_overall_health(
        cls, score_val: float, explanations: dict[str, ScoreResult], config: Any
    ) -> ScoreResult:
        pos = []
        neg = []

        # Gather insights from sub-scores
        aq = explanations["audio_quality"]
        flow = explanations["conversation_flow"]
        vs = explanations["voice_stability"]

        if aq.value >= 85:
            pos.append("Excellent raw audio quality with stable channels")
        else:
            neg.append("Overall call health degraded by poor/unstable audio quality")

        if flow.value >= 80:
            pos.append("Fluent, interactive dialog exchange")
        elif flow.value < 60:
            neg.append(
                "Conversational flow interrupted by latency, dead air, or overlaps"
            )

        if vs.value >= 85:
            pos.append("Vocal registers remain calm, stable, and regular")
        elif vs.value < 65:
            neg.append("Frustrated, rapid, or trembling vocal pitch stability")

        return ScoreResult(
            name="Overall Call Health Score",
            value=score_val,
            grade=cls.get_grade(score_val, config),
            positives=pos,
            negatives=neg,
        )
