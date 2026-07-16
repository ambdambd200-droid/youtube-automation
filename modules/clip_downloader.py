"""
Clip Downloader — downloads video clips from YouTube using yt-dlp.
Handles both World Cup match highlights and movie scenes.
"""
import json
import os
import subprocess
import sys
import random

# Fix Windows console encoding for Unicode characters
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DOWNLOADS_DIR, YT_COOKIES_FILE, BASE_DIR
from modules.utils import find_ffprobe

_FFPROBE_BIN = find_ffprobe()
from config import (
    VIRAL_TIER_1_VIEWS, VIRAL_TIER_1_VELOCITY,
    VIRAL_TIER_2_VIEWS, VIRAL_TIER_2_VELOCITY,
    VIRAL_TIER_3_VIEWS,
    VIRAL_WEIGHT_VELOCITY, VIRAL_WEIGHT_ENGAGEMENT,
    VIRAL_WEIGHT_VIEWS, VIRAL_WEIGHT_RECENCY,
)


# ── Copyright / Freshness filters ───────────────────────
# Major studios with aggressive Content ID (skip these channels)
# See .github/POLICIES.md and modules/youtube_policy_check.py for full list
_COPYRIGHT_BLACKLIST = [
    "paramount", "paramount pictures", "paramount movies",
    "universal pictures", "universal",
    "warner bros", "warner bros. pictures", "warnervod",
    "sony pictures", "movieclips",
    "marvel", "disney", "pixar", "20th century",
    "netflix", "netflix official", "hbo", "hbo max",
    "dc comics", "nbc", "abc", "cbs",
    "dreamworks", "illumination", "studio ghibli",
    "lionsgate", "mgm", "a24",
    "apple tv", "amazon prime video", "prime video",
    # Football broadcasters are safe for short clips
    # "fifa", "uefa", "premier league", "laliga",
    # "espn fc", "sky sports", "bt sport", "bein sports",
]
# But allow these specific copyright-safe channels
_COPYRIGHT_SAFE_CHANNELS = [
    "jo blo", "jolo", "shaeel", "now you see it",
    "kimer", "vibey", "yellow sub", "uday",
]


# ── Viral Score ──────────────────────────────────────────────

def viral_score(video):
    """Calculate viral potential score for a video.
    
    Factors:
    - views/day (velocity): how fast it's spreading
    - likes/views (engagement): how much viewers engage
    - total views: raw reach
    - recency: newer is better
    """
    from datetime import datetime
    views = video.get("view_count", 0) or 0

    # Days since upload
    ud = video.get("upload_date", "")
    days_old = 999
    try:
        if len(ud) == 8:
            days_old = max(1, (datetime.now() - datetime.strptime(ud, "%Y%m%d")).days)
    except ValueError:
        pass

    # View velocity (views per day)
    velocity = views / days_old

    # Engagement rate (likes/views)
    likes = video.get("like_count", 0) or 0
    engagement = likes / max(1, views)

    # Normalize to 0-1 range using log scaling
    vel_score = min(1.0, velocity / VIRAL_TIER_1_VELOCITY)
    eng_score = min(1.0, engagement * 100)  # 1% engagement = 1.0
    views_score = min(1.0, views / VIRAL_TIER_1_VIEWS)
    recency_score = max(0, 1.0 - (days_old / 365))

    score = (
        vel_score * VIRAL_WEIGHT_VELOCITY +
        eng_score * VIRAL_WEIGHT_ENGAGEMENT +
        views_score * VIRAL_WEIGHT_VIEWS +
        recency_score * VIRAL_WEIGHT_RECENCY
    )
    return round(score, 4)


def viral_tier(video):
    """Classify video into viral tier based on views and velocity."""
    from datetime import datetime
    views = video.get("view_count", 0) or 0
    ud = video.get("upload_date", "")
    days_old = 999
    try:
        if len(ud) == 8:
            days_old = max(1, (datetime.now() - datetime.strptime(ud, "%Y%m%d")).days)
    except ValueError:
        pass
    velocity = views / days_old

    if views >= VIRAL_TIER_1_VIEWS and velocity >= VIRAL_TIER_1_VELOCITY:
        return 1  # Viral
    if views >= VIRAL_TIER_2_VIEWS and velocity >= VIRAL_TIER_2_VELOCITY:
        return 2  # Popular
    if views >= VIRAL_TIER_3_VIEWS:
        return 3  # Normal
    return 4  # Weak


# ── Cookie sanitisation ─────────────────────────────────────

def _sanitize_cookies():
    """Strip Restricted Mode (PREF f6=40000000) from cookies in-place."""
    if not YT_COOKIES_FILE or not os.path.isfile(YT_COOKIES_FILE):
        return YT_COOKIES_FILE
    with open(YT_COOKIES_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    cleaned = [l for l in lines if not ("\tPREF\t" in l and "f6=40000000" in l)]
    if len(cleaned) != len(lines):
        with open(YT_COOKIES_FILE, "w", encoding="utf-8") as f:
            f.writelines(cleaned)
        print(f"  [cookies] Stripped Restricted Mode from {YT_COOKIES_FILE}", flush=True)
    return YT_COOKIES_FILE


# ── Anti-bot helpers ────────────────────────────────────────

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

_PLAYER_CLIENTS = [
    "web",
    "android",
    "ios",
    "android_vr",
]


def _get_random_user_agent():
    """Return a random desktop Chrome User-Agent string."""
    return random.choice(_USER_AGENTS)


def _log_cookie_status():
    """Log whether cookies file is available and its size for debugging."""
    if not YT_COOKIES_FILE:
        print("  [downloader] No YT_COOKIES_FILE configured", flush=True)
    elif not os.path.isfile(YT_COOKIES_FILE):
        print(f"  [downloader] YT_COOKIES_FILE not found: {YT_COOKIES_FILE}", flush=True)
    else:
        size = os.path.getsize(YT_COOKIES_FILE)
        print(f"  [downloader] Cookies file found: {size} bytes", flush=True)
        if size < 50:
            print(f"  [downloader] WARNING: Cookies file too small ({size} bytes) — likely empty/invalid", flush=True)


def _get_info_args(player_client=None):
    """Return yt-dlp arguments for fast info-only operations (search, metadata)."""
    _log_cookie_status()
    args = [
        "--no-warnings",
        "--extractor-retries", "3",
        "--user-agent", _get_random_user_agent(),
    ]
    cookie_file = _sanitize_cookies() if YT_COOKIES_FILE else None
    if cookie_file and os.path.isfile(cookie_file):
        args.extend(["--cookies", cookie_file])
    return args


def _get_download_args(player_client=None):
    """Return yt-dlp arguments for video downloads with full anti-bot mitigations.

    Includes throttling, delays, and retries to avoid rate limiting and bot
    detection during the actual download.
    """
    args = [
        "--no-warnings",
        "--extractor-retries", "3",
        "--retries", "10",
        "--fragment-retries", "10",
        "--throttled-rate", "100K",
        "--sleep-requests", "1",
        "--sleep-interval", "3",
        "--max-sleep-interval", "10",
        "--geo-bypass",
        "--user-agent", _get_random_user_agent(),
    ]
    if YT_COOKIES_FILE and os.path.isfile(YT_COOKIES_FILE):
        args.extend(["--cookies", YT_COOKIES_FILE])
    return args


def _try_with_client_fallback(operation_fn, timeout=30):
    """Try an operation with multiple player clients in sequence.

    Tries all clients in _PLAYER_CLIENTS order.
    Retries ALL errors (bot and non-bot) with the next client —
    any single client failure is treated as potentially transient.

    Args:
        operation_fn: Callable(client, timeout) -> (success_bool, result_or_error_msg)
        timeout: Per-attempt timeout in seconds

    Returns:
        result on success, or None if all clients fail
    """
    for client in _PLAYER_CLIENTS:
        print(f"  [downloader] Trying {client}...", flush=True)

        success, payload = operation_fn(client, timeout)

        if success:
            return payload

        # Log the error, but always try the next client
        err_msg = str(payload) if payload else "unknown error"
        bot_hint = ""
        err_lower = err_msg.lower()
        if "sign in" in err_lower or "bot" in err_lower or "login" in err_lower:
            bot_hint = " (bot detection)"

        print(f"  [downloader] Client {client} failed{bot_hint}: {err_msg[:200]}", flush=True)

    return None


def search_youtube(query, max_results=30):
    """Search YouTube for videos matching the query using yt-dlp.

    Returns full metadata including view_count and channel for quality filtering.
    Tries multiple player clients to bypass bot detection.
    """
    def _search(client, timeout):
        cmd = [
            "yt-dlp",
            "-J",
            "--flat-playlist",
            f"ytsearch{max_results}:{query}",
        ] + _get_info_args(player_client=client)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return False, "timed out"

        if result.returncode != 0:
            return False, result.stderr[:300]

        try:
            data = json.loads(result.stdout)
            entries = data.get("entries", [])
            videos = []
            for entry in entries:
                video_id = entry.get("id", "")
                title = entry.get("title", "")
                duration = entry.get("duration", 0)
                url = entry.get("webpage_url", f"https://youtu.be/{video_id}")
                view_count = entry.get("view_count", 0) or 0
                like_count = entry.get("like_count", 0) or 0
                channel = entry.get("channel", "") or entry.get("uploader", "") or ""
                channel_id = entry.get("channel_id", "") or ""
                upload_date = entry.get("upload_date", "") or ""  # YYYYMMDD

                if duration and duration > 600:
                    continue

                videos.append({
                    "id": video_id,
                    "title": title,
                    "url": url,
                    "duration": duration,
                    "view_count": view_count,
                    "like_count": like_count,
                    "channel": channel,
                    "channel_id": channel_id,
                    "upload_date": upload_date,
                })

            if videos:
                return True, videos
            return False, "no matching videos in results"
        except (json.JSONDecodeError, KeyError) as e:
            return False, f"parse error: {e}"

    result = _try_with_client_fallback(_search, timeout=30)
    if result:
        return result

    print("  [downloader] All search clients exhausted, no results", flush=True)
    return []


def _extract_video_info(video_url):
    """Get video metadata, trying multiple player clients.

    Returns:
        Tuple of (info_dict, video_id, duration) or (None, None, 0)
    """
    def _get_info(client, timeout):
        info_cmd = [
            "yt-dlp",
            "-J",
            video_url,
        ] + _get_info_args(player_client=client)
        try:
            info_result = subprocess.run(info_cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return False, "timed out"

        if info_result.returncode != 0:
            return False, info_result.stderr[:300]

        try:
            info = json.loads(info_result.stdout)
            return True, (
                info,
                info.get("id", "unknown"),
                info.get("duration", 0),
            )
        except json.JSONDecodeError as e:
            return False, f"parse error: {e}"

    result = _try_with_client_fallback(_get_info, timeout=30)
    if result:
        return result

    print("  [downloader] All clients blocked for info fetch", flush=True)
    return None, None, 0


def download_clip(video_url, output_template=None, video_id=None):
    """Download a full video from YouTube with fallback.

    Strategy:
      Tries cookies first (if available), then falls back to
      no cookies + android_vr for unblocked IPs.

    Returns:
        Path to downloaded file, or None on failure
    """
    if output_template is None:
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        output_template = os.path.join(DOWNLOADS_DIR, "%(id)s.%(ext)s")

    cookie_file = _sanitize_cookies() if YT_COOKIES_FILE else None
    attempts = []
    if cookie_file and os.path.isfile(cookie_file):
        attempts.append(("with cookies", cookie_file, None))
    attempts.append(("no cookies", None, "android_vr"))

    for label, cookie_path, client in attempts:
        cmd = [
            "yt-dlp",
            "--no-warnings",
            "-f", "best[height<=2160]/best[height<=1080]/best[height<=720]/best",
        ]
        if client:
            cmd += ["--extractor-args", f"youtube:player_client={client}"]
        if cookie_path:
            cmd += ["--cookies", cookie_path]
        cmd += ["-o", output_template, video_url]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            print(f"  [downloader] {label}: timed out", flush=True)
            continue
        except Exception as e:
            print(f"  [downloader] {label}: error {e}", flush=True)
            continue

        if result.returncode == 0:
            break

        err = (result.stderr or "").lower()
        if any(x in err for x in ["sign in", "bot", "requested format is not available",
                                   "failed to extract any player response"]):
            print(f"  [downloader] {label}: {err[:200]}", flush=True)
            print(f"  [downloader] Trying next method...", flush=True)
            continue

        print(f"  [downloader] {label}: {result.stderr[:300]}", flush=True)
        return None
    else:
        print("  [downloader] All download methods exhausted", flush=True)
        return None

    if video_id:
        for ext in [".mp4", ".webm", ".mkv"]:
            fname = os.path.join(DOWNLOADS_DIR, f"{video_id}{ext}")
            if os.path.exists(fname):
                print(f"  [downloader] Downloaded: {fname} ({os.path.getsize(fname)} bytes)", flush=True)
                return fname

    for ext in [".mp4", ".webm", ".mkv"]:
        for fname in os.listdir(DOWNLOADS_DIR):
            if fname.endswith(ext):
                fpath = os.path.join(DOWNLOADS_DIR, fname)
                print(f"  [downloader] Downloaded: {fpath} ({os.path.getsize(fpath)} bytes)", flush=True)
                return fpath

    print("  [downloader] Downloaded but file not found at expected paths", flush=True)
    return None


_CONTENT_TERMS = {
    "football": ["football", "soccer", "goal", "match", "fifa", "uefa",
                 "champion", "league", "player", "sport", "athletic", "stadium",
                 "highlight", "skills", "top play", "best moment", "viral",
                 "world cup", "cup", "free kick", "penalty", "save"],
    "movie": ["movie", "film", "scene", "trailer", "clip", "cinema", "cinematic",
              "actor", "actress", "director", "hollywood", "animated",
              "behind the scenes", "iconic", "masterpiece", "4k hd",
              "blockbuster", "award", "movie moment"],
    "series": ["episode", "series", "show", "tv", "television", "netflix",
               "season", "finale", "drama", "comedy", "sitcom",
               "hit show", "tv series", "hbo", "amazon prime"],
}
_BLACKLIST_TITLE = [
    "documentary", "history of", "explained", "tutorial", "how to",
    "review", "reaction", "analysis", "deep dive", "interview",
    "behind the news", "mystery of", "story of",
    # Gaming / non-relevant content
    "gameplay", "walkthrough", "let's play", "minecraft", "fortnite",
    "among us", "gta", "roblox", "pubg", "call of duty", "fifa gameplay",
    # Low-effort / compilation garbage
    "compilation", "memes", "funny fails", "try not to laugh",
    "satisfying", "oddly satisfying", "amazing moments",
    # Non-English content that slips through
    "shorts", "#shorts", "youtube shorts",
]


def _is_relevant(title, content_type):
    """Check if a video title is relevant for the given content type."""
    tl = title.lower()
    if any(b in tl for b in _BLACKLIST_TITLE):
        return False
    if content_type and content_type in _CONTENT_TERMS:
        return any(t in tl for t in _CONTENT_TERMS[content_type])
    return True


def get_video_dimensions_simple(video_path):
    """Quick ffprobe call to get video resolution."""
    import json, subprocess
    cmd = [_FFPROBE_BIN, "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height", "-of", "json", video_path]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout
        data = json.loads(out)
        s = data.get("streams", [{}])[0]
        return int(s.get("width", 0)), int(s.get("height", 0))
    except Exception:
        return 0, 0


MIN_DOWNLOAD_RESOLUTION = (854, 480)  # Minimum 480p - 720p too restrictive for football


def _check_resolution_quick(video_url):
    """Quick resolution check using yt-dlp format listing (no download)."""
    try:
        cmd = [
            "yt-dlp", "-J",
            "--no-warnings",
            "--user-agent", _get_random_user_agent(),
            "--format", "best[height>=720]/best[height>=480]/best",
            video_url,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            info = json.loads(r.stdout)
            height = info.get("height", 0) or 0
            width = info.get("width", 0) or 0
            return width, height
    except Exception:
        pass
    return 0, 0


def download_best_match(search_query, used_ids=None, content_type=None, min_resolution=None):
    """Search and download the best matching video.

    Filters by quality (view count, relevance) before selecting.
    Picks the best candidate, not a random one.

    Args:
        search_query: Search query for YouTube
        used_ids: Set of already-used video IDs to avoid repeats
        content_type: 'football', 'movie', or 'series' — for relevance filter

    Returns:
        Dict with 'path', 'title', 'video_id', 'content_type', or None
    """
    if used_ids is None:
        used_ids = set()
    if min_resolution is None:
        min_resolution = MIN_DOWNLOAD_RESOLUTION

    videos = search_youtube(search_query, max_results=30)

    fresh = [v for v in videos
             if v["id"] not in used_ids
             and _is_relevant(v["title"], content_type)]

    if not fresh:
        fresh = [v for v in videos if v["id"] not in used_ids]

    if not fresh:
        if videos:
            print("  [downloader] All recent videos used, picking best available", flush=True)
            fresh = videos
        else:
            print("  [downloader] No videos found for query", flush=True)
            return None

    # ── YOUTUBE POLICY CHECK ────────────────────────────
    # Run before every download to prevent copyright/Content ID blocks
    # This filters out studio channels BEFORE any processing
    policy_safe = []
    for v in fresh:
        from modules.youtube_policy_check import pre_download_check
        is_safe, reason = pre_download_check(v)
        if is_safe:
            policy_safe.append(v)
        else:
            print(f"  [downloader] POLICY BLOCKED: {v.get('title','?')[:60]} — {reason}", flush=True)
    if policy_safe:
        fresh = policy_safe
    else:
        print("  [downloader] ALL candidates blocked by policy — skipping safety gate", flush=True)

    # ── VIRAL QUALITY GATES ──────────────────────────────
    # Score each candidate by viral potential, sort by tier + score
    for v in fresh:
        v["_viral_score"] = viral_score(v)
        v["_viral_tier"] = viral_tier(v)

    # Log tiers for debugging
    tiers = {1: "Viral", 2: "Popular", 3: "Normal", 4: "Weak"}
    tier_counts = {}
    for v in fresh:
        t = v["_viral_tier"]
        tier_counts[t] = tier_counts.get(t, 0) + 1
    print(f"  [downloader] Viral tiers: "
          f"{', '.join(f'{tiers[k]}={v}' for k, v in sorted(tier_counts.items()))}", flush=True)

    # Sort by tier (ascending), then by viral_score (descending)
    fresh.sort(key=lambda v: (v["_viral_tier"], -v["_viral_score"]))

    # Filter: prefer tier 1-2, fall back to 3, skip 4 unless desperate
    viral_candidates = [v for v in fresh if v["_viral_tier"] <= 2]
    if not viral_candidates:
        viral_candidates = [v for v in fresh if v["_viral_tier"] <= 3]
    if not viral_candidates:
        viral_candidates = fresh  # even weak ones
    quality_candidates = viral_candidates

    # ── Copyright avoidance: reject major studio channels ─
    copyright_safe = []
    for v in quality_candidates:
        channel = (v.get("channel") or "").lower()
        # Skip major studio channels (aggressive Content ID)
        if any(studio in channel for studio in _COPYRIGHT_BLACKLIST):
            # But allow if channel is in the safe list
            if not any(safe in channel for safe in _COPYRIGHT_SAFE_CHANNELS):
                continue
        copyright_safe.append(v)
    if copyright_safe and len(copyright_safe) >= 2:
        quality_candidates = copyright_safe

    # ── Freshness: prefer recent uploads ──────────────────
    from datetime import datetime
    now = datetime.now()
    if content_type == "football":
        # Football: only last 7 days
        fresh_candidates = []
        for v in quality_candidates:
            upload_date = v.get("upload_date", "")
            if upload_date and len(upload_date) == 8:
                try:
                    vid_date = datetime.strptime(upload_date, "%Y%m%d")
                    if (now - vid_date).days <= 7:
                        fresh_candidates.append(v)
                except ValueError:
                    fresh_candidates.append(v)
            else:
                fresh_candidates.append(v)
        if fresh_candidates:
            quality_candidates = fresh_candidates

    # Reject videos from clearly non-relevant channels (gaming, music, news etc)
    filtered = []
    for v in quality_candidates:
        channel = (v.get("channel") or "").lower()
        title = (v.get("title") or "").lower()
        # Skip gaming/music/news channels unless the title clearly matches
        if any(skip in channel for skip in ["gaming", "gameplay", "music", "news", "press", "tv"]):
            if content_type == "football" and any(ft in channel for ft in ["sport", "football", "goal"]):
                filtered.append(v)
            elif content_type in ("movie", "series") and any(mt in channel for mt in ["movie", "film", "scene", "clip", "trailer"]):
                filtered.append(v)
            else:
                continue
        else:
            filtered.append(v)
    if filtered:
        quality_candidates = filtered

    # Already sorted by (_viral_tier, -_viral_score); pick from top candidates

    # Try each candidate in order until one passes resolution check
    for chosen in quality_candidates[:5]:
        tier_label = {1: "Viral", 2: "Popular", 3: "Normal", 4: "Weak"}.get(chosen.get("_viral_tier", 4), "?")
        print(f"  [downloader] Downloading: {chosen['title']}", flush=True)
        print(f"  [downloader] Channel: {chosen.get('channel', '?')} | "
              f"Views: {chosen.get('view_count', 0):,} | "
              f"Tier: {tier_label} | Score: {chosen.get('_viral_score', 0):.3f}", flush=True)

        # Quick resolution check BEFORE download (uses yt-dlp metadata, no file)
        w, h = _check_resolution_quick(chosen["url"])
        min_w, min_h = min_resolution
        if w > 0 and h > 0 and (w < min_w or h < min_h):
            print(f"  [downloader] Skipped: {w}x{h} — below {min_w}x{min_h} minimum (pre-check)", flush=True)
            continue

        filepath = download_clip(chosen["url"], video_id=chosen["id"])

        if not filepath:
            continue

        # Post-download resolution verification
        w, h = get_video_dimensions_simple(filepath)
        if w > 0 and h > 0 and (w < min_w or h < min_h):
            print(f"  [downloader] Rejected after download: {w}x{h} — below {min_w}x{min_h}", flush=True)
            try:
                os.remove(filepath)
            except Exception:
                pass
            continue

        return {
            "path": filepath,
            "title": chosen["title"],
            "video_id": chosen["id"],
            "url": chosen["url"],
            "duration": chosen.get("duration", 0),
        }

    return None


if __name__ == "__main__":
    # Test
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "world cup 2026 best goal"
    result = download_best_match(query)
    print(json.dumps(result, indent=2, default=str) if result else "No result")
