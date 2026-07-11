---
title: "[COPYRIGHT] The Godfather — Paramount Pictures Content ID Block"
labels: copyright, policy-violation, urgent, permanent-blacklist
---

## 🚨 Video Blocked by Copyright

**Video:** THE GODFATHER | Opening Scene | Paramount Movies
**Video ID:** `BHYDRKx5moo`
**Source Channel:** Paramount Movies
**Copyright Claimant:** Paramount Pictures Corporation
**Type of Block:** Content ID — blocked worldwide

## Root Cause

The video was downloaded from **Paramount Movies** — an official movie studio channel. Paramount registers all their content with YouTube's Content ID system. Even a short clip of The Godfather triggers an instant match.

## Why This WILL Happen Again

Paramount owns thousands of movies. Any clip from any Paramount movie will trigger Content ID.
- The Godfather, Transformers, Mission: Impossible, Top Gun, Titanic, etc.
- These are ALL registered in Content ID
- No amount of editing (color grade, speed ramp, subtitles) will bypass this

## Permanent Fix Applied

- [x] `Paramount Movies` added to `STUDIO_CHANNELS` in `youtube_policy_check.py`
- [x] `Paramount Pictures` added to `STUDIO_CHANNELS` in `youtube_policy_check.py`
- [x] `paramount` added to `_COPYRIGHT_BLACKLIST` in `clip_downloader.py`
- [x] Pipeline now refuses to download from ANY channel matching "paramount"
- [x] Check logged in `policy_violations.jsonl`

## Verify Fix

```bash
python modules/youtube_policy_check.py "The Godfather Scene" "Paramount Movies"
# Expected: Safe: False, Reason: Channel contains 'paramount' — Content ID risk
```

## Lesson

**NEVER** download from channels with names like:
`Paramount Movies/Pictures`, `Movieclips`, `Warner Bros`, `Universal Pictures`, `Disney`, `Marvel`, `Netflix`, `HBO`, `Sony Pictures`, `20th Century Studios`, `Lionsgate`, `MGM`, `A24`
