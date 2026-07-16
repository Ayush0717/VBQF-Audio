# Voice Intelligence Platform (VIP)

The Voice Intelligence Platform is a state-of-the-art audio analysis and diarization pipeline. It ingests raw call recordings (human or AI voicebots) and automatically evaluates the conversational dynamics, acoustic quality, and behavioral health of the call across a 6-Pillar framework.

By fully automating QA, VIP allows organizations to monitor 100% of their call volume, detect hardware dropouts, track voicebot latency, and pinpoint critical communication breakdowns exactly when they happen.

---

## 🚀 Setup & Installation

### Option 1: Conda Environment (Recommended)
This ensures that all complex audio-processing C-libraries (like `libsndfile`) are installed correctly alongside Python.

```bash
# Create the environment from the config file
conda env create -f environment.yml

# Activate the environment
conda activate audio-confidence
```

### Option 2: Pure Python Virtual Environment
If you cannot use Conda, you can install the dependencies via `pip`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 🔑 Critical Requirement: Hugging Face Token & Agreements

This platform utilizes Pyannote 3.1 for state-of-the-art Speaker Diarization. You **must** do two things before running the pipeline on a new machine:

1. **Accept the User Agreements:** Go to Hugging Face and manually accept the conditions for these two models:
   - [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
   - [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
   *(If you skip this, the script will crash with a `403 Forbidden` error!)*

2. **Set your Token:**
   Provide your Hugging Face authentication token in your terminal:

**Mac/Linux:**
```bash
export HF_TOKEN="your_huggingface_token_here"
```

**Windows (PowerShell):**
```powershell
$env:HF_TOKEN="your_huggingface_token_here"
```

---

## 🛠️ Note on System Dependencies (Non-Conda Users)
If you install via `pip` instead of `conda`, you **must** have `libsndfile` and `ffmpeg` installed on your system for audio decoding to work.
- **Mac:** `brew install ffmpeg libsndfile`
- **Ubuntu/Debian:** `sudo apt-get install ffmpeg libsndfile1`

---

## 🧠 1. Running the AI Backend (Data Extraction)

To process a new call recording, place your `.wav` file into `data/audio/` and run the core pipeline:

```bash
python app.py data/audio/your_call.wav
```

### Batch Processing
To process **all** `.wav` files in your `data/audio/` directory automatically, use the batch script:
```bash
python batch_process_audio.py
```

### Optional Arguments (for `app.py`):
- `--num_speakers 2`: Forces the diarization engine to look for exactly 2 speakers (useful for noisy calls where auto-detect struggles).
- `--verbose`: Prints real-time extraction logs to the console.

**Output:** The pipeline will extract all features, score the call, and save a fully structured JSON file to `data/outputs/your_call_features.json`.

---

## 📊 2. Launching the Web App Dashboard

The dashboard is a static, blazingly fast HTML/JS interface that visualizes the JSON outputs. It will **automatically** detect and load any `*_features.json` files found in your `data/outputs/` directory!

1. **Start the local server:** (Run this from the project root)
   ```bash
   python -m http.server 8000
   ```
2. **View the Dashboard:** Open Google Chrome and navigate to [http://localhost:8000/webapp/](http://localhost:8000/webapp/)
3. **Select your file:** Use the dropdown in the top right of the dashboard to switch between all processed recordings.

---

## 🎯 The 6 Scoring Pillars Explained

The AI evaluates every call based on 6 critical dimensions:

1. **Audio Quality:** Measures physical acoustics (Signal-to-Noise Ratio, clipping). Detects if the call environment was too noisy or if the microphone hardware failed.
2. **Voice Stability:** Analyzes pitch fluctuations and RMS energy. Detects high emotional agitation, stress, shouting, or robotic synthesis errors in bots.
3. **Conversation Flow:** Tracks the rhythm of the interaction. Detects awkward silences, bot response latency, and severe overlaps/interruptions.
4. **Conversation Balance:** Evaluates the conversational dominance. Flags calls where the agent/bot talked for 90% of the time (monologuing) instead of listening.
5. **Speech Activity:** Measures the ratio of active speech to dead air. Detects calls that were mostly just hold music or silence.
6. **Collection Confidence:** A specialized rules engine that checks the structural integrity of the call. Flags abrupt hang-ups and sudden network drops.

---

## 📁 Directory Structure & File Locations

To ensure a smooth transition when moving this project to a new system or server, please adhere to the following directory structure:

- **`data/audio/`** 
  - **Purpose:** Place all your raw `.wav` or `.mp3` call recordings here before processing. 
  - **Note:** The batch processing script (`batch_process_audio.py`) strictly looks in this folder.
- **`data/outputs/`** 
  - **Purpose:** The AI pipeline automatically saves all generated `*_features.json` files here. 
  - **Note:** The Web App Dashboard dynamically reads from this folder. Do not rename or move this folder, or the dashboard will appear empty.
- **`exports/`**
  - **Purpose:** Automatically generated master CSV files (`batch_analysis_report_X.csv`) are saved here after running the batch script. These contain the 54-column aggregated data of all processed calls.
- **`webapp/`** 
  - **Purpose:** Contains the HTML, CSS, and JS files for the dashboard. You can also generate the master CSV directly from the dashboard using the "Export Batch Summary" button!
- **`config.py`**
  - **Purpose:** The master configuration file where you can tune the scoring weights, Usability Gate thresholds, and diarization settings.
