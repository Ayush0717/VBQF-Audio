import json
import glob
import sys
import os

sys.path.insert(0, "/Users/ayushgoel/Mmfsl")
from analytics.core.scoring import compute_scores

files = glob.glob("data/outputs/*.json")

for fpath in files:
    with open(fpath, "r") as f:
        data = json.load(f)

    if "engineered_features" not in data:
        continue

    res = compute_scores(data["engineered_features"])
    data["analysis_results"] = res
    
    # Legacy top-level keys (if needed by other scripts)
    data["scores"] = res["scores"]
    data["explanations"] = res["explanations"]
    data["alerts"] = res.get("alerts", [])
    data["warnings"] = res.get("warnings", [])

    # Save back to file
    with open(fpath, "w") as f:
        json.dump(data, f, indent=4)

print(f"Successfully updated scores for {len(files)} JSON files.")
