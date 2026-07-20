from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from aggregator.feature_store import FeatureStore
from config import DEFAULT_CONFIG, OUTPUT_DIR, PipelineConfig
from extractors import build_extractors
from preprocessing.loader import load_audio
from preprocessing.window_generator import generate_windows
from utils.logging import configure_logging

LOGGER = logging.getLogger(__name__)


def process_audio(
    audio_path: str | Path,
    output_path: str | Path | None = None,
    config: PipelineConfig = DEFAULT_CONFIG,
    extractors: list | None = None,
) -> FeatureStore:
    audio_path = Path(audio_path)
    audio = load_audio(
        audio_path,
        target_sample_rate=config.audio.target_sample_rate,
        normalize=config.audio.normalize,
    )
    if extractors is None:
        extractors = build_extractors(config)

    store = FeatureStore(
        metadata={
            "source_file": str(audio_path),
            "sample_rate": audio.sample_rate,
            "duration_seconds": audio.duration_seconds,
            "enabled_extractors": [extractor.name for extractor in extractors],
            "processing": {
                "window_size_seconds": config.windows.length_seconds,
                "hop_size_seconds": config.windows.hop_seconds,
                "diarization_model": (
                    "Pyannote pyannote/speaker-diarization-3.1"
                    if config.diarization_enabled
                    else None
                ),
                "pipeline_version": "0.3",
            },
            "processed_at": datetime.now().isoformat(),
        }
    )

    LOGGER.info(
        "Loaded %.2fs audio at %s Hz", audio.duration_seconds, audio.sample_rate
    )

    for window in generate_windows(
        audio.samples,
        audio.sample_rate,
        config.windows.length_seconds,
        config.windows.hop_seconds,
    ):
        features: dict[str, Any] = {}
        for extractor in extractors:
            started = time.perf_counter()
            features.update(extractor.extract(window.samples, audio.sample_rate))
            elapsed_ms = (time.perf_counter() - started) * 1000
            LOGGER.debug(
                "window=%s extractor=%s elapsed_ms=%.2f",
                window.index,
                extractor.name,
                elapsed_ms,
            )

        store.add_window(
            index=window.index,
            start_seconds=window.start_seconds,
            end_seconds=window.end_seconds,
            flat_features=features,
        )

    # Run Speaker Diarization if enabled
    if config.diarization_enabled:
        from extractors.speaker.diarizer import diarize_audio

        # We run diarization directly on the source file
        segments = diarize_audio(
            audio_path,
            num_speakers=config.num_speakers,
        )
        store.set_diarization(segments)

    store.finalize(long_pause_seconds=config.long_pause_seconds)

    if output_path is not None:
        store.save_json(output_path)
        LOGGER.info("Saved feature store to %s", output_path)

    return store


def default_output_path(audio_path: str | Path) -> Path:
    source = Path(audio_path)
    return OUTPUT_DIR / f"{source.stem}_features.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract Phase 1 audio confidence features into a JSON feature store."
    )
    parser.add_argument("audio_file", help="Path to a WAV/MP3 call recording.")
    parser.add_argument(
        "-o",
        "--output",
        help="Output JSON path. Defaults to data/outputs/<audio>_features.json.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    parser.add_argument(
        "--num_speakers",
        type=int,
        default=None,
        help="Optional: Explicitly define the number of speakers to extract (default: auto-detect).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)

    from config import DEFAULT_CONFIG
    import dataclasses

    config = DEFAULT_CONFIG
    if args.num_speakers is not None:
        config = dataclasses.replace(config, num_speakers=args.num_speakers)

    output_path = (
        Path(args.output) if args.output else default_output_path(args.audio_file)
    )
    store = process_audio(args.audio_file, output_path=output_path, config=config)
    LOGGER.info(
        "Processed %s windows and %s events",
        len(store.features["timeline"]),
        len(store.features["events"]),
    )


if __name__ == "__main__":
    main()
