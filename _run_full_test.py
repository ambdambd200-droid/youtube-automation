"""
End-to-end pipeline test.
Runs: Select → Download → Edit → Critique → SEO → Register → Evolve → Cleanup
Skips YouTube upload (no credentials).
"""
import sys, os, json
sys.path.insert(0, ".")

from config import LOG_DIR
from modules.content_selector import select_today_content, load_used_scenes, save_used_scene
from modules.clip_downloader import download_best_match
from modules.clip_editor import create_clip
from modules.thumbnail_generator import generate_thumbnails
from modules.seo_generator import generate_metadata
from modules.clip_critique import critique_clip
from modules.performance_tracker import register_upload, get_all_tracked_videos
from modules.evolution_engine import evolve
from modules.space_manager import full_cleanup
from datetime import datetime

results = {}

# ── Step 1: Content Selection ──────────────────────────────
print(f"\n{'='*60}")
print(f"  VARY — Full End-to-End Pipeline Test")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'='*60}")

print(f"\n>>> STEP 1/7: Selecting content...")
content_info = select_today_content()
print(f"  Type: {content_info['type']}")
print(f"  Query: {content_info['search_query']}")
results["selection"] = content_info

# ── Step 2: Download ────────────────────────────────────────
print(f"\n>>> STEP 2/7: Downloading clip...")
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
    print(f"  [FAILED] No video found, retrying with different query...")
    from config import WORLDCUP_KEYWORDS, MOVIE_KEYWORDS
    import random
    alt_queries = WORLDCUP_KEYWORDS if content_info["type"] == "worldcup_2026" else MOVIE_KEYWORDS
    alt_query = random.choice([q for q in alt_queries if q != content_info["search_query"]] or alt_queries)
    download_result = download_best_match(alt_query, used_ids=used_ids)

if not download_result:
    print(f"  ✗ FAILED: Could not download any clip")
    sys.exit(1)

print(f"  ✓ Downloaded: {download_result['title'][:80]}")
print(f"  Path: {download_result['path']}")
print(f"  Size: {os.path.getsize(download_result['path'])} bytes")
results["download"] = {"title": download_result["title"], "video_id": download_result["video_id"]}

# ── Step 3: Edit ───────────────────────────────────────────
print(f"\n>>> STEP 3/7: Editing to Shorts format...")
clip_result = create_clip(
    download_result["path"],
    content_info["type"],
    title=download_result["title"],
)

if not clip_result:
    print(f"  ✗ FAILED: Clip editing failed")
    sys.exit(1)

print(f"  ✓ Clip: {clip_result['path']}")
print(f"  Duration: {clip_result.get('duration', 0):.1f}s")
print(f"  Size: {os.path.getsize(clip_result['path'])} bytes")
results["edit"] = {"path": clip_result["path"], "duration": clip_result.get("duration")}

# ── Step 4: Critique ───────────────────────────────────────
print(f"\n>>> STEP 4/7: Critiquing clip...")
critique_result = critique_clip(
    clip_result["path"],
    content_info["type"],
    source_title=download_result["title"],
    source_duration=clip_result.get("duration", 0),
)

if critique_result:
    print(f"  ✓ Score: {critique_result['compound_score']}/100")
    print(f"  Grade: {critique_result['grade']}")
    for rec in critique_result["recommendations"][:3]:
        print(f"  • {rec}")
    results["critique"] = {
        "score": critique_result["compound_score"],
        "grade": critique_result["grade"],
        "axes": critique_result["axes"]
    }
else:
    print(f"  ⚠ Critique skipped (no frame analysis)")
    results["critique"] = None

# ── Step 5: Thumbnails + SEO ──────────────────────────────
print(f"\n>>> STEP 5/7: Generating thumbnails & SEO...")
thumbnails = generate_thumbnails(
    clip_result["path"],
    download_result["title"][:50],
    content_info["type"],
)
if thumbnails:
    print(f"  ✓ Thumbnails: {list(thumbnails.keys())}")
else:
    print(f"  ⚠ Thumbnails skipped")

seo = generate_metadata(
    download_result["title"],
    content_info["type"],
    source_url=download_result.get("url"),
)
print(f"  ✓ SEO Title: {seo['title']}")
print(f"  ✓ Tags: {len(seo['tags'])} tags")
results["seo"] = {"title": seo["title"]}

# ── Step 6: Register for Performance Tracking ─────────────
print(f"\n>>> STEP 6/7: Registering for performance tracking...")
reg = register_upload(
    video_id=download_result["video_id"],
    title=download_result["title"],
    content_type=content_info["type"],
    search_query=content_info["search_query"],
    seo_title=seo["title"],
    critique_score=critique_result["compound_score"] if critique_result else None,
    critique_grade=critique_result["grade"] if critique_result else None,
)
print(f"  ✓ Registered: {reg['video_id']}")
results["registration"] = reg

# ── Step 7: Run Evolution ─────────────────────────────────
print(f"\n>>> STEP 7/7: Running evolution cycle...")
evolution_result = evolve()
print(f"  Generation: {evolution_result.get('generation')}")
print(f"  Evolved: {evolution_result.get('evolved')}")
print(f"  Reason: {evolution_result.get('reason', 'completed')}")
results["evolution"] = evolution_result

# ── Cleanup ───────────────────────────────────────────────
print(f"\n>>> Cleanup: Deleting source files...")
source_paths = [download_result["path"]]
space_info = full_cleanup(source_paths)
save_used_scene(content_info["type"], download_result["video_id"])

# ── Final Summary ─────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  ✅ END-TO-END PIPELINE TEST COMPLETE")
print(f"  Content: {content_info['type']}")
print(f"  Source: {download_result['title'][:60]}...")
print(f"  Clip: {clip_result.get('duration', 0):.1f}s")
print(f"  Critique: {critique_result['compound_score']}/100" if critique_result else "")
print(f"  Evolution gen: {evolution_result.get('generation')}")
print(f"  Performance videos tracked: {len(get_all_tracked_videos())}")
print(f"{'='*60}")

# Save full results
with open(os.path.join(LOG_DIR, "end_to_end_test_result.json"), "w") as f:
    json.dump(results, f, indent=2, default=str)

print(f"\nFull results saved to: {os.path.join(LOG_DIR, 'end_to_end_test_result.json')}")
