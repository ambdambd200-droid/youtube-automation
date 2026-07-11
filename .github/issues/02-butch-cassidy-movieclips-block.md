---
title: "[COPYRIGHT] Butch Cassidy — Movieclips / Sony Content ID Block"
labels: copyright, policy-violation, urgent, permanent-blacklist
---

## 🚨 Video Blocked by Copyright

**Video:** Butch Cassidy and the Sundance Kid (1969) - Knife Fight Scene (1/5) | Movieclips
**Video ID:** `Np6EJ2oL7-8`
**Source Channel:** Movieclips
**Copyright Claimant:** Sony Pictures Entertainment / Movieclips
**Type of Block:** Content ID — blocked

## Root Cause

The video was downloaded from **Movieclips** — a channel owned by Sony Pictures Entertainment. Movieclips is a **honeypot**: they upload official movie clips specifically so they can Content ID anyone who reuses them.

**Movieclips = Sony. Sony = aggressive Content ID on everything.**

## Why This WILL Happen Again

Movieclips has uploaded **tens of thousands** of movie clips. Every single one is registered in Content ID. If a search result comes from Movieclips and we download it, it WILL be blocked.

## Permanent Fix Applied

- [x] `movieclips` added to `STUDIO_CHANNELS` in `youtube_policy_check.py`
- [x] `movieclips` added to `_COPYRIGHT_BLACKLIST` in `clip_downloader.py`
- [x] Studio SEO detection: if channel has "movieclips" AND title has "scene/clip" → BLOCK
- [x] Pipeline now refuses to download from movieclips or sony channels

## Additional Danger

Movieclips titles follow a pattern: `Movie Name (Year) - Scene Name (X/Y) | Movieclips`
The pipeline was selecting these because they're high-view, high-relevance results.
**We must explicitly filter out ALL results matching this pattern.**

## Verify Fix

```bash
python modules/youtube_policy_check.py "Butch Cassidy (1969) - Knife Fight Scene (1/5) | Movieclips" "Movieclips"
# Expected: Safe: False
```

## Lesson

Movieclips is the #1 most dangerous channel for our pipeline. They are the top result for almost any movie scene search. We must actively exclude them from search results AND block them at download.

Added `.github/POLICIES.md` with permanent documentation of all studio channels to block.
