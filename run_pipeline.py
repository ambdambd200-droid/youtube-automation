"""
VARY — Main Pipeline Runner.
Daily clip-based pipeline: Select → Download → Edit → Critique → Thumbnail → SEO → Upload → Evolve → Cleanup

Usage:
    python run_pipeline.py                     # Auto-select content (random daily)
    python run_pipeline.py --type football     # Force football clip
    python run_pipeline.py --type movie        # Force movie scene
    python run_pipeline.py --type series       # Force TV series clip
    python run_pipeline.py --query "custom search"  # Custom search
"""
import argparse
import json
import os
import sys
import random
import traceback
from datetime import datetime

# Fix Windows console encoding for Unicode characters (em dashes, arrows, etc.)
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(__file__))

from config import (
    LOG_DIR, FOOTBALL_KEYWORDS, MOVIE_KEYWORDS, SERIES_KEYWORDS,
)
from modules.content_selector import select_today_content, load_used_scenes, save_used_scene
from modules.clip_downloader import download_best_match
from modules.clip_editor import create_clip
from modules.thumbnail_generator import generate_thumbnails
from modules.seo_generator import generate_metadata
from modules.space_manager import full_cleanup
from modules.pipeline_watchdog import (
    register_run_start, register_stage, register_run_complete, register_run_failure,
)


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


def run_pipeline(force_type=None, force_query=None, pipeline_id=None):
    """Run the full daily pipeline.

    Args:
        force_type: Force a specific content type ("football", "movie", "series", or None)
        force_query: Force a specific search query

    Returns:
        Dict with results, or raises on failure
    """
    # ── Register with watchdog ─────────────────────────────
    pipeline_id = pipeline_id or register_run_start("daily")

    print(f"\n{'='*60}")
    print(f"  VARY — Daily Clip Pipeline")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Run: {pipeline_id}")
    print(f"{'='*60}\n")

    # ── Channel Branding Check ────────────────────────────
    print(f">>> Checking channel branding...")
    try:
        from modules.channel_manager import check_and_update_channel
        channel_result = check_and_update_channel()
        log_result("channel_check", "success", channel_result)
        if channel_result.get("description_updated"):
            print(f"  Channel description updated", flush=True)
    except BaseException as e:
        print(f"  [SKIP] Channel check failed: {e}", flush=True)
        log_result("channel_check", "skipped", {"error": str(e)})

    # ── Step 1: Content Selection ────────────────────────
    register_stage(pipeline_id, "content_selection")
    print(f">>> Step 1/9: Selecting content...")
    if force_type:
        keyword_map = {"football": FOOTBALL_KEYWORDS, "movie": MOVIE_KEYWORDS, "series": SERIES_KEYWORDS}
        content_info = {
            "type": force_type,
            "search_query": force_query or random.choice(
                keyword_map.get(force_type, MOVIE_KEYWORDS)
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
    register_stage(pipeline_id, "download")
    print(f"\n>>> Step 2/9: Downloading clip...")
    used = load_used_scenes()
    used_ids = set()
    for key in ["movie_scenes", "football_matches", "series_scenes"]:
        for entry in used.get(key, []):
            used_ids.add(entry.get("identifier", ""))

    download_result = download_best_match(
        content_info["search_query"],
        used_ids=used_ids,
        content_type=content_info["type"],
    )

    if not download_result:
        print(f"  [FAILED] No video found for query", flush=True)
        log_result("download", "failed", {"search": content_info["search_query"]})
        # Try one more time with a different query
        keyword_map = {"football": FOOTBALL_KEYWORDS, "movie": MOVIE_KEYWORDS, "series": SERIES_KEYWORDS}
        alt_queries = keyword_map.get(content_info["type"], MOVIE_KEYWORDS)
        alt_query = random.choice([q for q in alt_queries if q != content_info["search_query"]] or alt_queries)
        print(f"  Retrying with: {alt_query}", flush=True)
        download_result = download_best_match(alt_query, used_ids=used_ids, content_type=content_info["type"])

    if not download_result:
        raise Exception(f"Failed to download clip for: {content_info['search_query']}")

    print(f"  Downloaded: {download_result['title']}", flush=True)
    log_result("download", "success", download_result)

    # ── Step 3: Edit Clip ────────────────────────────────
    register_stage(pipeline_id, "editing")
    print(f"\n>>> Step 3/9: Editing clip — Full Blueprint Pipeline...")
    print(f"  [pipeline] Select Segment → Crop → Color Grade → Speed Ramp → Text → Audio → Breath Cut", flush=True)
    clip_result = create_clip(
        download_result["path"],
        content_info["type"],
        title=download_result["title"],
        skip_effects=False,
    )

    if not clip_result:
        raise Exception("Clip editing failed")

    print(f"  Clip duration: {clip_result.get('duration', 0):.1f}s", flush=True)
    log_result("editing", "success", clip_result)

    # ── Step 4: Generate Thumbnails (A/B variants) ──────
    register_stage(pipeline_id, "thumbnails")
    print(f"\n>>> Step 4/9: Generating thumbnails (Peak Action Frame)...")
    thumbnails = generate_thumbnails(
        clip_result["path"],
        download_result["title"][:50],
        content_info["type"],
    )

    if not thumbnails:
        print(f"  [WARNING] Thumbnail generation failed, continuing without", flush=True)
        thumbnails = {}

    log_result("thumbnails", "success" if thumbnails else "skipped", {"variants": list(thumbnails.keys())})

    # ── Step 5: Generate SEO (Tri-Part Titles + Rich Description) ──
    register_stage(pipeline_id, "seo")
    print(f"\n>>> Step 5/9: Generating SEO metadata (Tri-Part Title + 250w Description)...")
    seo = generate_metadata(
        download_result["title"],
        content_info["type"],
        source_url=download_result.get("url"),
    )

    print(f"  Title: {seo['title']}", flush=True)
    print(f"  Tags: {len(seo['tags'])} tags", flush=True)

    # ── Step 6: Critique (disabled — was causing hangs) ──
    critique_result = None
    print(f"  [SKIP] Critique disabled (was causing ffmpeg hangs)", flush=True)

    # ── Step 7: Upload to YouTube ────────────────────────
    register_stage(pipeline_id, "upload")
    print(f"\n>>> Step 7/9: Uploading to YouTube...")
    from config import YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN
    from modules.youtube_uploader import upload_video

    print(f"  [DEBUG] CI env: {os.environ.get('CI', 'not set')}", flush=True)
    print(f"  [DEBUG] CLIENT_ID: {'SET' if YOUTUBE_CLIENT_ID else 'MISSING'}", flush=True)
    print(f"  [DEBUG] CLIENT_SECRET: {'SET' if YOUTUBE_CLIENT_SECRET else 'MISSING'}", flush=True)
    print(f"  [DEBUG] REFRESH_TOKEN: {'SET' if YOUTUBE_REFRESH_TOKEN else 'MISSING'}", flush=True)

    if not YOUTUBE_CLIENT_ID or not YOUTUBE_CLIENT_SECRET or not YOUTUBE_REFRESH_TOKEN:
        print(f"  [SKIP] YouTube credentials not configured — skipping upload", flush=True)
        log_result("upload", "skipped", {"reason": "credentials not configured"})
        video_id = None
        video_url = None
    else:
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

        except BaseException as e:
            print(f"  [FAILED] Upload error: {e}", flush=True)
            log_result("upload", "failed", {"error": str(e)})
            video_id = None
            video_url = None

    # ── Step 6a: Register upload for performance tracking ──
    if video_id:
        try:
            from modules.performance_tracker import register_upload
            register_upload(
                video_id=video_id,
                title=download_result["title"],
                content_type=content_info["type"],
                search_query=content_info["search_query"],
                seo_title=seo["title"],
                critique_score=critique_result["compound_score"] if critique_result else None,
                critique_grade=critique_result["grade"] if critique_result else None,
            )
            print(f"  Registered for performance tracking: {video_id}", flush=True)
            log_result("performance_register", "success", {"video_id": video_id})
        except Exception as e:
            print(f"  [SKIP] Performance register error: {e}", flush=True)
            log_result("performance_register", "skipped", {"error": str(e)})

    # ── Step 8: Evolution — self-improvement cycle ────────
    register_stage(pipeline_id, "evolution")
    print(f"\n>>> Step 8/9: Running evolution cycle...")
    evolution_result = None
    try:
        from modules.evolution_engine import evolve
        evolution_result = evolve()
        log_result("evolution", "success", {
            "generation": evolution_result.get("generation", 0),
            "evolved": evolution_result.get("evolved", False),
            "trends": evolution_result.get("trends", {}),
        })
        if evolution_result.get("evolved"):
            print(f"  Parameters evolved to generation {evolution_result['generation']}", flush=True)
    except Exception as e:
        print(f"  [SKIP] Evolution error: {e}", flush=True)
        log_result("evolution", "skipped", {"error": str(e)})

    # ── Step 9: Space Cleanup ─────────────────────────────
    register_stage(pipeline_id, "cleanup")
    print(f"\n>>> Step 9/9: Cleaning up all downloaded files...")
    # Build list of everything to delete: source download + processed clip + thumbnails
    paths_to_clean = [download_result["path"]]
    if clip_result:
        paths_to_clean.append(clip_result["path"])
    for variant in thumbnails.values():
        if variant and os.path.exists(variant):
            paths_to_clean.append(variant)
    space_info = full_cleanup(paths_to_clean)

    # Mark as used to avoid repeat
    save_used_scene(content_info["type"], download_result["video_id"])

    # ── Mark complete in watchdog ─────────────────────────
    register_run_complete(pipeline_id)

    # ── Summary ──────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  ✅ PIPELINE COMPLETE")
    print(f"  Content: {content_info['type']}")
    print(f"  Source: {download_result['title']}")
    print(f"  Run ID: {pipeline_id}")
    if video_url:
        print(f"  Uploaded: {video_url}")
    if critique_result:
        print(f"  Critique: {critique_result['compound_score']}/100 ({critique_result['grade']})")
    if evolution_result:
        print(f"  Evolution gen: {evolution_result.get('generation', 'N/A')}")
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
        "critique_score": critique_result["compound_score"] if critique_result else None,
        "critique_grade": critique_result["grade"] if critique_result else None,
        "evolution_generation": evolution_result.get("generation") if evolution_result else None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VARY — Daily Clip Pipeline")
    parser.add_argument("--type", choices=["football", "movie", "series"], default=None,
                        help="Force a specific content type")
    parser.add_argument("--query", default=None,
                        help="Force a specific search query")
    args = parser.parse_args()

    force_type = None
    if args.type in ("football", "movie", "series"):
        force_type = args.type

    from modules.pipeline_watchdog import register_run_start, register_run_failure
    pipeline_id = register_run_start("daily")
    try:
        result = run_pipeline(force_type=force_type, force_query=args.query, pipeline_id=pipeline_id)
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(f"\n  ❌ PIPELINE CRASHED: {e}", flush=True)
        traceback.print_exc()
        register_run_failure(pipeline_id, str(e))
        sys.exit(1)
