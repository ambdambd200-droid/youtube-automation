# VARY — Content Strategy & Format Specification

> **Date:** 2026-06-29
> **Purpose:** Formal specification of all content formats, quality standards, and pipeline requirements for the VARY YouTube automation system.

---

## 1. Content Tiers

### 1.1 Tier 1: Daily Shorts (≤60 seconds)

**Published via:** `run_pipeline.py` triggered by `.github/workflows/daily_short.yml`
**Frequency:** 3× per day (at optimized posting times per weekday)
**Max duration:** 60 seconds
**Min duration:** 15 seconds

#### 1.1.1 Movie Shorts

**Style reference:** `KFaUdNMjXt8` — "The Greatest Scene In All Of Cinema - Kingdom Of Heaven"
- Duration: 4:50 (source video), shorts clipped to ≤60s
- Resolution: 1920×1080 (source), cropped to 1080×1920 (9:16 portrait for Shorts)
- Format: Scene clip from a notable film with text overlay
- **Key rule:** At the END of the short, add a hook/call-to-action suggesting the viewer watch the original movie
- **No watermarks** — absolutely none, anywhere

**Description format (movie shorts):**
```
Scene from: [Movie Title]

[hashtag1] [hashtag2] [hashtag3]
Watch the full movie to experience the moment.

━━━━━━━━━━━━━━━━━━━━━━━
🔔 VARY — three times daily
👍 one clip at a time
━━━━━━━━━━━━━━━━━━━━━━━
#VARY #DailyClips #[MovieTag]
```

#### 1.1.2 Football / World Cup Shorts

**Style:** Keep normal (existing format)
**No special treatment needed** — maintain current description/formatting.

**Description format (football shorts):**
```
Source: [Match/Event Title]

natural sound. no music. one clip.

━━━━━━━━━━━━━━━━━━━━━━━
[posting times]
daily.
━━━━━━━━━━━━━━━━━━━━━━━
```

---

### 1.2 Tier 2: Weekly Videos (>60 seconds)

**Published via:** New `.github/workflows/weekly_video.yml` (separate from weekly channel update)
**Frequency:** 1× per week (Sunday)
**Duration:** >1 minute (likely 3–10 minutes)
**Content type:** Movie story explanation

#### 1.2.1 Weekly Movie Story Format

**Style reference:** `qpenyPkJK2Q` — "Why Parasite is a masterpiece" (7:45)
- Format: Film analysis / story explanation
- Resolution: 1920×1080 minimum
- **Audio:** Original audio from the source movie (no voiceover/narration like shorts)
- **Text:** Silent text-based storytelling — on-screen text explains the story/analysis
- **Do NOT include** spoken words/voiceover like in shorts
- **No on-screen branding/words** from the short format — keep it natural and cinematic
- High quality throughout

**Description format (weekly videos):**
```
[Movie Title] — [Theme/Topic]

A deep dive into the story, themes, and cinematic brilliance of [Movie].

━━━━━━━━━━━━━━━━━━━━━━━
🎬 VARY Weekly — every Sunday
👍 one story at a time
━━━━━━━━━━━━━━━━━━━━━━━
#[MovieTitle] #VARY #FilmAnalysis #[RelatedTags]
```

---

## 2. Quality Standards (ALL Content)

### 2.1 Video Quality
- **Resolution:** ≥720p (1280×720). Target 1080p (1920×1080 source → 1080×1920 Shorts)
- **Codec:** H.264 (libx264), profile high, level 4.1
- **Bitrate:** CRF 23 (standard quality)
- **FPS:** 30
- **Pixel format:** yuv420p
- **Audio:** AAC, 192k bitrate (or original source audio preserved)
- **Audio must be clear** — no distortion, noise, or clipping

### 2.2 No Watermarks — ABSOLUTE RULE
- **No VARY watermark** in the video frame itself
- No channel logo overlay on clips
- No text overlays that obstruct the viewing experience
- Thumbnails may still have "VARY" text (they're promotional, not the content)
- Only exception: The end-of-video "watch the original movie" hook for movie shorts

### 2.3 Description Format
- Clean, readable, well-spaced
- Hashtags included
- Source credit when applicable
- Posting schedule displayed
- Channel signature at bottom

---

## 3. Pipeline Requirements Summary

### 3.1 Downloader (`modules/clip_downloader.py`)
- ✅ Removed `--download-sections` (was slow on Windows with DASH formats)
- ✅ Client list: `["android_vr", "android"]` only
- ✅ No `--sleep-requests` (removed unnecessary 2s delay)
- ✅ `--extractor-retries 1` (faster fallthrough)
- ⚠️ Requires: Format selection should prefer ≥720p (`bestvideo[height<=720]+bestaudio/best[height<=720]` minimum)

### 3.2 Editor (`modules/clip_editor.py`)
- Currently has 30% chance of "VARY" text overlay — **must be removed** (no watermarks)
- Crop to 9:16 landscape (1080×1920)
- Preserve original audio (no BG music added)
- **NEW:** For movie shorts, append an "end card" suggesting to watch the original movie (~3 seconds)
- **NEW:** Weekly videos need separate pipeline — no cropping to 9:16, keep original landscape

### 3.3 SEO Generator (`modules/seo_generator.py`)
- Movie description template needs update to include hashtags and "watch original movie" hook
- Weekly video SEO needs its own templates

### 3.4 Thumbnail Generator (`modules/thumbnail_generator.py`)
- No changes needed — thumbnails are external promotional assets

### 3.5 Critique Engine (`modules/clip_critique.py`)
- No changes needed — scoring logic works across content types

### 3.6 Space Manager (`modules/space_manager.py`)
- No changes needed

---

## 4. Current Code Issues & Fixes Applied

| File | Issue | Fix |
|------|-------|-----|
| `modules/clip_downloader.py` | `--download-sections` slow on Windows | Removed, let clip_editor handle trimming |
| `modules/clip_downloader.py` | Too many slow-failing clients | Reduced to `android_vr` + `android` |
| `modules/clip_downloader.py` | Unnecessary 2s delays | Removed `--sleep-requests` and inter-client sleep |
| `modules/clip_downloader.py` | 3 retries per client too slow | Reduced to 1 retry |
| `modules/clip_downloader.py` | Dead code (`import time`, `max_duration`, unused `i`) | Cleaned up |
| `modules/clip_editor.py` | 30% chance of VARY watermark overlay | ⚠️ Still needs removal |

---

## 5. Reference Videos

### KFaUdNMjXt8 — "The Greatest Scene In All Of Cinema - Kingdom Of Heaven"
- **Channel:** Juuzou999 (11.1K subs)
- **Duration:** 4:50
- **Resolution:** 1920×1080 (1080p)
- **Description:** Brief text about the scene's greatness
- **Use:** Format model for movie shorts

### qpenyPkJK2Q — "Why Parasite is a masterpiece"
- **Duration:** 7:45
- **Resolution:** 1920×1080 (1080p)
- **Description:** Film analysis/review
- **Use:** Format model for weekly videos (silent text storytelling)

---

## 6. Next Steps / Pending Work

1. **Remove watermark overlay** from `crop_to_shorts()` in `modules/clip_editor.py`
2. **Add end-card hook** for movie shorts ("watch the original movie")
3. **Update description templates** in `modules/seo_generator.py` for movie shorts
4. **Create weekly video pipeline** — new workflow + editor path for >60s landscape videos
5. **Ensure format selection** downloads ≥720p content
6. **Test pipeline** end-to-end when YouTube rate limits reset
