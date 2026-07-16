from __future__ import annotations

from typing import Any


def build_rich_events(
    timeline: list[dict[str, Any]],
    speaker_segments: list[dict[str, Any]],
    long_pause_seconds: float = 1.0,
) -> list[dict[str, Any]]:
    """
    Scans the timeline and speaker segments to build a chronologically sorted
    list of rich events, each with a unique sequential ID.

    Detected events:
      - pause: Contiguous pause windows (rms below silence threshold) lasting >= long_pause_seconds.
      - dropout: Contiguous dropout windows (peak & rms extremely low).
      - speaker_change: Transition between different speakers in speaker_segments.

    Every event contains:
      - id: int (1-indexed)
      - type: str ("pause", "dropout", "speaker_change")
      - start: float (start time)
      - end: float (end time)
      - duration: float (end - start)
      - details: str (optional, extra context)
    """
    events: list[dict[str, Any]] = []

    # 1. Extract Pause Events
    pause_start: float | None = None
    last_pause_end: float | None = None

    for row in timeline:
        start = float(row.get("start_seconds", row.get("timestamp", 0.0)))
        end = float(row.get("end_seconds", start + 0.5))

        # Support nested/flat schemas
        is_pause = False
        if "derived" in row and "speech" in row["derived"]:
            # Note: in config, pause is determined by rms. We can check derived.speech or row.get("pause")
            # Wait, VAD has "pause" extractor which returns row.get("pause") or derived.speech.active
            # Let's check both
            is_pause = row.get("pause", False)
        else:
            is_pause = row.get("pause", False)

        if is_pause:
            if pause_start is None:
                pause_start = start
            last_pause_end = end
        else:
            if pause_start is not None and last_pause_end is not None:
                duration = last_pause_end - pause_start
                if duration >= long_pause_seconds:
                    events.append(
                        {
                            "type": "pause",
                            "start": pause_start,
                            "end": last_pause_end,
                            "duration": round(duration, 2),
                        }
                    )
                pause_start = None
                last_pause_end = None

    # Close open pause event at end
    if pause_start is not None and last_pause_end is not None:
        duration = last_pause_end - pause_start
        if duration >= long_pause_seconds:
            events.append(
                {
                    "type": "pause",
                    "start": pause_start,
                    "end": last_pause_end,
                    "duration": round(duration, 2),
                }
            )

    # 2. Extract Dropout Events
    dropout_start: float | None = None
    last_dropout_end: float | None = None

    for row in timeline:
        start = float(row.get("start_seconds", row.get("timestamp", 0.0)))
        end = float(row.get("end_seconds", start + 0.5))

        is_dropout = False
        if "derived" in row:
            # Dropout can be a flat feature or under derived
            is_dropout = row.get("dropout", False)
        else:
            is_dropout = row.get("dropout", False)

        if is_dropout:
            if dropout_start is None:
                dropout_start = start
            last_dropout_end = end
        else:
            if dropout_start is not None and last_dropout_end is not None:
                duration = last_dropout_end - dropout_start
                events.append(
                    {
                        "type": "dropout",
                        "start": dropout_start,
                        "end": last_dropout_end,
                        "duration": round(duration, 2),
                    }
                )
                dropout_start = None
                last_dropout_end = None

    # Close open dropout event at end
    if dropout_start is not None and last_dropout_end is not None:
        duration = last_dropout_end - dropout_start
        events.append(
            {
                "type": "dropout",
                "start": dropout_start,
                "end": last_dropout_end,
                "duration": round(duration, 2),
            }
        )

    # 3. Extract Speaker Change Events from segments
    for i in range(len(speaker_segments) - 1):
        seg_current = speaker_segments[i]
        seg_next = speaker_segments[i + 1]

        # Only record if the speaker actually changes (should always be true for contiguous segments)
        if seg_current["speaker"] != seg_next["speaker"]:
            events.append(
                {
                    "type": "speaker_change",
                    "start": seg_next["start"],
                    "end": seg_next["start"],
                    "duration": 0.0,
                    "details": f"{seg_current['speaker']} to {seg_next['speaker']}",
                }
            )

    # 4. Sort all events chronologically and assign unique sequential IDs
    events.sort(key=lambda e: (e["start"], e["type"]))

    for idx, event in enumerate(events, start=1):
        event["id"] = idx

    return events
