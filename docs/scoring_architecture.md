# Scoring Architecture — Pillar × Feature × Weight Mapping

> Scores are calculated using specialized normalization models to fit the nature of each feature. We use **Linear**, **Optimal Range (Band-pass)**, and **Categorical** models.

---

## 1. Normalization Models

### A. Linear Model (`_normalize_linear`)
- **Use case**: Metrics where higher is strictly better (e.g. SNR) or lower is strictly better (e.g. Jitter).
- **Invert = False**: $Score = \frac{Value - Low}{High - Low} \times 100$ (clamped to $[0, 100]$)
- **Invert = True**: $Score = (1 - \frac{Value - Low}{High - Low}) \times 100$ (clamped to $[0, 100]$)

### B. Optimal Range Model (`_normalize_optimal_range`)
- **Use case**: Metrics where a middle range is ideal, and going too high or too low is bad (e.g. speech percentage or turn counts).
- **Formula**:
  - Within $[OptStart, OptEnd]$: **100%**
  - Below $OptStart$: decays linearly to 0% at $LowBound$.
  - Above $OptEnd$: decays linearly to 0% at $HighBound$.

### C. Categorical Model (`_normalize_categorical`)
- **Use case**: Discrete countable categories (e.g. Speaker Count).
- **Formula**: Direct key-value lookup mapping.

---

## Pillar 1: Audio Quality Score (25% of Overall)

> Measures: How clear and clean is the recorded audio signal?

| # | Feature | Normalization Type | Range [Low, High] | Weight |
|---|---------|-------------------|-------------------|--------|
| 1 | **Average SNR** (dB) | Linear (higher is better) | [5, 40] dB | **35%** |
| 2 | **Speech Quality Proxy** (0–1) | Linear (higher is better) | [0.3, 1.0] | **30%** |
| 3 | **Noise Floor Level** (dB) | Linear (lower is better) | [−80, −10] dB | **20%** |
| 4 | **Dropout Count** | Linear (lower is better) | [0, 30] | **15%** |

---

## Pillar 2: Recording Reliability Score (15% of Overall)

> Measures: Is the signal transmission technically stable?

| # | Feature | Normalization Type | Range [Low, High] | Weight |
|---|---------|-------------------|-------------------|--------|
| 1 | **Dropout Count** | Linear (lower is better) | [0, 30] | **35%** |
| 2 | **Dropout Duration** (seconds) | Linear (lower is better) | [0, 30] s | **30%** |
| 3 | **Signal Stability** (SNR std dev) | Linear (higher is better) | [0, 100] | **20%** |
| 4 | **Clipping Percentage** (%) | Linear (lower is better) | [0, 5] % | **15%** |

---

## Pillar 3: Voice Stability Score (15% of Overall)

> Measures: Is the speaker's voice steady and natural?

| # | Feature | Normalization Type | Range [Low, High] | Weight |
|---|---------|-------------------|-------------------|--------|
| 1 | **Pitch Stability** (std dev Hz) | Linear (lower is better) | [0, 120] Hz | **25%** |
| 2 | **Loudness Stability** (std dev dB) | Linear (lower is better) | [0, 80] dB | **20%** |
| 3 | **Jitter** (%) | Linear (lower is better) | [0, 50] % | **25%** |
| 4 | **Shimmer** (%) | Linear (lower is better) | [0, 40] % | **20%** |
| 5 | **Speaking Rate Stability** (std dev) | Linear (lower is better) | [0, 5] sps | **10%** |

---

## Pillar 4: Conversation Flow Score (20% of Overall)

> Measures: Is the conversation interactive with smooth turn-taking?

| # | Feature | Normalization Type | Parameter Bounds | Weight |
|---|---------|-------------------|------------------|--------|
| 1 | **Response Latency** (seconds) | Linear (lower is better) | [0, 5] s | **25%** |
| 2 | **Overlap Count** | Linear (lower is better) | [0, 50] | **20%** |
| 3 | **Pause Frequency** (per minute) | **Optimal Range** | Low: 0.0, Opt: **[2.0, 7.0]**, High: 18.0 | **20%** |
| 4 | **Silence Percentage** (%) | Linear (lower is better) | [0, 60] % | **15%** |
| 5 | **Speaker Change Count** | Linear (higher is better) | [0, 50] | **20%** |

---

## Pillar 5: Conversation Balance Score (15% of Overall)

> Measures: Are both speakers participating equally with normal speaker layout?

| # | Feature | Normalization Type | Parameter Bounds | Weight |
|---|---------|-------------------|------------------|--------|
| 1 | **Speaker Balance Diff** (%) | Linear (lower is better) | [0, 100] % | **40%** |
| 2 | **Turn Count** | **Optimal Range** | Low: 2.0, Opt: **[10.0, 30.0]**, High: 60.0 | **30%** |
| 3 | **Speaker Count** | **Categorical** | 2 → **100%**, 3 → **50%**, 4+ → **25%**, 1/0 → **0%** | **30%** |

---

## Pillar 6: Speech Activity Score (10% of Overall)

> Measures: How much of the call is active speech vs dead air?

| # | Feature | Normalization Type | Parameter Bounds | Weight |
|---|---------|-------------------|------------------|--------|
| 1 | **Speech Percentage** (%) | **Optimal Range** | Low: 20.0, Opt: **[50.0, 75.0]**, High: 95.0 | **60%** |
| 2 | **Pause Frequency** (per minute) | **Optimal Range** | Low: 0.0, Opt: **[2.0, 7.0]**, High: 18.0 | **40%** |

---

## Pillar 7: Overall Call Health Score (Composite)

| Pillar | Weight in Overall |
|--------|:-:|
| Audio Quality | **25%** |
| Conversation Flow | **20%** |
| Recording Reliability | **15%** |
| Voice Stability | **15%** |
| Conversation Balance | **15%** |
| Speech Activity | **10%** |

---

## Grading Scale

| Grade | Score Range |
|-------|:----------:|
| **Excellent** | ≥ 90 |
| **Good** | 75 – 89 |
| **Fair** | 60 – 74 |
| **Poor** | < 60 |
