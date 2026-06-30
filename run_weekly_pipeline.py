"""
VARY — Weekly Video Pipeline.
Movie story analysis videos: Select → Download → Edit (landscape, text overlays) → SEO → Upload → Cleanup

Usage:
    python run_weekly_pipeline.py                              # Auto-select weekly movie content
    python run_weekly_pipeline.py --query "movie analysis"     # Custom search
"""
import argparse
import json
import os
import sys
import random
import traceback
from datetime import datetime

# Fix Windows console encoding for Unicode characters
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(__file__))

from config import (
    LOG_DIR, DOWNLOADS_DIR, CLIPS_DIR, MOVIE_KEYWORDS,
)
from modules.clip_downloader import download_best_match
from modules.clip_editor import create_weekly_video, remux_to_compatible, get_video_duration
from modules.clip_critique import critique_weekly_video
from modules.seo_generator import generate_weekly_metadata
from modules.thumbnail_generator import generate_weekly_thumbnails
from modules.space_manager import full_cleanup
from modules.content_selector import load_used_scenes, save_used_scene, save_history
from modules.performance_tracker import register_upload
from modules.pipeline_watchdog import (
    register_run_start, register_stage, register_run_complete, register_run_failure,
)


WEEKLY_KEYWORDS = [
    "movie analysis scene breakdown",
    "film story explained",
    "cinematic masterpiece analysis",
    "movie scene explained",
    "film director analysis",
    "movie storytelling breakdown",
]


def log_result(stage, status, details=None):
    """Log a pipeline step result."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "stage": stage,
        "status": status,
        "details": details or {},
    }
    with open(os.path.join(LOG_DIR, "weekly_pipeline_log.jsonl"), "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def run_weekly_pipeline(force_query=None, pipeline_id=None):
    """Run the full weekly video pipeline.

    Args:
        force_query: Force a specific search query

    Returns:
        Dict with results, or raises on failure
    """
    # ── Register with watchdog ─────────────────────────────
    pipeline_id = pipeline_id or register_run_start("weekly")

    print(f"\n{'='*60}")
    print(f"  VARY — Weekly Video Pipeline")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Run: {pipeline_id}")
    print(f"{'='*60}\n")

    # ── Step 1: Content Selection ────────────────────────
    register_stage(pipeline_id, "content_selection")
    print(f">>> Step 1/7: Selecting content...")
    if force_query:
        search_query = force_query
        print(f"  Custom query: {search_query}")
    else:
        search_query = random.choice(WEEKLY_KEYWORDS + MOVIE_KEYWORDS)
        print(f"  Selected: {search_query}")

    content_info = {
        "type": "weekly_movie",
        "search_query": search_query,
    }
    log_result("content_selection", "success", content_info)

    # Record in content history for tracking and streak-avoidance
    save_history({
        "type": "weekly_movie",
        "search_query": search_query,
        "date": datetime.now().isoformat(),
    })

    # ── Step 2: Download Clip ────────────────────────────
    register_stage(pipeline_id, "download")
    print(f"\n>>> Step 2/7: Downloading video...")
    # Load used scenes to avoid re-downloading the same videos
    used = load_used_scenes()
    used_ids = set()
    for key in ["movie_scenes", "worldcup_matches"]:
        for entry in used.get(key, []):
            used_ids.add(entry.get("identifier", ""))

    download_result = download_best_match(search_query, used_ids=used_ids)

    if not download_result:
        print(f"  [FAILED] No video found for query", flush=True)
        log_result("download", "failed", {"search": search_query})
        # Try once more with a different query
        alt_query = random.choice([q for q in WEEKLY_KEYWORDS if q != search_query] or WEEKLY_KEYWORDS)
        print(f"  Retrying with: {alt_query}", flush=True)
        download_result = download_best_match(alt_query, used_ids=used_ids)

    if not download_result:
        raise Exception(f"Failed to download video for: {search_query}")

    print(f"  Downloaded: {download_result['title']}", flush=True)
    log_result("download", "success", download_result)

    # ── Step 3: Edit Weekly Video ────────────────────────
    register_stage(pipeline_id, "editing")
    print(f"\n>>> Step 3/7: Creating weekly video with story text...")
    import uuid
    output_path = os.path.join(CLIPS_DIR, f"weekly_{uuid.uuid4().hex[:10]}.mp4")

    weekly_result = create_weekly_video(
        download_result["path"],
        output_path,
        source_title=download_result["title"],
    )

    if not weekly_result:
        raise Exception("Weekly video creation failed")

    print(f"  Weekly video duration: {weekly_result.get('duration', 0):.1f}s", flush=True)
    log_result("editing", "success", weekly_result)

    # ── Step 4: Critique ───────────────────────────────────
    register_stage(pipeline_id, "critique")
    print(f"\n>>> Step 4/7: Critiquing weekly video...")
    critique_result = critique_weekly_video(
        weekly_result["path"],
        source_title=download_result["title"],
        source_duration=weekly_result.get("duration", 0),
    )

    if critique_result:
        print(f"  [critique] Score: {critique_result['compound_score']:.1f}/100", flush=True)
        print(f"  [critique] Axes: {json.dumps(critique_result['axes'])}", flush=True)
        log_result("critique", "success", {
            "compound_score": critique_result["compound_score"],
            "axes": critique_result["axes"],
        })
    else:
        print(f"  [WARNING] Weekly critique failed, continuing without", flush=True)
        log_result("critique", "skipped", {"reason": "critique returned None"})

    # ── Step 5: Generate Thumbnails (landscape variants) ──
    register_stage(pipeline_id, "thumbnails")
    print(f"\n>>> Step 5/7: Generating landscape thumbnails...")
    thumbnails = generate_weekly_thumbnails(
        weekly_result["path"],
        download_result["title"][:50],
    )

    if not thumbnails:
        print(f"  [WARNING] Weekly thumbnail generation failed, continuing without", flush=True)
        thumbnails = {}

    log_result("thumbnails", "success" if thumbnails else "skipped", {"variants": list(thumbnails.keys())})

    # ── Step 6: Generate SEO ─────────────────────────────
    register_stage(pipeline_id, "seo")
    print(f"\n>>> Step 6/7: Generating SEO metadata...")
    seo = generate_weekly_metadata(
        download_result["title"],
        source_url=download_result.get("url"),
    )

    print(f"  Title: {seo['title']}", flush=True)
    print(f"  Tags: {len(seo['tags'])} tags", flush=True)

    # ── Step 7: Upload to YouTube ────────────────────────
    register_stage(pipeline_id, "upload")
    print(f"\n>>> Step 7/7: Uploading to YouTube...")

    # Pick the best thumbnail (prefer v3, then v2, then v1)
    best_thumb = None
    for variant in ["v3", "v2", "v1"]:
        if variant in thumbnails:
            best_thumb = thumbnails[variant]
            break

    video_id = None
    video_url = None

    try:
        from modules.youtube_uploader import upload_video

        video_id, response = upload_video(
            video_path=weekly_result["path"],
            title=seo["title"],
            description=seo["description"],
            tags=seo["tags"],
            thumbnail_path=best_thumb,
            privacy_status="public",
        )

        video_url = f"https://youtu.be/{video_id}"
        print(f"\n  ✅ UPLOADED: {seo['title']}", flush=True)
        print(f"  URL: {video_url}", flush=True)
        log_result("upload", "success", {"video_id": video_id, "url": video_url})

    except Exception as e:
        print(f"  [FAILED] Upload error: {e}", flush=True)
        log_result("upload", "failed", {"error": str(e)})

    # ── Performance Registration ─────────────────────────
    if video_id:
        try:
            register_upload(
                video_id=video_id,
                title=download_result["title"],
                content_type="weekly_movie",
                search_query=search_query,
                seo_title=seo["title"],
            )
            print(f"  Registered for performance tracking: {video_id}", flush=True)
            log_result("performance_register", "success", {"video_id": video_id})
        except Exception as e:
            print(f"  [SKIP] Performance register error: {e}", flush=True)
            log_result("performance_register", "skipped", {"error": str(e)})

    # ── Mark as used to avoid repeat ─────────────────────
    if download_result.get("video_id"):
        save_used_scene("movie", download_result["video_id"])

    # ── Space Cleanup ─────────────────────────────────────
    print(f"\n>>> Cleaning up all downloaded files...")
    # Build list of everything to delete: source download + processed clip + thumbnails
    paths_to_clean = [download_result["path"]]
    if weekly_result:
        paths_to_clean.append(weekly_result["path"])
    for variant in thumbnails.values():
        if variant and os.path.exists(variant):
            paths_to_clean.append(variant)
    space_info = full_cleanup(paths_to_clean)

    # ── Mark complete in watchdog ─────────────────────────
    register_run_complete(pipeline_id)

    # ── Summary ──────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  ✅ WEEKLY PIPELINE COMPLETE")
    print(f"  Source: {download_result['title']}")
    print(f"  Run ID: {pipeline_id}")
    if video_url:
        print(f"  Uploaded: {video_url}")
    print(f"  Duration: {weekly_result.get('duration', 0):.1f}s")
    print(f"  Space: {space_info.get('size_mb', 0):.1f} MB used")
    print(f"{'='*60}\n")

    return {
        "source_title": download_result["title"],
        "video_path": weekly_result["path"],
        "seo_title": seo["title"],
        "video_id": video_id,
        "video_url": video_url,
        "duration": weekly_result.get("duration", 0),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VARY — Weekly Video Pipeline")
    parser.add_argument("--query", default=None,
                        help="Custom search query")
    args = parser.parse_args()

    from modules.pipeline_watchdog import register_run_start, register_run_failure
    pipeline_id = register_run_start("weekly")
    try:
        result = run_weekly_pipeline(force_query=args.query, pipeline_id=pipeline_id)
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(f"\n  ❌ WEEKLY PIPELINE CRASHED: {e}", flush=True)
        traceback.print_exc()
        register_run_failure(pipeline_id, str(e))
        sys.exit(1)