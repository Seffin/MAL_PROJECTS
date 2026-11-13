# Malayalam Scripture Alignment Projects (MAL_RAP & MAL_SLOW)

This repository contains the audio-lyric forced alignment pipelines and video generation configs for Malayalam Scripture songs:
- **`MAL_RAP`**: Malayalam Rap Scripture songs (Philippians Chapters 1 & 2).
- **`MAL_SLOW`**: Malayalam Slow Scripture songs (Philippians Chapters 1 & 2).

---

## Repository Structure

```
MAL_PROJECTS/
├── .gitignore                     # Ignores large media (*.mp4, *.wav, *.mp3), venvs, caches
├── requirements.txt               # Unified project dependencies
├── setup_venv.ps1                 # Automated 1-click venv setup script
├── README.md                      # Documentation & instructions
│
├── MAL_RAP/                       # Rap Scripture project
│   ├── align_song.py              # Core forced alignment engine (Demucs + Meta MMS Aligner)
│   ├── generate_all_timings.py    # Batch alignment pipeline for Rap tracks
│   ├── generate_timings.ps1       # PowerShell wrapper to run batch alignment
│   ├── phi_*.yaml                 # VIDX video rendering configurations
│   └── PHI/                       # Data directories:
│       ├── LYRICS/                # Text lyrics (tracked in Git)
│       ├── MP3/                   # Audio files (*.mp3, local only)
│       ├── TIMING/                # Generated USFM \zt, JSON & review reports (tracked in Git)
│       ├── USFM/                  # Generated Scripture USFM \v (tracked in Git)
│       ├── WAV/                   # 16kHz WAV files (local only)
│       └── MP4/                   # Rendered video outputs (local only)
│
└── MAL_SLOW/                      # Slow Scripture songs project
    ├── generate_all_timings_slow.py # Batch alignment pipeline for Slow tracks
    ├── generate_timings.ps1       # PowerShell wrapper to run batch alignment
    ├── phil_slow_*.yaml           # VIDX video rendering configurations
    ├── LYRICS/                    # Text lyrics (tracked in Git)
    ├── MP3/                       # Audio files (*.mp3, local only)
    ├── TIMING/                    # Generated USFM \zt, JSON & review reports (tracked in Git)
    ├── USFM/                      # Generated Scripture USFM \v (tracked in Git)
    └── MP4/                       # Rendered video outputs (local only)
```

---

## Dependencies & Prerequisites

### 1. Python 3.12 (64-bit) — **Required**
> [!IMPORTANT]
> Use **Python 3.12**. Do **not** use Python 3.13 or 3.15 for this project. Demucs depends on `sphn` and `soundfile` which have pre-compiled Windows binary wheels for Python 3.12. Under Python 3.13+, pip attempts to compile `sphn` from source using Rust/Cargo and fails.

### 2. FFmpeg — **Required**
FFmpeg is required by Demucs and `align_song.py` for audio decoding and resampling.
- Verify: `ffmpeg -version`
- If not installed, install via PowerShell:
  ```powershell
  winget install Gyan.FFmpeg
  ```
  *(Restart your terminal after installation so `ffmpeg` is available in PATH).*

### 3. Python Libraries
- **`torch` & `torchaudio` (CPU-only)**: Meta wav2vec2 CTC acoustic model.
- **`demucs`**: Meta AI vocal separation (`htdemucs`).
- **`soundfile`**: High-performance audio I/O via libsndfile.
- **`uroman`**: Unicode Malayalam transliteration for Meta MMS Forced Aligner.
- **`numpy`**: Fast matrix and audio waveform operations.
- **`PyYAML`**: YAML parser for VIDX configurations.

---

## How to Set Up the Virtual Environment (venv)

### Option A: One-Click Setup Script (Recommended)
Run the included PowerShell setup script:
```powershell
powershell -ExecutionPolicy Bypass -File .\setup_venv.ps1
```

### Option B: Manual Setup Steps
If you prefer doing it manually in PowerShell:

```powershell
# 1. Navigate to the project root
cd D:\Seffin\MAL_PROJECTS

# 2. Create the virtual environment using Python 3.12
C:\Users\Kalaivani\AppData\Local\Programs\Python\Python312\python.exe -m venv .venv

# 3. Activate the environment
.\.venv\Scripts\Activate.ps1

# 4. Upgrade pip
python -m pip install --upgrade pip

# 5. Install PyTorch CPU wheels (Must specify the CPU wheel index!)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# 6. Install the remaining requirements
pip install -r requirements.txt

# 7. Verify all dependencies
python -c "import torch, torchaudio, demucs, uroman, soundfile, yaml; print('All dependencies ready!')"
```

---

## How to Run Alignment

### Running Malayalam Rap Alignment (`MAL_RAP`)
```powershell
cd D:\Seffin\MAL_PROJECTS\MAL_RAP

# Align all pending tracks:
.\generate_timings.ps1

# Re-align all tracks from scratch:
.\generate_timings.ps1 -force

# Align a specific track:
.\generate_timings.ps1 -track PHI_1_PART_1
```

### Running Malayalam Slow Song Alignment (`MAL_SLOW`)
```powershell
cd D:\Seffin\MAL_PROJECTS\MAL_SLOW

# Align all pending tracks:
.\generate_timings.ps1

# Re-align all tracks from scratch:
.\generate_timings.ps1 -force

# Align a specific track:
.\generate_timings.ps1 -track PHIL_CH_1_PART_1
```

---

## Git & Version Control Notice

- **Tracked in Git**:
  - Python scripts (`align_song.py`, `generate_*.py`)
  - PowerShell scripts (`generate_timings.ps1`, `setup_venv.ps1`)
  - VIDX YAML project configurations (`*.yaml`)
  - Malayalam lyrics text files (`LYRICS/*.txt`)
  - Generated USFM timings (`TIMING/*.usfm`), JSON word timings, and review reports
  - Generated Scripture USFM files (`USFM/*.usfm`)
  - Subtitle styling files (`*.ass`)
  - Documentation and requirements

- **Ignored via `.gitignore`**:
  - Virtual environments (`.venv/`, `align_venv/`, `venv/`)
  - Large generated video renders (`*.mp4`)
  - Large uncompressed audio (`*.wav`) and source audio (`*.mp3`)
  - Python caches (`__pycache__/`, `*.pyc`)
  - Scaled video render caches (`.cache/`, `YouTube_Upload_Package/`)
