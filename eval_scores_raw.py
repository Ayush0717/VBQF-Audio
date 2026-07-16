import json
import glob
import sys

sys.path.insert(0, "/Users/ayushgoel/Mmfsl")
from analytics.core.scoring import compute_scores

files = glob.glob("data/outputs/rec*.json")
files.sort()

# Raw feature names to print
raw_keys = [
    ("AQ: SNR", "audio_quality", "average_snr"),
    ("AQ: Dropouts", "audio_quality", "dropout_count"),
    ("VS: PitchStd", "voice_stability", "pitch_stability"),
    ("VS: Jitter", "voice_stability", "avg_jitter_pct"),
    ("CF: Overlap", "response_dynamics", "overlap_count"),
    ("CF: Pause Freq", "speech_behaviour", "pause_frequency"),
    ("SA: Speech%", "speech_behaviour", "speech_percentage"),
]

header = f"{'File':<15} | {'Overall':<7}"
for name, _, _ in raw_keys:
    header += f" | {name:<12}"
print(header)
print("-" * 120)

for fpath in files:
    with open(fpath) as f:
        data = json.load(f)

    if "engineered_features" not in data:
        continue

    res = compute_scores(data["engineered_features"])
    s = res["scores"]
    eng = data["engineered_features"]

    name = fpath.split("/")[-1].replace("_features.json", "")

    row = f"{name:<15} | {s['overall_call_health']:>7}"
    for _, cat, key in raw_keys:
        val = eng.get(cat, {}).get(key, 0.0)
        if isinstance(val, float):
            row += f" | {val:>12.2f}"
        else:
            row += f" | {val:>12}"

    print(row)
