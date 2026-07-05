"""
VARY Weekly Pipeline — End-to-End Test Script.

Tests the entire weekly pipeline flow without uploading to YouTube:
  1. Module imports
  2. Voiceover generation (edge-tts)
  3. Story text generation
  4. Weekly video creation (uses a test file if available)
  5. Thumbnail generation
  6. SEO generation

Usage:
    python scripts/test_weekly_pipeline.py --query "Interstellar movie analysis"
    python scripts/test_weekly_pipeline.py --local path/to/test_video.mp4
"""
import argparse
import json
import os
import sys
import traceback
from datetime import datetime

# Fix Windows console encoding for Unicode characters
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_imports():
    """Step 1: Verify all modules can be imported."""
    print("\n[TEST] Step 1/6: Module imports...")
    modules = [
        "config",
        "modules.clip_downloader",
        "modules.clip_editor",
        "modules.seo_generator",
        "modules.thumbnail_generator",
        "modules.voiceover_generator",
        "modules.space_manager",
        "modules.youtube_uploader",
        "modules.performance_tracker",
        "modules.pipeline_watchdog",
        "modules.evolution_engine",
    ]
    for mod_name in modules:
        try:
            __import__(mod_name)
            print(f"  [OK] {mod_name}")
        except Exception as e:
            print(f"  [FAIL] {mod_name}: {e}")
            return False
    return True


def test_voiceover():
    """Step 2: Test edge-tts voiceover generation."""
    print("\n[TEST] Step 2/6: Voiceover generation...")
    from modules.clip_editor import generate_story_texts
    from modules.voiceover_generator import generate_voiceover

    texts = generate_story_texts("Inception: Dreams Within Dreams")
    print(f"  Story texts generated: {len(texts)} segments")

    voiceover_path = generate_voiceover(texts, "Inception")
    if not voiceover_path or not os.path.exists(voiceover_path):
        print("  [FAIL] Voiceover generation failed")
        return None

    size_kb = os.path.getsize(voiceover_path) / 1024
    print(f"  [OK] Voiceover generated: {os.path.basename(voiceover_path)} ({size_kb:.0f} KB)")

    from modules.clip_editor import get_video_duration
    dur = get_video_duration(voiceover_path)
    print(f"  [OK] Voiceover duration: {dur:.1f}s")

    # Clean up
    try:
        os.remove(voiceover_path)
    except Exception:
        pass

    return True


def test_seo():
    """Step 3: Test weekly SEO metadata generation."""
    print("\n[TEST] Step 3/6: SEO metadata generation...")
    from modules.seo_generator import generate_weekly_metadata

    result = generate_weekly_metadata("Interstellar — The Science Behind the Story")
    required = ["title", "description", "tags"]
    for key in required:
        if key not in result:
            print(f"  [FAIL] Missing key: {key}")
            return False
    print(f"  [OK] Title: {result['title'][:60]}...")
    print(f"  [OK] Tags: {len(result['tags'])} tags")
    return True


def test_thumbnail(local_video=None):
    """Step 4: Test thumbnail generation.

    If local_video is provided, uses it; otherwise skips.
    """
    print("\n[TEST] Step 4/6: Thumbnail generation...")
    if not local_video or not os.path.exists(local_video):
        print(f"  [SKIP] No local video provided")
        return True

    from modules.thumbnail_generator import generate_weekly_thumbnails
    thumbnails = generate_weekly_thumbnails(local_video, "Test Movie")
    if not thumbnails:
        print(f"  [FAIL] Thumbnail generation failed")
        return False

    print(f"  [OK] Generated {len(thumbnails)} variants: {list(thumbnails.keys())}")
    for v, path in thumbnails.items():
        if os.path.exists(path):
            print(f"    {v}: {os.path.getsize(path)} bytes")
    return True


def test_weekly_video(local_video):
    """Step 5: Test weekly video creation.

    Args:
        local_video: Path to a local video file for testing.
    """
    print("\n[TEST] Step 5/6: Weekly video creation...")
    if not local_video or not os.path.exists(local_video):
        print(f"  [SKIP] No local video provided")
        return None

    from modules.clip_editor import create_weekly_video, remux_to_compatible, generate_story_texts
    from modules.voiceover_generator import generate_voiceover, cleanup_voiceover

    from config import CLIPS_DIR
    import uuid
    output = os.path.join(CLIPS_DIR, f"test_weekly_{uuid.uuid4().hex[:8]}.mp4")

    working = remux_to_compatible(local_video)

    voiceover_path = None
    try:
        texts = generate_story_texts("Test Movie")
        voiceover_path = generate_voiceover(texts, "Test Movie")
    except Exception as e:
        print(f"  Voiceover generation failed (continuing): {e}")

    result = create_weekly_video(
        working,
        output,
        source_title="Test Movie Analysis",
        voiceover_path=voiceover_path,
    )

    if voiceover_path:
        cleanup_voiceover(voiceover_path)

    if working != local_video and os.path.exists(working):
        try:
            os.remove(working)
        except Exception:
            pass

    if not result:
        print(f"  [FAIL] Weekly video creation failed")
        return None

    print(f"  [OK] Created: {result['path']}")
    print(f"  [OK] Duration: {result['duration']:.1f}s")
    print(f"  [OK] Size: {os.path.getsize(result['path']) / 1024:.0f} KB")
    return result


def test_cleanup(video_result=None):
    """Step 6: Clean up test artifacts."""
    print("\n[TEST] Step 6/6: Cleanup...")
    if video_result and os.path.exists(video_result["path"]):
        try:
            os.remove(video_result["path"])
            print(f"  [OK] Removed test video")
        except Exception as e:
            print(f"  [WARN] Could not remove: {e}")
    print(f"  [OK] Done")
    return True


def run_all_tests(local_video=None):
    """Run all test steps."""
    start = datetime.now()
    print(f"{'='*60}")
    print(f"  VARY Weekly Pipeline — E2E Test Suite")
    print(f"  {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    results = {}

    results["imports"] = test_imports()
    if not results["imports"]:
        print("\n[FAIL] CRITICAL: Module imports failed. Aborting.")
        return results

    results["seo"] = test_seo()
    results["voiceover"] = test_voiceover()
    results["thumbnail"] = test_thumbnail(local_video)

    results["video"] = False
    video_result = test_weekly_video(local_video)
    if video_result:
        results["video"] = True

    results["cleanup"] = test_cleanup(video_result)

    elapsed = (datetime.now() - start).total_seconds()
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed}/{total} passed ({elapsed:.0f}s)")
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  {status} {name}")
    print(f"{'='*60}\n")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the weekly pipeline end-to-end")
    parser.add_argument("--local", default=None,
                        help="Path to a local video file for testing")
    parser.add_argument("--query", default=None,
                        help="Search query to download a test video")
    args = parser.parse_args()

    local_video = args.local

    if args.query and not local_video:
        print(f"Downloading test video for query: {args.query}")
        from modules.clip_downloader import download_best_match
        result = download_best_match(args.query, content_type="movie")
        if result:
            local_video = result["path"]
            print(f"Downloaded: {local_video}")
        else:
            print(f"Failed to download video")

    run_all_tests(local_video=local_video)
