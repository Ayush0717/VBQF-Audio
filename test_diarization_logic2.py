def calculate_metrics(segments):
    sorted_segments = sorted(segments, key=lambda x: x["start"])
    
    if not sorted_segments:
        return {}

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
                floor_durations.append(last_end - last_start)
                
                last_speaker = seg["speaker"]
                last_start = seg["start"]
                last_end = seg["end"]
                speaker_changes_count += 1
            else:
                # Overlap!
                overlap_time = min(last_end, seg["end"]) - seg["start"]
                if overlap_time > 0.2:
                    overlaps.append(overlap_time)
                    
                # Floor change?
                if seg["end"] > last_end:
                    floor_durations.append(last_end - last_start)
                    
                    last_speaker = seg["speaker"]
                    last_start = seg["start"] # Floor changes at the start of the new speaker's turn
                    last_end = seg["end"]
                    speaker_changes_count += 1
        else:
            last_end = max(last_end, seg["end"])
            
    if last_speaker is not None:
        floor_durations.append(last_end - last_start)

    return {
        "speaker_changes_count": speaker_changes_count,
        "latencies": latencies,
        "overlaps": overlaps,
        "floor_durations": floor_durations
    }

segs = [
    {"speaker": "A", "start": 0, "end": 10},
    {"speaker": "B", "start": 2, "end": 3},
    {"speaker": "A", "start": 11, "end": 15},
    {"speaker": "B", "start": 16, "end": 20}
]
print("Test 1:", calculate_metrics(segs))

segs2 = [
    {"speaker": "A", "start": 0, "end": 5},
    {"speaker": "B", "start": 4, "end": 10},
]
print("Test 2:", calculate_metrics(segs2))
