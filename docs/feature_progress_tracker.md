# MMFSL Audio Confidence Scoring — Feature Progress Tracker

Features for the MMFSL per-call confidence score, organized by their respective scoring pillars. This sheet tracks the active implementation of the MMFSL Layer 2 (Engineered) features used in the scoring engine.

**Progress vocabulary:** Not started • In progress • Implemented

| Feature | Pillar | Range | What it measures | Data type | Progress |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Average SNR** | Audio Quality | Whole call | Mean signal-to-noise ratio over the call. | Continuous (dB) | Implemented |
| **Avg Speech Quality** | Audio Quality | Whole call | Quality estimate combining SNR and RMS stability. | Continuous (0–1) | Implemented |
| **Noise Level** | Audio Quality | Silence frames | Average loudness level during silence frames. | Continuous (dB) | Implemented |
| **Dropout Count** | Audio Quality | Whole call | Total count of transmission signal dropouts. | Discrete integer (count) | Implemented |
| **Pitch Deviation** | Voice Stability | Whole call | Standard deviation of vocal pitch (lower is more stable). | Continuous (Hz) | Implemented |
| **Loudness Deviation** | Voice Stability | Whole call | Standard deviation of loudness. | Continuous (dB) | Implemented |
| **Jitter** | Voice Stability | Whole call | Frequency perturbation (vocal cycle-to-cycle frequency variations). | Continuous (%) | Implemented |
| **Shimmer** | Voice Stability | Whole call | Amplitude perturbation (vocal cycle-to-cycle amplitude variations). | Continuous (%) | Implemented |
| **Speaking Rate Deviation** | Voice Stability | Whole call | Standard deviation of speaking rates (lower = rhythmic). | Continuous (sps) | Implemented |
| **Response Latency** | Conversation Flow | Whole call | Average gap before a speaker replies to another. | Continuous (seconds) | Implemented |
| **Overlap Count** | Conversation Flow | Whole call | Total times speakers talk over one another. | Discrete integer (count) | Implemented |
| **Pause Frequency** | Conversation Flow / Speech Activity | Whole call | Pauses per minute of call time. | Continuous (/min) | Implemented |
| **Silence Percentage** | Conversation Flow | Whole call | Percentage of dead air or silent duration during the call. | Continuous (%) | Implemented |
| **Speaker Change Count** | Conversation Flow | Whole call | Number of speaker change transitions. | Discrete integer (count) | Implemented |
| **Conversation Balance** | Conversation Balance | Whole call | Speech balance deviation (closer to 0 is perfectly balanced). | Continuous (%) | Implemented |
| **Turn Count** | Conversation Balance | Whole call | Total conversational back-and-forth turns. | Discrete integer (count) | Implemented |
| **Speaker Count** | Conversation Balance | Whole call | Number of expected voices detected (2 = 100% score). | Discrete integer (count) | Implemented |
| **Speech Percentage** | Speech Activity | Whole call | Percentage of active speech duration during the call. | Continuous (%) | Implemented |
| **Abrupt Cutoff** | Interaction Integrity | End of call | Flag if call ends with active speech and high energy. | Boolean | Implemented |
| **Trailing Silence** | Interaction Integrity | End of call | Seconds of silence at the absolute end of the recording. | Continuous (seconds) | Implemented |
| **Final Window Overlap** | Interaction Integrity | End of call | Disruptive overlapping speech near the end of the call. | Discrete integer (count) | Implemented |

---

## Detailed Scoring Techniques, Weights, and Thresholds

The MMFSL Engine scores features from 0 to 100 and aggregates them into 6 Pillars, which are then combined into a final "Overall Call Health" score.

### Pillar 1: Audio Quality (Weight: 25%)
1. **Average SNR (Weight: 35%)**
   * *Technique:* Linear Normalization
2. **Avg Speech Quality Proxy (Weight: 30%)**
   * *Technique:* Linear Normalization
3. **Noise Level (Weight: 20%)**
   * *Technique:* Inverted Linear Normalization (Lower noise is better)
4. **Dropout Count (Weight: 15%)**
   * *Technique:* Linear Normalization (Inverted)

### Pillar 2: Conversation Flow (Weight: 25%)
1. **Response Latency (Weight: 25%)**
   * *Technique:* Optimal Range Mapping
2. **Overlap Count (Weight: 20%)**
   * *Technique:* Optimal Range Mapping
3. **Pause Frequency (Weight: 20%)**
   * *Technique:* Optimal Range Mapping
4. **Silence Percentage (Weight: 15%)**
   * *Technique:* Optimal Range Mapping
5. **Speaker Change Count (Weight: 20%)**
   * *Technique:* Optimal Range Mapping

### Pillar 3: Interaction Integrity (Weight: 20%)
1. **Abrupt Cutoff (Weight: 35%)**
   * *Technique:* Categorical (True=0, False=100)
2. **Trailing Silence (Weight: 35%)**
   * *Technique:* Linear Normalization (0.0s to 2.0s)
3. **Final Window Overlap (Weight: 30%)**
   * *Technique:* Inverted Linear Normalization (0 to 2 overlaps)

### Pillar 4: Voice Stability (Weight: 10%)
1. **Pitch Deviation (Weight: 45%)**
   * *Technique:* Inverted Linear Normalization
2. **Loudness Deviation (Weight: 35%)**
   * *Technique:* Inverted Linear Normalization
3. **Jitter Pct (Weight: 10%)**
   * *Technique:* Inverted Linear Normalization
4. **Shimmer Pct (Weight: 5%)**
   * *Technique:* Inverted Linear Normalization
5. **Speaking Rate Deviation (Weight: 5%)**
   * *Technique:* Inverted Linear Normalization

### Pillar 5: Conversation Balance (Weight: 10%)
1. **Conversation Balance (Weight: 40%)**
   * *Technique:* Inverted Linear Normalization
2. **Turn Count (Weight: 30%)**
   * *Technique:* Optimal Range Mapping
3. **Speaker Count (Weight: 30%)**
   * *Technique:* Categorical Mapping

### Pillar 6: Speech Activity (Weight: 10%)
1. **Speech Percentage (Weight: 60%)**
   * *Technique:* Optimal Range Mapping
2. **Pause Frequency (Weight: 40%)**
   * *Technique:* Optimal Range Mapping
