"""
generate_all_timings.py â€” Automated Timing Generator for Malayalam Scripture Rap Songs

Aligns all songs using Demucs vocal separation + Meta MMS Malayalam Forced Alignment.
Produces:
  - PHI/TIMING/{name}.usfm           (USFM with custom \\zt timestamps)
  - PHI/TIMING/{name}_words.json     (Word-level timestamps & confidence scores)
  - PHI/TIMING/{name}_review.txt     (Quality review report)
  - PHI/TIMING/{name}_MAL_RAP.txt    (VIDX SAB timing file: start \\t end \\t verse)
  - PHI/USFM/{name}.usfm             (VIDX Scripture USFM: \\v verse lyric)

Usage:
  python generate_all_timings.py                 # Aligns pending tracks (skips already aligned)
  python generate_all_timings.py --force         # Re-aligns all tracks
  python generate_all_timings.py --track PHI_2_PART_1   # Aligns specific track
"""

import argparse
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

# Python executable lookup: root .venv -> local align_venv -> system python
if (PROJECT_ROOT / ".venv" / "Scripts" / "python.exe").exists():
    PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
elif (BASE_DIR / "align_venv" / "Scripts" / "python.exe").exists():
    PYTHON_EXE = BASE_DIR / "align_venv" / "Scripts" / "python.exe"
else:
    PYTHON_EXE = Path(sys.executable)

ALIGN_SCRIPT = BASE_DIR / "align_song.py"

TRACKS = [
    {
        "id": "PHI_1_PART_1",
        "title": "Philippians 1 Part 1 Malayalam Rap",
        "book": "PHI",
        "chapter": 1,
        "audio": BASE_DIR / "PHI" / "MP3" / "PHI_1_PART_1_MAL_RAP.mp3",
        "lyrics": BASE_DIR / "PHI" / "LYRICS" / "PHI_1_PART_1_MAL_RAP.txt",
        "out": BASE_DIR / "PHI" / "TIMING" / "PHI_1_PART_1",
    },
    {
        "id": "PHI_1_PART_2",
        "title": "Philippians 1 Part 2 Malayalam Rap",
        "book": "PHI",
        "chapter": 1,
        "audio": BASE_DIR / "PHI" / "MP3" / "PHI_1_PART_2_MAL_RAP.mp3",
        "lyrics": BASE_DIR / "PHI" / "LYRICS" / "PHI_1_PART_2_MAL_RAP.txt",
        "out": BASE_DIR / "PHI" / "TIMING" / "PHI_1_PART_2",
    },
    {
        "id": "PHI_2_PART_1",
        "title": "Philippians 2 Part 1 Malayalam Rap",
        "book": "PHI",
        "chapter": 2,
        "audio": BASE_DIR / "PHI" / "MP3" / "PHI_2_PART_1_MAL_RAP.mp3",
        "lyrics": BASE_DIR / "PHI" / "LYRICS" / "PHI_2_PART_1_MAL_RAP.txt",
        "out": BASE_DIR / "PHI" / "TIMING" / "PHI_2_PART_1",
    },
    {
        "id": "PHI_2_PART_2",
        "title": "Philippians 2 Part 2 Malayalam Rap",
        "book": "PHI",
        "chapter": 2,
        "audio": BASE_DIR / "PHI" / "MP3" / "PHI_2_PART_2_MAL_RAP.mp3",
        "lyrics": BASE_DIR / "PHI" / "LYRICS" / "PHI_2_PART_2_MAL_RAP.txt",
        "out": BASE_DIR / "PHI" / "TIMING" / "PHI_2_PART_2",
    },
]


def run_track(t: dict, force: bool = False) -> bool:
    sab_file = t["out"].parent / f"{t['id']}_MAL_RAP.txt"
    usfm_file = BASE_DIR / "PHI" / "USFM" / f"{t['id']}.usfm"

    if not force and sab_file.exists() and usfm_file.exists():
        print(f"\n[SKIP] {t['id']} â€” Timing and USFM already exist.")
        print(f"       Timing: {sab_file}")
        print(f"       USFM:   {usfm_file}")
        print("       (Use --force to re-generate)")
        return True

    print(f"\n{'='*70}")
    print(f"Aligning: {t['title']} ({t['id']})")
    print(f"Audio:    {t['audio']}")
    print(f"Lyrics:   {t['lyrics']}")
    print(f"Output:   {t['out']}")
    print(f"{'='*70}\n")

    cmd = [
        str(PYTHON_EXE if PYTHON_EXE.exists() else sys.executable),
        str(ALIGN_SCRIPT),
        "--audio", str(t["audio"]),
        "--lyrics", str(t["lyrics"]),
        "--out", str(t["out"]),
        "--title", t["title"],
        "--book", t["book"],
        "--chapter", str(t["chapter"]),
        "--lang", "mal",
        "--model", "htdemucs"
    ]

    try:
        subprocess.run(cmd, check=True)
        print(f"\n[SUCCESS] Completed {t['id']}!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Failed to align {t['id']}: exit code {e.returncode}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Generate timings for all Malayalam rap songs")
    parser.add_argument("--track", help="Specific track ID to run (e.g. PHI_2_PART_1)")
    parser.add_argument("--force", action="store_true", help="Force re-generation even if files exist")
    args = parser.parse_args()

    tracks_to_run = TRACKS
    if args.track:
        tracks_to_run = [t for t in TRACKS if t["id"].lower() == args.track.lower()]
        if not tracks_to_run:
            print(f"Unknown track '{args.track}'. Available: {[t['id'] for t in TRACKS]}")
            sys.exit(1)

    print(f"Starting Timing Generation Pipeline ({len(tracks_to_run)} tracks queued)...")
    for t in tracks_to_run:
        ok = run_track(t, force=args.force)
        if not ok:
            print(f"\nPipeline halted due to error on {t['id']}.")
            sys.exit(1)

    print("\n" + "="*70)
    print("ALL TIMINGS & USFM FILES GENERATED SUCCESSFULLY!")
    print("="*70)


if __name__ == "__main__":
    main()


