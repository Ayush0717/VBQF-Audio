from __future__ import annotations

from config import PipelineConfig
from extractors.acoustic import (
    EnergyExtractor,
    LoudnessExtractor,
    RmsExtractor,
    SpectralCentroidExtractor,
    ZeroCrossingRateExtractor,
)
from extractors.base import BaseExtractor
from extractors.pitch import PitchExtractor
from extractors.quality import (
    SilenceRatioExtractor,
    SnrExtractor,
    SpeechQualityExtractor,
)
from extractors.vad import DropoutExtractor, PauseExtractor, VadExtractor
from extractors.prosody_advanced import (
    JitterExtractor,
    ShimmerExtractor,
    HnrExtractor,
    SpeakingRateExtractor,
)
from extractors.spectral_advanced import (
    SpectralFluxExtractor,
    FormantDispersionExtractor,
)
from extractors.spectral_features import (
    SpectralBandwidthExtractor,
    SpectralRolloffExtractor,
)


def build_extractors(config: PipelineConfig) -> list[BaseExtractor]:
    factories = {
        "rms": RmsExtractor,
        "energy": EnergyExtractor,
        "loudness": LoudnessExtractor,
        "zero_crossing_rate": ZeroCrossingRateExtractor,
        "spectral_centroid": SpectralCentroidExtractor,
        "pitch": PitchExtractor,
        "snr": SnrExtractor,
        "speech_quality": SpeechQualityExtractor,
        "silence_ratio": lambda: SilenceRatioExtractor(config.silence_rms_threshold),
        "vad": lambda: VadExtractor(config.silence_rms_threshold),
        "pause": lambda: PauseExtractor(config.silence_rms_threshold),
        "dropout": lambda: DropoutExtractor(config.dropout_rms_threshold),
        "jitter": JitterExtractor,
        "shimmer": ShimmerExtractor,
        "hnr": HnrExtractor,
        "speaking_rate": SpeakingRateExtractor,
        "spectral_flux": SpectralFluxExtractor,
        "formant_dispersion": FormantDispersionExtractor,
        "spectral_bandwidth": SpectralBandwidthExtractor,
        "spectral_roll_off": SpectralRolloffExtractor,
    }

    extractors: list[BaseExtractor] = []
    for name in config.enabled_extractors:
        if name not in factories:
            raise KeyError(f"Unknown extractor configured: {name}")
        extractors.append(factories[name]())
    return extractors
