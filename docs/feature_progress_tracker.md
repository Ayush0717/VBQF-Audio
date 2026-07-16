# MMFSL Audio Confidence Scoring — Feature Progress Tracker

Features for the MMFSL per-call confidence score, organized by their respective scoring pillars. This sheet tracks the active implementation of the MMFSL Layer 2 (Engineered) features used in the scoring engine.

**Progress vocabulary:** Not started • In progress • Implemented

| Feature | Pillar | Range | What it measures | Data type | Progress |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Average SNR** | Audio Quality | Whole call | Mean signal-to-noise ratio over the call. | Continuous (dB) | Implemented |
| **Avg Speech Quality** | Audio Quality | Whole call | Quality estimate combining SNR and RMS stability. | Continuous (0–1) | Implemented |
| **Noise Level** | Audio Quality | Silence frames | Average loudness level during silence frames. | Continuous (dB) | Implemented |
| **Dropout Count** | Audio Quality / Recording Reliability | Whole call | Total count of transmission signal dropouts. | Discrete integer (count) | Implemented |
| **Dropout Duration** | Recording Reliability | Whole call | Total length of dropouts in seconds. | Continuous (seconds) | Implemented |
| **Recording Stability** | Recording Reliability | Whole call | Standard deviation of SNR across the call (lower = more stable). | Continuous (std dev) | Implemented |
| **Clipping Percentage** | Recording Reliability | Recording Reliability | Percentage of samples showing amplitude clipping. | Continuous (%) | Implemented |
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

---

## Detailed Scoring Techniques, Weights, and Thresholds

The MMFSL Engine scores features from 0 to 100 and aggregates them into 6 Pillars, which are then combined into a final "Overall Call Health" score.

### Pillar 1: Audio Quality (Weight: 25%)
1. **Average SNR (Weight: 35%)**
   * *Technique:* Piecewise Interpolation
   * *Thresholds:* 0dB ➔ Score 0 | 40dB ➔ Score 30 | 50dB ➔ Score 60 | 65dB ➔ Score 100
2. **Avg Speech Quality Proxy (Weight: 30%)**
   * *Technique:* Linear Normalization
   * *Thresholds:* 0.3 ➔ Score 0 | 1.0 ➔ Score 100
3. **Noise Level (Weight: 20%)**
   * *Technique:* Inverted Linear Normalization (Lower noise is better)
   * *Thresholds:* -10.0dB ➔ Score 0 | -80.0dB ➔ Score 100
4. **Dropout Count (Weight: 15%)**
   * *Technique:* Piecewise Interpolation
   * *Thresholds:* 0 ➔ 100 | 1 ➔ 95 | 2 ➔ 90 | 3 ➔ 75 | 5 ➔ 50 | 10 ➔ 0

### Pillar 2: Recording Reliability (Weight: 15%)
1. **Dropout Count (Weight: 35%)**
   * *Technique:* Same piecewise mapping as above.
2. **Dropout Duration (Weight: 30%)**
   * *Technique:* Inverted Linear Normalization
   * *Thresholds:* 30.0s ➔ Score 0 | 0.0s ➔ Score 100
3. **Recording Stability (Weight: 20%)**
   * *Technique:* Linear Normalization
   * *Thresholds:* 0.0 ➔ Score 0 | 100.0 ➔ Score 100
4. **Clipping Percentage (Weight: 15%)**
   * *Technique:* Strict Threshold
   * *Thresholds:* ≤ 0.0% ➔ Score 100 | > 0.0% ➔ Score 20

### Pillar 3: Voice Stability (Weight: 15%)
*All features in this pillar use Inverted Linear Normalization (Lower deviation/perturbation = Higher stability score).*
1. **Pitch Deviation (Weight: 25%)**
   * *Thresholds:* 90.0Hz ➔ Score 0 | 20.0Hz ➔ Score 100
2. **Loudness Deviation (Weight: 20%)**
   * *Thresholds:* 80.0dB ➔ Score 0 | 0.0dB ➔ Score 100
3. **Jitter Pct (Weight: 25%)**
   * *Thresholds:* 55.0% ➔ Score 0 | 40.0% ➔ Score 100
4. **Shimmer Pct (Weight: 20%)**
   * *Thresholds:* 40.0% ➔ Score 0 | 0.0% ➔ Score 100
5. **Speaking Rate Deviation (Weight: 10%)**
   * *Thresholds:* 5.0 sps ➔ Score 0 | 0.0 sps ➔ Score 100

### Pillar 4: Conversation Flow (Weight: 20%)
1. **Response Latency (Weight: 25%)**
   * *Technique:* Optimal Range Mapping
   * *Thresholds:* Ideal is 0.5s to 2.0s (Score 100). Decays down to Score 0 if latency is 0.0s or > 5.0s.
2. **Overlap Count (Weight: 20%)**
   * *Technique:* Optimal Range Mapping
   * *Thresholds:* Ideal is 15 to 40 overlaps (Score 100). Decays to Score 0 at 0 or 60 overlaps.
3. **Pause Frequency (Weight: 20%)**
   * *Technique:* Piecewise Interpolation
   * *Thresholds:* 2/min ➔ Score 100 | 5/min ➔ Score 90 | 10/min ➔ 60 | 30/min ➔ 0
4. **Silence Percentage (Weight: 15%)**
   * *Technique:* Optimal Range Mapping
   * *Thresholds:* Ideal is 10% to 30% silence (Score 100). Decays to Score 0 at 0% and 60% silence.
5. **Speaker Change Count (Weight: 20%)**
   * *Technique:* Optimal Range Mapping
   * *Thresholds:* Ideal is 15 to 40 changes (Score 100). Decays to Score 0 at 5 or 70 changes.

### Pillar 5: Conversation Balance (Weight: 15%)
1. **Conversation Balance (Weight: 40%)**
   * *Technique:* Inverted Linear Normalization (0 deviation from 50/50 is perfect).
   * *Thresholds:* 100% ➔ Score 0 | 0.0% ➔ Score 100
2. **Turn Count (Weight: 30%)**
   * *Technique:* Optimal Range Mapping
   * *Thresholds:* Ideal is 10 to 30 turns (Score 100). Decays to Score 0 at 2 turns and 60 turns.
3. **Speaker Count (Weight: 30%)**
   * *Technique:* Categorical Mapping
   * *Thresholds:* 2 ➔ Score 100 | 3 ➔ Score 50 | 4 ➔ Score 25 | 1 or 0 ➔ Score 0

### Pillar 6: Speech Activity (Weight: 10%)
1. **Speech Percentage (Weight: 60%)**
   * *Technique:* Optimal Range Mapping
   * *Thresholds:* Ideal is 85% to 95% active speech (Score 100). Decays to Score 0 at 70% and 100%.
2. **Pause Frequency (Weight: 40%)**
   * *Technique:* Piecewise Interpolation (Same thresholds as in Pillar 4).
