"""
VARY — Flask API server for n8n orchestration.
Endpoints for the clip-based daily Shorts pipeline.
Run: python api_server.py
Runs on: http://localhost:5001
"""
import os
import sys
import random
from datetime import datetime

# Fix Windows console encoding for Unicode characters
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from flask import Flask, request, jsonify

sys.path.insert(0, os.path.dirname(__file__))

from config import (
    CLIPS_DIR, THUMBNAILS_DIR, DOWNLOADS_DIR, LOG_DIR, is_world_cup_active,
)
from modules.content_selector import select_today_content, load_used_scenes
from modules.clip_downloader import download_best_match
from modules.clip_editor import create_clip
from modules.thumbnail_generator import generate_thumbnails
from modules.seo_generator import generate_metadata
from modules.space_manager import full_cleanup

app = Flask(__name__)

# Ensure all dirs exist
for d in [CLIPS_DIR, THUMBNAILS_DIR, DOWNLOADS_DIR, LOG_DIR]:
    os.makedirs(d, exist_ok=True)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "channel": "VARY", "timestamp": datetime.now().isoformat()})


@app.route("/select-content", methods=["POST"])
def select_content():
    """Step 1: Select today's content type and search query."""
    data = request.get_json() or {}
    force_type = data.get("type")  # "worldcup_2026" or "movie"
    force_query = data.get("query")

    try:
        if force_type or force_query:
            from config import WORLDCUP_KEYWORDS, MOVIE_KEYWORDS
            content_info = {
                "type": force_type or "custom",
                "search_query": force_query or random.choice(
                    WORLDCUP_KEYWORDS if force_type == "worldcup_2026" else MOVIE_KEYWORDS
                ),
                "description": f"{'Forced: ' + force_type if force_type else 'Custom: ' + force_query}",
            }
        else:
            content_info = select_today_content()

        return jsonify(content_info)
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/download-clip", methods=["POST"])
def download_clip():
    """Step 2: Download a clip based on search query."""
    data = request.get_json() or {}
    search_query = data.get("search_query", "")
    content_type = data.get("type", "movie")

    if not search_query:
        return jsonify({"error": "No search_query provided"}), 400

    try:
        used = load_used_scenes()
        used_ids = set()
        for key in ["movie_scenes", "worldcup_matches"]:
            for entry in used.get(key, []):
                used_ids.add(entry.get("identifier", ""))

        result = download_best_match(search_query, used_ids=used_ids)

        if not result:
            return jsonify({"error": f"No video found for: {search_query}"}), 404

        return jsonify({
            "status": "downloaded",
            "path": result["path"],
            "title": result["title"],
            "video_id": result["video_id"],
            "url": result.get("url", ""),
            "duration": result.get("duration", 0),
        })
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/edit-clip", methods=["POST"])
def edit_clip():
    """Step 3: Edit downloaded clip to Shorts format."""
    data = request.get_json() or {}
    source_path = data.get("source_path", "")
    content_type = data.get("type", "movie")
    title = data.get("title", "")

    if not source_path or not os.path.exists(source_path):
        return jsonify({"error": f"Source file not found: {source_path}"}), 400

    try:
        result = create_clip(source_path, content_type, title=title)

        if not result:
            return jsonify({"error": "Clip editing failed"}), 500

        return jsonify({
            "status": "edited",
            "path": result["path"],
            "duration": result.get("duration", 0),
            "content_type": content_type,
            "source_title": title,
        })
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/generate-thumbnail", methods=["POST"])
def generate_thumbnail():
    """Step 4: Generate thumbnail variants from the processed clip."""
    data = request.get_json() or {}
    video_path = data.get("video_path", "")
    title = data.get("title", "VARY Clip")
    content_type = data.get("type", "movie")

    if not video_path or not os.path.exists(video_path):
        return jsonify({"error": f"Video file not found: {video_path}"}), 400

    try:
        variants = generate_thumbnails(video_path, title, content_type)

        return jsonify({
            "status": "generated" if variants else "skipped",
            "variants": variants or {},
        })
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/generate-seo", methods=["POST"])
def generate_seo():
    """Step 5: Generate SEO metadata."""
    data = request.get_json() or {}
    source_title = data.get("source_title", "")
    content_type = data.get("type", "movie")
    source_url = data.get("source_url", "")

    try:
        metadata = generate_metadata(source_title, content_type, source_url)

        return jsonify({
            "status": "generated",
            "title": metadata["title"],
            "description": metadata["description"],
            "tags": metadata["tags"],
        })
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/upload", methods=["POST"])
def upload():
    """Step 6: Upload to YouTube."""
    data = request.get_json() or {}
    video_path = data.get("video_path", "")
    title = data.get("title", "VARY Clip")
    description = data.get("description", "")
    tags = data.get("tags", [])
    thumbnail_path = data.get("thumbnail_path")

    if not video_path or not os.path.exists(video_path):
        return jsonify({"error": f"Video file not found: {video_path}"}), 400

    try:
        from modules.youtube_uploader import upload_video

        video_id, response = upload_video(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            thumbnail_path=thumbnail_path if thumbnail_path and os.path.exists(thumbnail_path) else None,
            privacy_status="public",
        )

        return jsonify({
            "status": "uploaded",
            "video_id": video_id,
            "url": f"https://youtu.be/{video_id}",
            "title": title,
        })
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/cleanup", methods=["POST"])
def cleanup():
    """Step 7: Delete source files and free space."""
    data = request.get_json() or {}
    source_paths = data.get("source_paths", [])

    try:
        space_info = full_cleanup(source_paths)
        return jsonify({
            "status": "cleaned",
            "space": space_info,
        })
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/run-full-pipeline", methods=["POST"])
def run_full_pipeline():
    """Run the complete pipeline end-to-end."""
    data = request.get_json() or {}
    force_type = data.get("type")
    force_query = data.get("query")

    try:
        from run_pipeline import run_pipeline

        result = run_pipeline(force_type=force_type, force_query=force_query)

        return jsonify({
            "status": "complete",
            "result": result,
        })
    except Exception as ex:
        return jsonify({
            "status": "failed",
            "error": str(ex),
        }), 500


@app.route("/channel-info", methods=["GET"])
def channel_info():
    """Get current YouTube channel information."""
    try:
        from modules.channel_manager import get_channel_info
        info = get_channel_info()
        if info:
            info["world_cup_active"] = is_world_cup_active()
            return jsonify(info)
        return jsonify({"error": "Could not fetch channel info"}), 500
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/update-channel", methods=["POST"])
def update_channel():
    """Update channel branding (description, profile pic, banner)."""
    try:
        from modules.channel_manager import check_and_update_channel
        result = check_and_update_channel()
        return jsonify({
            "status": "complete",
            "result": result,
        })
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/generate-branding", methods=["POST"])
def generate_branding():
    """Generate channel profile picture and banner assets."""
    try:
        from modules.channel_branding_generator import generate_all_branding
        result = generate_all_branding()
        return jsonify({
            "status": "generated",
            "profile_picture": result.get("profile_picture"),
            "banner": result.get("banner"),
            "directory": result.get("directory"),
        })
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


# ── Critique & Evolution Endpoints ─────────────────────────


@app.route("/critique-clip", methods=["POST"])
def critique_clip_endpoint():
    """Run critique analysis on a processed clip."""
    data = request.get_json() or {}
    video_path = data.get("video_path", "")
    content_type = data.get("type", "movie")
    source_title = data.get("title", "")
    duration = data.get("duration", 0)

    if not video_path or not os.path.exists(video_path):
        return jsonify({"error": f"Video not found: {video_path}"}), 400

    try:
        from modules.clip_critique import critique_clip
        result = critique_clip(video_path, content_type, source_title, duration)
        if result:
            return jsonify({
                "status": "critiqued",
                "compound_score": result["compound_score"],
                "grade": result["grade"],
                "axes": result["axes"],
                "recommendations": result["recommendations"],
            })
        return jsonify({"error": "Critique returned no result"}), 500
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/critique-history", methods=["GET"])
def critique_history():
    """Get critique history and trend summary."""
    try:
        from modules.clip_critique import load_critique_history, get_trend_summary
        count = request.args.get("count", 50, type=int)
        entries = load_critique_history(n=count)
        trends = get_trend_summary(entries)
        return jsonify({
            "count": len(entries),
            "trends": trends,
        })
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/evolution-status", methods=["GET"])
def evolution_status():
    """Get current evolution engine state."""
    try:
        from modules.evolution_engine import get_evolution_status
        status = get_evolution_status()
        return jsonify(status)
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/evolution-run", methods=["POST"])
def evolution_run():
    """Run one evolution cycle manually."""
    try:
        from modules.evolution_engine import evolve
        result = evolve()
        return jsonify({
            "status": "evolved" if result.get("evolved") else "no_change",
            "generation": result.get("generation"),
            "mutations": result.get("mutations", 0),
            "trends": result.get("trends", {}),
        })
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/evolution-reset", methods=["POST"])
def evolution_reset():
    """Reset evolution engine to defaults."""
    try:
        from modules.evolution_engine import reset_evolution
        reset_evolution()
        return jsonify({"status": "reset"})
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


# ── Performance Tracking Endpoints ─────────────────────────


@app.route("/performance-summary", methods=["GET"])
def performance_summary():
    """Get performance tracking summary."""
    try:
        from modules.performance_tracker import get_performance_summary
        summary = get_performance_summary()
        return jsonify(summary)
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/performance-poll", methods=["POST"])
def performance_poll():
    """Fetch performance data for all stale videos."""
    try:
        from modules.performance_tracker import poll_all_videos
        results = poll_all_videos()
        return jsonify({
            "status": "polled",
            "videos_updated": len(results),
        })
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/performance/video/<video_id>", methods=["GET"])
def performance_video(video_id):
    """Get performance data for a specific video."""
    try:
        from modules.performance_tracker import get_performance_for_video
        data = get_performance_for_video(video_id)
        if data:
            return jsonify(data)
        return jsonify({"error": "No data for this video"}), 404
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/performance/videos", methods=["GET"])
def performance_videos():
    """Get all tracked videos."""
    try:
        from modules.performance_tracker import get_all_tracked_videos
        videos = get_all_tracked_videos()
        return jsonify({
            "count": len(videos),
            "videos": videos,
        })
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


# ── Pipeline Watchdog Endpoints ────────────────────────────


@app.route("/pipeline-health", methods=["GET"])
def pipeline_health():
    """Get the pipeline watchdog health summary.

    Returns total runs, completed/failed/running counts,
    recent failures, recovery retries, and recent activity.
    """
    try:
        from modules.pipeline_watchdog import get_runs_summary
        summary = get_runs_summary()
        return jsonify(summary)
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


@app.route("/pipeline-prune", methods=["POST"])
def pipeline_prune():
    """Prune old pipeline state entries.

    Optional JSON body:
      - days: entries older than this many days are pruned (default: 7)

    Returns:
      - pruned: number of entries removed
      - remaining: number of entries left
    """
    try:
        from modules.pipeline_watchdog import load_state, save_state, prune_old_state
        data = request.get_json() or {}
        days = data.get("days")
        state = load_state()
        pruned, remaining = prune_old_state(state, days=days)
        save_state(state)
        return jsonify({
            "status": "pruned",
            "pruned": pruned,
            "remaining": remaining,
        })
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


# ── Dashboard Endpoint ─────────────────────────────────────


@app.route("/dashboard", methods=["GET"])
def dashboard():
    """Return the full performance dashboard data as JSON.

    Includes critique comparison (daily vs weekly), real YouTube metrics,
    grade distribution, upload timeline, top performers, and evolution status.
    """
    try:
        from run_performance_dashboard import build_dashboard_data
        data = build_dashboard_data()
        return jsonify(data)
    except Exception as ex:
        return jsonify({"error": str(ex)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("API_PORT", 5001))
    print(f"Starting VARY API on port {port}...")
    app.run(host="127.0.0.1", port=port, debug=False)
