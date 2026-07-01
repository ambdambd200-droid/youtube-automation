"""
Clip Downloader — downloads video clips from YouTube using yt-dlp.
Handles both World Cup match highlights and movie scenes.
"""
import json
import os
import re
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


# ── Anti-bot helpers ────────────────────────────────────────

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

# Ordered list of player clients to try.
# Priority order:
#   1. web        — Works best with cookies; cookies-based auth most effective
#   2. android    — POT via bgutil plugin; broad format support
#   3. ios        — Alternative mobile client with POT support (bgutil plugin)
#   4. android_vr — No PO token needed, but often blocked first (last resort)
#
# The bgutil-ytdlp-pot-provider plugin auto-generates Proof-of-Origin tokens for
# android, ios, and web clients. web is tried first because it works best with
# cookie-based authentication from --cookies.
_PLAYER_CLIENTS = [
    "web",               # Best with cookies — tries cookie auth first
    "android",           # POT via bgutil plugin
    "ios",               # POT via bgutil plugin
    "android_vr",        # No PO token needed, last resort
]

# bgutil-ytdlp-pot-provider HTTP server address (Docker container on port 4416)
_BGUTIL_BASE_URL = "http://127.0.0.1:4416"


def _get_random_user_agent():
    """Return a random desktop Chrome User-Agent string."""
    return random.choice(_USER_AGENTS)


def _get_clean_cookies():
    """Return path to a cookies file with auth tokens stripped and restricted mode off.

    The original cookies (from browser export) include auth tokens (SID, SSID, etc.)
    that trigger YouTube's Restricted Mode, limiting formats to storyboard only.
    This function creates a sanitized copy with:
      - Auth tokens removed (LOGIN_INFO, SAPISID, SSID, HSID, SID, etc.)
      - PREF f6 parameter set to 0 (restricted mode off)
      - Essential visitor/cookies tokens preserved (VISITOR_INFO1_LIVE, PREF, etc.)
    """
    if not YT_COOKIES_FILE or not os.path.isfile(YT_COOKIES_FILE):
        return None

    clean_path = os.path.join(BASE_DIR, "cookies_clean.txt")
    raw = ""
    try:
        with open(YT_COOKIES_FILE, "r", encoding="utf-8") as f:
            raw = f.read()
    except Exception:
        return YT_COOKIES_FILE

    # Remove restricted mode from PREF cookie
    raw = re.sub(r'f6=[^&\t]*', 'f6=0', raw)

    # Filter out auth/secure cookies that trigger Restricted Mode
    auth_patterns = [
        "LOGIN_INFO", "__Secure-1P", "__Secure-3P",
        "SAPISID", "SSID", "HSID", "YSC", "__Secure-YNID",
    ]
    auth_re = re.compile("|".join(auth_patterns))
    lines = raw.splitlines()
    keep = []
    for line in lines:
        if line.startswith("#") or line.strip() == "":
            keep.append(line)
            continue
        if auth_re.search(line):
            continue
        keep.append(line)

    result = "\n".join(keep)
    try:
        with open(clean_path, "w", encoding="utf-8") as f:
            f.write(result)
    except Exception:
        return YT_COOKIES_FILE

    if os.path.getsize(clean_path) > 100:
        return clean_path
    return YT_COOKIES_FILE


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
    """Return yt-dlp arguments for fast info-only operations (search, metadata).

    Lightweight — no throttling or extra delays so info fetches stay fast.
    Still has retries and cookies for bot bypass.

    NOTE: player_client is no longer forced via extractor-args. yt-dlp >=2026
    auto-selects the best client when --cookies is provided. The bgutil POT
    provider extractor args were removed — they were interfering with normal
    extraction and not actually solving the n-challenge.
    """
    _log_cookie_status()
    args = [
        "--no-warnings",
        "--extractor-retries", "3",
        "--user-agent", _get_random_user_agent(),
    ]
    if YT_COOKIES_FILE and os.path.isfile(YT_COOKIES_FILE):
        args.extend(["--cookies", YT_COOKIES_FILE])
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


def search_youtube(query, max_results=10):
    """Search YouTube for videos matching the query using yt-dlp.

    Tries multiple player clients to bypass bot detection.
    """
    def _search(client, timeout):
        cmd = [
            "yt-dlp",
            "--flat-playlist",
            "-J",
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

                if duration and duration > 600:
                    continue

                videos.append({
                    "id": video_id,
                    "title": title,
                    "url": url,
                    "duration": duration,
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
    """Download a full video from YouTube.

    Intentionally does NOT use cookies for download — cookies from browser
    extensions often trigger YouTube Restricted Mode, which limits available
    formats to storyboard images only. Uses android_vr client which works
    without cookies and returns full format access.

    Search (with cookies) is handled separately in download_best_match().

    Args:
        video_url: YouTube URL to download
        output_template: Output file template (default: downloads dir)
        video_id: Video ID for file finding (optional, auto-detected if None)

    Returns:
        Path to downloaded file, or None on failure
    """
    if output_template is None:
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        output_template = os.path.join(DOWNLOADS_DIR, "%(id)s.%(ext)s")

    try:
        # Use clean cookies (auth tokens stripped) to avoid Restricted Mode
        clean_cookies_path = _get_clean_cookies()

        cmd = [
            "yt-dlp",
            "--no-warnings",
            "--extractor-args", "youtube:player_client=android_vr",
            "-f", "best[height<=1080]",
        ]
        if clean_cookies_path:
            cmd += ["--cookies", clean_cookies_path]
        cmd += ["-o", output_template, video_url]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            print("  [downloader] Download timed out", flush=True)
            return None

        # Fallback: if bot detected, try with original cookies (limited formats)
        if result.returncode != 0 and ("sign in" in (result.stderr or "").lower() or "bot" in (result.stderr or "").lower()):
            print("  [downloader] Bot detected with clean cookies, trying original cookies...", flush=True)
            cmd = [
                "yt-dlp",
                "--no-warnings",
                "-f", "best[height<=1080]",
            ]
            if YT_COOKIES_FILE and os.path.isfile(YT_COOKIES_FILE):
                cmd += ["--cookies", YT_COOKIES_FILE]
            cmd += ["-o", output_template, video_url]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            except subprocess.TimeoutExpired:
                print("  [downloader] Download timed out", flush=True)
                return None

        if result.returncode != 0:
            print(f"  [downloader] ERROR: {result.stderr[:300]}", flush=True)
            return None

        # Find the downloaded file
        if video_id:
            for ext in [".mp4", ".webm", ".mkv"]:
                fname = os.path.join(DOWNLOADS_DIR, f"{video_id}{ext}")
                if os.path.exists(fname):
                    print(f"  [downloader] Downloaded: {fname} ({os.path.getsize(fname)} bytes)", flush=True)
                    return fname

        # Fallback: scan downloads dir for any new file
        for ext in [".mp4", ".webm", ".mkv"]:
            for fname in os.listdir(DOWNLOADS_DIR):
                if fname.endswith(ext):
                    fpath = os.path.join(DOWNLOADS_DIR, fname)
                    print(f"  [downloader] Downloaded: {fpath} ({os.path.getsize(fpath)} bytes)", flush=True)
                    return fpath

        print("  [downloader] Downloaded but file not found at expected paths", flush=True)
        return None

    except Exception as e:
        print(f"  [downloader] Error: {e}", flush=True)
        return None


def download_best_match(search_query, used_ids=None):
    """Search and download the best matching video.

    Uses cookies for SEARCH (to bypass CI bot detection) but downloads WITHOUT
    cookies (cookies trigger Restricted Mode which limits formats).

    Args:
        search_query: Search query for YouTube
        used_ids: Set of already-used video IDs to avoid repeats

    Returns:
        Dict with 'path', 'title', 'video_id', 'content_type', or None
    """
    if used_ids is None:
        used_ids = set()

    videos = search_youtube(search_query, max_results=15)

    # Filter out already-used videos
    fresh_videos = [v for v in videos if v["id"] not in used_ids]

    if not fresh_videos:
        if videos:
            print("  [downloader] All recent videos used, picking best available", flush=True)
            fresh_videos = videos
        else:
            print("  [downloader] No videos found for query", flush=True)
            return None

    # Pick a random video from the results (not just the first — for variety)
    chosen = random.choice(fresh_videos[:8])

    print(f"  [downloader] Downloading: {chosen['title']}", flush=True)
    filepath = download_clip(chosen["url"], video_id=chosen["id"])

    if filepath:
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
