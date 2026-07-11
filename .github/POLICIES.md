# VARY — YouTube Policy Compliance Reference

> **Golden Rule:** If a video can be found identically on another channel, DO NOT UPLOAD.
> Transformation (editing) is NOT the same as fair use. You need COMMENTARY + ANALYSIS.

---

## 1. Copyright & Content ID ⚠️ DEATH PENALTY

### What happened
3 videos blocked because they contained clips from:
- **Paramount Movies** (The Godfather)
- **Movieclips** (Sony Pictures — Butch Cassidy, Little Women)
- **Compilation videos** containing multiple copyrighted clips

### The Rule
YouTube's **Content ID** system automatically scans every upload. Major studios register their catalogs. Even 1-3 seconds of a known movie clip = instant block.

**Studio channels that will ALWAYS trigger Content ID:**
| Studio | Channels |
|--------|----------|
| Paramount | `Paramount Movies`, `Paramount Pictures` |
| Sony | `Movieclips`, `Sony Pictures Entertainment` |
| Warner Bros | `Warner Bros. Pictures`, `Warnervod` |
| Disney | `Marvel`, `Disney Plus`, `Pixar` |
| Universal | `Universal Pictures`, `Focus Features` |
| Netflix | `Netflix`, `Netflix Official` |
| HBO | `HBO`, `HBO Max`, `Max` |
| Apple/Amazon | `Apple TV+`, `Prime Video`, `Amazon MGM` |

### Consequences
- ❌ **Video blocked worldwide** (cannot appeal via standard process)
- ❌ **Copyright strike** (3 strikes = channel terminated forever)
- ❌ **Channel demonetized**
- ❌ **Repeat offender status** on YouTube

### Prevention (hardcoded in pipeline)
1. `modules/youtube_policy_check.py` checks every video against the **STUDIO_CHANNELS blacklist** before download
2. Pipeline **REFUSES** to download from any studio channel
3. Every violation is logged to `assets/logs/policy_violations.jsonl`

---

## 2. Reused Content Policy

### What it says
YouTube defines **reused content** as: *"Content that repurposes existing material from YouTube or other online sources without adding significant original commentary, modifications, or value."*

**2026 update:** Simply editing clips together cleanly no longer qualifies as "transformative."

### What triggers it
- ❌ Compilations or clips edited together with little or no narrative
- ❌ Short videos compiled from other social media
- ❌ Content downloaded from other sources without substantive changes
- ❌ Identical structure, voiceover style, and b-roll across videos
- ❌ Mass-produced Shorts that just reword trending topics

### What is safe
- ✅ Commentary + analysis with original voiceover
- ✅ Educational or critical analysis of scenes
- ✅ Unique storytelling that couldn't exist without your input
- ✅ Each video has distinguishable value from previous uploads

### Prevention
- Every video MUST have **voiceover** (commentary/analysis/narration)
- Every video MUST apply **3+ transformations** (speed ramp, color grade, subtitles, zoom effects)
- Never produce templated content — vary structure daily

---

## 3. Inauthentic (Repetitious) Content

### What it says
YouTube targets *"content that is repetitive or mass-produced."* This is now called **Inauthentic Content** (renamed July 2025).

### What triggers it
- ❌ Identical video structure every day
- ❌ Same intro, same pacing, same effects, same voiceover style
- ❌ Content that looks like it was made by a bot/template
- ❌ Videos that differ only in small details (title, thumbnail)

### Prevention
- Vary video structure daily
- Use different voiceover styles
- Different pacing, different effects, different music
- Each upload should offer something distinct
- Minimum 30% original creation per video

---

## 4. Fair Use — The Truth

### What fair use IS
A **legal defense** in US copyright law. Only a court can decide. YouTube does NOT decide fair use.

### The 4 factors
1. **Purpose & character** — Is it transformative? Commentary? Criticism? Education?
2. **Nature of work** — Creative works (movies) get MORE protection than factual works
3. **Amount used** — Use only what's necessary. Small clips ≠ automatic fair use
4. **Market impact** — Does your video replace the original? If yes, NOT fair use

### Myths that got us blocked
- ❌ "I edited it (color grade, speed ramp, subtitles)" → NOT enough
- ❌ "I only used 10 seconds" → Still infringing if it's the "heart" of the work
- ❌ "I gave credit" → Copyright doesn't care about credit
- ❌ "I added a disclaimer" → Legal myth, has no effect

### What actually helps
- ✅ Voiceover commentary analyzing the scene
- ✅ Critical review or educational analysis
- ✅ Parody or satire (strongest fair use protection)
- ✅ Original content surrounding the clip (at least 50% of video)

---

## 5. Quick Reference: Safe vs Unsafe Sources

| Source Type | Risk | Example | Action |
|------------|------|---------|--------|
| Official Studio Channel | 🔴 DEATH | `Movieclips`, `Paramount Movies` | BLOCK at download |
| Fan Edits Channel | 🟢 Low | `[Fan] Best Movie Edits` | Allow with caution |
| Analysis/Commentary | 🟢 Low | `Movie Analysis`, `Film Breakdown` | Preferred source |
| News/Sports Broadcast | 🟡 Medium | `ESPN`, `Sky Sports` | Check terms |
| Compilation Channel | 🟡 Medium | `Best Movie Moments` | Check each clip source |
| User Upload | 🟢 Low | Random user upload | Safer than official |

---

## 6. Pipeline Enforcement

The following code enforces these policies automatically:

| File | What it does |
|------|-------------|
| `modules/youtube_policy_check.py` | Pre-download check against studio blacklist + title risk patterns |
| `modules/clip_downloader.py` | `_COPYRIGHT_BLACKLIST` — skips studio channels in search results |
| `modules/youtube_policy_check.py` | Pre-upload check: transformation count + content type safety |

### How to add a new studio to the blacklist
Edit `STUDIO_CHANNELS` in `modules/youtube_policy_check.py` and add the channel name (lowercase).

### How to check policy violations
```bash
# View last 50 policy violations
python -c "from modules.youtube_policy_check import get_policy_report; import json; print(json.dumps(get_policy_report(), indent=2))"
```

---

*Last updated: 2026-07-11*
*This document is part of the VARY repository and must be updated whenever YouTube policies change.*
