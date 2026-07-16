from __future__ import annotations

from typing import Any


def compute_speaker_statistics(
    speaker_segments: list[dict[str, Any]],
    total_call_duration: float,
) -> dict[str, Any]:
    """
    Computes turn and talk-time statistics for each speaker from speaker_segments,
    and identifies the dominant speaker.

    Returns a dictionary suitable for the "summary" block containing:
      - speaker_statistics: dict mapping speaker label to stats:
          - talk_time_seconds: float
          - talk_percentage: float (percentage of total speech time)
          - turn_count: int
          - average_turn_duration_seconds: float
      - dominant_speaker: str | None (speaker with the most talk time)
    """
    stats: dict[str, dict[str, Any]] = {}

    # 1. Calculate talk times and collect segments per speaker
    total_speech_time = 0.0
    for segment in speaker_segments:
        speaker = segment["speaker"]
        duration = segment["duration"]

        if speaker not in stats:
            stats[speaker] = {
                "talk_time_seconds": 0.0,
                "talk_percentage": 0.0,
                "turn_count": 0,
                "average_turn_duration_seconds": 0.0,
            }

        stats[speaker]["talk_time_seconds"] += duration
        stats[speaker]["turn_count"] += 1
        total_speech_time += duration

    # 2. Compute percentages and averages
    dominant_speaker = None
    max_talk_time = -1.0

    for speaker, s_info in stats.items():
        talk_time = s_info["talk_time_seconds"]
        turn_count = s_info["turn_count"]

        # Round talk time
        s_info["talk_time_seconds"] = round(talk_time, 2)

        # Percentage of total SPEECH time
        if total_speech_time > 0:
            s_info["talk_percentage"] = round(
                (talk_time / total_speech_time) * 100.0, 1
            )
        else:
            s_info["talk_percentage"] = 0.0

        # Average turn duration
        if turn_count > 0:
            s_info["average_turn_duration_seconds"] = round(talk_time / turn_count, 2)
        else:
            s_info["average_turn_duration_seconds"] = 0.0

        # Determine dominant speaker
        if talk_time > max_talk_time:
            max_talk_time = talk_time
            dominant_speaker = speaker

    return {
        "speaker_statistics": stats,
        "dominant_speaker": dominant_speaker,
    }
