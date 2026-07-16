from __future__ import annotations

from typing import Any


def summary_metrics(summary: dict[str, Any]) -> list[tuple[str, str]]:
    """Formats high-level summary metrics from the summary block for dashboard display."""
    return [
        ("Duration", _seconds(summary.get("duration_seconds"))),
        ("Speaker Count", str(summary.get("speaker_count", "n/a"))),
        ("Dominant Speaker", str(summary.get("dominant_speaker", "n/a"))),
        ("Average SNR", _number(summary.get("average_snr_db"), " dB")),
        ("Average Pitch", _number(summary.get("average_pitch_hz"), " Hz")),
        ("Average Loudness", _number(summary.get("average_loudness_db"), " dB")),
        ("Total Pause Time", _seconds(summary.get("total_pause_time_seconds"))),
        ("Total Dropouts", str(summary.get("total_dropouts", "0"))),
    ]


def _number(value: Any, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2f}{suffix}"


def _percent(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def _seconds(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.1f}s"
