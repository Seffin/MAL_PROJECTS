# align_song.py — Test Plan & Known Failure Cases
# ================================================

## Unit Test Plan

### Test 1: Basic integration (smoke test)
```powershell
# Use a 30-second test clip; verify output files are created
python align_song.py `
  --audio   "D:\Seffin\MAL_RAP\PHI\MP3\PHI_1_PART_1_MAL_RAP.mp3" `
  --lyrics  "D:\Seffin\MAL_RAP\PHI\LYRICS\PHI_1_PART_1_MAL_RAP.txt" `
  --out     "D:\Seffin\MAL_RAP\PHI\TIMING\test_smoke" `
  --no-demucs
```
Expected: .usfm, _words.json, _review.txt all created; 0 errors.

### Test 2: Confidence thresholds
Inspect `_review.txt` — all conf < 0.5 flagged.
Manually listen to 2–3 flagged lines; confirm they are actually hard to align.

### Test 3: Section split mode
```powershell
python align_song.py --audio ... --lyrics ... --section-split
```
Expected: section count matches label count; no alignment drift in later sections.

### Test 4: Overlap detection
Manually set two overlapping lines in the timing and re-run quality_check().
Expected: OVERLAP flag appears in _review.txt.

### Test 5: USFM parser round-trip
Run the USFM→VIDX converter in SETUP.md; verify VIDX produces a correct video.

---

## Known Failure Cases & Tips

### 1. Fast singing / rap flow
**Symptom:** Multiple words get merged into one timing slot; words start/end differ by < 50ms.
**Cause:** CTC aligner has limited temporal resolution at 20ms per frame.
**Tip:**
- Pre-process with Demucs to remove music (critical for rap).
- Use --section-split to align each verse independently.
- Accept ±0.2s accuracy for fast delivery; it is normal.

### 2. Heavy reverb or echo
**Symptom:** Lines start 200–400ms late; "pre-echo" appears in confidence.
**Cause:** Reverb tail pushes the energy peak forward; aligner fires late.
**Tip:**
- Apply a light de-reverb filter before aligning:
  `ffmpeg -i vocals.wav -af "arnndn=m=rn_model_path" clean_vocals.wav`
- Or use the dry (close-mic) sub-stem from Demucs's 6-stem model.

### 3. Harmonies / backing vocals
**Symptom:** Aligner drifts during harmony sections; confidence drops sharply.
**Cause:** Multiple simultaneous voices confuse the CTC lattice.
**Tip:**
- Demucs's htdemucs already separates the main vocal well.
- If backing vocals remain, use the `mdx_extra` Demucs model which is
  better at lead/backing separation:
  `--model mdx_extra`

### 4. Long instrumentals between sections
**Symptom:** All subsequent lyric lines shift by the gap length.
**Cause:** Whole-file alignment stretches to fill the silence.
**Tip:**
- Always use --section-split for songs with instrumentals > 3 seconds.
- If section count mismatches, manually add extra [Bridge] / [Instrumental]
  markers in the lyrics file at each break point.

### 5. MMS language code wrong for dialectal Malayalam
**Symptom:** Very low confidence across all lines (avg < 0.3).
**Cause:** MMS 'mal' model was trained on standard written Malayalam;
  some regional dialects or heavily code-switched text may not match.
**Tip:**
- Try --lang mlt (Maltese) is NOT valid; stick with mal.
- For dialectal speech: pre-romanize the lyrics manually using uroman,
  inspect the romanized text, and edit obvious errors before aligning.

### 6. GPU not available
**Symptom:** demucs takes 30+ minutes on a 4-min song.
**Cause:** htdemucs uses a Transformer architecture; CPU is slow.
**Tip:**
- Split the song into 2-minute chunks before Demucs:
  `ffmpeg -i song.mp3 -f segment -segment_time 120 chunk_%02d.mp3`
  Then align each chunk with --no-demucs after extracting vocals per chunk.
- htdemucs_ft (fine-tuned) is slightly faster than htdemucs on CPU.

### 7. Malayalam Unicode normalization
**Symptom:** Words with chillu letters (ൻ, ർ, ൽ, ൾ, ൺ) aligned incorrectly.
**Cause:** Some Malayalam text uses deprecated atomic chillu codepoints vs.
  base + virama sequences; the romanizer treats them differently.
**Tip:**
- Normalize your lyrics file before running:
  ```python
  import unicodedata
  text = unicodedata.normalize('NFC', text)
  ```
- The script already does NFC normalization internally via uroman's pipeline.

