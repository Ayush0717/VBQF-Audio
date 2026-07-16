def calculate_metrics(segments):
    # Sort segments by start time
    sorted_segments = sorted(segments, key=lambda x: x["start"])
    
    if not sorted_segments:
        return {}

    # 1. Merge segments by the SAME speaker that overlap or are very close (e.g., < 0.5s gap)
    # This prevents backchannels from shattering a single long turn.
    speaker_tracks = []
    
    for seg in sorted_segments:
        # Find if this speaker already has an active track we can merge into
        merged = False
        for track in reversed(speaker_tracks):
            if track["speaker"] == seg["speaker"]:
                # If the gap between this segment and the speaker's last segment is small, merge
                if seg["start"] - track["end"] < 1.5:
                    track["end"] = max(track["end"], seg["end"])
                    track["duration"] = track["end"] - track["start"]
                    merged = True
                    break
        if not merged:
            speaker_tracks.append(dict(seg))
            
    # Re-sort tracks by start time just in case
    speaker_tracks.sort(key=lambda x: x["start"])
    
    # 2. Now calculate floor changes and latencies
    latencies = []
    overlaps = []
    
    speaker_changes_count = 0
    
    for j in range(1, len(speaker_tracks)):
        prev = speaker_tracks[j-1]
        curr = speaker_tracks[j]
        
        if prev["speaker"] != curr["speaker"]:
            speaker_changes_count += 1
            gap = curr["start"] - prev["end"]
            if gap > 0:
                latencies.append(gap)
            elif gap < 0:
                # Overlap!
                overlap_time = min(prev["end"], curr["end"]) - curr["start"]
                if overlap_time > 0.2:
                    overlaps.append(overlap_time)

    return {
        "tracks": speaker_tracks,
        "speaker_changes_count": speaker_changes_count,
        "latencies": latencies,
        "overlaps": overlaps,
    }

segs = [
    {"speaker": "A", "start": 0, "end": 10},
    {"speaker": "B", "start": 2, "end": 3},
    {"speaker": "A", "start": 11, "end": 15},
    {"speaker": "B", "start": 16, "end": 20}
]

print(calculate_metrics(segs))
