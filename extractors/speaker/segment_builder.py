from __future__ import annotations

from typing import Any


def build_speaker_segments(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Scans the timeline and aggregates contiguous windows with the same speaker label
    into rich segments. Ignores silent windows (speaker: null), ensuring that silences
    break speaker turns naturally.

    Each segment contains:
      - speaker: str (e.g., "Speaker 0")
      - cluster: int (e.g., 0)
      - start: float (start time of turn)
      - end: float (end time of turn)
      - duration: float (end - start)
    """
    segments: list[dict[str, Any]] = []
    current_segment: dict[str, Any] | None = None

    for row in timeline:
        # Support both nested and flat timeline schemas
        speaker_info = None
        if "derived" in row:
            speaker_info = row["derived"].get("speaker")
        else:
            speaker_info = row.get("speaker")

        start = float(row.get("start_seconds", row.get("timestamp", 0.0)))
        end = float(row.get("end_seconds", start + 0.5))

        if speaker_info is None:
            # Silence/pause: close current segment if open
            if current_segment is not None:
                current_segment["duration"] = round(
                    current_segment["end"] - current_segment["start"], 2
                )
                segments.append(current_segment)
                current_segment = None
            continue

        label = speaker_info["label"]
        cluster = speaker_info["cluster"]

        if current_segment is None:
            # Start a new speaker segment
            current_segment = {
                "speaker": label,
                "cluster": cluster,
                "start": start,
                "end": end,
                "duration": 0.0,
            }
        elif current_segment["speaker"] == label:
            # Continue the current speaker segment
            current_segment["end"] = end
        else:
            # Speaker changed: close current and start new
            current_segment["duration"] = round(
                current_segment["end"] - current_segment["start"], 2
            )
            segments.append(current_segment)
            current_segment = {
                "speaker": label,
                "cluster": cluster,
                "start": start,
                "end": end,
                "duration": 0.0,
            }

    # Add final segment if still open
    if current_segment is not None:
        current_segment["duration"] = round(
            current_segment["end"] - current_segment["start"], 2
        )
        segments.append(current_segment)

    return segments
