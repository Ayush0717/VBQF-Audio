import json
import glob
from pathlib import Path
import pandas as pd
import re

def derive_batch_business_fields(explanations: dict) -> dict:
    if not explanations:
        return {"impact": "", "action": "", "nextStep": "No action required", "worstPillar": None, "secondWorstPillar": None}

    worst_pillar = None
    worst_score = 100
    second_worst_pillar = None
    second_worst_score = 100

    for key, data in explanations.items():
        if key == "overall_call_health":
            continue
        val = data.get("value", 100)
        if val < worst_score:
            second_worst_pillar = worst_pillar
            second_worst_score = worst_score
            worst_pillar = key
            worst_score = val
        elif val < second_worst_score:
            second_worst_pillar = key
            second_worst_score = val

    impact_map = {
        "voice_stability": {"impact": "Possible customer distress — escalation risk", "action": "Review voice stability segment"},
        "conversation_flow": {"impact": "Failed/incomplete interaction — possible callback required", "action": "Review response delay/interruption segment"},
        "audio_quality": {"impact": "Recording unreliable for compliance audit", "action": "Escalate to IT/vendor"},
        "conversation_balance": {"impact": "One-sided interaction — training opportunity", "action": "Schedule agent coaching"},
        "collection_confidence": {"impact": "Abrupt termination — possible failed collection", "action": "Flag for re-attempt"},
        "speech_activity": {"impact": "Excessive dead air — system or connection issue", "action": "Check for connection issues"},
    }

    mapped = impact_map.get(worst_pillar, {"impact": "", "action": ""})
    needs_review = worst_score < 75

    return {
        "impact": mapped["impact"],
        "action": mapped["action"],
        "nextStep": "Listen to investigation timestamps" if needs_review else "No action required",
        "worstPillar": worst_pillar,
        "secondWorstPillar": second_worst_pillar
    }

def generate_batch_csv(outputs_dir: str = "data/outputs", exports_dir: str = "exports"):
    outputs_path = Path(outputs_dir)
    exports_path = Path(exports_dir)
    exports_path.mkdir(parents=True, exist_ok=True)
    
    json_files = [f for f in outputs_path.glob("*_features.json") if "copy" not in f.name]
    
    rows = []
    
    for jf in json_files:
        call_id = jf.name.replace("_features.json", "")
        with open(jf, "r") as f:
            try:
                data = json.load(f)
            except Exception:
                continue
                
        meta = data.get("metadata", {})
        summary = data.get("summary", {})
        analysis = data.get("analysis_results", {})
        scores = analysis.get("scores", {})
        expl = analysis.get("explanations", {})
        eng = data.get("engineered_features", {})
        
        aq = eng.get("audio_quality", {})
        vs = eng.get("voice_stability", {})
        sb = eng.get("speech_behaviour", {})
        cb = eng.get("conversation_behaviour", {})
        vq = eng.get("voice_quality", {})
        rd = eng.get("response_dynamics", {})
        anomalies = eng.get("timeline_anomalies", {})
        
        overall_score = scores.get("overall_call_health", "")
        overall_grade = expl.get("overall_call_health", {}).get("grade", "")
        
        dropout_count = aq.get("dropout_count", 0)
        cutoffs = anomalies.get("collection_confidence", {}).get("abrupt_cutoff", [])
        recording_status = "FAIL" if (dropout_count > 0 or len(cutoffs) > 0) else "PASS"
        
        any_poor = any(v.get("grade") == "Poor" for k, v in expl.items() if k != "overall_call_health")
        if overall_score != "" and overall_score < 70 or recording_status == "FAIL" or any_poor:
            review_required = "Yes"
        else:
            review_required = "No"
            
        priority = "Low"
        if overall_score != "":
            if overall_score < 40: priority = "Critical"
            elif overall_score < 60: priority = "High"
            elif overall_score < 75: priority = "Medium"
            
        biz = derive_batch_business_fields(expl)
        
        worst = expl.get(biz["worstPillar"], {}) if biz["worstPillar"] else {}
        primary_issue = worst.get("negatives", [None])[0].split(" at ")[0] if worst.get("negatives") else ""
        
        second_worst = expl.get(biz["secondWorstPillar"], {}) if biz["secondWorstPillar"] else {}
        secondary_issue = second_worst.get("negatives", [None])[0].split(" at ")[0] if second_worst.get("negatives") else ""
        
        total_issues = 0
        critical_issues = 0
        high_severity_issues = 0
        medium_severity_issues = 0
        
        for k, v in expl.items():
            if k == "overall_call_health":
                continue
            total_issues += len(v.get("negatives", []))
            g = v.get("grade", "")
            if g == "Poor": critical_issues += 1
            elif g == "Fair": high_severity_issues += 1
            elif g == "Good": medium_severity_issues += 1
            
        evidence_count = 0
        evidence_type_set = set()
        for cat, issues in anomalies.items():
            if not isinstance(issues, dict): continue
            for issue_type, timestamps in issues.items():
                if isinstance(timestamps, list) and len(timestamps) > 0:
                    evidence_count += len(timestamps)
                    clean_type = issue_type.replace("_", " ").title()
                    evidence_type_set.add(clean_type)
        
        evidence_types = "; ".join(evidence_type_set)
        
        interruption_count = len(anomalies.get("conversation_flow", {}).get("interruptions", []))
        clipping_events = len(anomalies.get("audio_quality", {}).get("clipping", []))
        
        row = {
            "Call ID": call_id,
            "Source File": meta.get("source_file", ""),
            "Processing Timestamp": meta.get("processed_at", ""),
            "Call Duration (sec)": meta.get("duration_seconds", ""),
            "Call Type": "",
            "Speaker Count": summary.get("speaker_count", ""),
            "Dominant Speaker": summary.get("dominant_speaker", ""),
            
            "Overall Health Score": overall_score,
            "Overall Grade": overall_grade,
            "Review Required": review_required,
            "Priority": priority,
            "Recording Status": recording_status,
            "Gate Multiplier": scores.get("gate_multiplier", ""),
            
            "Audio Quality Score": scores.get("audio_quality", ""),
            "Audio Quality Grade": expl.get("audio_quality", {}).get("grade", ""),
            "Voice Stability Score": scores.get("voice_stability", ""),
            "Voice Stability Grade": expl.get("voice_stability", {}).get("grade", ""),
            "Conversation Flow Score": scores.get("conversation_flow", ""),
            "Conversation Flow Grade": expl.get("conversation_flow", {}).get("grade", ""),
            "Conversation Balance Score": scores.get("conversation_balance", ""),
            "Conversation Balance Grade": expl.get("conversation_balance", {}).get("grade", ""),
            "Speech Activity Score": scores.get("speech_activity", ""),
            "Speech Activity Grade": expl.get("speech_activity", {}).get("grade", ""),
            "Collection Confidence Score": scores.get("collection_confidence", ""),
            "Collection Confidence Grade": expl.get("collection_confidence", {}).get("grade", ""),
            
            "Average SNR (dB)": aq.get("average_snr", summary.get("average_snr_db", "")),
            "Average Speech Quality": vq.get("avg_speech_quality", ""),
            "Average Pitch (Hz)": summary.get("average_pitch_hz", ""),
            "Average Loudness (dB)": summary.get("average_loudness_db", ""),
            "Speech Percentage": sb.get("speech_percentage", ""),
            "Silence Percentage": sb.get("silence_percentage", ""),
            "Average Response Latency (sec)": rd.get("avg_response_latency_seconds", ""),
            
            "Speaker Changes": cb.get("speaker_change_count", ""),
            "Turns": cb.get("turn_count", ""),
            "Pauses": sb.get("pause_count", ""),
            "Longest Pause (sec)": sb.get("longest_pause", ""),
            "Dropouts": aq.get("dropout_count", 0),
            "Clipping Events": clipping_events,
            "Interruptions": interruption_count,
            "Overlaps": rd.get("overlap_count", ""),
            
            "Primary Issue": primary_issue,
            "Secondary Issue": secondary_issue,
            "Total Issues": total_issues,
            "Critical Issues": critical_issues,
            "High Severity Issues": high_severity_issues,
            "Medium Severity Issues": medium_severity_issues,
            
            "Business Impact": biz["impact"],
            "Recommended Action": biz["action"],
            "Next Review Step": biz["nextStep"],
            
            "Evidence Count": evidence_count,
            "Evidence Types": evidence_types,
            
            "Investigation Package": f"{call_id}_report.zip",
            "JSON File": f"{call_id}_features.json",
            "Original Audio File": meta.get("source_file", ""),
        }
        rows.append(row)
        
    df = pd.DataFrame(rows)
    
    # Find next available filename
    base_name = "batch_analysis_report"
    i = 1
    while True:
        csv_path = exports_path / f"{base_name}_{i}.csv"
        if not csv_path.exists():
            break
        i += 1
        
    df.to_csv(csv_path, index=False)
    return str(csv_path)

if __name__ == "__main__":
    out_file = generate_batch_csv()
    print(f"Generated {out_file}")
