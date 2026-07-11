---
title: "[COPYRIGHT] The 100 Most Iconic Movie Lines — Multi-Source Compilation Block"
labels: copyright, policy-violation, urgent, compilation-risk
---

## 🚨 Video Blocked by Copyright

**Video:** The 100 Most Iconic Movie Lines of All Time
**Video ID:** `AnlBJfFY8Ww`
**Source Channel:** (compilation from multiple sources)
**Copyright Claimant:** Multiple studios
**Type of Block:** Content ID — multiple claims, video blocked

## Root Cause

This was a **compilation video** containing clips from many different movies. Each clip is owned by a different studio. Content ID matched multiple clips from multiple studios:
- Each studio claimed their portion
- Multiple claims = video blocked or monetized by others
- Cannot dispute because each claim is valid

## Why Compilations Are Especially Dangerous

A compilation contains **N copyrighted works**, which means **N opportunities for Content ID to match**:
- Movie 1 clip → Studio A claims
- Movie 2 clip → Studio B claims
- Movie 3 clip → Studio C claims
- = 3x the risk of a block versus a single-source video

Even if we have permission/fair use for one clip, the other clips get us blocked.

## Permanent Fix Applied

- [x] `youtube_policy_check.py` now flags titles matching compilation patterns
- [x] "Most Iconic", "Top 100", "Best of" compilations flagged as high-risk
- [x] Recommended: NEVER use compilation videos as sources
- [x] Policy documented in `.github/POLICIES.md`

## Safer Alternative

Instead of downloading a compilation (which contains N copyrighted works), download **individual scenes** from non-studio channels (fan channels, analysis channels) and assemble our own narrative with original commentary.

## Verify Fix

```bash
python modules/youtube_policy_check.py "The 100 Most Iconic Movie Lines of All Time" "Some Channel"
# Expected: flagged for compilation risk
```

## Lesson

Compilation videos are **force multipliers for copyright risk**. One compilation = 5-20 copyright claims.
- Prefer single-scene sources
- Prefer analysis/commentary sources
- NEVER use "Top X" / "Best of" / "Most Iconic" compilations
