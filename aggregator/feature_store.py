from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from extractors.speaker import (
    build_rich_events,
)


@dataclass
class FeatureStore:
    metadata: dict[str, Any] = field(default_factory=dict)
    features: dict[str, Any] = field(
        default_factory=lambda: {
            "timeline": [],
            "events": [],
        }
    )
    diarization: dict[str, Any] = field(
        default_factory=lambda: {
            "segments": [],
            "statistics": {},
        }
    )
    summary: dict[str, Any] = field(default_factory=dict)
    engineered_features: dict[str, Any] = field(default_factory=dict)
    analysis_results: dict[str, Any] = field(default_factory=dict)

    def add_window(
        self,
        index: int,
        start_seconds: float,
        end_seconds: float,
        flat_features: dict[str, Any],
    ) -> None:
        """
        Takes flat features from window extraction and reorganizes them into
        the nested raw/derived production-grade JSON schema.
        Note: The timeline no longer tracks 'speaker' data. Diarization is stored separately.
        """
        row = {
            "index": index,
            "timestamp": start_seconds,
            "start_seconds": start_seconds,
            "end_seconds": end_seconds,
            "raw": {
                "acoustic": {
                    "rms": flat_features.get("rms"),
                    "energy": flat_features.get("energy"),
                    "loudness_db": flat_features.get("loudness_db"),
                    "spectral_centroid_hz": flat_features.get("spectral_centroid_hz"),
                    "spectral_bandwidth_hz": flat_features.get("spectral_bandwidth_hz"),
                    "spectral_rolloff_hz": flat_features.get("spectral_rolloff_hz"),
                },
                "quality": {
                    "snr_db": flat_features.get("snr_db"),
                    "speech_quality_proxy": flat_features.get("speech_quality_proxy"),
                    "clipping_ratio": flat_features.get("clipping_ratio"),
                    "hnr_db": flat_features.get("hnr_db"),
                    "spectral_flux": flat_features.get("spectral_flux"),
                    "formant_dispersion": flat_features.get("formant_dispersion"),
                },
                "prosody": {
                    "pitch_hz": flat_features.get("pitch_hz"),
                    "jitter_pct": flat_features.get("jitter_pct"),
                    "shimmer_pct": flat_features.get("shimmer_pct"),
                    "speaking_rate_sps": flat_features.get("speaking_rate_sps"),
                },
            },
            "derived": {
                "speech": {
                    "active": flat_features.get("speech", False),
                    "probability": 1.0 if flat_features.get("speech", False) else 0.0,
                    "silence_ratio": flat_features.get("silence_ratio", 0.0),
                },
            },
            # Helper flags at root for event detection algorithms
            "pause": flat_features.get("pause", False),
            "dropout": flat_features.get("dropout", False),
        }
        self.features["timeline"].append(row)

    def set_diarization(self, segments: list[dict[str, Any]]) -> None:
        """Stores the continuous speaker segments and calculates high-level statistics."""
        # Calculate initial talk times to identify phantom speakers
        spk_times = {}
        total_speech = 0.0
        for seg in segments:
            spk = seg["speaker"]
            spk_times[spk] = spk_times.get(spk, 0.0) + seg["duration"]
            total_speech += seg["duration"]

        # Filter out speakers that speak for < 1.5s AND < 1% of total speech time
        valid_speakers = {
            spk for spk, duration in spk_times.items()
            if duration >= 1.5 or (total_speech > 0 and (duration / total_speech) >= 0.01)
        }

        # If all speakers were somehow filtered out, keep the one with max duration
        if not valid_speakers and spk_times:
            valid_speakers = {max(spk_times, key=spk_times.get)}

        # Filter segments to only include valid speakers
        filtered_segments = [seg for seg in segments if seg["speaker"] in valid_speakers]

        self.diarization["segments"] = filtered_segments

        # Recalculate stats for valid speakers only
        valid_spk_times = {spk: spk_times[spk] for spk in valid_speakers}

        self.diarization["statistics"] = {
            "speaker_count": len(valid_spk_times),
            "talk_times": valid_spk_times,
        }

    def _compute_call_baseline(self) -> None:
        import numpy as np

        # Extract all valid loudness values where speech is active
        loudness_values = [
            frame["raw"]["acoustic"]["energy"]
            for frame in self.features["timeline"]
            if frame.get("raw", {}).get("acoustic", {}).get("energy") is not None
            and frame.get("derived", {}).get("speech", {}).get("active")
        ]
        if loudness_values:
            median_loudness = float(np.median(loudness_values))
            mad_loudness = float(
                np.median(np.abs(np.array(loudness_values) - median_loudness))
            )
            self.summary["baseline_loudness_median"] = median_loudness
            self.summary["baseline_loudness_mad"] = (
                mad_loudness if mad_loudness > 0 else 1.0
            )
        else:
            self.summary["baseline_loudness_median"] = 0.0
            self.summary["baseline_loudness_mad"] = 1.0


    def finalize(self, long_pause_seconds: float = 1.0) -> None:
        """
        Runs the derived analytics layer to complete the feature store.
        """
        # 1. Build Rich Events (from timeline)
        # Note: We pass diarization segments to build_rich_events so it can still map speakers to events if needed
        self.features["events"] = build_rich_events(
            self.features["timeline"], self.diarization["segments"], long_pause_seconds
        )

        # 2. Compute Summary Metrics using SummaryAnalysisEngine
        from analytics.engines.summary_analysis import SummaryAnalysisEngine

        self.summary = SummaryAnalysisEngine.compute_summary(
            self.features["timeline"],
            self.diarization["segments"],
            self.features["events"],
            self.metadata,
        )

        self._compute_call_baseline()

        # 3. Compute Engineered Features and scoring using context-based engines
        try:
            from analytics import (
                AnalysisContext,
                compute_engineered_features,
                compute_scores,
            )

            context = AnalysisContext(
                timeline=self.features["timeline"],
                diarization=self.diarization,
                events=self.features["events"],
                metadata=self.metadata,
                summary=self.summary,
            )

            self.engineered_features = compute_engineered_features(context)
            self.analysis_results = compute_scores(self.engineered_features)
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(
                "Failed to compute analytics results in finalize: %s", e
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata,
            "features": self.features,
            "diarization": self.diarization,
            "summary": self.summary,
            "engineered_features": self.engineered_features,
            "analysis_results": self.analysis_results,
        }

    def save_json(self, path: str | Path) -> Path:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return output_path

    @classmethod
    def load_json(cls, path: str | Path) -> "FeatureStore":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))

        metadata = payload.get("metadata", {})
        summary = payload.get("summary", {})
        engineered = payload.get("engineered_features", {})
        analysis_results = payload.get("analysis_results", {})
        diarization = payload.get("diarization", {"segments": [], "statistics": {}})
        features = payload.get("features", {"timeline": [], "events": []})

        store = cls(
            metadata=metadata,
            features=features,
            diarization=diarization,
            summary=summary,
            engineered_features=engineered,
            analysis_results=analysis_results,
        )

        return store
