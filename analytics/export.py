from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Any
import pandas as pd

from analytics.models import AnalysisContext
from analytics.engines.block_analysis import BlockAnalysisEngine


def generate_block_summary(
    speech_percent: float,
    snr: float,
    pause_count: int,
    dropout_count: int,
    speaker_changes: int,
    audio_quality: str,
) -> str:
    """Helper to generate a deterministic, rule-based summary for a call block segment."""
    if speech_percent < 15.0:
        return "Mostly silence."
    if dropout_count > 0:
        return "Speech with dropout."
    if audio_quality == "Poor" or snr < 10.0:
        return "Low audio quality."
    if pause_count > 1:
        return "Multiple pauses."
    if speaker_changes > 1:
        return "Speaker transition."
    return "Clear speech."


def generate_excel_report(
    analysis_results: dict[str, Any],
    engineered: dict[str, Any],
    summary: dict[str, Any],
    metadata: dict[str, Any],
    timeline: list[dict[str, Any]],
    diarization: dict[str, Any],
    events: list[dict[str, Any]],
    block_size: float = 10.0,
) -> bytes:
    """Generates an in-memory Excel report with a single sheet named 'sheet block details'

    containing the block-wise analysis and clickable absolute links to the audio snippets.
    """
    output = io.BytesIO()

    # Sanitize inputs to prevent NoneType attribute errors on custom/legacy uploads
    if not analysis_results:
        analysis_results = {}
    if not engineered:
        engineered = {}
    if not summary:
        summary = {}
    if not metadata:
        metadata = {}
    if not timeline:
        timeline = []
    if not diarization:
        diarization = {}
    if not events:
        events = []

    # Create the computational context for block evaluations
    context = AnalysisContext(
        timeline=timeline,
        diarization=diarization,
        events=events,
        metadata=metadata,
        summary=summary,
    )

    dur_val = metadata.get("duration_seconds")
    duration = float(dur_val) if dur_val is not None else 60.0
    num_blocks = int(math.ceil(duration / block_size)) if block_size > 0 else 1

    # Audio Slicing Setup
    source_file_path = metadata.get("source_file")
    audio_export_ok = False
    export_dir_name = Path(source_file_path).stem if source_file_path else "call"

    # Establish local exports directories: exports/<audio_name>/<block_size>s_blocks/
    block_size_label = f"{int(block_size)}s_blocks"
    exports_root = Path("/Users/ayushgoel/Mmfsl/exports")
    block_dir = exports_root / export_dir_name / block_size_label

    if source_file_path:
        try:
            source_path = Path(source_file_path)
            if not source_path.is_absolute():
                source_path = Path("/Users/ayushgoel/Mmfsl") / source_path

            if source_path.exists() and source_path.is_file():
                import soundfile as sf

                audio_data, samplerate = sf.read(str(source_path))
                block_dir.mkdir(parents=True, exist_ok=True)
                audio_export_ok = True
        except Exception:
            pass  # Gracefully fall back if soundfile cannot parse the file format

    # Compile the 15-column Block Analysis details
    block_rows = []
    for i in range(num_blocks):
        b_start = i * block_size
        b_end = min(duration, b_start + block_size)
        target_t = b_start + (block_size / 2.0)

        # Dynamically retrieve parameters from the temporal blocks engine
        b_data = BlockAnalysisEngine.get_block_metrics(
            context, target_t, block_size, metadata
        )
        b_scores = b_data["scores"]
        b_stats = b_data["stats"]
        b_events = b_data["events"]

        # Slice and export sub-segment audio clip files if source waveform is readable
        segment_filepath = block_dir / f"block_{i:03d}.wav"
        if audio_export_ok:
            try:
                start_frame = int(b_start * samplerate)
                end_frame = int(b_end * samplerate)
                segment_slice = audio_data[start_frame:end_frame]
                sf.write(str(segment_filepath), segment_slice, samplerate)
            except Exception:
                pass

        # Store the absolute path for now; we inject clickable HYPERLINK formulas via openpyxl after writing
        clip_abs_path = str(segment_filepath.resolve())
        clip_display = f"block_{i:03d}.wav"

        # Determine Dominant Speaker in block
        speaker_ratios = b_events.get("speaker_ratios") or {}
        dominant_speaker = "Silence"
        if speaker_ratios:
            dominant_speaker = max(speaker_ratios, key=speaker_ratios.get)

        # Determine block Audio Quality grade label
        aq_score = b_scores.get("audio_quality", 0)
        if aq_score >= 80:
            aq_label = "Good"
        elif aq_score >= 50:
            aq_label = "Fair"
        else:
            aq_label = "Poor"

        # Compute deterministic rule-based block summary
        summary_sentence = generate_block_summary(
            speech_percent=b_events.get("speech_percent", 0.0),
            snr=b_stats["snr"]["mean"] if b_stats["snr"]["mean"] is not None else 0.0,
            pause_count=b_events.get("pause_count", 0),
            dropout_count=b_events.get("dropout_count", 0),
            speaker_changes=b_events.get("speaker_changes", 0),
            audio_quality=aq_label,
        )

        block_rows.append(
            {
                "Block ID": f"Block #{i}",
                "Start Time (s)": round(b_start, 2),
                "End Time (s)": round(b_end, 2),
                "Audio Clip": clip_display,
                "_clip_path": clip_abs_path,
                "Dominant Speaker": dominant_speaker,
                "Speech %": round(b_events.get("speech_percent", 0.0), 1),
                "Avg Loudness (dB)": (
                    round(b_stats["loudness"]["mean"], 1)
                    if b_stats["loudness"]["mean"] is not None
                    else -60.0
                ),
                "Avg Pitch (Hz)": (
                    round(b_stats["pitch"]["mean"], 1)
                    if b_stats["pitch"]["mean"] is not None
                    else 0.0
                ),
                "Avg SNR (dB)": (
                    round(b_stats["snr"]["mean"], 1)
                    if b_stats["snr"]["mean"] is not None
                    else 0.0
                ),
                "Pause Count": b_events.get("pause_count", 0),
                "Pause Duration (s)": round(b_events.get("pause_duration", 0.0), 2),
                "Dropout Count": b_events.get("dropout_count", 0),
                "Speaker Changes": b_events.get("speaker_changes", 0),
                "Audio Quality": aq_label,
                "Block Summary": summary_sentence,
            }
        )

    df_block_analysis = pd.DataFrame(block_rows)

    # Extract the hidden clip paths before writing, then drop the column from the visible sheet
    clip_paths = df_block_analysis["_clip_path"].tolist()
    df_block_analysis = df_block_analysis.drop(columns=["_clip_path"])

    # Write the DataFrame to Excel first (pandas handles headers + data types)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_block_analysis.to_excel(
            writer, sheet_name="sheet block details", index=False
        )

        # Now inject real =HYPERLINK() formulas into column D (Audio Clip) using openpyxl directly.
        # pandas to_excel() escapes formula strings as literal text, so this post-processing step
        # is the only way to get clickable links in Excel.
        ws = writer.sheets["sheet block details"]
        audio_clip_col = 4  # Column D (1-indexed: A=1, B=2, C=3, D=4)
        for row_idx, abs_path in enumerate(
            clip_paths, start=2
        ):  # start=2 to skip the header row
            ws.cell(row=row_idx, column=audio_clip_col).value = (
                f'=HYPERLINK("file://{abs_path}", "block_{row_idx - 2:03d}.wav")'
            )

    return output.getvalue()
