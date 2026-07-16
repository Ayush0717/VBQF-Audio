import sys, json

sys.path.insert(0, "/Users/ayushgoel/Mmfsl")

from analytics.core.scoring import compute_scores

with open("data/outputs/call_features.json") as f:
    data = json.load(f)

# Re-run pipeline engineered features mapping
eng = data["engineered_features"]

# Run new compute scores
res = compute_scores(eng)
scores = res["scores"]

print("=" * 60)
print("RE-CALIBRATED PILLAR SCORES (NON-LINEAR/CATEGORICAL SUPPORT)")
print("=" * 60)
for k, v in scores.items():
    print(f"  {k:30s} : {v}/100")
print()
print("OVERALL HEALTH: ", scores["overall_call_health"])
print("=" * 60)
