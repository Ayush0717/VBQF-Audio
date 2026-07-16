"""Diagnostic: progressively test each section of the dashboard to find the crash."""

import streamlit as st
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

st.set_page_config(page_title="Dashboard Debug", layout="wide")
st.title("🔍 Dashboard Debug Mode")

try:
    st.write("Step 1: Imports...")
    from aggregator.feature_store import FeatureStore
    from visualization.timeline import build_timeline_figure, flatten_timeline
    from analytics import (
        AnalysisContext,
        CurrentAnalysisEngine,
        BlockAnalysisEngine,
        SummaryAnalysisEngine,
    )
    import plotly.graph_objects as go
    import numpy as np
    import pandas as pd

    st.success("✅ All imports OK")

    st.write("Step 2: Load JSON...")
    store = FeatureStore.load_json("data/outputs/call_features.json")
    st.success(
        f"✅ Loaded store — timeline has {len(store.features.get('timeline',[]))} windows"
    )

    metadata = store.metadata
    summary = store.summary
    timeline = store.features.get("timeline", [])
    speaker_segments = store.features.get("speaker_segments", [])
    events = store.features.get("events", [])
    duration = float(metadata.get("duration_seconds", 60.0))

    context = AnalysisContext(
        timeline=timeline,
        speaker_segments=speaker_segments,
        events=events,
        metadata=metadata,
        summary=summary,
    )
    st.success("✅ Context initialized")

    st.write("Step 3: CurrentAnalysisEngine...")
    current_metrics = CurrentAnalysisEngine.get_current_metrics(context, 10.0)
    st.success(f"✅ Current metrics status: {current_metrics.get('status')}")

    st.write("Step 4: BlockAnalysisEngine...")
    block_metrics = BlockAnalysisEngine.get_block_metrics(context, 10.0, 10.0, metadata)
    st.success(f"✅ Block metrics computed - keys: {list(block_metrics.keys())}")

    st.write("Step 5: SummaryAnalysisEngine...")
    sum_data = SummaryAnalysisEngine.compute_summary(
        timeline, speaker_segments, events, metadata
    )
    st.success(
        f"✅ Summary calculated - average SNR: {sum_data.get('average_snr_db')} dB"
    )

    st.write("Step 6: build_timeline_figure...")
    fig_timeline = build_timeline_figure(timeline, cursor_time=10.0, auto_pan=True)
    st.plotly_chart(fig_timeline, use_container_width=True)
    st.success("✅ Timeline chart OK")

    st.balloons()
    st.success("🎉 ALL STEPS PASSED — The analytics package is functional!")

except Exception as e:
    st.error(f"💥 CRASH: {type(e).__name__}: {e}")
    import traceback

    st.code(traceback.format_exc())
