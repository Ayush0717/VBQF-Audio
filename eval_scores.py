import json
import glob
import sys

sys.path.insert(0, "/Users/ayushgoel/Mmfsl")
from analytics.core.scoring import compute_scores

files = glob.glob("data/outputs/rec*.json")
files.sort()

print(
    f"{'File':<25} | {'Overall':<7} | {'AQ':<3} | {'RR':<3} | {'VS':<3} | {'CF':<3} | {'CB':<3} | {'SA':<3}"
)
print("-" * 75)

for fpath in files:
    with open(fpath) as f:
        data = json.load(f)

    if "engineered_features" not in data:
        print(f"{fpath:<25} | Missing engineered_features")
        continue

    res = compute_scores(data["engineered_features"])
    s = res["scores"]

    name = fpath.split("/")[-1].replace("_features.json", "")
    print(
        f"{name:<25} | {s['overall_call_health']:>7} | {s['audio_quality']:>3} | {s['recording_reliability']:>3} | {s['voice_stability']:>3} | {s['conversation_flow']:>3} | {s['conversation_balance']:>3} | {s['speech_activity']:>3}"
    )
