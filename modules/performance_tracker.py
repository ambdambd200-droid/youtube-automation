"""
VARY Performance Tracker — fetches real YouTube analytics and turns them
into evolution signals.

This is the bridge between simulated critique scores and actual viewer behavior.
A clip can score 95/100 in critique but get 10 views. That gap is where
the evolution engine learns what truly resonates.

Data Sources:
  - YouTube Data API v3 (videos.list with statistics part)
  - Views, likes, comments, (estimated) retention

Signals:
  - view_velocity: views per hour since upload
  - like_ratio: likes / views * 100
  - engagement_rate: (likes + comments) / views * 100
  - retention_estimate: inferred from view count patterns
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LOG_DIR


PERFORMANCE_LOG = os.path.join(LOG_DIR, "performance_log.jsonl")
UPLOAD_REGISTRY = os.path.join(LOG_DIR, "upload_registry.json")


# ── Upload Registry ─────────────────────────────────────────


def _load_registry():
    """Load the registry of uploaded videos."""
    if os.path.exists(UPLOAD_REGISTRY):
        try:
            with open(UPLOAD_REGISTRY, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"videos": []}


def _save_registry(registry):
    """Save upload registry."""
    os.makedirs(os.path.dirname(UPLOAD_REGISTRY), exist_ok=True)
    with open(UPLOAD_REGISTRY, "w") as f:
        json.dump(registry, f, indent=2)


def register_upload(video_id, title, content_type, search_query, seo_title,
                    critique_score=None, critique_grade=None):
    """Register a video upload for future performance tracking.

    Called by the pipeline after a successful upload.
    """
    registry = _load_registry()

    # Avoid duplicates
    for v in registry["videos"]:
        if v["video_id"] == video_id:
            return v

    entry = {
        "video_id": video_id,
        "title": title,
        "content_type": content_type,
        "search_query": search_query,
        "seo_title": seo_title,
        "critique_score": critique_score,
        "critique_grade": critique_grade,
        "uploaded_at": datetime.now().isoformat(),
        "last_fetched": None,
    }
    registry["videos"].append(entry)
    _save_registry(registry)
    return entry


def get_unfetched_videos():
    """Get videos that haven't had their stats fetched yet (or fetched long ago)."""
    registry = _load_registry()
    now = datetime.now()
    stale = []
    for v in registry["videos"]:
        if v.get("last_fetched"):
            try:
                last = datetime.fromisoformat(v["last_fetched"])
                # Only re-fetch if > 6 hours old
                if now - last < timedelta(hours=6):
                    continue
            except (ValueError, TypeError):
                pass
        stale.append(v)
    return stale


def get_all_tracked_videos():
    """Get all videos ever uploaded, ordered by upload time (newest first)."""
    registry = _load_registry()
    videos = sorted(registry["videos"], key=lambda v: v.get("uploaded_at", ""), reverse=True)
    return videos


# ── YouTube API Calls ─────────────────────────────────────


def _get_youtube_service():
    """Get authenticated YouTube service for read-only stats fetching.

    Gracefully handles sys.exit() from auth failures by catching BaseException.
    """
    try:
        from modules.youtube_uploader import get_authenticated_service
        return get_authenticated_service()
    except BaseException as e:
        print(f"  [performance] Auth error: {e}", flush=True)
        return None


def fetch_video_stats(video_id):
    """Fetch statistics for a single YouTube video.

    Args:
        video_id: YouTube video ID.

    Returns:
        Dict with statistics, or None on failure.
    """
    try:
        youtube = _get_youtube_service()
        if not youtube:
            print(f"  [performance] No YouTube service (auth failed)", flush=True)
            return None
        request = youtube.videos().list(
            part="statistics,snippet",
            id=video_id,
        )
        response = request.execute()
        items = response.get("items", [])
        if not items:
            print(f"  [performance] No data for video {video_id}", flush=True)
            return None

        item = items[0]
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})

        view_count = int(stats.get("viewCount", 0))
        like_count = int(stats.get("likeCount", 0))
        comment_count = int(stats.get("commentCount", 0))

        return {
            "video_id": video_id,
            "view_count": view_count,
            "like_count": like_count,
            "comment_count": comment_count,
            "title": snippet.get("title", ""),
            "published_at": snippet.get("publishedAt", ""),
        }
    except Exception as e:
        print(f"  [performance] YouTube API error for {video_id}: {e}", flush=True)
        return None


def fetch_all_video_stats(video_ids, delay=0.5):
    """Fetch stats for multiple videos with rate limiting.

    Args:
        video_ids: List of YouTube video IDs.
        delay: Seconds between API calls (YouTube quota management).

    Returns:
        List of stats dicts.
    """
    results = []
    for vid in video_ids:
        stats = fetch_video_stats(vid)
        if stats:
            results.append(stats)
        if delay > 0:
            time.sleep(delay)
    return results


# ── Performance Signal Calculation ─────────────────────────


def calculate_signals(stats, upload_time):
    """Calculate performance signals from raw stats.

    Args:
        stats: Dict with view_count, like_count, comment_count.
        upload_time: ISO datetime string of when the video was uploaded.

    Returns:
        Dict of derived performance signals.
    """
    view_count = stats.get("view_count", 0)
    like_count = stats.get("like_count", 0)
    comment_count = stats.get("comment_count", 0)

    # Hours since upload
    try:
        uploaded = datetime.fromisoformat(upload_time)
    except (ValueError, TypeError):
        uploaded = datetime.now() - timedelta(days=1)
    hours_since = max(1, (datetime.now() - uploaded).total_seconds() / 3600)

    # View velocity (views per hour)
    view_velocity = round(view_count / hours_since, 1)

    # Like ratio (likes per 100 views)
    like_ratio = round((like_count / max(view_count, 1)) * 100, 2)

    # Engagement rate (likes + comments per 100 views)
    engagement_rate = round(
        ((like_count + comment_count) / max(view_count, 1)) * 100, 2
    )

    # Performance tiers (based on typical Shorts benchmarks)
    if view_count >= 10000:
        view_tier = "viral"
    elif view_count >= 1000:
        view_tier = "strong"
    elif view_count >= 100:
        view_tier = "moderate"
    else:
        view_tier = "low"

    if like_ratio >= 8.0:
        engagement_tier = "excellent"
    elif like_ratio >= 4.0:
        engagement_tier = "good"
    elif like_ratio >= 2.0:
        engagement_tier = "average"
    else:
        engagement_tier = "weak"

    # Compound performance score (0-100), real-world version of critique score
    # Weight: views matter most, then engagement
    view_score = min(100, (view_count / 5000) * 100) if view_count < 5000 else 100
    like_score = min(100, (like_ratio / 10) * 100)
    comment_score = min(100, comment_count * 10)
    velocity_score = min(100, (view_velocity / 50) * 100)

    compound = round(
        view_score * 0.30 +
        like_score * 0.30 +
        velocity_score * 0.25 +
        comment_score * 0.15,
        1,
    )

    return {
        "view_velocity": view_velocity,
        "like_ratio": like_ratio,
        "engagement_rate": engagement_rate,
        "view_tier": view_tier,
        "engagement_tier": engagement_tier,
        "performance_score": compound,
        "hours_since_upload": round(hours_since, 1),
    }


# ── Main Fetch & Log ──────────────────────────────────────


def fetch_and_log_performance(video_id, upload_time):
    """Fetch stats for one video, calculate signals, and log them.

    Args:
        video_id: YouTube video ID.
        upload_time: ISO datetime string of upload.

    Returns:
        Dict with results, or None on failure.
    """
    stats = fetch_video_stats(video_id)
    if not stats:
        return None

    signals = calculate_signals(stats, upload_time)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "video_id": video_id,
        "fetched_at": datetime.now().isoformat(),
        "raw_stats": stats,
        "signals": signals,
    }

    # Append to performance log
    os.makedirs(os.path.dirname(PERFORMANCE_LOG), exist_ok=True)
    with open(PERFORMANCE_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

    # Update registry with last_fetched
    registry = _load_registry()
    for v in registry["videos"]:
        if v["video_id"] == video_id:
            v["last_fetched"] = datetime.now().isoformat()
            v["last_stats"] = stats
            v["last_signals"] = signals
            break
    _save_registry(registry)

    print(f"  [performance] {video_id}: {stats['view_count']} views, "
          f"{signals['like_ratio']}% likes, score={signals['performance_score']:.1f}",
          flush=True)

    return entry


def poll_all_videos():
    """Fetch performance data for all unfetched/stale videos.

    Designed to be called periodically (e.g., from GitHub Actions or cron).

    Returns:
        List of performance entries.
    """
    print(f">>> Polling YouTube video performance...", flush=True)
    videos = get_unfetched_videos()

    if not videos:
        print(f"  [performance] No videos to poll", flush=True)
        return []

    print(f"  Polling {len(videos)} videos...", flush=True)
    results = []
    for v in videos:
        entry = fetch_and_log_performance(
            v["video_id"],
            v.get("uploaded_at", ""),
        )
        if entry:
            results.append(entry)

    print(f"  Done. Updated {len(results)}/{len(videos)} videos.", flush=True)
    return results


# ── Trend Analysis for Evolution Engine ───────────────────

# Performance signal weights for evolution (higher = more influence)
PERFORMANCE_WEIGHTS = {
    "view_velocity": 0.25,
    "like_ratio": 0.30,
    "engagement_rate": 0.25,
    "performance_score": 0.20,
}


def load_performance_history(hours=168):
    """Load performance entries from the last N hours (default: 7 days).

    Returns:
        List of performance entries.
    """
    if not os.path.exists(PERFORMANCE_LOG):
        return []

    entries = []
    cutoff = datetime.now() - timedelta(hours=hours)

    try:
        with open(PERFORMANCE_LOG, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        ts = datetime.fromisoformat(entry.get("fetched_at", ""))
                        if ts > cutoff:
                            entries.append(entry)
                    except (json.JSONDecodeError, ValueError, TypeError):
                        continue
    except IOError:
        return []

    return entries


def calculate_performance_trends(entries=None):
    """Calculate performance trends across all tracked videos.

    Args:
        entries: Optional list of performance entries (loads from log if None).

    Returns:
        Dict with trend data, or None if no data.
    """
    if entries is None:
        entries = load_performance_history()

    if not entries:
        return None

    # Use the latest entry per video_id (most recent fetch)
    latest_by_video = {}
    for e in entries:
        vid = e.get("video_id")
        if vid:
            latest_by_video[vid] = e  # later entries overwrite earlier ones

    signals = [e.get("signals", {}) for e in latest_by_video.values() if e.get("signals")]

    if not signals:
        return None

    avg_view_velocity = sum(s.get("view_velocity", 0) for s in signals) / len(signals)
    avg_like_ratio = sum(s.get("like_ratio", 0) for s in signals) / len(signals)
    avg_engagement = sum(s.get("engagement_rate", 0) for s in signals) / len(signals)
    avg_performance = sum(s.get("performance_score", 0) for s in signals) / len(signals)

    # Load the upload registry to correlate with content_type, etc.
    registry = _load_registry()
    registry_by_id = {v["video_id"]: v for v in registry.get("videos", [])}

    # Per-type performance
    type_scores = defaultdict(list)
    for e in latest_by_video.values():
        vid = e.get("video_id", "")
        reg = registry_by_id.get(vid, {})
        ct = reg.get("content_type", "unknown")
        ps = e.get("signals", {}).get("performance_score", 0)
        type_scores[ct].append(ps)

    type_avgs = {ct: round(sum(vals) / len(vals), 1) for ct, vals in type_scores.items()}

    # Correlation: critique score vs performance score
    critique_vs_performance = []
    for e in latest_by_video.values():
        vid = e.get("video_id", "")
        reg = registry_by_id.get(vid, {})
        cs = reg.get("critique_score")
        ps = e.get("signals", {}).get("performance_score", 0)
        if cs is not None:
            critique_vs_performance.append({
                "video_id": vid,
                "critique_score": cs,
                "performance_score": ps,
                "delta": round(ps - cs, 1),
            })

    avg_delta = 0
    if critique_vs_performance:
        avg_delta = round(
            sum(c["delta"] for c in critique_vs_performance) / len(critique_vs_performance), 1
        )

    return {
        "videos_tracked": len(latest_by_video),
        "total_data_points": len(entries),
        "average_view_velocity": round(avg_view_velocity, 1),
        "average_like_ratio": round(avg_like_ratio, 2),
        "average_engagement_rate": round(avg_engagement, 2),
        "average_performance_score": round(avg_performance, 1),
        "type_averages": dict(type_avgs),
        "critique_vs_performance": {
            "videos_with_both": len(critique_vs_performance),
            "average_delta": avg_delta,
            "critique_underestimates_by": max(0, avg_delta),
            "critique_overestimates_by": max(0, -avg_delta),
        },
    }


# ── API Data ──────────────────────────────────────────────


def get_performance_summary():
    """Get a summary of performance data for API display."""
    registry = _load_registry()
    total = len(registry.get("videos", []))
    fetched = sum(1 for v in registry["videos"] if v.get("last_fetched"))
    trends = calculate_performance_trends()

    return {
        "total_videos_uploaded": total,
        "videos_with_performance_data": fetched,
        "trends": trends,
    }


def get_performance_for_video(video_id):
    """Get all performance history for a specific video."""
    entries = load_performance_history(hours=24 * 365)  # up to 1 year
    video_entries = [e for e in entries if e.get("video_id") == video_id]

    if not video_entries:
        # Try to fetch fresh data
        registry = _load_registry()
        for v in registry.get("videos", []):
            if v["video_id"] == video_id:
                return fetch_and_log_performance(video_id, v.get("uploaded_at", ""))
        return None

    return video_entries[-1]  # Most recent


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--poll":
        result = poll_all_videos()
        print(json.dumps({"polled": len(result)}, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "--trends":
        trends = calculate_performance_trends()
        print(json.dumps(trends, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "--summary":
        summary = get_performance_summary()
        print(json.dumps(summary, indent=2))
    else:
        print("Usage:")
        print("  python -m modules.performance_tracker --poll")
        print("  python -m modules.performance_tracker --trends")
        print("  python -m modules.performance_tracker --summary")
