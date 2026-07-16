from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

TIMELINE_FEATURES = (
    ("pitch_hz", "Pitch (Hz)"),
    ("rms", "RMS Amplitude"),
    ("energy", "Energy"),
    ("loudness_db", "Loudness (dB)"),
    ("speech", "Speech Activity"),
    ("snr_db", "SNR (dB)"),
)


def flatten_timeline(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Flattens the nested raw/derived timeline dictionary structure
    into a list of flat dictionaries suitable for pandas DataFrame conversion.
    """
    flat_list = []
    for row in timeline:
        flat_row = {
            "index": row.get("index"),
            "timestamp": row.get("timestamp"),
            "start_seconds": row.get("start_seconds"),
            "end_seconds": row.get("end_seconds"),
        }

        raw = row.get("raw", {}) or {}

        # Acoustic
        acoustic = raw.get("acoustic", {}) or {}
        flat_row["rms"] = acoustic.get("rms")
        flat_row["energy"] = acoustic.get("energy")
        flat_row["loudness_db"] = acoustic.get("loudness_db")
        flat_row["spectral_centroid_hz"] = acoustic.get("spectral_centroid_hz")
        flat_row["spectral_bandwidth_hz"] = acoustic.get("spectral_bandwidth_hz")
        flat_row["spectral_rolloff_hz"] = acoustic.get("spectral_rolloff_hz")

        # Quality
        quality = raw.get("quality", {}) or {}
        flat_row["snr_db"] = quality.get("snr_db")
        flat_row["speech_quality_proxy"] = quality.get("speech_quality_proxy")

        # Prosody
        prosody = raw.get("prosody", {}) or {}
        flat_row["pitch_hz"] = prosody.get("pitch_hz")

        derived = row.get("derived", {}) or {}

        # Speech
        speech = derived.get("speech", {}) or {}
        flat_row["speech"] = speech.get("active")
        flat_row["speech_probability"] = speech.get("probability")
        flat_row["silence_ratio"] = speech.get("silence_ratio")

        flat_list.append(flat_row)
    return flat_list


def build_timeline_figure(
    timeline: list[dict[str, Any]],
    diarization_segments: list[dict[str, Any]] = None,
    cursor_time: float | None = None,
    auto_pan: bool = True,
) -> go.Figure:
    """
    Builds a multi-panel synchronized Plotly timeline of acoustic
    and speaker features. Supports a moving vertical cursor, auto-panning,
    and continuous speaker segments.
    """
    if diarization_segments is None:
        diarization_segments = []

    flat_timeline = flatten_timeline(timeline)
    frame = pd.DataFrame(flat_timeline)
    if frame.empty:
        return go.Figure()

    available = [
        (key, label) for key, label in TIMELINE_FEATURES if key in frame.columns
    ]

    # We will add 1 extra row at the top for the Diarization Segments
    total_rows = len(available) + 1

    subplot_titles = ["Speaker Timeline"] + [label for _, label in available]

    figure = make_subplots(
        rows=total_rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=subplot_titles,
    )

    # 1. Plot Diarization Segments as horizontal bars (Gantt style)
    # We map speakers to a y-axis index
    spk_map = {}
    y_idx = 0
    for seg in diarization_segments:
        spk = seg["speaker"]
        if spk not in spk_map:
            spk_map[spk] = y_idx
            y_idx += 1

    # Assign distinct colors for speakers
    colors = ["#8884d8", "#82ca9d", "#ffc658", "#ff7300"]

    for seg in diarization_segments:
        spk = seg["speaker"]
        spk_y = spk_map[spk]
        color = colors[spk_y % len(colors)]

        # Draw a horizontal line segment
        figure.add_trace(
            go.Scatter(
                x=[seg["start"], seg["end"]],
                y=[spk_y, spk_y],
                mode="lines",
                line=dict(width=15, color=color),
                name=spk,
                showlegend=False,
                hoverinfo="text",
                text=f"{spk}: {seg['start']}s - {seg['end']}s ({seg['duration']}s)",
            ),
            row=1,
            col=1,
        )

    # Format speaker axis
    if spk_map:
        figure.update_yaxes(
            tickvals=list(spk_map.values()),
            ticktext=list(spk_map.keys()),
            row=1,
            col=1,
        )
    else:
        figure.update_yaxes(
            tickvals=[0],
            ticktext=["No Speakers"],
            row=1,
            col=1,
        )

    # 2. Plot Acoustic Features
    for i, (key, label) in enumerate(available):
        row_index = i + 2  # offset by 1 for speaker timeline
        if key == "speech":
            # Plot boolean step chart for VAD
            y_data = frame[key].astype(int)
            figure.add_trace(
                go.Scatter(
                    x=frame["timestamp"],
                    y=y_data,
                    mode="lines",
                    line=dict(shape="hv", width=1.5, color="#ffc658"),
                    name=label,
                ),
                row=row_index,
                col=1,
            )
        else:
            # Standard numeric line chart
            figure.add_trace(
                go.Scatter(
                    x=frame["timestamp"],
                    y=frame[key],
                    mode="lines",
                    line=dict(width=1.5, color="#82ca9d"),
                    name=label,
                ),
                row=row_index,
                col=1,
            )

    # --- UI Polish ---
    # Add vertical playback cursor
    if cursor_time is not None:
        figure.add_vline(
            x=cursor_time,
            line_width=2,
            line_dash="solid",
            line_color="red",
        )

        # Auto-pan logic (30-second sliding window)
        if auto_pan:
            window_size = 30.0
            x_min = max(0.0, cursor_time - (window_size / 2.0))
            x_max = x_min + window_size

            # If near the end of the file, clamp to total duration
            max_ts = frame["timestamp"].max()
            if x_max > max_ts and max_ts > window_size:
                x_max = max_ts
                x_min = x_max - window_size

            figure.update_xaxes(range=[x_min, x_max])

    figure.update_layout(
        height=200 * total_rows,
        showlegend=False,
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    return figure
