"""
run_all_scores.py
=================
Runs ALL pre-computed feature JSON files through the scoring engine
and prints a detailed breakdown:
  - All engineered features (per pillar)
  - All sub-scores inside each pillar
  - Gate multiplier components and final multiplier
  - Pillar scores
  - Overall health score

Usage:
  python run_all_scores.py
  python run_all_scores.py --json   # also dump full JSON output
"""

from __future__ import annotations
import sys, json, glob, argparse
from pathlib import Path

# -- Make sure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analytics.core.scoring import (
    compute_scores,
    _normalize_linear,
    _normalize_piecewise,
    _normalize_optimal_range,
    _normalize_threshold,
    calculate_gate_multiplier,
)


# ---------------------------------------------------------------------------
# Gate sub-component breakdown
# ---------------------------------------------------------------------------
def gate_breakdown(aq: dict, sb: dict) -> dict:
    snr         = aq.get("average_snr", 0.0)
    clip        = aq.get("clipping_percentage", 0.0)
    speech_pct  = sb.get("speech_percentage", 0.0)
    dropouts    = aq.get("dropout_count", 0)

    snr_score       = _normalize_linear(snr,  low=30.0, high=55.0) / 100.0
    clipping_score  = _normalize_linear(clip, low=2.0,  high=5.0, invert=True) / 100.0
    active_score    = _normalize_linear(speech_pct, low=25.0, high=50.0) / 100.0
    dropout_score   = 1.0 if dropouts <= 4 else max(0.0, 1.0 - (dropouts - 4) * 0.15)

    gate = min(snr_score, clipping_score, active_score, dropout_score)
    gate = max(0.2, gate)

    return {
        "inputs": {
            "average_snr_db":       round(snr, 2),
            "clipping_pct":         round(clip, 2),
            "speech_pct":           round(speech_pct, 1),
            "dropout_count":        dropouts,
        },
        "component_scores": {
            "snr_gate_score":       round(snr_score, 4),
            "clipping_gate_score":  round(clipping_score, 4),
            "speech_activity_gate": round(active_score, 4),
            "dropout_gate_score":   round(dropout_score, 4),
        },
        "final_gate_multiplier":    round(gate, 4),
    }


# ---------------------------------------------------------------------------
# Pillar sub-score breakdown
# ---------------------------------------------------------------------------
def pillar_breakdown(engineered: dict) -> dict:
    aq = engineered.get("audio_quality", {})
    vq = engineered.get("voice_quality", {})
    vs = engineered.get("voice_stability", {})
    sb = engineered.get("speech_behaviour", {})
    cb = engineered.get("conversation_behaviour", {})
    rd = engineered.get("response_dynamics", {})
    dt = engineered.get("decision_turn_features", {})

    snr_sub      = _normalize_piecewise(aq.get("average_snr", 0.0), [(0,0),(40,30),(50,60),(65,100)])
    quality_sub  = _normalize_linear(vq.get("avg_speech_quality", 0.0), low=0.3, high=1.0)
    noise_sub    = _normalize_linear(aq.get("noise_level", -60.0), low=-80.0, high=-10.0, invert=True)
    dropout_sub  = _normalize_piecewise(aq.get("dropout_count", 0), [(0,100),(1,95),(2,90),(3,75),(5,50),(10,0)])
    clipping_sub = _normalize_threshold(aq.get("clipping_percentage", 0.0), threshold=0.0, condition="<=", pass_score=100.0, fail_score=20.0)

    pitch_sub      = _normalize_linear(vs.get("pitch_stability", 0.0), low=12.0, high=30.0, invert=True)
    loud_std_sub   = _normalize_linear(vs.get("loudness_stability", 0.0), low=0.0, high=80.0, invert=True)
    jitter_sub     = _normalize_linear(vs.get("avg_jitter_pct", 0.0), low=1.5, high=3.0, invert=True)
    shimmer_sub    = _normalize_linear(vs.get("avg_shimmer_pct", 0.0), low=3.0, high=6.0, invert=True)
    speak_std_sub  = _normalize_linear(vs.get("speaking_stability", 0.0), low=1.0, high=3.0, invert=True)

    latency_sub  = _normalize_optimal_range(cb.get("response_latency", 0.0), 0.0, 0.5, 2.0, 5.0)
    overlap_sub  = _normalize_linear(rd.get("overlap_frequency", 0.0), low=0.0, high=10.0, invert=True)
    changes_sub  = _normalize_optimal_range(cb.get("speaker_change_count", 0), 0.0, 5.0, 25.0, 50.0)

    balance_sub    = _normalize_optimal_range(cb.get("conversation_balance", 0.0), 0.0, 20.0, 60.0, 90.0)
    turns_sub      = _normalize_optimal_range(cb.get("turn_count", 0), 2.0, 10.0, 30.0, 60.0)
    spk_count_sub  = {2: 100.0, 3: 50.0, 4: 25.0, 1: 0.0, 0: 0.0}.get(cb.get("speaker_count", 2), 25.0)

    speech_pct_sub  = _normalize_optimal_range(sb.get("speech_percentage", 0.0), 40.0, 50.0, 75.0, 95.0)
    pause_freq_sub  = _normalize_piecewise(sb.get("pause_frequency", 0.0), [(0,90),(2,100),(5,90),(10,60),(20,20),(30,0)])
    pause_dur_sub   = _normalize_optimal_range(sb.get("average_pause_duration", 0.0), 0.5, 1.0, 2.5, 4.5)

    pitch_slope_sub = _normalize_linear(dt.get("terminal_pitch_slope", 0.0), low=-50.0, high=100.0, invert=True)
    dur_z_sub       = _normalize_optimal_range(dt.get("decision_turn_duration_z", 0.0), -1.5, -0.5, 2.0, 5.0)
    loud_z_sub      = _normalize_linear(dt.get("answer_loudness_z", 0.0), low=-2.0, high=2.0)
    voice_frac_sub  = _normalize_linear(dt.get("voicing_fraction", 0.0), low=0.4, high=0.9)
    cutoff_sub      = 0.0 if dt.get("abrupt_cutoff", False) else 100.0
    backchannel_sub = _normalize_linear(dt.get("backchannel_composite", 0.0), low=0.0, high=1.0, invert=True)

    return {
        "audio_quality": {
            "snr_sub (30%)":         round(snr_sub, 1),
            "quality_sub (25%)":     round(quality_sub, 1),
            "noise_sub (15%)":       round(noise_sub, 1),
            "dropout_sub (15%)":     round(dropout_sub, 1),
            "clipping_sub (15%)":    round(clipping_sub, 1),
        },
        "voice_stability": {
            "pitch_std_sub (25%)":   round(pitch_sub, 1),
            "loudness_std_sub (20%)":round(loud_std_sub, 1),
            "jitter_sub (25%)":      round(jitter_sub, 1),
            "shimmer_sub (20%)":     round(shimmer_sub, 1),
            "speaking_std_sub (10%)":round(speak_std_sub, 1),
        },
        "conversation_flow": {
            "latency_sub (40%)":     round(latency_sub, 1),
            "overlap_sub (30%)":     round(overlap_sub, 1),
            "changes_sub (30%)":     round(changes_sub, 1),
        },
        "conversation_balance": {
            "balance_sub (40%)":     round(balance_sub, 1),
            "turns_sub (30%)":       round(turns_sub, 1),
            "spk_count_sub (30%)":   round(spk_count_sub, 1),
        },
        "speech_activity": {
            "speech_pct_sub (40%)":  round(speech_pct_sub, 1),
            "pause_freq_sub (30%)":  round(pause_freq_sub, 1),
            "pause_dur_sub (30%)":   round(pause_dur_sub, 1),
        },
        "collection_confidence": {
            "pitch_slope_sub (25%)": round(pitch_slope_sub, 1),
            "dur_z_sub (20%)":       round(dur_z_sub, 1),
            "loudness_z_sub (20%)":  round(loud_z_sub, 1),
            "voicing_frac_sub (15%)":round(voice_frac_sub, 1),
            "cutoff_sub (10%)":      round(cutoff_sub, 1),
            "backchannel_sub (10%)": round(backchannel_sub, 1),
        },
    }


PILLAR_WEIGHTS = {
    "collection_confidence": 0.30,
    "audio_quality":         0.20,
    "conversation_flow":     0.20,
    "voice_stability":       0.10,
    "conversation_balance":  0.10,
    "speech_activity":       0.10,
}

def label(score):
    if score >= 90: return "EXCELLENT"
    if score >= 75: return "GOOD"
    if score >= 60: return "FAIR"
    return "POOR"

def bar(score, width=28):
    filled = int(score / 100 * width)
    return "[" + "#" * filled + "." * (width - filled) + f"] {score:>5.1f}"


def print_report(name, ef, scores, gate, subs):
    aq = ef.get("audio_quality", {})
    vq = ef.get("voice_quality", {})
    vs = ef.get("voice_stability", {})
    sb = ef.get("speech_behaviour", {})
    cb = ef.get("conversation_behaviour", {})
    rd = ef.get("response_dynamics", {})
    dt = ef.get("decision_turn_features", {})

    SEP = "=" * 90

    print(f"\n{SEP}")
    print(f"  FILE: {name}")
    print(SEP)

    print("\n  [AUDIO QUALITY - engineered features]")
    print(f"    avg_snr_db          : {aq.get('average_snr', 'N/A')}")
    print(f"    noise_level_db      : {aq.get('noise_level', 'N/A')}")
    print(f"    dropout_count       : {aq.get('dropout_count', 'N/A')}")
    print(f"    dropout_duration    : {aq.get('dropout_duration', 'N/A')}s")
    print(f"    clipping_pct        : {aq.get('clipping_percentage', 'N/A')}%")
    print(f"    avg_speech_quality  : {vq.get('avg_speech_quality', 'N/A')}")

    print("\n  [VOICE STABILITY - engineered features]")
    print(f"    pitch_std           : {vs.get('pitch_stability', 'N/A')} Hz")
    print(f"    loudness_std        : {vs.get('loudness_stability', 'N/A')} dB")
    print(f"    avg_jitter_pct      : {vs.get('avg_jitter_pct', 'N/A')}%")
    print(f"    avg_shimmer_pct     : {vs.get('avg_shimmer_pct', 'N/A')}%")
    print(f"    speaking_rate_std   : {vs.get('speaking_stability', 'N/A')} sps")

    print("\n  [SPEECH BEHAVIOUR - engineered features]")
    print(f"    speech_pct          : {sb.get('speech_percentage', 'N/A')}%")
    print(f"    pause_count         : {sb.get('pause_count', 'N/A')}")
    print(f"    avg_pause_duration  : {sb.get('average_pause_duration', 'N/A')}s")
    print(f"    pause_freq/min      : {sb.get('pause_frequency', 'N/A')}")

    print("\n  [CONVERSATION BEHAVIOUR - engineered features]")
    print(f"    speaker_count       : {cb.get('speaker_count', 'N/A')}")
    print(f"    turn_count          : {cb.get('turn_count', 'N/A')}")
    print(f"    speaker_changes     : {cb.get('speaker_change_count', 'N/A')}")
    print(f"    response_latency    : {cb.get('response_latency', 'N/A')}s")
    print(f"    conv_balance_diff   : {cb.get('conversation_balance', 'N/A')}%")
    print(f"    overlap_freq/min    : {rd.get('overlap_frequency', 'N/A')}")

    print("\n  [DECISION TURN FEATURES]")
    if dt:
        print(f"    terminal_pitch_slope: {dt.get('terminal_pitch_slope', 'N/A')}")
        print(f"    decision_turn_dur_z : {dt.get('decision_turn_duration_z', 'N/A')}")
        print(f"    answer_loudness_z   : {dt.get('answer_loudness_z', 'N/A')}")
        print(f"    voicing_fraction    : {dt.get('voicing_fraction', 'N/A')}")
        print(f"    abrupt_cutoff       : {dt.get('abrupt_cutoff', 'N/A')}")
        print(f"    backchannel_compos. : {dt.get('backchannel_composite', 'N/A')}")
    else:
        print("    (no decision turn detected)")

    print(f"\n  {'-'*88}")
    print("  USABILITY GATE MULTIPLIER")
    gcomp = gate["component_scores"]
    ginp  = gate["inputs"]
    print(f"    avg SNR         : {ginp['average_snr_db']:>8} dB   gate score: {gcomp['snr_gate_score']:.4f}")
    print(f"    clipping        : {ginp['clipping_pct']:>8}%    gate score: {gcomp['clipping_gate_score']:.4f}")
    print(f"    speech activity : {ginp['speech_pct']:>8}%    gate score: {gcomp['speech_activity_gate']:.4f}")
    print(f"    dropout count   : {ginp['dropout_count']:>8}     gate score: {gcomp['dropout_gate_score']:.4f}")
    print(f"    >> GATE MULTIPLIER = {gate['final_gate_multiplier']:.4f}  ({gate['final_gate_multiplier']*100:.1f}%)")

    print(f"\n  {'-'*88}")
    print("  PILLAR SUB-SCORES")
    for pillar, sub_dict in subs.items():
        pillar_score = scores.get(pillar, 0)
        w = PILLAR_WEIGHTS.get(pillar, 0)
        print(f"\n    [{pillar.upper().replace('_',' ')}]  Score={pillar_score}  ({label(pillar_score)})  weight={w*100:.0f}%")
        for k, v in sub_dict.items():
            print(f"      {k:<32}: {bar(v)}")

    print(f"\n  {'-'*88}")
    print("  PILLAR SCORES SUMMARY")
    pillar_keys = ["collection_confidence", "audio_quality", "voice_stability",
                   "conversation_flow", "conversation_balance", "speech_activity"]
    for pk in pillar_keys:
        sc = scores.get(pk, 0)
        w  = PILLAR_WEIGHTS.get(pk, 0)
        wc = sc * w
        print(f"    {pk:<28} {bar(sc)}  wt={w*100:.0f}%  contrib={wc:.1f}")

    overall = scores.get("overall_call_health", 0)
    gate_m  = gate["final_gate_multiplier"]
    raw_health = sum(scores.get(pk, 0) * PILLAR_WEIGHTS.get(pk, 0) for pk in pillar_keys)
    print(f"\n  {'='*88}")
    print(f"    raw_health (pre-gate) = {raw_health:.1f}")
    print(f"    gate_multiplier       = {gate_m:.4f}")
    print(f"    gated_health          = {raw_health:.1f} x {gate_m:.4f} = {raw_health*gate_m:.1f}")
    print(f"    >> OVERALL CALL HEALTH = {overall}   [{label(overall)}]")
    print(f"  {'='*88}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Also dump full JSON")
    parser.add_argument("--file", default=None, help="Run a single specific feature JSON file")
    args = parser.parse_args()

    if args.file:
        files = [Path(args.file)]
    else:
        base = Path(__file__).resolve().parent / "data" / "outputs"
        files = sorted(base.glob("*.json"))
        files = [f for f in files if "copy" not in f.name.lower()]

    all_results = []

    for fpath in files:
        fpath = Path(fpath)
        try:
            data = json.loads(fpath.read_text())
        except Exception as e:
            print(f"[SKIP] {fpath.name}: cannot read - {e}")
            continue

        ef = data.get("engineered_features")
        if not ef:
            print(f"[SKIP] {fpath.name}: no engineered_features section")
            continue

        try:
            result = compute_scores(ef)
            scores = result["scores"]
            gate   = gate_breakdown(ef.get("audio_quality", {}), ef.get("speech_behaviour", {}))
            subs   = pillar_breakdown(ef)
        except Exception as e:
            print(f"[ERROR] {fpath.name}: {e}")
            import traceback; traceback.print_exc()
            continue

        print_report(fpath.name, ef, scores, gate, subs)

        all_results.append({
            "file": fpath.name,
            "engineered_features": ef,
            "gate": gate,
            "sub_scores": subs,
            "scores": scores,
        })

    if len(all_results) > 1:
        print("\n\n" + "=" * 112)
        print("  SUMMARY TABLE - ALL FILES")
        print("=" * 112)
        print(f"  {'File':<28} | {'CC':>4} | {'AQ':>4} | {'VS':>4} | {'CF':>4} | {'CB':>4} | {'SA':>4} | {'Gate':>6} | {'Overall':>7} | Label")
        print("  " + "-" * 109)
        for r in all_results:
            s = r["scores"]
            g = r["gate"]["final_gate_multiplier"]
            n = r["file"].replace("_features.json", "")
            print(
                f"  {n:<28} | {s.get('collection_confidence',0):>4} | {s.get('audio_quality',0):>4} "
                f"| {s.get('voice_stability',0):>4} | {s.get('conversation_flow',0):>4} "
                f"| {s.get('conversation_balance',0):>4} | {s.get('speech_activity',0):>4} "
                f"| {g:>6.3f} | {s.get('overall_call_health',0):>7} | {label(s.get('overall_call_health',0))}"
            )
        print("=" * 112)

    if args.json:
        print(json.dumps(all_results, indent=2, default=str))


if __name__ == "__main__":
    main()
