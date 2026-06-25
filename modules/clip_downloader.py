"""
Clip Downloader — downloads video clips from YouTube using yt-dlp.
Handles both World Cup match highlights and movie scenes.
"""
import json
import os
import subprocess
import sys
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DOWNLOADS_DIR


def search_youtube(query, max_results=10):
    """Search YouTube for videos matching the query using yt-dlp."""
    try:
        cmd = [
            "yt-dlp",
            "--flat-playlist",
            "-J",
            f"ytsearch{max_results}:{query}",
            "--no-warnings",
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            print(f"  [downloader] Search error: {result.stderr[:200]}", flush=True)
            return []

        data = json.loads(result.stdout)
        entries = data.get("entries", [])
        videos = []
        for entry in entries:
            video_id = entry.get("id", "")
            title = entry.get("title", "")
            duration = entry.get("duration", 0)
            url = entry.get("webpage_url", f"https://youtu.be/{video_id}")

            # Filter: only short-ish videos (under 10 min) or any if labeled as short
            if duration and duration > 600:  # Skip videos longer than 10 min
                continue

            videos.append({
                "id": video_id,
                "title": title,
                "url": url,
                "duration": duration,
            })

        return videos

    except subprocess.TimeoutExpired:
        print("  [downloader] Search timed out", flush=True)
        return []
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  [downloader] Parse error: {e}", flush=True)
        return []


def download_clip(video_url, output_template=None, max_duration=60):
    """Download a video clip from YouTube.

    Args:
        video_url: YouTube URL to download
        output_template: Output file template (default: downloads dir)
        max_duration: Maximum duration in seconds to download

    Returns:
        Path to downloaded file, or None on failure
    """
    if output_template is None:
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        output_template = os.path.join(DOWNLOADS_DIR, "%(id)s.%(ext)s")

    # First, get info about the video
    try:
        info_cmd = [
            "yt-dlp",
            "-J",
            video_url,
            "--no-warnings",
        ]
        info_result = subprocess.run(
            info_cmd, capture_output=True, text=True, timeout=30
        )
        if info_result.returncode != 0:
            print(f"  [downloader] Info error: {info_result.stderr[:200]}", flush=True)
            return None

        info = json.loads(info_result.stdout)
        duration = info.get("duration", 0)
        video_id = info.get("id", "unknown")
        title = info.get("title", "unknown")

        # For long videos, we'll download only a segment
        # For short videos (< 2 min), download the whole thing
        if duration and duration > 120:
            # Pick a random 60-second segment from the video
            start_time = random.randint(0, max(0, int(duration) - max_duration))
            print(f"  [downloader] Video is {duration}s long, extracting {max_duration}s from {start_time}s", flush=True)

            download_cmd = [
                "yt-dlp",
                "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
                "--download-sections", f"*{start_time}-{start_time + max_duration}",
                "--force-keyframes-at-cuts",
                "--no-warnings",
                "-o", output_template,
                video_url,
            ]
        else:
            # Short video — download full
            download_cmd = [
                "yt-dlp",
                "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
                "--no-warnings",
                "-o", output_template,
                video_url,
            ]

        result = subprocess.run(
            download_cmd, capture_output=True, text=True, timeout=300
        )

        if result.returncode != 0:
            print(f"  [downloader] Download error: {result.stderr[:300]}", flush=True)
            return None

        # Find the downloaded file
        base = os.path.splitext(output_template.split("%(ext)s")[0])[0]
        for ext in [".mp4", ".webm", ".mkv"]:
            fname = f"{base}{ext}".replace("%(id)s", video_id)
            # Also check with the video id pattern from yt-dlp
            fname2 = os.path.join(DOWNLOADS_DIR, f"{video_id}{ext}")
            for path_candidate in [fname, fname2]:
                if os.path.exists(path_candidate):
                    print(f"  [downloader] Downloaded: {path_candidate} ({os.path.getsize(path_candidate)} bytes)", flush=True)
                    return path_candidate

        # If we couldn't find the file, list the downloads dir
        print(f"  [downloader] Downloaded but file not found at expected paths", flush=True)
        return None

    except subprocess.TimeoutExpired:
        print("  [downloader] Download timed out", flush=True)
        return None
    except Exception as e:
        print(f"  [downloader] Error: {e}", flush=True)
        return None


def download_best_match(search_query, used_ids=None):
    """Search and download the best matching video.

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
        # If all used, try with a broader query
        if videos:
            print("  [downloader] All recent videos used, picking best available", flush=True)
            fresh_videos = videos
        else:
            print("  [downloader] No videos found for query", flush=True)
            return None

    # Pick a random video from the results (not just the first — for variety)
    chosen = random.choice(fresh_videos[:8])

    print(f"  [downloader] Downloading: {chosen['title']}", flush=True)
    filepath = download_clip(chosen["url"])

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
