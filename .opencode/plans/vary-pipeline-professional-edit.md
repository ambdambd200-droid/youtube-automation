# Plan: VARY Pipeline Professional Edit — Extract & Apply Best Practices from ALL/

## Goal
Upgrade the VARY pipeline to produce professional-grade cinematic shorts that consistently score 90+/100, using the proven techniques extracted from `C:\Users\A\Desktop\ALL\` (AI Video Editor prompts v1-v3 and agentic-dev-workflow). Eliminate the amateur mistakes seen in earlier videos (aggressive zoom, jarring speed ramp, static captions, no sound design, no hook structure).

## Approach
Extract the 8 highest-leverage techniques from the ALL/ prompt files and implement them as modular upgrades to the existing pipeline. Each upgrade is independently verifiable by running the pipeline and checking the critique score and visual output. Implement in priority order (highest impact first).

### Technique Extraction Summary (from AI Video Editor prompts v2 Section 2 & 3)

| # | Technique | Source | Impact | Est. Score Boost |
|---|-----------|--------|--------|------------------|
| 1 | 5-Beat Caption Formula | v2 §2, v3 §4 | **Highest** — captions are the #1 retention driver | +5-10 |
| 2 | Sound Design (riser, silence-dip, impact) | v2 §3.5 | Adds emotional weight without music | +3-5 |
| 3 | Hook Engineering (pattern interrupt in 0-1.5s) | v2 §3.4 | Stops scroll, defines first-frame impact | +3-5 |
| 4 | Dynamic Vertical Reframing | v2 §3.1 | Per-shot focal tracking instead of static crop | +2-4 |
| 5 | Cinematic Color Grading (split-tone) | v2 §3.2 | Mood-matching grade across all cuts | +2-4 |
| 6 | Watermark/Branding | v2 §3.10 | Subtle channel identity, 0.3 opacity | +1-2 |
| 7 | Silence-Dip Psychoacoustic Trick | v2 §3.5 | 0.5s audio pull before climax hit | +1-3 |
| 8 | Loop-Back Ending | v2 §6 | Seamless rewatch, boosts avg watch time | +1-2 |

## Files Touched

1. **`modules/clip_editor.py`** — Major changes:
   - Replace `_generate_word_captions` with `_generate_5beat_captions` (hook→build→peak_signal→emotion_label→twist)
   - Add sound design to filter graph (riser, silence-dip, impact hit via audio filters)
   - Add per-shot reframing logic (detect scenes, calculate focal point per shot)
   - Add watermark overlay
   - Improve hook timing (pattern interrupt in first 1.5s)
   - Add loop-back ending

2. **`modules/audio_pipeline.py`** — Major changes:
   - Add SFX layering (ambient bed, tension riser, sub-bass impact)
   - Add silence-dip psychoacoustic effect
   - Implement ducking (ambient under dialogue)
   - Keep `licensed_music_used = false` rule

3. **`modules/clip_critique.py`** — Minor changes:
   - Strengthen caption detection bonus (+3→+5)
   - Add sound design axis or synergy
   - Check watermark presence in critique
   - Tighten production_quality baseline

4. **`run_pipeline.py`** — Minor changes:
   - Add pipeline stage for watermark and loop-back
   - Increase upload bitrate to 10 Mbps

5. **`config.py`** — Minor changes:
   - Add `WATERMARK_OPACITY = 0.3`
   - Add `TARGET_BITRATE = 10` (Mbps)
   - Add `LOOP_BACK_ENABLED = True`

6. **`CLAUDE.md`** — Add agentic-dev-workflow standing rules

## Key Decisions

- **Decision:** Implement 5-beat caption formula as structured SRT captions (not drawtext)
  **Alternatives considered:** Keep word-by-word SRT but add beat structure
  **Why this one:** The 5-beat structure (hook→build→peak_signal→emotion_label→twist) is the proven formula extracted from high-performing clips. Word-by-word alone misses the narrative architecture that drives retention. Each beat gets its own timing, position, and style.

- **Decision:** Use ffmpeg audio filters for sound design (no external audio processing)
  **Alternatives considered:** Pre-rendered SFX WAV files, external audio tools
  **Why this one:** Keeps the pipeline self-contained, no external dependencies. ffmpeg's `aeval`, `acrossfade`, `volume`, and `adelay` filters can synthesize risers, impacts, and silence-dips.

- **Decision:** Per-shot reframing via ffmpeg `detect_scene` + `crop` per segment
  **Alternatives considered:** ML-based object detection, manual per-shot reframing
  **Why this one:** ffmpeg's scene detection is already used in the pipeline. Extending it to track focal points per shot is faster and more reliable than adding an ML dependency.

- **Decision:** Silence-dip implemented as simple volume envelope before climax
  **Alternatives considered:** Dynamic compressor with sidechain
  **Why this one:** Simpler, more predictable, avoids compression artifacts. A `volume=0.3:enable='between(t,X-0.8,X)'` filter is clean and verifiable.

- **Decision:** Watermark via ffmpeg `drawtext` or `overlay` with low opacity
  **Alternatives considered:** Subtitles/ASS with embedded styling
  **Why this one:** Simple, reliable, works on all ffmpeg versions. Using `format=rgba,colorchannelmixer=aa=0.3` for transparency.

- **Decision:** NOT implementing licensed music (per v2 §3.5 hard rule)
  **Alternatives considered:** Royalty-free music libraries
  **Why this one:** v3 §3 Rule 2 explicitly forbids licensed music references. All emotional weight comes from sound design.

## Risks / Unknowns

- ffmpeg's `detect_scene` may not reliably identify shot boundaries in dark/low-contrast footage
- Synthesized risers/impacts via ffmpeg may sound too artificial — may need pre-rendered SFX samples
- Per-shot reframing adds compute time (~5-10s per shot)
- The 5-beat formula needs to be timed to specific climax moments, which requires accurate climax detection
- `aeval` filter compatibility across ffmpeg 8.1 on Windows
- Watermark overlay might conflict with caption positioning
- The `amix` encoder errors (already seen) may block complex audio filterchains

## Rollback Plan
Each change is in a separate commit. Revert specific commits to undo individual features. Full rollback: `git revert HEAD~N..HEAD` to undo all edit upgrades while keeping config changes.

---

## Implementation Order (highest impact first)

### Phase A: 5-Beat Caption Formula (files 1-2)
1. Create `_generate_5beat_captions()` with the 5-beat structure
2. Integrate into `apply_movie_effects` replacing current word-by-word
3. Each beat: 2-6 words, timed to climax, different position per beat type
4. Use SRT with `subtitles` filter (already working from prior change)

### Phase B: Hook Engineering (file 1)
1. Ensure first 1.5s has a pattern interrupt (bold text + zoom-punch)
2. Hook beat at 0-0.8s, center screen, large font
3. Pre-hook frame: freeze frame or hard cut to most striking frame

### Phase C: Sound Design (file 2)
1. Tension riser: 1.5s before climax, pitch sweep via `aeval`
2. Silence-dip: volume 0.3 for 0.8s before climax
3. Impact hit: short sub-bass tone (50Hz) on climax frame
4. Ambient bed: low-pass noise throughout (optional)

### Phase D: Color Grading Enhancement (file 1)
1. Apply split-tone in color pipeline: cool shadows + warm highlights
2. Increase contrast in shadows, desaturate midtones
3. Add film grain to unify grade and disguise compression

### Phase E: Dynamic Reframing (file 1)
1. Run scene detection on clip before editing
2. For each shot, calculate focal point (center of motion)
3. Apply per-shot crop with slow virtual pan/zoom

### Phase F: Watermark + Loop-Back (file 1)
1. Add `drawtext` or `overlay` watermark at bottom-right, 0.3 opacity
2. Loop-back: crossfade last 0.5s into first frame

### Phase G: Critique Tuning (file 3)
1. Increase caption bonus to +5 with beat structure detection
2. Add sound design axis (check for audio dynamics near climax)
3. Add watermark detection check

---

## QA Verification (per Phase 3 of agentic-dev-workflow)

Each phase must pass:
1. **Layer 1**: `python run_pipeline.py --type movie` completes without error
2. **Layer 2**: Critique score ≥ 90
3. **Layer 3**: Upload to YouTube, verify playback on mobile

Max 3 retry loops per phase. If any phase fails 3 times, surface to human.
