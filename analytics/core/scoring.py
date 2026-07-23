from __future__ import annotations

from typing import Any
from config import ScoreConfig, DEFAULT_CONFIG, CallType, CALL_TYPE_BALANCE_BANDS
from analytics.core.explainability import ExplainabilityEngine
from analytics.models import ScoreResult


def _normalize_linear(
    value: float, low: float, high: float, invert: bool = False
) -> float:
    """Standard min-max linear normalization to a 0–100 scale."""
    if high <= low:
        return 50.0
    clamped = max(low, min(high, value))
    ratio = (clamped - low) / (high - low)
    if invert:
        return (1.0 - ratio) * 100.0
    return ratio * 100.0


def _normalize_optimal_range(
    value: float, low_bound: float, opt_start: float, opt_end: float, high_bound: float
) -> float:
    """Normalizes value to 0-100 where [opt_start, opt_end] is the ideal range (scoring 100%).
    Values decaying below opt_start down to low_bound drop to 0.
    Values decaying above opt_end up to high_bound drop to 0.
    """
    if opt_start <= value <= opt_end:
        return 100.0
    if value < opt_start:
        if opt_start <= low_bound:
            return 0.0
        clamped = max(low_bound, value)
        return ((clamped - low_bound) / (opt_start - low_bound)) * 100.0
    else:
        if high_bound <= opt_end:
            return 0.0
        clamped = min(high_bound, value)
        return (1.0 - (clamped - opt_end) / (high_bound - opt_end)) * 100.0


def _normalize_categorical(
    value: Any, mapping: dict[Any, float], default: float = 0.0
) -> float:
    """Direct category mapping to a score value (0–100)."""
    return float(mapping.get(value, default))


def _normalize_piecewise(value: float, points: list[tuple[float, float]]) -> float:
    """
    Interpolates a score based on a defined curve of (value, score) points.
    Points must be sorted by value (x-axis).
    """
    if not points:
        return 0.0
    points = sorted(points, key=lambda p: p[0])
    if value <= points[0][0]:
        return float(points[0][1])
    if value >= points[-1][0]:
        return float(points[-1][1])
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        if x1 <= value <= x2:
            if x1 == x2:
                return float(y1)
            ratio = (value - x1) / (x2 - x1)
            return float(y1 + ratio * (y2 - y1))
    return 0.0


def _normalize_threshold(
    value: float,
    threshold: float,
    pass_score: float = 100.0,
    fail_score: float = 0.0,
    condition: str = "<=",
) -> float:
    """Applies a strict threshold. condition can be '<=', '<', '>=', '>', '=='"""
    passed = False
    if condition == "<=":
        passed = value <= threshold
    elif condition == "<":
        passed = value < threshold
    elif condition == ">=":
        passed = value >= threshold
    elif condition == ">":
        passed = value > threshold
    elif condition == "==":
        passed = value == threshold
    return float(pass_score if passed else fail_score)


def calculate_gate_multiplier(
    aq: dict[str, Any], sb: dict[str, Any]
) -> dict[str, Any]:
    """
    Computes a Usability Gate multiplier between 0.0 and 1.0.

    The gate answers one question: "Can we trust this recording?"
    If the answer is no, the overall score SHOULD collapse — a good-looking score
    from a bad recording is actively misleading.

    Returns a structured dict (not just a float) so callers and the UI can
    explain exactly which component was the bottleneck.

    Gate components:
      snr       — Signal-to-noise ratio. Range calibrated from telephony norms
                  (30 dB = very noisy, 55 dB = clean). TODO: recalibrate from
                  1000+ production calls once available.
      clipping  — Amplitude clipping ratio. > 2% degrades intelligibility.
      speech    — Speech activity percentage. < 25% means not enough content.
      dropout   — Recording interruptions. > 4 dropouts indicates connectivity issues.

    Floor is 0.2 (not raised) — a fundamentally bad recording should score badly.
    """
    # SNR Gate: 0.0 at <= 30.0 dB, 1.0 at >= 55.0 dB
    snr = aq.get("average_snr", 0.0)
    snr_score = _normalize_linear(snr, low=30.0, high=55.0, invert=False) / 100.0

    # Clipping Gate: 1.0 if <= 2%, 0.0 at >= 5%
    clip = aq.get("clipping_percentage", 0.0)
    clipping_score = _normalize_linear(clip, low=2.0, high=5.0, invert=True) / 100.0

    # Speech Activity Gate: 0.0 at <= 25%, 1.0 at >= 50%
    speech_pct = sb.get("speech_percentage", 0.0)
    active_ratio_score = (
        _normalize_linear(speech_pct, low=25.0, high=50.0, invert=False) / 100.0
    )

    # Dropout Gate: 1.0 for <= 4 dropouts, -0.15 per dropout above 4
    dropouts = aq.get("dropout_count", 0)
    if dropouts <= 4:
        dropout_score = 1.0
    else:
        dropout_score = max(0.0, 1.0 - (dropouts - 4) * 0.15)

    # Bottleneck = whichever component is lowest (strict min, not average)
    component_map = {
        "snr": snr_score,
        "clipping": clipping_score,
        "speech_activity": active_ratio_score,
        "dropout": dropout_score,
    }
    bottleneck = min(component_map, key=component_map.get)
    gate_multiplier = max(0.2, min(component_map.values()))

    return {
        "multiplier": gate_multiplier,
        "bottleneck": bottleneck,
        "components": {
            "snr": round(snr_score, 4),
            "clipping": round(clipping_score, 4),
            "speech_activity": round(active_ratio_score, 4),
            "dropout": round(dropout_score, 4),
        },
        "inputs": {
            "average_snr_db": round(snr, 2),
            "clipping_pct": round(clip, 2),
            "speech_pct": round(speech_pct, 1),
            "dropout_count": dropouts,
        },
    }


def compute_scores(
    engineered: dict[str, Any], score_config: ScoreConfig | None = None
) -> dict[str, Any]:
    """
    Computes Layer 3 quality scores using normalized sub-feature scoring.
    Supports linear, optimal-range, and categorical scoring mappings.
    """
    if score_config is None:
        score_config = DEFAULT_CONFIG.score

    aq = engineered.get("audio_quality", {})
    vq = engineered.get("voice_quality", {})
    vs = engineered.get("voice_stability", {})
    sb = engineered.get("speech_behaviour", {})
    cb = engineered.get("conversation_behaviour", {})
    rd = engineered.get("response_dynamics", {})

    # ══════════════════════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════════════════════
    # PILLAR 1: AUDIO QUALITY SCORE (Merged with Recording Reliability)
    # ══════════════════════════════════════════════════════════════════════
    snr_sub = _normalize_piecewise(
        aq.get("average_snr", 0.0), [(0, 0), (40, 30), (50, 60), (65, 100)]
    )
    quality_sub = _normalize_linear(
        vq.get("avg_speech_quality", 0.0), low=0.3, high=1.0, invert=False
    )
    noise_sub = _normalize_linear(
        aq.get("noise_level", -60.0), low=-80.0, high=-10.0, invert=True
    )
    dropout_sub = _normalize_piecewise(
        aq.get("dropout_count", 0),
        [(0, 100), (1, 95), (2, 90), (3, 75), (5, 50), (10, 0)],
    )
    clipping_sub = _normalize_threshold(
        aq.get("clipping_percentage", 0.0),
        threshold=0.0,
        condition="<=",
        pass_score=100.0,
        fail_score=20.0,
    )

    aq_score = (
        (0.30 * snr_sub)
        + (0.25 * quality_sub)
        + (0.15 * noise_sub)
        + (0.15 * dropout_sub)
        + (0.15 * clipping_sub)
    )
    aq_score = max(0, min(100, int(round(aq_score))))

    # ══════════════════════════════════════════════════════════════════════
    # PILLAR 2: VOICE STABILITY SCORE
    # ══════════════════════════════════════════════════════════════════════
    # Sub-feature thresholds kept at design values.
    # Internal weights come from score_config.voice_stability_weights so
    # they can be tuned without touching this function.
    #
    # Current weight rationale (derived from feature inspection):
    #   pitch_std   → SEPARATES good/bad recordings (21–87 Hz range)
    #   loudness_std → SEPARATES (6–58 dB range)
    #   jitter_pct  → NOT PREDICTIVE — nearly identical across all labels (34–50%)
    #   shimmer_pct → NOT PREDICTIVE — nearly identical across all labels (20–22%)
    #   speaking_std → limited separation; kept for structural completeness
    #
    # TODO: recalibrate thresholds when labeled production data is available.
    # Do NOT change them based on this 11-recording sample.
    pitch_sub = _normalize_linear(
        vs.get("pitch_stability", 0.0), low=12.0, high=90.0, invert=True
    )
    loud_std_sub = _normalize_linear(
        vs.get("loudness_stability", 0.0), low=0.0, high=80.0, invert=True
    )
    jitter_sub = _normalize_linear(
        vs.get("avg_jitter_pct", 0.0), low=1.5, high=3.0, invert=True
    )
    shimmer_sub = _normalize_linear(
        vs.get("avg_shimmer_pct", 0.0), low=3.0, high=6.0, invert=True
    )
    speak_std_sub = _normalize_linear(
        vs.get("speaking_stability", 0.0), low=1.0, high=3.0, invert=True
    )

    vsw = score_config.voice_stability_weights
    vs_score = (
        (vsw.get("pitch_sub", 0.45)     * pitch_sub)
        + (vsw.get("loud_std_sub", 0.35) * loud_std_sub)
        + (vsw.get("jitter_sub", 0.10)   * jitter_sub)
        + (vsw.get("shimmer_sub", 0.05)  * shimmer_sub)
        + (vsw.get("speak_std_sub", 0.05) * speak_std_sub)
    )
    vs_score = max(0, min(100, int(round(vs_score))))

    # ══════════════════════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════════════════════
    # PILLAR 3: CONVERSATION FLOW SCORE (Interaction specific)
    # ══════════════════════════════════════════════════════════════════════
    latency_sub = _normalize_optimal_range(
        cb.get("response_latency", 0.0),
        low_bound=0.0,
        opt_start=0.5,
        opt_end=2.0,
        high_bound=5.0,
    )
    overlap_sub = _normalize_linear(
        rd.get("overlap_frequency", 0.0), low=0.0, high=10.0, invert=True
    )
    changes_sub = _normalize_optimal_range(
        cb.get("speaker_change_count", 0),
        low_bound=0.0,
        opt_start=5.0,
        opt_end=25.0,
        high_bound=50.0,
    )

    flow_score = (0.40 * latency_sub) + (0.30 * overlap_sub) + (0.30 * changes_sub)
    flow_score = max(0, min(100, int(round(flow_score))))

    # ══════════════════════════════════════════════════════════════════════
    # PILLAR 4: CONVERSATION BALANCE SCORE
    # ══════════════════════════════════════════════════════════════════════
    # "Balance" is philosophically different per call type.
    # A collection call is not a debate — agent speaking 70% is correct.
    # A survey should be near 50/50.
    # We look up the optimal band from config, keyed by call_type.
    call_type = score_config.call_type
    balance_band = CALL_TYPE_BALANCE_BANDS.get(
        call_type, CALL_TYPE_BALANCE_BANDS[CallType.COLLECTION]
    )
    balance_sub = _normalize_optimal_range(
        cb.get("conversation_balance", 0.0),
        low_bound=balance_band[0],
        opt_start=balance_band[1],
        opt_end=balance_band[2],
        high_bound=balance_band[3],
    )
    turns_sub = _normalize_optimal_range(
        cb.get("turn_count", 0),
        low_bound=2.0,
        opt_start=10.0,
        opt_end=30.0,
        high_bound=60.0,
    )
    spk_count_sub = _normalize_categorical(
        cb.get("speaker_count", 2),
        mapping={2: 100.0, 3: 50.0, 4: 25.0, 1: 0.0, 0: 0.0},
        default=25.0,
    )

    balance_score = (0.40 * balance_sub) + (0.30 * turns_sub) + (0.30 * spk_count_sub)
    balance_score = max(0, min(100, int(round(balance_score))))

    # ══════════════════════════════════════════════════════════════════════
    # PILLAR 5: SPEECH ACTIVITY SCORE (Pacing specific)
    # ══════════════════════════════════════════════════════════════════════
    speech_pct_sub = _normalize_optimal_range(
        sb.get("speech_percentage", 0.0),
        low_bound=40.0,
        opt_start=50.0,
        opt_end=75.0,
        high_bound=95.0,
    )
    pause_freq_sub = _normalize_piecewise(
        sb.get("pause_frequency", 0.0),
        [(0, 90), (2, 100), (5, 90), (10, 60), (20, 20), (30, 0)],
    )
    pause_dur_sub = _normalize_optimal_range(
        sb.get("average_pause_duration", 0.0),
        low_bound=0.5,
        opt_start=1.0,
        opt_end=2.5,
        high_bound=4.5,
    )

    sa_score = (
        (0.40 * speech_pct_sub) + (0.30 * pause_freq_sub) + (0.30 * pause_dur_sub)
    )
    sa_score = max(0, min(100, int(round(sa_score))))

    # ══════════════════════════════════════════════════════════════════════
    # PILLAR 6: INTERACTION INTEGRITY SCORE
    # ══════════════════════════════════════════════════════════════════════
    # Three objective, acoustically grounded structural features.
    # No psychoacoustic inference. No speaker intent assumptions.
    # Weights: Abrupt Cutoff 35% | Trailing Silence 35% | Final Overlap 30%
    ii = engineered.get("interaction_integrity", {})

    cutoff_sub = 0.0 if ii.get("abrupt_cutoff", False) else 100.0

    trailing_silence_sub = _normalize_linear(
        ii.get("trailing_silence_seconds", 0.0),
        low=0.0,
        high=2.0,
        invert=False,
    )

    final_overlap_sub = _normalize_linear(
        float(ii.get("final_overlap_count", 0)),
        low=0.0,
        high=2.0,
        invert=True,
    )

    ii_score = (
        (0.35 * cutoff_sub)
        + (0.35 * trailing_silence_sub)
        + (0.30 * final_overlap_sub)
    )
    ii_score = max(0, min(100, int(round(ii_score))))

    # Generate Explanations using ExplainabilityEngine
    explanations = {
        "interaction_integrity": (
            ExplainabilityEngine.explain_interaction_integrity(
                ii_score, engineered, score_config
            )
            if hasattr(ExplainabilityEngine, "explain_interaction_integrity")
            else None
        ),
        "audio_quality": ExplainabilityEngine.explain_audio_quality(
            aq_score, engineered, score_config
        ),
        "voice_stability": ExplainabilityEngine.explain_voice_stability(
            vs_score, engineered, score_config
        ),
        "conversation_flow": ExplainabilityEngine.explain_conversation_flow(
            flow_score, engineered, score_config
        ),
        "conversation_balance": ExplainabilityEngine.explain_conversation_balance(
            balance_score, engineered, score_config
        ),
        "speech_activity": ExplainabilityEngine.explain_speech_activity(
            sa_score, engineered, score_config
        ),
    }

    # Remove None values if ExplainabilityEngine isn't updated yet
    explanations = {k: v for k, v in explanations.items() if v is not None}

    # ══════════════════════════════════════════════════════════════════════
    # OVERALL CALL HEALTH (Weighted Composite + Gate Multiplier)
    # ══════════════════════════════════════════════════════════════════════
    w = score_config.weights
    w_sum = sum(w.values())
    if w_sum <= 0:
        w_sum = 1.0

    raw_health = (
        (w.get("interaction_integrity", 0.20) * ii_score)
        + (w.get("audio_quality", 0.25) * aq_score)
        + (w.get("voice_stability", 0.10) * vs_score)
        + (w.get("conversation_flow", 0.25) * flow_score)
        + (w.get("conversation_balance", 0.10) * balance_score)
        + (w.get("speech_activity", 0.10) * sa_score)
    ) / w_sum

    # Calculate Gate Multiplier
    # Returns structured dict — multiplier + per-component breakdown for explainability
    gate_result = calculate_gate_multiplier(aq, sb)
    gate_multiplier = gate_result["multiplier"]

    # Apply strict gate penalty — the gate is intentionally NOT weakened.
    # A bad recording should produce a bad score.
    gated_health = raw_health * gate_multiplier
    overall_health = max(0, min(100, int(round(gated_health))))

    explanations["overall_call_health"] = ExplainabilityEngine.explain_overall_health(
        overall_health, explanations, score_config
    )

    scores_dict = {
        "interaction_integrity": ii_score,
        "audio_quality": aq_score,
        "voice_stability": vs_score,
        "conversation_flow": flow_score,
        "conversation_balance": balance_score,
        "speech_activity": sa_score,
        "overall_call_health": overall_health,
        "gate_multiplier": gate_multiplier,
        "gate_bottleneck": gate_result["bottleneck"],
    }

    explanations_dict = {key: result.to_dict() for key, result in explanations.items()}

    return {
        "scores": scores_dict,
        "gate": gate_result,
        "explanations": explanations_dict,
        "alerts": [],
        "warnings": [],
    }

