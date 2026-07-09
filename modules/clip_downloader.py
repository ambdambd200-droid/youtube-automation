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


# ── Copyright / Freshness filters ───────────────────────
# Major studios with aggressive Content ID (skip these channels)
_COPYRIGHT_BLACKLIST = [
    "marvel", "disney", "pixar", "warner bros", "universal pictures",
    "sony pictures", "paramount", "20th century", "fox", "netflix",
    "hbo", "hbo max", "dc comics", "nbc", "abc", "cbs",
    "dreamworks", "illumination", "studio ghibli",
    # Football broadcasters with strict copyright
    "fifa", "uefa", "premier league", "laliga", "serie a",
    "espn fc", "sky sports", "bt sport", "bein sports",
]
# But allow these specific copyright-safe channels
_COPYRIGHT_SAFE_CHANNELS = [
    "jo blo", "jolo", "shaeel", "now you see it",
    "kimer", "vibey", "yellow sub", "uday",
]


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
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height", "-of", "json", video_path]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout
        data = json.loads(out)
        s = data.get("streams", [{}])[0]
        return int(s.get("width", 0)), int(s.get("height", 0))
    except Exception:
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

    # ── Quality gates ────────────────────────────────────
    # Reject very low-view videos (weird/obscure content)
    quality_candidates = [v for v in fresh if v.get("view_count", 0) >= 10000]
    if not quality_candidates:
        quality_candidates = [v for v in fresh if v.get("view_count", 0) >= 1000]
    if not quality_candidates:
        quality_candidates = fresh

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

    # Sort by recency + views for all types
    def _freshness_score(v):
        ud = v.get("upload_date", "")
        try:
            days_old = (now - datetime.strptime(ud, "%Y%m%d")).days if len(ud) == 8 else 999
        except ValueError:
            days_old = 999
        views = v.get("view_count", 0)
        return (-days_old, -views)
    quality_candidates.sort(key=_freshness_score)

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

    # Sort by view count descending, pick from top 5
    quality_candidates.sort(key=lambda v: v.get("view_count", 0), reverse=True)

    # Try each candidate in order until one passes resolution check
    for chosen in quality_candidates[:5]:
        print(f"  [downloader] Downloading: {chosen['title']}", flush=True)
        print(f"  [downloader] Channel: {chosen.get('channel', '?')} | Views: {chosen.get('view_count', 0):,}", flush=True)
        filepath = download_clip(chosen["url"], video_id=chosen["id"])

        if not filepath:
            continue

        # Check resolution minimum if specified
        if min_resolution:
            w, h = get_video_dimensions_simple(filepath)
            min_w, min_h = min_resolution
            if w < min_w or h < min_h:
                print(f"  [downloader] Rejected: {w}x{h} — below {min_w}x{min_h} minimum", flush=True)
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
