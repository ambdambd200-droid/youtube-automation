# VARY — Project Progress & Roadmap

> File: PROGRESS.md  
> Purpose: Single source of truth for what's built, what's left, and what should be done next.  
> Last updated: 2026-06-29

---

## ✅ COMPLETED — System Architecture

### Core Pipelines

| Pipeline | File | Steps | Status |
|---|---|---|---|
| **Daily Shorts Pipeline** | `run_pipeline.py` | 9 steps: channel check → select → download → edit → thumbnails → SEO → critique → upload → evolve → cleanup | ✅ Complete |
| **Weekly Video Pipeline** | `run_weekly_pipeline.py` | 7 steps: select → download → edit → critique → thumbnails → SEO → upload → cleanup | ✅ Complete |

### Clip Editor (`modules/clip_editor.py`)

| Component | Status | Details |
|---|---|---|
| `crop_to_shorts()` | ✅ Complete | 9:16 vertical crop for YouTube Shorts. No VARY watermark. Outputs 1080×1920. |
| `create_clip()` | ✅ Complete | Re-muxes WebM → MP4, crops to Shorts, appends end card for movie content. |
| `select_clip_segment()` | ✅ Complete | Scene-detection-based segment selection with evolution engine integration. |
| `create_weekly_video()` | ✅ Complete | Landscape video with silent text storytelling. Timed text overlays. **720p minimum enforced** (if width-scaling gives <720h, scales by height). Even-dimension enforcement for both W+H. |
| `generate_weekly_intro()` | ✅ NEW | 3-second animated VARY Weekly intro card — deep blue background, fading text reveals (VARY → WEEKLY → movie name), horizontal accent line, glow ring. Prepended via ffmpeg concat. |
| `append_movie_end_card()` | ✅ Complete | 3-second "Watch the original movie" end card for movie clips. |
| `remux_to_compatible()` | ✅ Complete | WebM → MP4 conversion for ffmpeg compatibility. |
| `_extract_movie_name()` | ✅ NEW | Shared helper that cleans YouTube titles to extract actual movie name. Used by both intro generator and story text generator. |
| **720p Minimum** | ✅ DONE | Enforced in `create_weekly_video()`. Even dims for both W+H. Fallback: 1280×720. |

### SEO Generator (`modules/seo_generator.py`)

| Component | Status | Details |
|---|---|---|
| `generate_metadata()` | ✅ Complete | Three-tier titles (poetic/balanced/direct) for worldcup + movie. Description templates. Tags. |
| `generate_weekly_metadata()` | ✅ Complete | Essay-style titles with `[movie]` and `[theme]` placeholders. Film analysis descriptions. Weekly-specific tags. |

### Downloader (`modules/clip_downloader.py`)

| Component | Status | Details |
|---|---|---|
| `download_best_match()` | ✅ Complete | YouTube search + download with used-video dedup. |
| `download_clip()` | ✅ Complete | Multi-client fallback (android_vr → android) for bot bypass. Cookies support. |
| `search_youtube()` | ✅ Complete | Flat playlist search with duration filter (≤600s). |

### Content Selector (`modules/content_selector.py`)

| Component | Status | Details |
|---|---|---|
| `select_today_content()` | ✅ Complete | Weighted random selection (World Cup 40% / Movie 60%), evolved weights, streak avoidance. |
| Used-scenes tracking | ✅ Complete | JSON-based dedup registry with 500-entry limit. |

### Thumbnail Generator (`modules/thumbnail_generator.py`)

| Component | Status | Details |
|---|---|---|
| Daily Shorts: 3 A/B variants | ✅ Complete | v1: bottom text bar. v2: left-aligned with emoji. v3: dramatic with box. Note: v1 and v3 include "VARY" drawtext (intentional thumbnail branding, not video watermark). |
| **Weekly: 3 landscape variants** | ✅ **NEW** | `generate_weekly_thumbnails()` — 16:9 variants for landscape weekly videos: v1: bottom bar + gold "VARY Weekly" top. v2: left-aligned + film emoji + "Story Analysis". v3: minimal with top/bottom bars. Uses `extract_landscape_frame()` for frame sampling. |

### Critique Engine (`modules/clip_critique.py`)

| Component | Status | Details |
|---|---|---|
| **Daily: 6-axis scoring** | ✅ Complete | first_frame_hook, motion_dynamics, audio_impact, scene_composition, color_vibrancy, pacing. Weighted compound. Grades A–F. |
| **Weekly: 6-axis landscape scoring** | ✅ **NEW** | `critique_weekly_video()` — 6 axes for longer-form analysis content: visual_quality, audio_quality, pacing (0.3–1.0 changes/10s ideal), story_coherence (text density + audio presence), narrative_flow (duration sweet spot 3–8 min), intro_presence (dark background detection). Logs to `weekly_critique_scores.jsonl`. |
| Critique logging | ✅ Complete | JSONL history logs for both daily (`critique_scores.jsonl`) and weekly (`weekly_critique_scores.jsonl`). |

### Evolution Engine (`modules/evolution_engine.py`)

| Component | Status | Details |
|---|---|---|
| Auto-mutation (6 axes) | ✅ Complete | Content weights, keywords, clip duration, scene threshold, title style, real performance. |
| Public API | ✅ Complete | `get_parameter()`, `get_evolved_weights()`, `get_evolved_keywords()`, `get_evolution_status()`, `reset_evolution()`. |
| Real performance integration | ✅ Complete | Reads `performance_tracker` data for ground-truth mutations. |
| **Posting time evolution** | ✅ **NEW** | `_mutate_posting_times()` — analyzes real view_velocity data per hour/day-of-week from uploaded videos. Evolves optimal posting windows per weekday. Merges with static defaults (evolved wins). Only activates when ≥10 performance entries exist across ≥3 days. |
| **`get_evolved_posting_times()`** | ✅ **NEW** | Public getter for `config.py` to check evolved times before falling back to static schedule. |

### Performance Tracker (`modules/performance_tracker.py`)

| Component | Status | Details |
|---|---|---|
| YouTube API stats fetching | ✅ Complete | Views, likes, comments per video. |
| Signal calculation | ✅ Complete | view_velocity, like_ratio, engagement_rate, performance_score. |
| Trend analysis | ✅ Complete | Per-type averages, critique-vs-real delta. |
| Polling workflow | ✅ Complete | Every 6 hours via `performance_poll.yml`. |

### Performance Dashboard (`run_performance_dashboard.py`)

| Component | Status | Details |
|---|---|---|
| **Full dashboard** | ✅ **NEW** | Overview + critique comparison + per-axis breakdown + real YouTube performance + upload timeline + evolution summary + actionable recommendations. |
| **CLI modes** | ✅ **NEW** | `--daily` / `--weekly` / `--realtime` (fetch fresh YouTube data before display) / `--json` (machine-readable) / `--trends` (time-series view). |
| **Grade distribution** | ✅ **NEW** | Daily (A–F) vs Weekly grade distribution with visual bar charts. |
| **Critique-vs-real delta** | ✅ **NEW** | Compares critique scores to actual YouTube performance, shows over/under estimation. |
| **Top performers** | ✅ **NEW** | Lists top videos by performance score with views and content type. |

### Pipeline Watchdog & Recovery (`modules/pipeline_watchdog.py`, `run_recovery.py`)

| Component | Status | Details |
|---|---|---|
| **Persistent run tracker** | ✅ **NEW** | `pipeline_watchdog.py` — registers every pipeline run with pipeline_id, type, status, stage, timestamps. Persistent state in `pipeline_state.json`. |
| **Crash detection** | ✅ **NEW** | `get_failed_runs()` / `get_stuck_runs()` — detects crashes within configurable windows. Handles both clean failures and hard crashes (timeout-based detection). |
| **Retry management** | ✅ **NEW** | `get_failed_runs_for_retry()` — filters by retry count (max 2 retries per run). `mark_retried()` increments counter. |
| **Missed run detection** | ✅ **NEW** | `detect_missed_runs()` — compares pipeline logs against expected upload schedule (3 daily, 1 weekly). |
| **Recovery script** | ✅ **NEW** | `run_recovery.py` — auto, check (dry-run), force modes. `--daily` / `--weekly` filter. 60s delay between retries. |
| **Recovery workflow** | ✅ **NEW** | `.github/workflows/recovery_check.yml` — every 4 hours, checks pipeline state and retries eligible failures. Manual dispatch with mode selection. |

### YouTube Uploader (`modules/youtube_uploader.py`)

| Component | Status | Details |
|---|---|---|
| OAuth authentication | ✅ Complete | 3-tier: env vars → pickle file → interactive OAuth. |
| Video upload | ✅ Complete | Resumable upload with progress. Thumbnail attachment. |

### Space Manager (`modules/space_manager.py`)

| Component | Status | Details |
|---|---|---|
| Source cleanup | ✅ Complete | Deletes downloads after processing. |
| **Temp file cleanup** | ✅ **NEW** | `cleanup_temp_files()` — removes `_temp_*` and `_endcard_*` intermediate files from editing. |
| **Critique frame cleanup** | ✅ **NEW** | `cleanup_critique_frames()` — deletes JPEG frames from `logs/_frames/` after analysis. |
| **Aggressive clip cleanup** | ✅ **NEW** | `full_cleanup()` now calls `cleanup_old_clips(max_days=0)` — deletes ALL processed clips immediately after upload (not waiting 7 days). |
| Old clip cleanup | ✅ Complete | Removes clips older than configurable days. |
| Disk usage logging | ✅ Complete | Logs file count + total size. |

### Channel Management

| Component | File | Status | Details |
|---|---|---|---|
| Branding generator | `channel_branding_generator.py` | ✅ Complete | Pillow-based profile pic (goalpost/film V) and banner (split football/cinema). |
| Channel manager | `channel_manager.py` | ✅ Complete | Description updates, branding upload. Auto-transitions when World Cup ends. |

### GitHub Actions Workflows

| Workflow | File | Schedule | Status | Details |
|---|---|---|---|---|
| **Daily Shorts (×3)** | `daily_short.yml` | 3× daily (day-optimized times) | ✅ Complete | Full pipeline with auto-retry (MAX_RETRIES=1). |
| **Weekly Video** | `weekly_video.yml` | Sundays 12:00 UTC | ✅ Complete | Weekly story analysis video. Auto-retry (MAX_RETRIES=1). Manual trigger. |
| **Weekly Channel Update** | `weekly_channel_update.yml` | Sundays 12:00 UTC | ✅ Complete | Branding + description refresh. |
| **Performance Poll** | `performance_poll.yml` | Every 6 hours | ✅ Complete | Stats fetching + evolution cycle. |
| **Pipeline Recovery Check** | `recovery_check.yml` | Every 4 hours | ✅ NEW | Checks pipeline state, retries eligible failures. Auto on schedule, manual with mode selection. |

### Configuration (`config.py`)

| Component | Status | Details |
|---|---|---|
| YouTube credentials | ✅ Complete | Client ID, secret, refresh token. |
| Output directories | ✅ Complete | downloads, clips, thumbnails, logs. |
| Video settings | ✅ Complete | 1080×1920, 30fps, 15-60s duration. |
| Content weights | ✅ Complete | Active (40/60) and post-WC (100% movie). |
| Posting schedule | ✅ Complete | Day-optimized times per weekday. **Evolved times checked first** via `get_evolved_posting_times()` from evolution engine. |

### Used-Scenes & Performance Tracking in Weekly Pipeline

| Component | Status | Details |
|---|---|---|
| **Used-scenes dedup** | ✅ **NEW** | `run_weekly_pipeline.py` now calls `load_used_scenes()` before download and passes `used_ids` to `download_best_match()`. Calls `save_used_scene()` after upload. |
| **Performance registration** | ✅ **NEW** | Weekly pipeline now calls `register_upload()` with `weekly_movie` content type, enabling performance tracking and evolution feedback. |

---

## 📋 REMAINING WORK

### High Priority

1. **Feed weekly critique scores into evolution engine**  
   The evolution engine currently only reads daily Shorts critique scores from `critique_scores.jsonl`. Weekly critique scores in `weekly_critique_scores.jsonl` are not factored into parameter mutations. The evolution engine should learn from both data streams.

2. **Add weekly performance poll**  
   `performance_poll.yml` fetches YouTube stats for videos in the upload registry. Weekly videos are registered (`content_type: weekly_movie`) but the poll doesn't distinguish them. Consider adding weekly-specific signals (avg view duration, retention).

3. **Add content history logging for weekly pipeline**  
   The weekly pipeline logs to `weekly_pipeline_log.jsonl` but doesn't update `content_history.json`. Either extend the existing system or create a dedicated weekly content history.

4. **Add recovery webhook/notification**  
   When the recovery pipeline runs and finds failures it can't fix (retries exhausted), send a notification via Slack, Discord, or email. Currently silent.

### Medium Priority

5. **Wire the pipeline watchdog into the performance dashboard**  
   `run_performance_dashboard.py` doesn't show pipeline health stats (failed runs, stuck runs, success rate). The `pipeline_watchdog.get_runs_summary()` has all the data — just needs a section in the dashboard.

6. **Add `/dashboard` and `/cleanup` API endpoints**  
   `api_server.py` has a `/health` and `/run-pipeline` endpoint but no dashboard or cleanup trigger. Add `/dashboard` (returns performance dashboard JSON) and `/cleanup` (triggers space_manager).

7. **Add disk space monitoring and alerts**  
   `space_manager.py` logs disk usage but doesn't alert when space is low. Add a warning threshold in the pipeline output and recovery check.

8. **Add auto-cleaning of old pipeline state entries**  
   `pipeline_watchdog.py` keeps the last 100 runs but doesn't prune failures older than 7 days. Add `prune_old_state()` to keep the state file clean.

### Low Priority / Nice-to-Have

9. **Add subtitle/CC support** for accessibility — auto-generated subtitle tracks via ffmpeg or external API.

10. **Dynamic weekly video duration** based on source length — calculate duration from number of story texts × segment duration instead of fixed 20s per segment.

11. **Weekly video story texts from AI** — use an LLM to generate more diverse, source-specific story texts instead of hardcoded templates.

12. **Add more kinetic weekly video styles** — alternate visual styles: zoom-pan effects (Ken Burns), lower-third title cards, chapter markers via embedded scene text.

13. **Add video length check for weekly pipeline** — warn if source is too short (<90s) for meaningful analysis.

14. **Create self-hosted runner setup** — for lower latency and no CI dependency, document how to run the full system on a dedicated machine with cron.

15. **Add `--log` viewer for weekly pipeline** — simple script similar to critique_scores viewer for weekly_pipeline_log.jsonl.

16. **Cross-promotion** — in weekly video descriptions, link to related daily shorts. In daily shorts, tease the upcoming weekly video.

---

## 💡 ADDITIONAL SUGGESTIONS

### Architecture Improvements

- **Separate weekly log viewer**: `run_weekly_pipeline.py` logs to `weekly_pipeline_log.jsonl`. No visualizer for it yet.
- **Shared retry utility**: Extract retry logic from workflows into `modules/utils.py` as `retry_with_backoff()`.
- **Config-driven keywords**: Move `WEEKLY_KEYWORDS` from `run_weekly_pipeline.py` into `config.py` for consistency.
- **Pipeline ID in return dicts**: Both pipelines now track `pipeline_id` via watchdog but don't return it in their result dicts. Adding it would help API callers correlate runs.

### Content Strategy

- **Weekly video niche expansion**: Currently weekly is always movie analysis. Could expand post-World-Cup (e.g., "Why this director's style works", "The making of...").
- **Weekend experiment slot**: Use one of the three daily shorts slots for experimental content types (trending audio, memes, etc.).

### Monitoring

- **Alert on pipeline failure**: GitHub Actions sends email on failure. Consider Discord/Slack webhook for real-time alerts.
- **Weekly health check**: A workflow that checks if the last weekly pipeline ran successfully within the expected time window.

### VARY Watermark Clarification

- **Confirmed**: No VARY drawtext exists in any video output functions (`crop_to_shorts()`, `create_weekly_video()`, `append_movie_end_card()`).
- **VARY text DOES exist in**: `thumbnail_generator.py` (thumbnail v1 and v3 — intentional brand placement), `channel_branding_generator.py` (channel art/banner).
- **To remove VARY from thumbnails**: edit `modules/thumbnail_generator.py` — remove the second `drawtext` with `text='VARY'` in v1 (~line 69) and v3 (~line 134).

---

## RECENT CHANGES (2026-06-30)

| Change | Files | Description |
|---|---|---|
| **Recovery webhook alerts** | `config.py`, `modules/pipeline_watchdog.py`, `run_recovery.py`, `.github/workflows/recovery_check.yml` | Added `send_alert()` (Discord/Slack auto-detect), `get_exhausted_runs()`, `notify_exhausted_retries()`. Wired into `run_recovery.py` after recovery attempt. `--notify` CLI option. `ALERT_WEBHOOK_URL` secret deployed in `recovery_check.yml`. |
| **Auto-prune old pipeline state** | `modules/pipeline_watchdog.py` | Added `prune_old_state()` — auto-removes entries older than 7 days on every state write, caps total to 100. Safely handles missing/invalid timestamps. `--prune [days]` CLI option for manual cleanup. |
| **Weekly content history logging** | `run_weekly_pipeline.py` | Weekly pipeline now calls `save_history()` after content selection, recording `weekly_movie` entries in `content_history.json` alongside daily shorts. |
| **Weekly critique fed into evolution** | `modules/clip_critique.py`, `modules/evolution_engine.py` | Added `load_weekly_critique_history()` + `load_all_critiques()`. Evolution engine now loads both daily AND weekly critique scores via `load_all_critiques()`, learning from both content streams. |
| **Dashboard API endpoint** | `api_server.py` | Added `GET /dashboard` endpoint returning full performance dashboard JSON (critique comparison, real metrics, grade distribution, timeline, top performers, evolution status). |
| **yt-dlp bot bypass overhaul** | `modules/clip_downloader.py` | Added 4 fallback player clients (android, ios, android_vr, web). Increased retries (extractor=3, download=10, fragment=10). Added throttling (`100K`), geo-bypass, and randomized delays between requests. |
| **Animated weekly intro card** | `modules/clip_editor.py` | `generate_weekly_intro()` — 3s animated VARY branding card with fade-in text, accent line, glow ring. Prepended via ffmpeg concat. |
| **Posting time evolution** | `modules/evolution_engine.py`, `config.py` | `_mutate_posting_times()` learns optimal hours per day from real view velocity. `get_evolved_posting_times()` checked by get_posting_times() before static defaults. |
| **Aggressive space cleanup** | `modules/space_manager.py` | Added cleanup of temp files, critique frames, and immediate clip deletion (max_days=0). Both pipelines pass clip + thumbnails for immediate cleanup. |
| **Weekly critique step** | `modules/clip_critique.py`, `run_weekly_pipeline.py` | `critique_weekly_video()` with 6 landscape-optimized axes. Integrated as Step 4/7 in weekly pipeline. |
| **Landscape thumbnail variants** | `modules/thumbnail_generator.py` | `generate_weekly_thumbnails()` — 3 new 16:9 variants for weekly landscape videos. |
| **Performance dashboard** | `run_performance_dashboard.py` | Full CLI dashboard comparing daily vs weekly: critique scores, real YouTube metrics, grade distribution, timeline, recommendations. |
| **Auto-retry safety net** | `modules/pipeline_watchdog.py`, `run_recovery.py`, `.github/workflows/recovery_check.yml` | Persistent crash tracking, recovery script, and every-4h CI recovery check. |
| **Used-scenes + perf tracking in weekly** | `run_weekly_pipeline.py` | Download dedup via used_ids + performance registration for weekly videos. |
| **Weekly pipeline retry loop** | `.github/workflows/weekly_video.yml` | MAX_RETRIES=1 with 60s delay, matching daily Shorts workflow. |
| **Posting schedule evolution** | `config.py` | `get_posting_times()` checks evolution engine for optimized times before static defaults. |
| **Bugs fixed** | `modules/evolution_engine.py`, `modules/space_manager.py` | Fixed `day_hour_perf` initialization bug in `_mutate_posting_times()`. Fixed private import. Removed dead `cleanup_processed_clip()` function. |

---

## FILE MAP

```
C:\Users\A\Desktop\Movies\
├── config.py                           # Central configuration
├── run_pipeline.py                     # Daily Shorts pipeline (9 steps)
├── run_weekly_pipeline.py              # Weekly video pipeline (7 steps)
├── run_performance_dashboard.py        # Performance dashboard (NEW)
├── run_recovery.py                     # Pipeline recovery script (NEW)
├── PROGRESS.md                         # THIS FILE
│
├── modules/
│   ├── clip_editor.py                  # Video trimming, cropping, text, intro card
│   ├── clip_downloader.py              # yt-dlp YouTube downloader
│   ├── clip_critique.py                # 6-axis daily + 6-axis weekly scoring
│   ├── content_selector.py             # Weighted random content type selection
│   ├── seo_generator.py                # Titles, descriptions, tags
│   ├── thumbnail_generator.py          # 3-variant daily + 3-variant landscape thumbnails
│   ├── evolution_engine.py             # Parameter mutation + posting time evolution
│   ├── performance_tracker.py          # YouTube analytics polling & signal calc
│   ├── pipeline_watchdog.py            # Crash detection & retry tracking (NEW)
│   ├── youtube_uploader.py             # YouTube Data API v3 upload
│   ├── space_manager.py                # Aggressive disk cleanup
│   ├── channel_manager.py              # Channel branding + description updates
│   ├── channel_branding_generator.py   # Pillow-based profile pic & banner
│   └── utils.py                        # Font path resolution
│
├── .github/workflows/
│   ├── daily_short.yml                 # 3× daily Shorts pipeline
│   ├── weekly_video.yml                # Sunday weekly video pipeline
│   ├── weekly_channel_update.yml       # Sunday branding refresh
│   ├── performance_poll.yml            # Every 6h analytics poll
│   └── recovery_check.yml              # Every 4h pipeline health check (NEW)
│
├── assets/
│   ├── downloads/                      # Raw downloads (auto-cleaned)
│   ├── clips/                          # Processed videos (immediately cleaned)
│   ├── thumbnails/variants/            # A/B thumbnail variants
│   ├── logs/
│   │   ├── _frames/                    # Critique analysis frames (auto-cleaned)
│   │   ├── pipeline_state.json         # Watchdog state (NEW)
│   │   ├── pipeline_log.jsonl          # Daily pipeline log
│   │   ├── weekly_pipeline_log.jsonl   # Weekly pipeline log
│   │   ├── critique_scores.jsonl       # Daily critique history
│   │   ├── weekly_critique_scores.jsonl# Weekly critique history (NEW)
│   │   ├── performance_log.jsonl       # YouTube analytics
│   │   ├── upload_registry.json        # All uploaded videos
│   │   ├── content_history.json        # Content selection history
│   │   ├── evolution_state.json        # Evolution parameters
│   │   ├── evolution_log.jsonl         # Evolution mutation log
│   │   ├── channel_updates.jsonl       # Channel branding log
│   │   └── used_scenes.json            # Dedup registry
│   └── channel_art/                    # Branding assets
│
├── VARY_CONTENT_STRATEGY.md            # Content strategy notes
├── DEPLOYMENT.md                       # Deployment guide
├── _debug_editor.py                    # Debug scripts
├── _run_e2e_test.py
├── _run_full_test.py
├── create_workflows.py                 # n8n workflow creator
└── api_server.py                       # Flask API server
```
