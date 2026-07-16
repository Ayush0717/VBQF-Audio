from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Add project root to sys.path to allow importing local packages
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from aggregator.feature_store import FeatureStore
from visualization.timeline import build_timeline_figure
from analytics import (
    AnalysisContext,
    CurrentAnalysisEngine,
    BlockAnalysisEngine,
    SummaryAnalysisEngine,
    FEATURE_REGISTRY,
)

# Set page config at the very top
st.set_page_config(
    page_title="Voice Call Analysis Platform",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _prepare_audio_static(metadata: dict[str, Any]) -> str | None:
    """Copy the source audio into ``visualization/static/`` so Streamlit can serve it.
    Returns the URL path (e.g. ``/app/static/current_audio.wav``) or *None*.
    """
    source = metadata.get("source_file")
    if not source:
        return None
    audio_file = Path(source)
    if not audio_file.exists():
        return None

    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(exist_ok=True)
    target = static_dir / audio_file.name

    if target.is_symlink():
        try:
            target.unlink()
        except Exception:
            pass

    import shutil

    try:
        if not target.exists() or target.stat().st_size != audio_file.stat().st_size:
            temp_target = target.with_suffix(".tmp")
            shutil.copy2(audio_file, temp_target)
            temp_target.replace(target)
    except Exception as e:
        st.sidebar.error(f"Failed to copy audio: {e}")
        return None

    # Add a cache-busting query parameter just in case
    import time

    return f"/app/static/{audio_file.name}?v={int(time.time())}"


def get_score_color(score: float) -> str:
    if score >= 90:
        return "#00e676"  # Green
    elif score >= 75:
        return "#66bb6a"  # Light Green
    elif score >= 60:
        return "#ffeb3b"  # Yellow
    else:
        return "#ff1744"  # Red


def run_dashboard() -> None:
    st.title("🎙️ Voice Call Analysis Platform (Phase 1)")
    st.caption(
        "Objective Voice Call Quality Assessment & Conversational Speech Analytics"
    )
    st.markdown("---")

    # ── Sidebar: Data Loader ─────────────────────────────────────────────────
    st.sidebar.header("📁 Data Source")
    feature_file = st.sidebar.file_uploader("Upload Feature JSON", type=["json"])
    path_text = st.sidebar.text_input("Or local JSON directory/path", "data/outputs")

    store: FeatureStore | None = None

    if feature_file is not None:
        import json

        payload = json.load(feature_file)
        store = FeatureStore(
            metadata=payload.get("metadata", {}),
            features=payload.get("features", {}),
            diarization=payload.get("diarization", {"segments": [], "statistics": {}}),
            summary=payload.get("summary", {}),
            engineered_features=payload.get("engineered_features", {}),
            analysis_results=payload.get("analysis_results", {}),
        )
    elif path_text:
        path = Path(path_text)
        if path.is_file():
            store = FeatureStore.load_json(path)
        elif path.is_dir():
            candidates = sorted(path.glob("*_features.json"))
            if candidates:
                selected = st.sidebar.selectbox("Available feature files", candidates)
                store = FeatureStore.load_json(selected)

    if store is None or not store.features.get("timeline"):
        st.info(
            "💡 Run `python app.py data/audio/call.wav` to extract features, then load the JSON."
        )
        return

    # ── Initialize State & Context ───────────────────────────────────────────
    metadata = store.metadata
    summary = store.summary
    timeline = store.features.get("timeline", [])
    diarization = store.diarization
    events = store.features.get("events", [])
    duration = float(metadata.get("duration_seconds", 60.0))
    engineered_feats = store.engineered_features
    analysis_results = store.analysis_results

    # Build the computational AnalysisContext
    context = AnalysisContext(
        timeline=timeline,
        diarization=diarization,
        events=events,
        metadata=metadata,
        summary=summary,
    )

    # ── Sidebar: Settings & Export Report ─────────────────────────────────────
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Global Settings")
    block_size_option = st.sidebar.selectbox(
        "Analysis Block Size",
        ["5 seconds", "10 seconds", "15 seconds", "20 seconds", "30 seconds"],
        index=1,
        help="Select the window segment duration for Level 2 and Excel export analysis.",
    )
    block_size = float(block_size_option.split()[0])

    st.sidebar.subheader("📥 Export Report")
    from analytics.export import generate_excel_report

    try:
        excel_bytes = generate_excel_report(
            analysis_results,
            engineered_feats,
            summary,
            metadata,
            timeline,
            diarization,
            events,
            block_size,
        )
        st.sidebar.download_button(
            label="Download Excel Report",
            data=excel_bytes,
            file_name=f"call_analysis_{Path(metadata.get('source_file', 'call')).stem}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        st.sidebar.error(f"Failed to generate export: {e}")

    def render_investigation_panel(
        title: str,
        score: float,
        color: str,
        grade: str,
        positives: list[str],
        negatives: list[str],
    ):
        if not negatives and score <= 75:
            negatives = [
                f"General degradation detected in {title.lower()} continuous metrics"
            ]

        st.markdown(
            f"""
            <div style="background-color: #1e1e24; padding: 15px; border-radius: 10px 10px 0 0; border-left: 4px solid {color}; border-top: 1px solid #333; border-right: 1px solid #333;">
                <h4 style="margin: 0; color: #a0a0b0; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;">{title}</h4>
                <h2 style="margin: 8px 0 2px 0; font-size: 32px; color: {color}; font-weight: bold;">{score}/100</h2>
                <span style="color: #808090; font-size: 11px; font-weight: 600;">{grade.upper()}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        def render_evidence_item(item_text: str, title: str, is_top_issue: bool):
            import re

            if " at " in item_text:
                category, ts_block = item_text.split(" at ", 1)
                ts_block = ts_block.replace("...", "").strip()

                if is_top_issue:
                    st.error(category)
                else:
                    st.markdown(f"**⚠ {category}**")

                timestamps = [t.strip() for t in ts_block.split(",")]
                cols = st.columns(min(len(timestamps), 4))
                for i, ts in enumerate(timestamps):
                    match = re.search(r"(\d{2}):(\d{2})", ts)
                    if match:
                        start_sec = max(
                            0.0,
                            float(int(match.group(1)) * 60 + int(match.group(2))) - 3.0,
                        )
                        btn_key = f"play_{title.replace(' ', '_')}_{category[:10].replace(' ', '')}_{i}_{'top' if is_top_issue else 'reg'}"
                        if cols[i % 4].button(f"▶ {ts}", key=btn_key):
                            st.session_state.playback_time = start_sec
                            st.session_state.force_seek = start_sec
            else:
                if is_top_issue:
                    st.error(item_text)
                else:
                    st.markdown(f"**⚠ {item_text}**")

        with st.expander("🔍 View Evidence"):
            if negatives:
                st.markdown("**🚨 Top Issue**")
                render_evidence_item(negatives[0], title, True)

                if len(negatives) > 1:
                    st.divider()
                    st.markdown("**⚠ Evidence Requiring Review**")
                    for n in negatives[1:]:
                        render_evidence_item(n, title, False)
                        st.markdown("<br>", unsafe_allow_html=True)
            else:
                st.markdown("**✨ Top Issue**")
                st.success("No critical degradations detected.")
                st.divider()

            st.markdown("**✅ Strengths**")
            if positives:
                for p in positives:
                    st.write(f"- {p}")
            else:
                st.write("- No strengths recorded.")
        st.markdown("<br>", unsafe_allow_html=True)

    # ==============================================================================
    # SECTION 1 — AI CALL REVIEW & INVESTIGATION REPORT
    # ==============================================================================
    st.header("1. AI Call Review & Investigation Report")

    # AI Summary Block
    health_val = analysis_results.get("scores", {}).get("overall_call_health", 0)
    st.info(
        f"**AI Summary:** This call achieved an overall health score of {health_val}/100. Review the investigation panels below to trace exactly where and why the call degraded. The exact timestamps for every deduction are provided in the Evidence logs."
    )

    # 1.1 General Call Information
    col_info1, col_info2, col_info3 = st.columns(3)
    col_info1.metric("Call Duration", f"{summary.get('duration_seconds', 0.0):.1f}s")
    col_info2.metric("Number of Speakers", f"{summary.get('speaker_count', 0)}")
    col_info3.metric("Dominant Speaker", f"{summary.get('dominant_speaker', 'n/a')}")

    # 1.2 Overall Scores Layout
    st.markdown("### Overall Call Assessment Scores")
    scores = analysis_results.get("scores", {})
    explanations = analysis_results.get("explanations", {})

    col_h_score, col_other_scores = st.columns([1, 3])

    with col_h_score:
        gate_mult = scores.get("gate_multiplier", 1.0)
        h_color = get_score_color(health_val)
        h_grade = explanations.get("overall_call_health", {}).get("grade", "n/a")
        gate_color = "#4CAF50" if gate_mult == 1.0 else "#F44336"

        st.markdown(
            f"""
            <div style="background-color: #1e1e24; padding: 25px; border-radius: 12px; border-left: 5px solid {h_color}; text-align: center; height: 100%;">
                <h3 style="margin: 0; color: #a0a0b0; font-size: 13px; text-transform: uppercase; letter-spacing: 1px;">Overall Call Health</h3>
                <h1 style="margin: 15px 0 5px 0; font-size: 64px; color: {h_color}; font-weight: bold;">{health_val}</h1>
                <p style="margin: 0; color: #808090; font-size: 14px; font-weight: 500;">{h_grade}</p>
                <div style="margin-top: 15px; padding-top: 10px; border-top: 1px solid #303040;">
                    <span style="color: #a0a0b0; font-size: 11px; text-transform: uppercase;">Gate Multiplier:</span> 
                    <strong style="color: {gate_color}; font-size: 13px;">{gate_mult}x</strong>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_other_scores:
        sub_cols = st.columns(3)

        with sub_cols[0]:
            cc_val = scores.get("collection_confidence", 0)
            cc_exp = explanations.get("collection_confidence", {})
            render_investigation_panel(
                "Collection Confidence",
                cc_val,
                get_score_color(cc_val),
                cc_exp.get("grade", "n/a"),
                cc_exp.get("positives", []),
                cc_exp.get("negatives", []),
            )

        with sub_cols[1]:
            aq_val = scores.get("audio_quality", 0)
            aq_exp = explanations.get("audio_quality", {})
            render_investigation_panel(
                "Audio Quality",
                aq_val,
                get_score_color(aq_val),
                aq_exp.get("grade", "n/a"),
                aq_exp.get("positives", []),
                aq_exp.get("negatives", []),
            )

        with sub_cols[2]:
            flow_val = scores.get("conversation_flow", 0)
            flow_exp = explanations.get("conversation_flow", {})
            render_investigation_panel(
                "Conversation Flow",
                flow_val,
                get_score_color(flow_val),
                flow_exp.get("grade", "n/a"),
                flow_exp.get("positives", []),
                flow_exp.get("negatives", []),
            )

        sub_cols2 = st.columns(3)

        with sub_cols2[0]:
            vs_val = scores.get("voice_stability", 0)
            vs_exp = explanations.get("voice_stability", {})
            render_investigation_panel(
                "Voice Stability",
                vs_val,
                get_score_color(vs_val),
                vs_exp.get("grade", "n/a"),
                vs_exp.get("positives", []),
                vs_exp.get("negatives", []),
            )

        with sub_cols2[1]:
            bal_val = scores.get("conversation_balance", 0)
            bal_exp = explanations.get("conversation_balance", {})
            render_investigation_panel(
                "Conversation Balance",
                bal_val,
                get_score_color(bal_val),
                bal_exp.get("grade", "n/a"),
                bal_exp.get("positives", []),
                bal_exp.get("negatives", []),
            )

        with sub_cols2[2]:
            sa_val = scores.get("speech_activity", 0)
            sa_exp = explanations.get("speech_activity", {})
            render_investigation_panel(
                "Speech Activity",
                sa_val,
                get_score_color(sa_val),
                sa_exp.get("grade", "n/a"),
                sa_exp.get("positives", []),
                sa_exp.get("negatives", []),
            )

    st.markdown("---")

    # ==============================================================================
    # SECTION 2 — PLAYBACK CONTROLLER
    # ==============================================================================
    st.header("2. Playback Controller")

    # Audio Playback sync
    audio_url = _prepare_audio_static(metadata)
    if audio_url:
        from visualization.audio_player_sync import audio_player_sync

        force_seek = st.session_state.pop("force_seek", -1.0)
        synced_time = audio_player_sync(
            audio_url=audio_url, seek_time=force_seek, key="audio_sync"
        )
        if "playback_time" not in st.session_state:
            st.session_state.playback_time = 0.0
        if (
            synced_time is not None
            and abs(synced_time - st.session_state.playback_time) >= 0.3
        ):
            st.session_state.playback_time = synced_time
    else:
        source_file = metadata.get("source_file")
        if source_file and Path(source_file).exists():
            st.audio(str(source_file))

    st.slider(
        "Master Clock (Position in seconds)",
        min_value=0.0,
        max_value=duration,
        step=0.5,
        format="%.1fs",
        key="playback_time",
    )
    current_time = st.session_state.playback_time

    st.markdown("---")

    # Retrieve instantaneous metrics from CurrentAnalysisEngine
    current_metrics = CurrentAnalysisEngine.get_current_metrics(context, current_time)

    # ==============================================================================
    # SECTION 3 — INSTANTANEOUS ANALYSIS
    # ==============================================================================
    st.header(f"3. Instantaneous Analysis (t = {current_time:.1f}s)")

    # Render Status
    active_spk = current_metrics["speaker"]
    status_val = current_metrics["status"]

    col_inst_left, col_inst_right = st.columns([1, 2])
    with col_inst_left:
        st.subheader("Conversational State")
        if status_val == "Dropout":
            st.error("🔴 SIGNAL DROPOUT")
        elif status_val == "Speaker Change":
            st.info("🔵 SPEAKER CHANGE")
        elif status_val == "Pause":
            st.warning("🟡 PAUSE ACTIVE")
        elif status_val == "Speech":
            st.success("🟢 SPEECH ACTIVE")
        else:
            st.metric("Status", "⚪ IDLE")

        active_seg = current_metrics["active_segment"]
        if active_seg:
            elapsed = current_time - active_seg["start"]
            st.markdown(
                f"👤 **Active Speaker:** `{active_seg['speaker']}`\n\n"
                f"⏱️ **Segment Time:** `{active_seg['start']:.1f}s` to `{active_seg['end']:.1f}s` (Elapsed: `{elapsed:.1f}s`)"
            )
        else:
            st.markdown("🔇 **No active speaker** (Silence / Pause)")

    with col_inst_right:
        st.subheader("Physical Window Features")
        p_cols = st.columns(3)

        # Column 1
        pitch_val = current_metrics["pitch_hz"]
        p_cols[0].metric(
            "Vocal Pitch",
            f"{pitch_val:.1f} Hz" if pitch_val is not None else "Silence/Unvoiced",
        )
        rms_val = current_metrics["rms"]
        p_cols[0].metric(
            "RMS Amplitude", f"{rms_val:.4f}" if rms_val is not None else "n/a"
        )
        energy_val = current_metrics["energy"]
        p_cols[0].metric(
            "Energy", f"{energy_val:.4f}" if energy_val is not None else "n/a"
        )
        loud_val = current_metrics["loudness_db"]
        p_cols[0].metric(
            "Loudness", f"{loud_val:.1f} dB" if loud_val is not None else "n/a"
        )

        # Column 2
        snr_val = current_metrics["snr_db"]
        p_cols[1].metric("SNR", f"{snr_val:.1f} dB" if snr_val is not None else "n/a")
        flux_val = current_metrics["spectral_flux"]
        p_cols[1].metric(
            "Spectral Flux", f"{flux_val:.3f}" if flux_val is not None else "n/a"
        )
        zcr_val = current_metrics["zero_crossing_rate"]
        p_cols[1].metric(
            "Zero Crossing Rate", f"{zcr_val:.3f}" if zcr_val is not None else "n/a"
        )
        quality_proxy = current_metrics["speech_quality_proxy"]
        p_cols[1].metric(
            "Speech Quality Proxy",
            f"{quality_proxy:.2f}" if quality_proxy is not None else "n/a",
        )

        # Column 3
        centroid_val = current_metrics["spectral_centroid_hz"]
        p_cols[2].metric(
            "Spectral Centroid",
            f"{centroid_val:.1f} Hz" if centroid_val is not None else "n/a",
        )
        bandwidth_val = current_metrics["spectral_bandwidth_hz"]
        p_cols[2].metric(
            "Spectral Bandwidth",
            f"{bandwidth_val:.1f} Hz" if bandwidth_val is not None else "n/a",
        )
        rolloff_val = current_metrics["spectral_rolloff_hz"]
        p_cols[2].metric(
            "Spectral Roll-off",
            f"{rolloff_val:.1f} Hz" if rolloff_val is not None else "n/a",
        )
        hnr_val = current_metrics["hnr_db"]
        p_cols[2].metric(
            "Harmonics-to-Noise (HNR)",
            f"{hnr_val:.1f} dB" if hnr_val is not None else "n/a",
        )

    st.markdown("---")

    # ==============================================================================
    # SECTION 4 — BLOCK ANALYSIS
    # ==============================================================================
    st.header("4. Block Analysis")
    st.caption(
        f"Showing Level 2 temporal summaries computed dynamically for block size = {block_size}s."
    )

    import math

    num_blocks = int(math.ceil(duration / block_size)) if block_size > 0 else 1

    # 4.1 Call Block Score Overview (Summary table of all blocks)
    st.markdown("### 📊 Call Block Score Overview")
    all_blocks_rows = []
    for i in range(num_blocks):
        b_start = i * block_size
        b_end = min(duration, b_start + block_size)
        target_t = b_start + (block_size / 2.0)
        # Compute metrics dynamically for the summary table
        b_metrics = BlockAnalysisEngine.get_block_metrics(
            context, target_t, block_size, metadata
        )
        b_scores = b_metrics["scores"]

        all_blocks_rows.append(
            {
                "Block": f"Block #{i}",
                "Time Interval": f"{b_start:.1f}s – {b_end:.1f}s",
                "Audio Quality": f"{b_scores.get('audio_quality', 0)}/100",
                "Voice Stability": f"{b_scores.get('voice_stability', 0)}/100",
                "Conversation Flow": f"{b_scores.get('conversation_flow', 0)}/100",
                "Conversation Balance": f"{b_scores.get('conversation_balance', 0)}/100",
                "Speech Activity": f"{b_scores.get('speech_activity', 0)}/100",
            }
        )
    df_all_blocks = pd.DataFrame(all_blocks_rows)
    st.dataframe(df_all_blocks, use_container_width=True, hide_index=True)

    # 4.2 Detailed Block Inspection (Dropdown + details)
    st.markdown("### 🔍 Detailed Block Inspection")
    block_options = [
        f"Block #{i} ({i*block_size:.1f}s – {min(duration, (i+1)*block_size):.1f}s)"
        for i in range(num_blocks)
    ]
    default_idx = min(int(current_time // block_size), num_blocks - 1)
    default_idx = max(0, default_idx)

    selected_block_str = st.selectbox(
        "Select Block to Inspect in Detail", block_options, index=default_idx
    )
    selected_block_idx = block_options.index(selected_block_str)

    target_time_for_selected = (selected_block_idx * block_size) + (block_size / 2.0)
    block_data = BlockAnalysisEngine.get_block_metrics(
        context, target_time_for_selected, block_size, metadata
    )

    b_acoustic, b_events, b_scores = (
        block_data["stats"],
        block_data["events"],
        block_data["scores"],
    )

    tab_b_scores, tab_b_stats, tab_b_speech, tab_b_conv = st.tabs(
        [
            "🏆 Block Quality Scores",
            "📊 Block Physical Statistics",
            "🗣️ Block Speech Activity",
            "🤝 Block Conversation Turn Stats",
        ]
    )

    with tab_b_scores:
        col_bs1, col_bs2, col_bs3, col_bs4, col_bs5 = st.columns(5)

        aq_b_score = b_scores.get("audio_quality", 0)
        col_bs1.metric(
            "Audio Quality", f"{aq_b_score}/100", get_score_color(aq_b_score)
        )

        vs_b_score = b_scores.get("voice_stability", 0)
        col_bs2.metric(
            "Voice Stability", f"{vs_b_score}/100", get_score_color(vs_b_score)
        )

        flow_b_score = b_scores.get("conversation_flow", 0)
        col_bs3.metric(
            "Conversation Flow", f"{flow_b_score}/100", get_score_color(flow_b_score)
        )

        bal_b_score = b_scores.get("conversation_balance", 0)
        col_bs4.metric(
            "Conversation Balance", f"{bal_b_score}/100", get_score_color(bal_b_score)
        )

        sa_b_score = b_scores.get("speech_activity", 0)
        col_bs5.metric(
            "Speech Activity", f"{sa_b_score}/100", get_score_color(sa_b_score)
        )

    with tab_b_stats:
        stats_rows = []
        for feature, val_dict in b_acoustic.items():
            reg_info = FEATURE_REGISTRY.get(feature, {})
            display_name = reg_info.get("display", feature)
            unit = reg_info.get("unit", "")
            unit_suffix = f" ({unit})" if unit else ""

            stats_rows.append(
                {
                    "Feature Metric": display_name + unit_suffix,
                    "Minimum": (
                        round(val_dict["min"], 3)
                        if val_dict["min"] is not None
                        else None
                    ),
                    "Maximum": (
                        round(val_dict["max"], 3)
                        if val_dict["max"] is not None
                        else None
                    ),
                    "Average": (
                        round(val_dict["mean"], 3)
                        if val_dict["mean"] is not None
                        else None
                    ),
                    "Std Deviation": (
                        round(val_dict["std"], 3)
                        if val_dict["std"] is not None
                        else None
                    ),
                }
            )
        st.dataframe(
            pd.DataFrame(stats_rows), use_container_width=True, hide_index=True
        )

    with tab_b_speech:
        col_bsp1, col_bsp2, col_bsp3 = st.columns(3)
        col_bsp1.metric(
            "Speech active time", f"{b_events.get('speech_percent', 0.0):.1f}%"
        )
        col_bsp1.metric("Silence time", f"{b_events.get('silence_percent', 0.0):.1f}%")

        col_bsp2.metric("Pause Count", b_events.get("pause_count", 0))
        col_bsp2.metric(
            "Total Pause Duration", f"{b_events.get('pause_duration', 0.0):.1f}s"
        )
        col_bsp2.metric(
            "Longest Pause in Block", f"{b_events.get('longest_pause', 0.0):.1f}s"
        )

        col_bsp3.metric("Dropout Count", b_events.get("dropout_count", 0))
        col_bsp3.metric(
            "Total Dropout Duration", f"{b_events.get('dropout_duration', 0.0):.1f}s"
        )

    with tab_b_conv:
        col_bcv1, col_bcv2 = st.columns(2)
        with col_bcv1:
            st.metric("Total Turns in Block", b_events.get("turn_count", 0))
            st.metric("Speaker Changes", b_events.get("speaker_changes", 0))
            st.metric(
                "Average Response Latency", f"{b_events.get('avg_latency', 0.0):.2f}s"
            )
        with col_bcv2:
            st.markdown("**Speaker Share inside this Block:**")
            for spk, ratio in b_events.get("speaker_ratios", {}).items():
                st.progress(ratio / 100.0, text=f"{spk}: {ratio:.1f}%")
            if not b_events.get("speaker_ratios"):
                st.info("Silent block (no speech segments)")

    st.markdown("---")

    # ==============================================================================
    # SECTION 5 — TIMELINE VISUALIZATIONS
    # ==============================================================================
    st.header("5. Timeline Visualizations")

    col_time_ctrl, col_chart_space = st.columns([1, 4])
    with col_time_ctrl:
        st.markdown("**Timeline Display Options**")
        auto_pan = st.checkbox("Auto-pan plot cursor (60s window)", value=True)
    with col_chart_space:
        fig_timeline = build_timeline_figure(
            timeline,
            diarization.get("segments", []),
            cursor_time=current_time,
            auto_pan=auto_pan,
        )
        st.plotly_chart(fig_timeline, use_container_width=True)

    st.markdown("---")

    # ==============================================================================
    # SECTION 6 — SPEAKER ANALYSIS
    # ==============================================================================
    st.header("6. Speaker Analysis")

    col_spk_stats, col_spk_ratios = st.columns(2)

    with col_spk_stats:
        st.subheader("Conversational Exchange Demographics")
        spk_table = []
        for spk, info in summary.get("speaker_statistics", {}).items():
            spk_table.append(
                {
                    "Speaker Label": spk,
                    "Total Talk Time (s)": info.get("talk_time_seconds"),
                    "Talk Percentage (%)": info.get("talk_percentage"),
                    "Total Speaking Turns": info.get("turn_count"),
                    "Average Turn Duration (s)": info.get(
                        "average_turn_duration_seconds"
                    ),
                    "Speaking Rate": f"{info.get('avg_speaking_rate_sps', 0.0):.1f} sps",
                }
            )
        if spk_table:
            st.dataframe(
                pd.DataFrame(spk_table), use_container_width=True, hide_index=True
            )
        else:
            st.info("No speaker statistics calculated.")

    with col_spk_ratios:
        st.subheader("Conversational Ratios (Speech Share)")
        ratios_data = []
        labels_data = []
        for spk, info in summary.get("speaker_statistics", {}).items():
            labels_data.append(spk)
            ratios_data.append(info.get("talk_percentage", 0.0))

        if ratios_data:
            fig_pie = go.Figure(
                data=[go.Pie(labels=labels_data, values=ratios_data, hole=0.3)]
            )
            fig_pie.update_layout(
                height=260, margin=dict(l=20, r=20, t=20, b=20), showlegend=True
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No ratios chart available.")

    st.markdown("### Diarization Timeline")
    st.caption("Detailed segment-by-segment speaker analysis.")

    segments = diarization.get("segments", [])
    if segments:
        st.markdown("**Real-time Audio Sync Playback**")
        audio_url = _prepare_audio_static(metadata)
        if audio_url:
            from visualization.synced_player import render_synced_player

            duration = metadata.get("duration_seconds", 60.0)
            render_synced_player(audio_url, segments, duration)
        else:
            st.warning("Audio file unavailable for real-time playback.")

        # Display segments table
        with st.expander("View Raw Diarization Timestamps", expanded=False):
            seg_df = pd.DataFrame(segments)
            if not seg_df.empty:
                seg_df = seg_df[["speaker", "start", "end", "duration"]]
                st.dataframe(seg_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ==============================================================================
    # SECTION 7 — SCORE BREAKDOWN
    # ==============================================================================
    st.header("7. Score Breakdown")
    st.caption(
        "Detailed objective analysis rules, grades, and contributing factors for each score."
    )

    for score_key in [
        "overall_call_health",
        "audio_quality",
        "recording_reliability",
        "voice_stability",
        "conversation_flow",
        "conversation_balance",
        "speech_activity",
    ]:
        info = explanations.get(score_key, {})
        val = info.get("value", 0)
        grade = info.get("grade", "n/a")
        color = get_score_color(val)

        with st.container():
            col_score_lbl, col_pos, col_neg = st.columns([1.5, 2, 2])
            with col_score_lbl:
                st.markdown(
                    f"""
                <div style="background-color: #1e1e24; padding: 15px; border-radius: 8px; border-left: 5px solid {color}; margin-bottom: 10px;">
                    <h5 style="margin: 0; color: #a0a0b0; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">{info.get('name', score_key)}</h5>
                    <h2 style="margin: 8px 0 2px 0; color: {color}; font-weight: bold; font-size: 28px;">{val}/100</h2>
                    <span style="color: #808090; font-size: 12px; font-weight: 500;">{grade}</span>
                </div>
                """,
                    unsafe_allow_html=True,
                )
            with col_pos:
                st.markdown("**Positives (✓)**")
                for p in info.get("positives", []):
                    st.markdown(f"✓ :green[{p}]")
                if not info.get("positives"):
                    st.caption("No positive contributing factors detected.")
            with col_neg:
                st.markdown("**Negatives (✗)**")
                for n in info.get("negatives", []):
                    st.markdown(f"✗ :red[{n}]")
                if not info.get("negatives"):
                    st.caption("No negative contributing factors detected.")
            st.markdown(
                "<hr style='margin: 10px 0; border: 0; border-top: 1px solid #333;'>",
                unsafe_allow_html=True,
            )


if __name__ == "__main__":
    # Force streamlit hot-reload trigger
    run_dashboard()
