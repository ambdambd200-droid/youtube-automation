"""
VARY — Main Pipeline Runner.
Daily clip-based pipeline: Select → Download → Edit → Thumbnail → Upload → Cleanup

Usage:
    python run_pipeline.py                     # Auto-select content (random daily)
    python run_pipeline.py --type worldcup     # Force World Cup content
    python run_pipeline.py --type movie        # Force movie content
    python run_pipeline.py --query "custom search"  # Custom search
"""
import argparse
import json
import os
import sys
import random
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from config import (
    CHANNEL_NAME, CLIPS_DIR, CLIP_MIN_DURATION, CLIP_MAX_DURATION,
    LOG_DIR, WORLDCUP_KEYWORDS, MOVIE_KEYWORDS,
)
from modules.content_selector import select_today_content, load_used_scenes, save_used_scene
from modules.clip_downloader import download_best_match
from modules.clip_editor import create_clip
from modules.thumbnail_generator import generate_thumbnails
from modules.seo_generator import generate_metadata
from modules.space_manager import full_cleanup


def log_result(stage, status, details=None):
    """Log a pipeline step result."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "stage": stage,
        "status": status,
        "details": details or {},
    }
    with open(os.path.join(LOG_DIR, "pipeline_log.jsonl"), "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def run_pipeline(force_type=None, force_query=None):
    """Run the full daily pipeline.

    Args:
        force_type: Force a specific content type ("worldcup_2026", "movie", or None)
        force_query: Force a specific search query

    Returns:
        Dict with results, or raises on failure
    """
    print(f"\n{'='*60}")
    print(f"  VARY — Daily Clip Pipeline")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # ── Step 1: Content Selection ────────────────────────
    print(f">>> STEP 1/6: Selecting content...")
    if force_type:
        content_info = {
            "type": force_type,
            "search_query": force_query or random.choice(
                WORLDCUP_KEYWORDS if force_type == "worldcup_2026" else MOVIE_KEYWORDS
            ),
            "description": f"Forced: {force_type}",
        }
        print(f"  Forced type: {force_type}")
    elif force_query:
        content_info = {
            "type": "custom",
            "search_query": force_query,
            "description": f"Custom query: {force_query}",
        }
        print(f"  Custom query: {force_query}")
    else:
        content_info = select_today_content()
        print(f"  Selected: {content_info['type']}")
        print(f"  Search: {content_info['search_query']}")

    log_result("content_selection", "success", content_info)

    # ── Step 2: Download Clip ────────────────────────────
    print(f"\n>>> STEP 2/6: Downloading clip...")
    used = load_used_scenes()
    used_ids = set()
    for key in ["movie_scenes", "worldcup_matches"]:
        for entry in used.get(key, []):
            used_ids.add(entry.get("identifier", ""))

    download_result = download_best_match(
        content_info["search_query"],
        used_ids=used_ids,
    )

    if not download_result:
        print(f"  [FAILED] No video found for query", flush=True)
        log_result("download", "failed", {"search": content_info["search_query"]})
        # Try one more time with a different query
        alt_queries = WORLDCUP_KEYWORDS if content_info["type"] == "worldcup_2026" else MOVIE_KEYWORDS
        alt_query = random.choice([q for q in alt_queries if q != content_info["search_query"]] or alt_queries)
        print(f"  Retrying with: {alt_query}", flush=True)
        download_result = download_best_match(alt_query, used_ids=used_ids)

    if not download_result:
        raise Exception(f"Failed to download clip for: {content_info['search_query']}")

    print(f"  Downloaded: {download_result['title']}", flush=True)
    log_result("download", "success", download_result)

    # ── Step 3: Edit Clip ────────────────────────────────
    print(f"\n>>> STEP 3/6: Editing clip to Shorts format...")
    clip_result = create_clip(
        download_result["path"],
        content_info["type"],
        title=download_result["title"],
    )

    if not clip_result:
        raise Exception("Clip editing failed")

    print(f"  Clip duration: {clip_result.get('duration', 0):.1f}s", flush=True)
    log_result("editing", "success", clip_result)

    # ── Step 4: Generate Thumbnails (A/B variants) ──────
    print(f"\n>>> STEP 4/6: Generating thumbnails...")
    thumbnails = generate_thumbnails(
        clip_result["path"],
        download_result["title"][:50],
        content_info["type"],
    )

    if not thumbnails:
        print(f"  [WARNING] Thumbnail generation failed, continuing without", flush=True)
        thumbnails = {}

    log_result("thumbnails", "success" if thumbnails else "skipped", {"variants": list(thumbnails.keys())})

    # ── Step 5: Generate SEO & Upload ────────────────────
    print(f"\n>>> STEP 5/6: Generating SEO metadata...")
    seo = generate_metadata(
        download_result["title"],
        content_info["type"],
        source_url=download_result.get("url"),
    )

    print(f"  Title: {seo['title']}", flush=True)
    print(f"  Tags: {len(seo['tags'])} tags", flush=True)

    # Upload to YouTube
    print(f"\n>>> Uploading to YouTube...")
    from modules.youtube_uploader import upload_video

    # Pick the best thumbnail (prefer v3, then v2, then v1)
    best_thumb = None
    for variant in ["v3", "v2", "v1"]:
        if variant in thumbnails:
            best_thumb = thumbnails[variant]
            break

    try:
        video_id, response = upload_video(
            video_path=clip_result["path"],
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
        video_id = None
        video_url = None

    # ── Step 6: Space Cleanup ────────────────────────────
    print(f"\n>>> STEP 6/6: Cleaning up source files...")
    source_paths = [download_result["path"]]
    space_info = full_cleanup(source_paths)

    # Mark as used to avoid repeat
    save_used_scene(content_info["type"], download_result["video_id"])

    # ── Summary ──────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  ✅ PIPELINE COMPLETE")
    print(f"  Content: {content_info['type']}")
    print(f"  Source: {download_result['title']}")
    if video_url:
        print(f"  Uploaded: {video_url}")
    print(f"  Space: {space_info.get('size_mb', 0):.1f} MB used")
    print(f"{'='*60}\n")

    return {
        "content_type": content_info["type"],
        "search_query": content_info["search_query"],
        "source_title": download_result["title"],
        "clip_path": clip_result["path"],
        "thumbnails": thumbnails,
        "seo_title": seo["title"],
        "video_id": video_id,
        "video_url": video_url,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VARY — Daily Clip Pipeline")
    parser.add_argument("--type", choices=["worldcup", "movie"], default=None,
                        help="Force a specific content type")
    parser.add_argument("--query", default=None,
                        help="Force a specific search query")
    args = parser.parse_args()

    force_type = None
    if args.type == "worldcup":
        force_type = "worldcup_2026"
    elif args.type == "movie":
        force_type = "movie"

    result = run_pipeline(force_type=force_type, force_query=args.query)
    print(json.dumps(result, indent=2, default=str))
