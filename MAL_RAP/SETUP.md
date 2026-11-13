# align_song — Setup Guide (Windows, CPU-Only, No NVIDIA GPU)
# =============================================================

## Prerequisites
- **Python 3.12** (Already installed on your system at `C:\Users\Kalaivani\AppData\Local\Programs\Python\Python312`)
- **ffmpeg** in PATH (Already installed)
- **Zero C++ or Rust compilers needed** — all dependencies use pre-compiled Windows binary wheels.

---

## Why You Saw the `sphn` / `maturin` Error Earlier
When you ran `pip install demucs ...`, your terminal was using **Python 3.15** (your default system Python).
Because Python 3.15 does not have pre-built wheels for `sphn` (a Demucs dependency), pip attempted to compile it from source using Rust/Cargo and failed.

Under **Python 3.12**, pre-compiled binary wheels exist for everything — no compiler required!

---

## Step 1 — Use the Python 3.12 Virtual Environment

The virtual environment has already been prepared for you at `D:\Seffin\MAL_RAP\align_venv`:

```powershell
# Activate the venv in PowerShell:
D:\Seffin\MAL_RAP\align_venv\Scripts\Activate.ps1
```

*(If PowerShell blocks activation with ExecutionPolicy, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` then activate again, or simply use `D:\Seffin\MAL_RAP\align_venv\Scripts\python.exe` directly).*

---

## Step 2 — Verify Environment

All required libraries are already installed in `align_venv`:
- `torch 2.15.0+cpu`
- `torchaudio 2.11.1+cpu`
- `demucs 4.1.0`
- `soundfile 0.14.0`
- `uroman 1.3.1.1`
- `numpy 2.5.4`
- Meta MMS Forced Aligner weights (1.18 GB model cached locally)

Verify in 1 line:
```powershell
D:\Seffin\MAL_RAP\align_venv\Scripts\python.exe -c "import torch, torchaudio, demucs, uroman, soundfile; print('All alignment dependencies are ready!')"
```

---

## Step 3 — Run align_song.py

### A. Full Run with Vocal Separation (Demucs)
```powershell
D:\Seffin\MAL_RAP\align_venv\Scripts\python.exe D:\Seffin\MAL_RAP\align_song.py `
  --audio   "D:\Seffin\MAL_RAP\PHI\MP3\PHI_1_PART_1_MAL_RAP.mp3" `
  --lyrics  "D:\Seffin\MAL_RAP\PHI\LYRICS\PHI_1_PART_1_MAL_RAP.txt" `
  --out     "D:\Seffin\MAL_RAP\PHI\TIMING\PHI_1_PART_1" `
  --title   "Philippians 1 Part 1 Malayalam Rap" `
  --lang    mal
```

### B. Fast Test Run Without Demucs (Takes < 15 seconds)
If you want to test alignment on the raw audio right away:
```powershell
D:\Seffin\MAL_RAP\align_venv\Scripts\python.exe D:\Seffin\MAL_RAP\align_song.py `
  --audio   "D:\Seffin\MAL_RAP\PHI\WAV\PHI_1_PART_1_MAL_RAP.wav" `
  --lyrics  "D:\Seffin\MAL_RAP\PHI\LYRICS\PHI_1_PART_1_MAL_RAP.txt" `
  --out     "D:\Seffin\MAL_RAP\PHI\TIMING\PHI_1_PART_1" `
  --no-demucs `
  --lang    mal
```

---

## Output Files Generated

| File | Format | Description |
| :--- | :--- | :--- |
| `PHI_1_PART_1.usfm` | USFM 3 | Timing file with custom `\zt <start> <end>` markers preceding each `\q1` line |
| `PHI_1_PART_1_words.json` | JSON | Word-level start, end, and confidence scores |
| `PHI_1_PART_1_review.txt` | Text | Quality report flagging low confidence (<0.50), overlaps, or zero durations |

---

## Converting to VIDX Timing Format

To convert the generated USFM timing file into VIDX's native SAB format:

```powershell
D:\Seffin\MAL_RAP\align_venv\Scripts\python.exe -c "
from pathlib import Path; import re
usfm = Path(r'D:\Seffin\MAL_RAP\PHI\TIMING\PHI_1_PART_1.usfm').read_text(encoding='utf-8')
out = ['\id PHI', '\c 1', '\level verse']; v = 1; cur = None
for line in usfm.splitlines():
    m = re.match(r'\\zt\s+([\d.]+)\s+([\d.]+)', line)
    if m: cur = (m.group(1), m.group(2))
    elif line.startswith(r'\q1') and cur:
        out.append(f'{float(cur[0]):.3f}\t{float(cur[1]):.3f}\t{v}'); v += 1; cur = None
Path(r'D:\Seffin\MAL_RAP\PHI\TIMING\PHI_1_PART_1_MAL_RAP.txt').write_text('\n'.join(out) + '\n', encoding='utf-8')
print(f'VIDX timing written with {v-1} lines!')
"
```
