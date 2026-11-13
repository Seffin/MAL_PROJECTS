#!/usr/bin/env python3
"""
align_song.py — Malayalam Song Lyric Forced Aligner
====================================================
Generates a USFM timing file + word-level JSON for a Malayalam song.

Pipeline:
  1. Vocal separation via Demucs (htdemucs, --two-stems=vocals)
  2. Forced alignment via Meta MMS wav2vec2 CTC for Malayalam ('mal')
     using the ctc-forced-aligner library (CPU-only, float32)
  3. Quality checks + review report
  4. USFM + JSON output

Usage:
  python align_song.py --audio song.mp3 --lyrics lyrics.txt --out song_name

  --audio    Path to input MP3 or WAV file
  --lyrics   Path to UTF-8 text file with one lyric line per row
  --out      Output name prefix (no extension); creates:
               <out>.usfm           — USFM timing file
               <out>_words.json     — word-level JSON
               <out>_review.txt     — flagged lines for review
  --title    Song title for USFM header (optional)
  --lang     MMS language code (default: mal for Malayalam)
  --model    Demucs model name (default: htdemucs)
  --no-demucs   Skip vocal separation (use raw audio directly)
  --section-split  Split alignment on blank-line section boundaries
  --cache-dir  Directory for cached models (default: ~/.align_song_cache)
  --verbose    Extra debug logging

Assumptions:
  - Lyrics are written out fully (repeated choruses appear multiple times)
  - Section labels like [Chorus], [Verse 1] are kept as-is in output but
    not aligned (they are treated as metadata lines)
  - float32 on CPU; no CUDA dependency
  - Demucs downloads htdemucs model on first run (~400 MB, cached)
  - MMS wav2vec2-base-960h-lv60 model downloaded on first run (~300 MB, cached)
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger("align_song")


# ─────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────

@dataclass
class LyricLine:
    idx: int                  # 1-based original line index
    text: str                 # original Malayalam text
    is_label: bool = False    # True if section label like [Chorus]
    start: float = 0.0
    end: float = 0.0
    words: list = field(default_factory=list)
    avg_confidence: float = 1.0
    flags: list = field(default_factory=list)

@dataclass
class WordTiming:
    word: str
    start: float
    end: float
    confidence: float


# ─────────────────────────────────────────────
# Audio helpers
# ─────────────────────────────────────────────

def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def audio_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True, encoding="utf-8"
    )
    return float(result.stdout.strip())


def convert_to_wav_16k(src: Path, dst: Path) -> None:
    """Convert any ffmpeg-readable audio to 16kHz mono float32 WAV."""
    subprocess.run([
        "ffmpeg", "-y", "-v", "warning",
        "-i", str(src),
        "-ac", "1", "-ar", "16000",
        "-sample_fmt", "s16",
        str(dst)
    ], check=True)


def load_audio_numpy(path: Path):
    """Load WAV as float32 numpy array at 16kHz."""
    import numpy as np
    import wave

    with wave.open(str(path), "rb") as wf:
        assert wf.getsampwidth() == 2, "Expected 16-bit PCM"
        assert wf.getframerate() == 16000, "Expected 16kHz"
        raw = wf.readframes(wf.getnframes())
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return audio


# ─────────────────────────────────────────────
# Step 1: Vocal Separation (Demucs)
# ─────────────────────────────────────────────

def separate_vocals(
    audio_path: Path,
    out_dir: Path,
    model: str = "htdemucs",
    cache_dir: Optional[Path] = None,
) -> Path:
    """Run Demucs --two-stems=vocals, return path to the isolated vocals WAV."""
    try:
        from demucs.separate import main as demucs_main
    except ImportError:
        log.error("Demucs not installed. Run: pip install demucs")
        sys.exit(1)

    log.info("Running Demucs vocal separation (model=%s)…", model)
    env = dict(os.environ)
    if cache_dir:
        env["TORCH_HOME"] = str(cache_dir / "torch")

    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "demucs.separate",
        "--two-stems", "vocals",
        "-n", model,
        "--out", str(out_dir),
        "--device", "cpu",
        str(audio_path),
    ]
    log.info("Demucs command: %s", " ".join(cmd))
    t0 = time.time()
    subprocess.run(cmd, check=True, env=env)
    elapsed = time.time() - t0
    log.info("Demucs finished in %.1fs", elapsed)

    # Demucs writes to: <out_dir>/<model>/<stem>/<filename>.wav
    stem_name = audio_path.stem
    vocals_path = out_dir / model / stem_name / "vocals.wav"
    if not vocals_path.exists():
        log.error("Expected vocals file not found: %s", vocals_path)
        log.error("Contents of %s:", out_dir)
        for p in out_dir.rglob("*"):
            log.error("  %s", p)
        sys.exit(1)

    log.info("Vocals isolated: %s", vocals_path)
    return vocals_path


# ─────────────────────────────────────────────
# Step 2: Lyrics parsing
# ─────────────────────────────────────────────

LABEL_PATTERN = re.compile(r"^\s*[\[\(].*[\]\)]\s*$")


def parse_lyrics(lyrics_path: Path) -> list[LyricLine]:
    """Parse lyrics file; return list of LyricLine (labels + text lines)."""
    lines = lyrics_path.read_text(encoding="utf-8").splitlines()
    result = []
    idx = 1
    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("```"):
            continue  # skip blank lines and markdown backticks
        is_label = bool(LABEL_PATTERN.match(stripped))
        result.append(LyricLine(idx=idx, text=stripped, is_label=is_label))
        idx += 1
    lyric_lines = [l for l in result if not l.is_label]
    log.info("Parsed lyrics: %d total lines (%d labels, %d alignable)",
             len(result), sum(1 for l in result if l.is_label), len(lyric_lines))
    return result


# ─────────────────────────────────────────────
# Step 3: Forced Alignment (MMS CTC via torchaudio)
# ─────────────────────────────────────────────

def ensure_torch():
    try:
        import torch
        import torchaudio
        return torch, torchaudio
    except ImportError:
        log.error(
            "PyTorch / torchaudio not installed.\n"
            "Run inside align_venv:\n"
            "  pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu"
        )
        sys.exit(1)


def align_section(
    vocal_wav_16k: Path,
    lyric_lines: list[LyricLine],
    lang: str,
    cache_dir: Path,
    start_offset: float = 0.0,
) -> list[LyricLine]:
    """
    Run MMS CTC forced alignment on a section of vocals.
    Uses PyTorch's native torchaudio.pipelines.MMS_FA:
      - Uses Meta's official MMS Forced Aligner weights
      - Uses PyTorch's built-in C++ Viterbi engine (zero MSVC compiler required)
      - Romanizes Malayalam to 29-letter CTC alphabet via uroman
    Returns lyric_lines with .start, .end, .words, .avg_confidence filled.
    """
    torch, torchaudio = ensure_torch()
    import torchaudio.pipelines as P
    import soundfile as sf
    import uroman

    align_lines = [l for l in lyric_lines if not l.is_label]
    if not align_lines:
        log.warning("No alignable lines in section.")
        return lyric_lines

    log.info("Loading Meta MMS forced aligner (torchaudio.pipelines.MMS_FA)…")
    t0 = time.time()
    bundle = P.MMS_FA
    model = bundle.get_model()
    tokenizer = bundle.get_tokenizer()
    aligner = bundle.get_aligner()
    u = uroman.Uroman()
    log.info("Model loaded in %.1fs", time.time() - t0)

    # Load audio via soundfile
    data, sr = sf.read(str(vocal_wav_16k))
    if data.ndim > 1:
        data = data.mean(axis=1)  # downmix to mono
    waveform = torch.from_numpy(data.astype("float32")).unsqueeze(0)

    # Collect words across all lines, keeping track of line boundaries
    line_word_counts = []
    raw_words = []
    for line in align_lines:
        w_list = line.text.split()
        line_word_counts.append(len(w_list))
        raw_words.extend(w_list)

    # Romanize and filter to MMS dictionary characters
    clean_words, valid_word_indices = [], []
    for idx, w in enumerate(raw_words):
        r = u.romanize_string(w, lcode=lang).lower()
        clean = "".join([c for c in r if c in tokenizer.dictionary])
        if clean:
            clean_words.append(clean)
            valid_word_indices.append(idx)

    if not clean_words:
        log.warning("No alignable words found after romanization.")
        return lyric_lines

    tokens = tokenizer(clean_words)

    log.info("Computing acoustic emissions for %.2fs audio…", len(data) / sr)
    t0 = time.time()
    with torch.inference_mode():
        emission, _ = model(waveform)
    log.info("Emissions generated in %.1fs", time.time() - t0)

    log.info("Running CTC Viterbi trellis alignment…")
    t0 = time.time()
    spans = aligner(emission[0], tokens)
    log.info("CTC alignment finished in %.1fs", time.time() - t0)

    ratio = (waveform.size(1) / bundle.sample_rate) / emission.size(1)

    # Build map from raw word index -> WordTiming
    word_timing_map = {}
    for orig_idx, span in zip(valid_word_indices, spans):
        if span:
            w_start = round(start_offset + float(span[0].start * ratio), 2)
            w_end   = round(start_offset + float(span[-1].end * ratio), 2)
            conf    = round(sum(s.score for s in span) / len(span), 4)
            word_timing_map[orig_idx] = WordTiming(
                word=raw_words[orig_idx],
                start=w_start,
                end=w_end,
                confidence=conf,
            )

    # Assign WordTimings back to each line
    global_word_idx = 0
    for line, count in zip(align_lines, line_word_counts):
        line_timings = []
        for _ in range(count):
            if global_word_idx in word_timing_map:
                line_timings.append(word_timing_map[global_word_idx])
            global_word_idx += 1

        if not line_timings:
            line.flags.append("NO_WORDS_ALIGNED")
            continue

        line.words = line_timings
        line.start = line_timings[0].start
        line.end   = line_timings[-1].end
        confs      = [w.confidence for w in line_timings]
        line.avg_confidence = round(sum(confs) / len(confs), 4)

    return lyric_lines


# ─────────────────────────────────────────────
# Step 4: Section splitting for long gaps
# ─────────────────────────────────────────────

def split_lyrics_on_labels(all_lines: list[LyricLine]) -> list[list[LyricLine]]:
    """Split all_lines into sections separated by label markers."""
    sections = []
    current = []
    for line in all_lines:
        if line.is_label and current:
            sections.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append(current)
    return sections


def detect_vocal_sections(vocal_wav: Path, min_silence_sec: float = 3.0) -> list[tuple[float, float]]:
    """
    Detect start/end times of vocal activity using RMS energy.
    Returns list of (start, end) pairs for active sections.
    min_silence_sec: minimum gap (seconds) to consider a section boundary.
    """
    import numpy as np

    log.info("Detecting vocal sections in %s…", vocal_wav.name)
    audio = load_audio_numpy(vocal_wav)
    sr = 16000
    frame = int(0.05 * sr)  # 50ms frames
    step = frame

    rms_vals = []
    for i in range(0, len(audio) - frame, step):
        rms_vals.append(np.sqrt(np.mean(audio[i:i+frame]**2)))
    rms_arr = np.array(rms_vals)

    # Dynamic threshold: 15% of 95th percentile
    threshold = np.percentile(rms_arr, 95) * 0.15
    active = rms_arr > threshold

    sections = []
    in_section = False
    sec_start = 0.0
    min_silence_frames = int(min_silence_sec / 0.05)
    silence_count = 0

    for idx, a in enumerate(active):
        t = idx * 0.05
        if a:
            if not in_section:
                sec_start = t
                in_section = True
            silence_count = 0
        else:
            if in_section:
                silence_count += 1
                if silence_count >= min_silence_frames:
                    sec_end = t - min_silence_sec + 0.05
                    sections.append((sec_start, sec_end))
                    in_section = False
                    silence_count = 0

    if in_section:
        sections.append((sec_start, len(audio) / sr))

    log.info("Found %d vocal sections with min_silence=%.1fs", len(sections), min_silence_sec)
    for i, (s, e) in enumerate(sections):
        log.info("  Section %d: %.2fs – %.2fs (%.1fs)", i+1, s, e, e-s)

    return sections


def slice_audio(src_wav: Path, start: float, end: float, dst: Path) -> None:
    """Extract a time slice from a WAV file."""
    subprocess.run([
        "ffmpeg", "-y", "-v", "warning",
        "-ss", str(start), "-to", str(end),
        "-i", str(src_wav),
        str(dst)
    ], check=True)


# ─────────────────────────────────────────────
# Step 5: Quality checks
# ─────────────────────────────────────────────

CONF_THRESHOLD = 0.5  # lines below this avg confidence get flagged


def quality_check(lyric_lines: list[LyricLine], audio_duration_sec: float) -> int:
    """Run quality checks on aligned lines. Returns number of flagged lines."""
    aligned = [l for l in lyric_lines if not l.is_label]
    flagged = 0

    for i, line in enumerate(aligned):
        if line.is_label:
            continue

        dur = line.end - line.start
        if dur <= 0:
            line.flags.append(f"ZERO_OR_NEG_DURATION ({dur:.2f}s)")
            flagged += 1

        if line.avg_confidence < CONF_THRESHOLD:
            line.flags.append(f"LOW_CONFIDENCE ({line.avg_confidence:.3f})")
            flagged += 1

        if line.end > audio_duration_sec + 0.5:
            line.flags.append(f"PAST_AUDIO_END ({line.end:.2f}s > {audio_duration_sec:.2f}s)")
            flagged += 1

        if i > 0 and not aligned[i-1].is_label:
            prev = aligned[i-1]
            if line.start < prev.end - 0.05:
                line.flags.append(
                    f"OVERLAP_WITH_LINE_{prev.idx} (prev_end={prev.end:.2f} this_start={line.start:.2f})"
                )
                flagged += 1

    return flagged


# ─────────────────────────────────────────────
# Step 6: Output writers
# ─────────────────────────────────────────────

USFM_COMMENT = """\
\\rem TIMING FILE — generated by align_song.py
\\rem Custom marker \\zt: \\zt <start_seconds> <end_seconds>
\\rem  - Placed on the line immediately BEFORE the \\q1 marker it annotates
\\rem  - Times are in seconds, 2 decimal places
\\rem  - Example: \\zt 5.20 8.40
\\rem  - Section labels (\\ms) carry no timing and are metadata only
\\rem Parse: read each \\zt to get the window; next \\q1 line is the lyric text
"""


def write_usfm(
    lyric_lines: list[LyricLine],
    out_path: Path,
    title: str = "",
    lang: str = "mal",
) -> None:
    lines_out = [
        f"\\id SONG {title}",
        f"\\h {title}",
        f"\\mt {title}",
        "\\rem Language: " + lang,
        "",
    ] + USFM_COMMENT.splitlines() + [""]

    for line in lyric_lines:
        if line.is_label:
            lines_out.append(f"\\ms {line.text}")
        else:
            lines_out.append(f"\\zt {line.start:.2f} {line.end:.2f}")
            lines_out.append(f"\\q1 {line.text}")

    out_path.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    log.info("USFM written: %s", out_path)


def write_vidx_timing(lyric_lines: list[LyricLine], out_path: Path, book: str = "PHI", chapter: int = 1) -> None:
    lines = [
        f"\\id {book}",
        f"\\c {chapter}",
        "\\level verse"
    ]
    verse_num = 1
    for line in lyric_lines:
        if line.is_label:
            continue
        lines.append(f"{line.start:.3f}\t{line.end:.3f}\t{verse_num}")
        verse_num += 1
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("VIDX SAB timing written: %s", out_path)


def write_vidx_usfm(lyric_lines: list[LyricLine], out_path: Path, book: str = "PHI", chapter: int = 1, title: str = "") -> None:
    lines = [
        f"\\id {book} {title}",
        f"\\h {title}",
        f"\\toc1 {title}",
        f"\\c {chapter}",
        ""
    ]
    verse_num = 1
    for line in lyric_lines:
        if line.is_label:
            lines.append("")
            lines.append(f"\\s {line.text}")
        else:
            lines.append(f"\\v {verse_num} {line.text}")
            verse_num += 1
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("VIDX USFM written: %s", out_path)


def write_json(lyric_lines: list[LyricLine], out_path: Path) -> None:
    output = []
    for line in lyric_lines:
        if line.is_label:
            continue
        output.append({
            "line_idx": line.idx,
            "text": line.text,
            "start": line.start,
            "end": line.end,
            "avg_confidence": line.avg_confidence,
            "flags": line.flags,
            "words": [
                {
                    "word": w.word,
                    "start": w.start,
                    "end": w.end,
                    "confidence": w.confidence,
                }
                for w in line.words
            ],
        })
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Word-level JSON written: %s", out_path)


def write_review(lyric_lines: list[LyricLine], out_path: Path, audio_dur: float) -> None:
    flagged = [l for l in lyric_lines if l.flags]
    if not flagged:
        out_path.write_text("No flagged lines. All checks passed.\n", encoding="utf-8")
        log.info("All quality checks passed.")
        return

    rows = ["# REVIEW REPORT — align_song.py", f"# Audio duration: {audio_dur:.2f}s", ""]
    for line in flagged:
        rows.append(f"Line {line.idx:3d}: {line.text[:60]}")
        rows.append(f"         start={line.start:.2f}s  end={line.end:.2f}s  conf={line.avg_confidence:.3f}")
        for flag in line.flags:
            rows.append(f"         ⚠  {flag}")
        rows.append("")
    out_path.write_text("\n".join(rows), encoding="utf-8")
    log.warning("Review file written: %s (%d flagged lines)", out_path, len(flagged))


def print_summary(lyric_lines: list[LyricLine], n_flagged: int, elapsed: float) -> None:
    aligned = [l for l in lyric_lines if not l.is_label and l.end > 0]
    labels = [l for l in lyric_lines if l.is_label]

    print("\n" + "═" * 60)
    print("  ALIGNMENT SUMMARY")
    print("═" * 60)
    print(f"  Total lines parsed  : {len(lyric_lines)}")
    print(f"  Section labels      : {len(labels)}")
    print(f"  Lines aligned       : {len(aligned)}")
    print(f"  Lines flagged       : {n_flagged}")

    if aligned:
        avg_conf = sum(l.avg_confidence for l in aligned) / len(aligned)
        print(f"  Avg confidence      : {avg_conf:.3f}")
        if aligned[-1].end > 0:
            print(f"  Coverage            : {aligned[0].start:.2f}s → {aligned[-1].end:.2f}s")

    print(f"  Total elapsed       : {elapsed:.1f}s")
    print("═" * 60 + "\n")


# ─────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(
        description="Malayalam song lyric forced aligner → USFM + JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Example:
              python align_song.py \\
                --audio D:/Seffin/MAL_RAP/PHI/MP3/PHI_1_PART_1_MAL_RAP.mp3 \\
                --lyrics D:/Seffin/MAL_RAP/PHI/LYRICS/PHI_1_PART_1_MAL_RAP.txt \\
                --out D:/Seffin/MAL_RAP/PHI/TIMING/PHI_1_PART_1 \\
                --title "Philippians 1 Part 1"
        """)
    )
    ap.add_argument("--audio",   required=True,  help="Input audio file (MP3 or WAV)")
    ap.add_argument("--lyrics",  required=True,  help="Input lyrics text file (UTF-8)")
    ap.add_argument("--out",     required=True,  help="Output path prefix (no extension)")
    ap.add_argument("--title",   default="",     help="Song title for USFM header")
    ap.add_argument("--book",    default="PHI",  help="Bible book code")
    ap.add_argument("--chapter", type=int, default=1, help="Bible chapter number")
    ap.add_argument("--lang",    default="mal",  help="MMS language code (default: mal)")
    ap.add_argument("--model",   default="htdemucs", help="Demucs model (default: htdemucs)")
    ap.add_argument("--no-demucs",   action="store_true", help="Skip vocal separation")
    ap.add_argument("--section-split", action="store_true",
                    help="Split alignment by section labels (helps with long instrumentals)")
    ap.add_argument("--cache-dir", default=None,
                    help="Cache dir for models (default: ~/.align_song_cache)")
    ap.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = ap.parse_args()

    # Logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )

    t_start = time.time()

    # Validate inputs
    audio_path = Path(args.audio)
    lyrics_path = Path(args.lyrics)
    out_prefix = Path(args.out)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    if not audio_path.exists():
        log.error("Audio file not found: %s", audio_path)
        sys.exit(1)
    if not lyrics_path.exists():
        log.error("Lyrics file not found: %s", lyrics_path)
        sys.exit(1)
    if not ffmpeg_available():
        log.error("ffmpeg not found in PATH. Install it and retry.")
        sys.exit(1)

    cache_dir = Path(args.cache_dir) if args.cache_dir else Path.home() / ".align_song_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    demucs_out_dir = cache_dir / "demucs_out"
    tmp_dir = Path(tempfile.mkdtemp(prefix="align_song_"))
    log.debug("Temp dir: %s", tmp_dir)

    try:
        # ── Step 1: Probe audio duration
        total_dur = audio_duration(audio_path)
        log.info("Audio duration: %.2fs (%.1f min)", total_dur, total_dur / 60)

        # ── Step 2: Vocal separation
        if args.no_demucs:
            log.info("Skipping vocal separation (--no-demucs)")
            vocal_source = audio_path
        else:
            vocal_wav_native = separate_vocals(audio_path, demucs_out_dir, model=args.model,
                                               cache_dir=cache_dir)
            vocal_source = vocal_wav_native

        # ── Step 3: Convert vocals to 16kHz mono WAV
        vocal_16k = tmp_dir / "vocals_16k.wav"
        log.info("Converting vocals to 16kHz mono WAV…")
        convert_to_wav_16k(vocal_source, vocal_16k)

        # ── Step 4: Parse lyrics
        lyric_lines = parse_lyrics(lyrics_path)

        # ── Step 5: Align
        if args.section_split:
            log.info("Section-split alignment mode enabled.")
            vocal_sections = detect_vocal_sections(vocal_16k, min_silence_sec=3.0)
            lyric_sections = split_lyrics_on_labels(lyric_lines)

            if len(vocal_sections) != len(lyric_sections):
                log.warning(
                    "Section count mismatch: %d vocal sections vs %d lyric sections. "
                    "Falling back to whole-file alignment.",
                    len(vocal_sections), len(lyric_sections)
                )
                lyric_lines = align_section(vocal_16k, lyric_lines, args.lang, cache_dir)
            else:
                aligned_all = []
                for s_idx, (v_sec, l_sec) in enumerate(zip(vocal_sections, lyric_sections)):
                    v_start, v_end = v_sec
                    log.info("Aligning section %d/%d (%.2fs–%.2fs)…",
                             s_idx+1, len(vocal_sections), v_start, v_end)
                    sec_wav = tmp_dir / f"section_{s_idx:02d}.wav"
                    slice_audio(vocal_16k, v_start, v_end, sec_wav)
                    aligned_sec = align_section(sec_wav, l_sec, args.lang, cache_dir,
                                                start_offset=v_start)
                    aligned_all.extend(aligned_sec)
                lyric_lines = aligned_all
        else:
            lyric_lines = align_section(vocal_16k, lyric_lines, args.lang, cache_dir)

        # ── Step 6: Quality checks
        n_flagged = quality_check(lyric_lines, total_dur)

        # ── Step 7: Write outputs
        usfm_path = out_prefix.parent / (out_prefix.name + ".usfm")
        json_path = out_prefix.parent / (out_prefix.name + "_words.json")
        review_path = out_prefix.parent / (out_prefix.name + "_review.txt")

        write_usfm(lyric_lines, usfm_path, title=args.title or lyrics_path.stem, lang=args.lang)
        write_json(lyric_lines, json_path)
        write_review(lyric_lines, review_path, total_dur)

        # Generate VIDX files automatically
        sab_timing_path = out_prefix.parent / (out_prefix.name + ".txt")
        write_vidx_timing(lyric_lines, sab_timing_path, book=args.book, chapter=args.chapter)
        if "MAL_RAP" in str(out_prefix):
            write_vidx_timing(lyric_lines, out_prefix.parent / (out_prefix.name + "_MAL_RAP.txt"), book=args.book, chapter=args.chapter)

        usfm_dir = out_prefix.parent.parent / "USFM"
        if usfm_dir.exists():
            vidx_usfm_path = usfm_dir / (out_prefix.name + ".usfm")
            write_vidx_usfm(lyric_lines, vidx_usfm_path, book=args.book, chapter=args.chapter, title=args.title or out_prefix.name)
            print(f"  VIDX USFM → {vidx_usfm_path}")
        print(f"  SAB Timing → {sab_timing_path}")

        elapsed = time.time() - t_start
        print_summary(lyric_lines, n_flagged, elapsed)

        print(f"  USFM   → {usfm_path}")
        print(f"  JSON   → {json_path}")
        print(f"  Review → {review_path}")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        log.debug("Cleaned up temp dir: %s", tmp_dir)


if __name__ == "__main__":
    main()

