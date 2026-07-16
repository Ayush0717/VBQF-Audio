from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
AUDIO_DIR = DATA_DIR / "audio"
OUTPUT_DIR = DATA_DIR / "outputs"


# ── Call type taxonomy ────────────────────────────────────────────────────────
class CallType(str, Enum):
    """
    Defines the business context of a call.
    Conversation Balance optimal ranges differ per call type because
    the expected agent/customer talk ratio is fundamentally different.
    """
    COLLECTION     = "collection"       # Agent leads: agent 65-85%, customer 15-35%
    CUSTOMER_SUPPORT = "customer_support"  # Near-equal: 45-65% agent
    SURVEY         = "survey"           # Near-equal: 45-55% agent
    UNKNOWN        = "unknown"          # Fall back to broad acceptable band


# ── Conversation Balance bands per call type ─────────────────────────────────
# Format: (low_bound, opt_start, opt_end, high_bound)
# These are the *absolute difference* between top-2 speaker talk %.
# e.g. collection: agent 70% / customer 30% → diff = 40 → inside opt range
CALL_TYPE_BALANCE_BANDS: dict[CallType, tuple[float, float, float, float]] = {
    CallType.COLLECTION:       (0.0,  30.0, 70.0, 95.0),
    CallType.CUSTOMER_SUPPORT: (0.0,  10.0, 40.0, 75.0),
    CallType.SURVEY:           (0.0,   0.0, 25.0, 60.0),
    CallType.UNKNOWN:          (0.0,  10.0, 70.0, 95.0),
}


@dataclass(frozen=True)
class AudioConfig:
    target_sample_rate: int = 16_000
    normalize: bool = True


@dataclass(frozen=True)
class WindowConfig:
    length_seconds: float = 1.0
    hop_seconds: float = 0.5


@dataclass(frozen=True)
class ScoreConfig:
    # ── Pillar weights ────────────────────────────────────────────────────────
    # Rationale for current values:
    #   AQ (0.25): Already behaving well and reliably measurable → increase
    #   CF (0.25): Proven discriminator → increase
    #   CC (0.20): Reduced from 0.30 until decision-turn detection is robust
    #   VS (0.10): Kept; jitter/shimmer deprioritised (see voice_stability_weights)
    #   CB (0.10): Kept; now call-type-aware via call_type parameter
    #   SA (0.10): Low discrimination; candidate for future merge into CF
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "collection_confidence": 0.20,
            "audio_quality": 0.25,
            "conversation_flow": 0.25,
            "voice_stability": 0.10,
            "conversation_balance": 0.10,
            "speech_activity": 0.10,
        }
    )

    # ── Voice Stability internal weights ─────────────────────────────────────
    # Jitter/Shimmer are nearly identical across good/bad/medium recordings →
    # not predictive features at this sample size.
    # Pitch_std and loudness_std DO show separation → upweighted.
    # These weights apply inside compute_scores() for VS pillar only.
    voice_stability_weights: dict[str, float] = field(
        default_factory=lambda: {
            "pitch_sub":     0.45,  # was 0.25 — shows separation
            "loud_std_sub":  0.35,  # was 0.20 — energy stability separates
            "jitter_sub":    0.10,  # was 0.25 — NOT predictive, deprioritise
            "shimmer_sub":   0.05,  # was 0.20 — NOT predictive, deprioritise
            "speak_std_sub": 0.05,  # was 0.10 — keep minor
        }
    )

    # ── Score label thresholds ────────────────────────────────────────────────
    thresholds: dict[str, float] = field(
        default_factory=lambda: {
            "Excellent": 90.0,
            "Good": 75.0,
            "Fair": 60.0,
        }
    )

    # ── Default call type ─────────────────────────────────────────────────────
    call_type: CallType = CallType.COLLECTION


@dataclass(frozen=True)
class PipelineConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    windows: WindowConfig = field(default_factory=WindowConfig)
    enabled_extractors: tuple[str, ...] = (
        "rms",
        "energy",
        "loudness",
        "zero_crossing_rate",
        "spectral_centroid",
        "pitch",
        "snr",
        "speech_quality",
        "silence_ratio",
        "vad",
        "pause",
        "dropout",
        "jitter",
        "shimmer",
        "hnr",
        "speaking_rate",
        "spectral_flux",
        "formant_dispersion",
        "spectral_bandwidth",
        "spectral_roll_off",
    )
    silence_rms_threshold: float = 0.015
    dropout_rms_threshold: float = 0.003
    long_pause_seconds: float = 1.0
    diarization_enabled: bool = True
    speaker_mode: str = "fixed"
    num_speakers: int | None = None
    score: ScoreConfig = field(default_factory=ScoreConfig)


DEFAULT_CONFIG = PipelineConfig()
