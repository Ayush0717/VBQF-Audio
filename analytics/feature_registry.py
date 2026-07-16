from __future__ import annotations

# Unified feature metadata registry for both raw and engineered metrics.
FEATURE_REGISTRY = {
    # Raw Acoustic Features (Layer 1)
    "rms": {
        "display": "RMS Amplitude",
        "unit": "",
        "category": "Acoustic",
        "description": "Root Mean Square of signal amplitude.",
    },
    "energy": {
        "display": "Energy",
        "unit": "",
        "category": "Acoustic",
        "description": "Sum of squared amplitude values.",
    },
    "loudness_db": {
        "display": "Loudness",
        "unit": "dB",
        "category": "Acoustic",
        "description": "Logarithmic measure of signal power in decibels.",
    },
    "spectral_centroid_hz": {
        "display": "Spectral Centroid",
        "unit": "Hz",
        "category": "Acoustic",
        "description": "The center of gravity of the frequency spectrum.",
    },
    "spectral_bandwidth_hz": {
        "display": "Spectral Bandwidth",
        "unit": "Hz",
        "category": "Acoustic",
        "description": "The variance/spread of the spectrum around its centroid.",
    },
    "spectral_rolloff_hz": {
        "display": "Spectral Roll-off",
        "unit": "Hz",
        "category": "Acoustic",
        "description": "Frequency below which 85% of magnitude energy lies.",
    },
    "zero_crossing_rate": {
        "display": "Zero Crossing Rate",
        "unit": "",
        "category": "Acoustic",
        "description": "Rate at which sign of the signal changes (noise indicator).",
    },
    # Raw Quality Features (Layer 1)
    "snr_db": {
        "display": "SNR",
        "unit": "dB",
        "category": "Quality",
        "description": "Signal-to-noise ratio in decibels.",
    },
    "speech_quality_proxy": {
        "display": "Speech Quality Proxy",
        "unit": "",
        "category": "Quality",
        "description": "Quality estimate combining SNR and RMS stability (0.0 to 1.0).",
    },
    "hnr_db": {
        "display": "HNR",
        "unit": "dB",
        "category": "Quality",
        "description": "Harmonics-to-noise ratio.",
    },
    "spectral_flux": {
        "display": "Spectral Flux",
        "unit": "",
        "category": "Quality",
        "description": "Speed of spectral variation frame-to-frame.",
    },
    "formant_dispersion": {
        "display": "Formant Dispersion",
        "unit": "Hz",
        "category": "Quality",
        "description": "Average frequency distance between the first two formant peaks.",
    },
    # Raw Prosody Features (Layer 1)
    "pitch_hz": {
        "display": "Vocal Pitch",
        "unit": "Hz",
        "category": "Prosody",
        "description": "Fundamental frequency of the vocal folds (F0).",
    },
    "jitter_pct": {
        "display": "Jitter",
        "unit": "%",
        "category": "Prosody",
        "description": "Frequency perturbation (vocal cycle-to-cycle frequency variations).",
    },
    "shimmer_pct": {
        "display": "Shimmer",
        "unit": "%",
        "category": "Prosody",
        "description": "Amplitude perturbation (vocal cycle-to-cycle amplitude variations).",
    },
    "speaking_rate_sps": {
        "display": "Speaking Rate",
        "unit": "sps",
        "category": "Prosody",
        "description": "Estimated speech rate in syllables per second.",
    },
    # Layer 2 Engineered Features - Audio Quality
    "average_rms": {
        "display": "Average RMS",
        "unit": "",
        "category": "Engineered Audio Quality",
        "description": "Mean RMS value over the call.",
    },
    "average_energy": {
        "display": "Average Energy",
        "unit": "",
        "category": "Engineered Audio Quality",
        "description": "Mean signal energy over the call.",
    },
    "average_loudness": {
        "display": "Average Loudness",
        "unit": "dB",
        "category": "Engineered Audio Quality",
        "description": "Mean loudness level over the call.",
    },
    "average_snr": {
        "display": "Average SNR",
        "unit": "dB",
        "category": "Engineered Audio Quality",
        "description": "Mean signal-to-noise ratio over the call.",
    },
    "noise_level": {
        "display": "Noise Level",
        "unit": "dB",
        "category": "Engineered Audio Quality",
        "description": "Average loudness level during silence frames.",
    },
    "recording_stability": {
        "display": "Recording Stability",
        "unit": "",
        "category": "Engineered Audio Quality",
        "description": "Standard deviation of SNR across the call (lower = more stable).",
    },
    "dropout_count": {
        "display": "Dropout Count",
        "unit": "",
        "category": "Engineered Audio Quality",
        "description": "Total count of transmission signal dropouts.",
    },
    "dropout_duration": {
        "display": "Dropout Duration",
        "unit": "s",
        "category": "Engineered Audio Quality",
        "description": "Total length of dropouts in seconds.",
    },
    "clipping_percentage": {
        "display": "Clipping Percentage",
        "unit": "%",
        "category": "Engineered Audio Quality",
        "description": "Percentage of samples showing amplitude clipping.",
    },
    # Layer 2 Engineered Features - Voice Stability
    "pitch_stability": {
        "display": "Pitch Deviation",
        "unit": "Hz",
        "category": "Engineered Voice Stability",
        "description": "Standard deviation of vocal pitch (lower is more stable).",
    },
    "pitch_variance": {
        "display": "Pitch Variance",
        "unit": "",
        "category": "Engineered Voice Stability",
        "description": "Variance of vocal pitch.",
    },
    "energy_stability": {
        "display": "Energy Deviation",
        "unit": "",
        "category": "Engineered Voice Stability",
        "description": "Standard deviation of energy (lower is more stable).",
    },
    "energy_variance": {
        "display": "Energy Variance",
        "unit": "",
        "category": "Engineered Voice Stability",
        "description": "Variance of signal energy.",
    },
    "loudness_stability": {
        "display": "Loudness Deviation",
        "unit": "dB",
        "category": "Engineered Voice Stability",
        "description": "Standard deviation of loudness (lower is more stable).",
    },
    "loudness_variance": {
        "display": "Loudness Variance",
        "unit": "",
        "category": "Engineered Voice Stability",
        "description": "Variance of loudness values.",
    },
    "speaking_stability": {
        "display": "Speaking Rate Deviation",
        "unit": "sps",
        "category": "Engineered Voice Stability",
        "description": "Standard deviation of speaking rates (lower means more rhythmic speech).",
    },
    # Layer 2 Engineered Features - Speech Behaviour
    "speech_percentage": {
        "display": "Speech Ratio",
        "unit": "%",
        "category": "Engineered Speech Behaviour",
        "description": "Percentage of active speech duration during the call.",
    },
    "silence_percentage": {
        "display": "Silence Ratio",
        "unit": "%",
        "category": "Engineered Speech Behaviour",
        "description": "Percentage of dead air or silent duration during the call.",
    },
    "pause_count": {
        "display": "Pause Count",
        "unit": "",
        "category": "Engineered Speech Behaviour",
        "description": "Number of brief speaking pauses.",
    },
    "average_pause_duration": {
        "display": "Average Pause Duration",
        "unit": "s",
        "category": "Engineered Speech Behaviour",
        "description": "Mean duration of speaking pauses.",
    },
    "longest_pause": {
        "display": "Longest Pause",
        "unit": "s",
        "category": "Engineered Speech Behaviour",
        "description": "Longest pause duration.",
    },
    "pause_frequency": {
        "display": "Pause Frequency",
        "unit": "/min",
        "category": "Engineered Speech Behaviour",
        "description": "Pauses per minute of call time.",
    },
    # Layer 2 Engineered Features - Conversation Behaviour
    "speaker_talk_time": {
        "display": "Talk Time",
        "unit": "s",
        "category": "Engineered Conversation Behaviour",
        "description": "Speaking duration in seconds for each speaker.",
    },
    "speaker_talk_ratio": {
        "display": "Talk Share",
        "unit": "%",
        "category": "Engineered Conversation Behaviour",
        "description": "Talk time percentage for each speaker.",
    },
    "turn_count": {
        "display": "Turn Count",
        "unit": "",
        "category": "Engineered Conversation Behaviour",
        "description": "Total conversational turns.",
    },
    "speaker_change_count": {
        "display": "Speaker Changes",
        "unit": "",
        "category": "Engineered Conversation Behaviour",
        "description": "Number of speaker change transitions.",
    },
    "average_turn_duration": {
        "display": "Average Turn Duration",
        "unit": "s",
        "category": "Engineered Conversation Behaviour",
        "description": "Average duration of a continuous speaking turn.",
    },
    "longest_turn": {
        "display": "Longest Turn",
        "unit": "s",
        "category": "Engineered Conversation Behaviour",
        "description": "The longest continuous speaking turn.",
    },
    "response_latency": {
        "display": "Response Latency",
        "unit": "s",
        "category": "Engineered Conversation Behaviour",
        "description": "Average gap before a speaker replies to another.",
    },
    "conversation_balance": {
        "display": "Conversation Balance",
        "unit": "%",
        "category": "Engineered Conversation Behaviour",
        "description": "Speech balance deviation (closer to 0 is perfectly balanced).",
    },
}
