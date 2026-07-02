"""End-to-end test: Critique → SEO → Register → Evolve"""
import sys, os
sys.path.insert(0, ".")

from datetime import datetime
from modules.clip_critique import critique_clip
from modules.seo_generator import generate_metadata
from modules.performance_tracker import register_upload, get_all_tracked_videos
from modules.evolution_engine import evolve, get_evolution_status

# Find an existing clip to use
clips_dir = "assets/clips"
existing_clips = [f for f in os.listdir(clips_dir) if f.endswith(".mp4")]
if not existing_clips:
    print("No existing clips found. Cannot run test.")
    sys.exit(1)

# Use the largest existing clip
clip_paths = [(f, os.path.getsize(os.path.join(clips_dir, f))) for f in existing_clips]
clip_paths.sort(key=lambda x: -x[1])
clip_name, clip_size = clip_paths[0]
clip_path = os.path.join(clips_dir, clip_name)

print(f"=" * 60)
print(f"  VARY — End-to-End Pipeline Component Test")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  Clip: {clip_name} ({clip_size} bytes)")
print(f"=" * 60)

# ── 1. Critique ───────────────────────────────────────────
print(f"\n>>> [1/5] Critique Engine...", flush=True)
sys.stdout.flush()
try:
    crit = critique_clip(clip_path, "movie", "Test Clip", 30)
    if crit:
        print(f"  Score: {crit['compound_score']}/100")
        print(f"  Grade: {crit['grade']}")
        for r in crit.get('recommendations', [])[:2]:
            print(f"  -> {r}")
        crit_score = crit['compound_score']
        crit_grade = crit['grade']
    else:
        print(f"  (critique returned None)")
        crit_score, crit_grade = None, None
except Exception as e:
    print(f"  Critique error: {e}")
    crit_score, crit_grade = None, None

# ── 2. SEO ────────────────────────────────────────────────
print(f"\n>>> [2/5] SEO Generator...", flush=True)
seo = generate_metadata("Test Movie Clip - Action Scene", "movie")
print(f"  Title: {seo['title']}")
print(f"  Tags: {len(seo['tags'])}")

# ── 3. Performance Registration ──────────────────────────
print(f"\n>>> [3/5] Performance Tracker...", flush=True)
reg = register_upload(
    video_id="e2e_test_clip",
    title="Test Movie Clip - Action Scene",
    content_type="movie",
    search_query="iconic movie scene",
    seo_title=seo["title"],
    critique_score=crit_score,
    critique_grade=crit_grade,
)
print(f"  Registered: {reg['video_id']}")
tracked = get_all_tracked_videos()
print(f"  Total tracked videos: {len(tracked)}")

# ── 4. Evolution Status ──────────────────────────────────
print(f"\n>>> [4/5] Evolution Engine Status...", flush=True)
status = get_evolution_status()
print(f"  Generation: {status['generation']}")
print(f"  Avg score: {status['average_score']}")
print(f"  Videos analyzed: {status['total_clips_analyzed']}")
print(f"  Title style: {status['parameters']['title_style_preference']}")
print(f"  Scene threshold: {status['parameters']['scene_threshold']}")

# ── 5. Evolution Cycle ───────────────────────────────────
print(f"\n>>> [5/5] Evolution Cycle...", flush=True)
evolved = evolve()
print(f"  Evolved: {evolved['evolved']}")
print(f"  Reason: {evolved.get('reason', 'completed')}")
print(f"  Generation: {evolved['generation']}")

print(f"\n" + "=" * 60)
print(f"  ✅ TEST COMPLETE")
print(f"  Critique: {crit_score}/100" if crit_score else "  Critique: N/A")
print(f"  Evolution: gen {evolved['generation']}")
print(f"  Tracked: {len(tracked)} videos")
print(f"  Parameters unchanged (no performance data yet — needs real uploads)")
print(f"=" * 60)
