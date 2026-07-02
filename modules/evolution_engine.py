"""
VARY Evolution Engine — the autonomous self-improvement core.

Philosophy:
  Most automation systems repeat the same patterns forever. VARY evolves.
  Every clip is critiqued. Every critique informs the next decision.
  Over time, the system learns which content types, search queries,
  clip durations, and posting times maximize hook potential.

This engine runs in FULL AUTONOMY mode — it adjusts parameters without
human approval. All changes are logged and reversible.

Evolution Axes:
   1. CONTENT_WEIGHTS — Shift between football/movie/series based on performance
  2. SEARCH_KEYWORDS — Promote keywords yielding high-scoring clips
  3. CLIP_DURATION — Adjust min/max duration sweet spot
  4. SCENE_THRESHOLD — Scene detection sensitivity
  5. SEO_TITLE_STYLES — Track which title styles perform best
"""
import json
import os
import sys
from datetime import datetime, timedelta
from copy import deepcopy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    LOG_DIR, CONTENT_WEIGHTS,
    FOOTBALL_KEYWORDS, MOVIE_KEYWORDS, SERIES_KEYWORDS,
    CLIP_MIN_DURATION, CLIP_MAX_DURATION,
)


EVOLUTION_STATE_FILE = os.path.join(LOG_DIR, "evolution_state.json")
EVOLUTION_LOG = os.path.join(LOG_DIR, "evolution_log.jsonl")


# ── Default State ───────────────────────────────────────────

DEFAULT_EVOLUTION_STATE = {
    "generation": 1,
    "last_updated": None,
    "parameters": {
        "content_weights": dict(CONTENT_WEIGHTS),
        "football_keywords": list(FOOTBALL_KEYWORDS),
        "movie_keywords": list(MOVIE_KEYWORDS),
        "series_keywords": list(SERIES_KEYWORDS),
        "clip_min_duration": CLIP_MIN_DURATION,
        "clip_max_duration": CLIP_MAX_DURATION,
        "scene_threshold": 0.3,
        "title_style_preference": "balanced",  # poetic | direct | balanced
        "thumbnail_variant_preference": "v2",  # which variant to use as primary
        "posting_times_by_day": {},  # Day->hour list, filled by real perf data
    },
    "performance": {
        "average_score": 50.0,
        "peak_score": 0.0,
        "total_clips_analyzed": 0,
        "total_evolutions": 0,
        "history_by_type": {},  # {content_type: [scores]}
        "history_by_hour": {},  # {hour: [scores]}
        # Real-world YouTube performance tracking
        "real_performance_average": None,
        "real_performance_best_type": None,
        "real_videos_tracked": 0,
        "critique_vs_real_delta": 0.0,  # avg difference: critique_score vs real_score
    },
    "mutations": [],  # log of parameter changes
}


# ── State Management ───────────────────────────────────────


def _load_state():
    """Load current evolution state, or create default."""
    if os.path.exists(EVOLUTION_STATE_FILE):
        try:
            with open(EVOLUTION_STATE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return deepcopy(DEFAULT_EVOLUTION_STATE)


def _save_state(state):
    """Persist evolution state."""
    state["last_updated"] = datetime.now().isoformat()
    os.makedirs(os.path.dirname(EVOLUTION_STATE_FILE), exist_ok=True)
    with open(EVOLUTION_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _log_evolution(action, details=None):
    """Log an evolution event."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "generation": _load_state().get("generation", 1),
        "action": action,
        "details": details or {},
    }
    with open(EVOLUTION_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ── Critique Data Loading ──────────────────────────────────


def _load_recent_critiques(hours=48):
    """Load critiques from the last N hours — includes both daily and weekly.

    Merges daily Shorts critiques with weekly video critiques so the
    evolution engine learns from both content streams.
    Weekly critiques have content_type "weekly_movie" and flow through
    naturally into _calculate_performance_trends() per-type averages.
    """
    try:
        from modules.clip_critique import load_all_critiques
    except ImportError:
        return []

    all_critiques = load_all_critiques(n=200)
    cutoff = datetime.now() - timedelta(hours=hours)

    recent = []
    for c in all_critiques:
        try:
            ts = datetime.fromisoformat(c.get("timestamp", ""))
            if ts > cutoff:
                recent.append(c)
        except (ValueError, TypeError):
            continue
    return recent


def _calculate_performance_trends(critiques):
    """Calculate performance metrics from critique data."""
    if not critiques:
        return None

    scores = [c.get("compound_score", 50) for c in critiques]
    avg = sum(scores) / len(scores)

    # Per-type breakdown
    by_type = {}
    for c in critiques:
        ct = c.get("content_type", "unknown")
        score = c.get("compound_score", 50)
        by_type.setdefault(ct, []).append(score)

    type_avgs = {ct: round(sum(vals) / len(vals), 1) for ct, vals in by_type.items()}

    # Per-hour breakdown (to find optimal posting times)
    by_hour = {}
    for c in critiques:
        try:
            ts = datetime.fromisoformat(c.get("timestamp", ""))
            hour = ts.hour
            score = c.get("compound_score", 50)
            by_hour.setdefault(hour, []).append(score)
        except (ValueError, TypeError):
            continue

    hour_avgs = {h: round(sum(vals) / len(vals), 1) for h, vals in by_hour.items()}

    # Axis weakness pattern
    axis_totals = {"first_frame_hook": [], "motion_dynamics": [], "audio_impact": [],
                   "scene_composition": [], "color_vibrancy": [], "pacing": []}
    for c in critiques:
        axes = c.get("axes", {})
        for axis in axis_totals:
            if axis in axes:
                axis_totals[axis].append(axes[axis])

    axis_avgs = {}
    for axis, vals in axis_totals.items():
        if vals:
            axis_avgs[axis] = round(sum(vals) / len(vals), 1)

    return {
        "average_score": round(avg, 1),
        "peak_score": round(max(scores), 1),
        "lowest_score": round(min(scores), 1),
        "count": len(critiques),
        "type_averages": type_avgs,
        "hour_averages": hour_avgs,
        "axis_averages": axis_avgs,
        "best_hour": max(hour_avgs, key=hour_avgs.get) if hour_avgs else None,
        "weakest_type": min(type_avgs, key=type_avgs.get) if type_avgs else None,
    }


# ── Mutation Functions ─────────────────────────────────────


def _mutate_content_weights(state, trends):
    """Shift content type weights based on performance."""
    params = state["parameters"]
    type_avgs = trends.get("type_averages", {})

    if not type_avgs:
        return

    for ct, avg_score in type_avgs.items():
        # Map content_type to weight key
        key = ct if ct in ("football", "movie", "series") else "movie"
        if key in params["content_weights"]:
            current = params["content_weights"][key]
            # If this type performs >10% above average, boost it
            overall_avg = trends.get("average_score", 50)
            if avg_score > overall_avg * 1.1:
                # Boost this type, reduce others
                boost = min(0.15, (avg_score - overall_avg) / 200)
                params["content_weights"][key] = round(min(0.9, current + boost), 2)
                # Normalize
                total = sum(params["content_weights"].values())
                for k in params["content_weights"]:
                    params["content_weights"][k] = round(params["content_weights"][k] / total, 2)
                state["mutations"].append({
                    "timestamp": datetime.now().isoformat(),
                    "axis": "content_weights",
                    "change": f"Boosted {key} from {current:.2f} to {params['content_weights'][key]:.2f} (score: {avg_score})"
                })


def _mutate_keywords(state, trends):
    """Promote keywords that yield high-scoring clips."""
    params = state["parameters"]
    critiques = _load_recent_critiques(hours=48)

    if not critiques:
        return

    # Collect keyword performance from critique source_titles
    keyword_scores = {}
    for c in critiques:
        title = c.get("source_title", "").lower()
        score = c.get("compound_score", 50)
        ct = c.get("content_type", "movie")

        # Check each keyword
        base_kws = {"football": FOOTBALL_KEYWORDS, "movie": MOVIE_KEYWORDS, "series": SERIES_KEYWORDS}.get(ct, MOVIE_KEYWORDS)
        for kw in base_kws:
            kw_lower = kw.lower()
            if kw_lower in title or any(word in title for word in kw_lower.split()):
                keyword_scores.setdefault(kw, []).append(score)

    if not keyword_scores:
        return

    # Calculate average per keyword
    kw_avgs = {kw: round(sum(vals) / len(vals), 1) for kw, vals in keyword_scores.items()}

    # Sort keywords by performance
    sorted_kws = sorted(kw_avgs.items(), key=lambda x: x[1], reverse=True)
    top_kw = sorted_kws[0][0] if sorted_kws else None

    if top_kw and len(sorted_kws) >= 2:
        # Log the top performer
        state["mutations"].append({
            "timestamp": datetime.now().isoformat(),
            "axis": "keywords",
            "change": f"Top keyword: '{top_kw}' ({kw_avgs[top_kw]:.1f})",
            "keyword_scores": {k: v for k, v in sorted_kws[:5]},
        })


def _mutate_clip_duration(state, trends):
    """Adjust clip duration sweet spot based on performance."""
    params = state["parameters"]
    critiques = _load_recent_critiques(hours=48)

    if not critiques:
        return

    # Bucket durations by performance
    duration_scores = {}  # duration_bucket -> [scores]
    for c in critiques:
        dur = c.get("duration", 30)
        bucket = round(dur / 5) * 5  # round to nearest 5s
        duration_scores.setdefault(bucket, []).append(c.get("compound_score", 50))

    if not duration_scores:
        return

    bucket_avgs = {b: round(sum(vals) / len(vals), 1) for b, vals in duration_scores.items()}
    best_bucket = max(bucket_avgs, key=bucket_avgs.get)
    best_score = bucket_avgs[best_bucket]

    # If best duration bucket differs from current defaults, shift toward it
    current_min = params["clip_min_duration"]
    current_max = params["clip_max_duration"]

    if best_bucket < current_min:
        params["clip_min_duration"] = max(10, best_bucket - 5)
        state["mutations"].append({
            "timestamp": datetime.now().isoformat(),
            "axis": "clip_duration",
            "change": f"Lowered min_duration from {current_min}s to {params['clip_min_duration']}s (best bucket: {best_bucket}s, {best_score})"
        })
    if best_bucket > current_max:
        params["clip_max_duration"] = min(120, best_bucket + 5)
        state["mutations"].append({
            "timestamp": datetime.now().isoformat(),
            "axis": "clip_duration",
            "change": f"Raised max_duration from {current_max}s to {params['clip_max_duration']}s (best bucket: {best_bucket}s, {best_score})"
        })


def _mutate_scene_threshold(state, trends):
    """Adjust scene detection threshold based on pacing scores."""
    axis_avgs = trends.get("axis_averages", {})
    pacing = axis_avgs.get("pacing", 50)

    params = state["parameters"]
    current = params["scene_threshold"]

    if pacing < 30:
        # Too static — lower threshold to detect more scenes
        new_threshold = max(0.1, round(current - 0.05, 2))
        params["scene_threshold"] = new_threshold
        state["mutations"].append({
            "timestamp": datetime.now().isoformat(),
            "axis": "scene_threshold",
            "change": f"Lowered from {current} to {new_threshold} (pacing was {pacing})"
        })
    elif pacing > 80:
        # Too chaotic — raise threshold to detect fewer scenes
        new_threshold = min(0.6, round(current + 0.05, 2))
        params["scene_threshold"] = new_threshold
        state["mutations"].append({
            "timestamp": datetime.now().isoformat(),
            "axis": "scene_threshold",
            "change": f"Raised from {current} to {new_threshold} (pacing was {pacing})"
        })


def _mutate_title_style(state, trends):
    """Evolve SEO title style preference based on performance."""
    params = state["parameters"]
    critiques = _load_recent_critiques(hours=48)

    if not critiques:
        return

    # For now, we track which types of titles correlate with higher scores
    # Title styles can be 'poetic', 'direct', or 'balanced'
    # The seo_generator will reference this preference
    current_style = params.get("title_style_preference", "balanced")

    # If compound scores are consistently below 50, try switching style
    avg = trends.get("average_score", 50)
    if avg < 45 and current_style != "poetic":
        params["title_style_preference"] = "poetic"
        state["mutations"].append({
            "timestamp": datetime.now().isoformat(),
            "axis": "title_style",
            "change": f"Switched from {current_style} to poetic (avg score was {avg})"
        })
    elif avg > 70 and current_style != "direct":
        params["title_style_preference"] = "direct"
        state["mutations"].append({
            "timestamp": datetime.now().isoformat(),
            "axis": "title_style",
            "change": f"Switched from {current_style} to direct (avg score was {avg})"
        })


def _mutate_from_real_performance(state):
    """Mutate parameters based on real-world YouTube performance data.

    Real performance is weighted higher than simulated critique scores.
    10 real data points outweigh 50 simulated critiques.
    """
    try:
        from modules.performance_tracker import calculate_performance_trends
    except ImportError:
        return

    perf_trends = calculate_performance_trends()
    if not perf_trends or perf_trends.get("videos_tracked", 0) < 3:
        return  # Need at least 3 real data points before trusting

    params = state["parameters"]
    videos = perf_trends["videos_tracked"]
    avg_perf = perf_trends["average_performance_score"]
    type_avgs = perf_trends.get("type_averages", {})
    cvs = perf_trends.get("critique_vs_performance", {})
    avg_delta = cvs.get("average_delta", 0)

    print(f"  [evolution] Real perf: {videos} videos, avg={avg_perf:.1f}, delta={avg_delta:+.1f}", flush=True)

    # Update performance tracking in state
    state["performance"]["real_performance_average"] = avg_perf
    state["performance"]["real_videos_tracked"] = videos
    state["performance"]["critique_vs_real_delta"] = avg_delta

    # If real performance is high for a content type, boost it
    for ct, avg_score in type_avgs.items():
        key = ct if ct in ("football", "movie", "series") else "movie"
        if key in params["content_weights"]:
            current = params["content_weights"][key]
            # Real performance is the ultimate signal
            if avg_score > 60:  # Strong real performance
                boost = min(0.10, (avg_score - 50) / 500)
                params["content_weights"][key] = round(min(0.9, current + boost), 2)
                total = sum(params["content_weights"].values())
                for k in params["content_weights"]:
                    params["content_weights"][k] = round(params["content_weights"][k] / total, 2)
                state["mutations"].append({
                    "timestamp": datetime.now().isoformat(),
                    "axis": "real_performance",
                    "change": f"Real perf boosted {key} from {current:.2f} to {params['content_weights'][key]:.2f} (real avg: {avg_score})"
                })

    # If critique consistently overestimates (large positive delta), lower expectations
    if avg_delta > 15:
        state["mutations"].append({
            "timestamp": datetime.now().isoformat(),
            "axis": "real_performance",
            "change": f"Critique overestimates by {avg_delta:.1f} pts. Adjusting expectations."
        })
    # If critique consistently underestimates (large negative delta), raise the bar
    elif avg_delta < -15:
        state["mutations"].append({
            "timestamp": datetime.now().isoformat(),
            "axis": "real_performance",
            "change": f"Critique underestimates by {-avg_delta:.1f} pts. Lowering selection bar."
        })


# ── Main Evolution Entry Point ─────────────────────────────


# ── Posting Time Evolution ────────────────────────────────

def _mutate_posting_times(state):
    """Evolve posting time slots based on real YouTube view velocity.

    Analyzes real performance data to find which hours of the day
    yield the highest view velocity and engagement. Updates the
    posting_times_by_day map in evolution state so the config
    can read optimized times per weekday.

    This is a slow-evolving parameter — needs at least 10 tracked
    videos across different hours before it starts shifting.
    """
    # Use the upload registry from the upload_registry.json file directly.
    # (No public getter exists for the raw registry yet.)
    from modules.performance_tracker import load_performance_history
    from config import LOG_DIR
    upload_registry_path = os.path.join(LOG_DIR, "upload_registry.json")
    registry = {"videos": []}
    if os.path.exists(upload_registry_path):
        try:
            with open(upload_registry_path, "r") as f:
                registry = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    params = state["parameters"]
    current_times = params.get("posting_times_by_day", {})

    # Load real performance data (last 7 days)
    entries = load_performance_history(hours=168)
    if len(entries) < 10:
        return  # Not enough data yet

    registry = _load_registry()
    registry_by_id = {v["video_id"]: v for v in registry.get("videos", [])}

    # Group by hour of upload time and calculate avg view_velocity
    hour_performance = {}  # hour -> [view_velocity]
    for entry in entries:
        vid = entry.get("video_id", "")
        reg = registry_by_id.get(vid, {})
        upload_str = reg.get("uploaded_at", "")
        if not upload_str:
            continue
        try:
            upload_hour = datetime.fromisoformat(upload_str).hour
        except (ValueError, TypeError):
            continue

        vv = entry.get("signals", {}).get("view_velocity", 0)
        if vv > 0:
            hour_performance.setdefault(upload_hour, []).append(vv)

    if len(hour_performance) < 3:
        return  # Need data across at least 3 different hours

    # Calculate average per hour and sort
    hour_avgs = {h: round(sum(vals) / len(vals), 1) for h, vals in hour_performance.items()}
    best_hours = sorted(hour_avgs, key=hour_avgs.get, reverse=True)[:5]

    # Group best hours by day of week
    from config import POSTING_TIMES_BY_DAY
    day_hour_perf = {}  # {our_day: {hour: [view_velocities]}}
    for entry in entries:
        vid = entry.get("video_id", "")
        reg = registry_by_id.get(vid, {})
        upload_str = reg.get("uploaded_at", "")
        if not upload_str:
            continue
        try:
            dt = datetime.fromisoformat(upload_str)
            day = dt.weekday()
            our_day = (day + 1) % 7
            hour = dt.hour
        except (ValueError, TypeError):
            continue

        vv = entry.get("signals", {}).get("view_velocity", 0)
        if vv > 0:
            day_hour_perf.setdefault(our_day, {}).setdefault(hour, []).append(vv)

    # For each day, pick top 3 hours
    evolved = {}
    for day in range(7):
        hour_data = day_hour_perf.get(day, {})
        if not hour_data:
            continue
        avgs = {h: round(sum(vals) / len(vals), 1) for h, vals in hour_data.items()}
        top_3 = sorted(avgs, key=avgs.get, reverse=True)[:3]
        if len(top_3) >= 2:
            evolved[day] = [(h, 0) for h in sorted(top_3)]

    if len(evolved) >= 3:  # Only mutate if we have data for at least 3 days
        # Merge evolved times with existing defaults (evolved wins)
        merged = dict(POSTING_TIMES_BY_DAY)
        for day, times in evolved.items():
            merged[day] = times
        params["posting_times_by_day"] = merged

        state["mutations"].append({
            "timestamp": datetime.now().isoformat(),
            "axis": "posting_times",
            "change": f"Adjusted posting times from real view velocity data ({len(evolved)} days updated)",
            "hour_performance": {str(h): hour_avgs[h] for h in best_hours[:3]},
        })
        print(f"  [evolution] Posting times evolved: best hours = {best_hours[:3]}", flush=True)


def get_evolved_posting_times():
    """Public getter for evolved posting times.

    Returns evolved posting_times_by_day dict, or None if not evolved.
    """
    state = _load_state()
    pts = state.get("parameters", {}).get("posting_times_by_day", {})
    if pts and len(pts) >= 3:
        return dict(pts)
    return None


def evolve():
    """Run one evolution cycle.

    This is called by the pipeline after each successful upload.
    It reads the latest critique data, calculates trends, and
    mutates pipeline parameters autonomously.

    Returns:
        Dict summarizing the evolution cycle.
    """
    print(f"\n{'=' * 50}")
    print(f"  VARY Evolution Engine - v1.0")
    print(f"{'=' * 50}")

    state = _load_state()
    generation = state.get("generation", 1)

    print(f"  Generation: {generation}")
    print(f"  Total clips analyzed: {state['performance']['total_clips_analyzed']}")
    print(f"  Current avg score: {state['performance']['average_score']:.1f}")

    # Load critiques
    critiques = _load_recent_critiques(hours=72)

    if not critiques:
        print(f"  [evolution] No critique data available yet. Skipping evolution.", flush=True)
        return {
            "generation": generation,
            "evolved": False,
            "reason": "no_data",
            "mutations": 0,
            "parameters": state["parameters"],
        }

    # Calculate trends
    trends = _calculate_performance_trends(critiques)

    if not trends:
        print(f"  [evolution] Could not calculate trends. Skipping.", flush=True)
        return {
            "generation": generation,
            "evolved": False,
            "reason": "trend_error",
            "mutations": 0,
        }

    print(f"  Trends: avg={trends['average_score']}, peak={trends['peak_score']}, "
          f"count={trends['count']}")

    # Run mutations
    mutations_before = len(state["mutations"])

    _mutate_content_weights(state, trends)
    _mutate_keywords(state, trends)
    _mutate_clip_duration(state, trends)
    _mutate_scene_threshold(state, trends)
    _mutate_title_style(state, trends)

    # ── Real-world performance mutation ────────────────
    # Real YouTube engagement data overrides simulated critique scores.
    # The performance tracker's trends provide ground-truth signals that
    # can override or amplify the critique-based mutations above.
    _mutate_from_real_performance(state)

    # ── Posting time evolution ──────────────────────────
    # Learn when viewers are most active from real view velocity data
    _mutate_posting_times(state)

    # Update performance metrics
    state["performance"]["average_score"] = trends["average_score"]
    state["performance"]["peak_score"] = max(
        state["performance"]["peak_score"], trends["peak_score"]
    )
    state["performance"]["total_clips_analyzed"] += trends["count"]
    state["performance"]["history_by_type"] = trends["type_averages"]
    state["performance"]["history_by_hour"] = trends["hour_averages"]

    # Check if any mutations occurred
    mutated = len(state["mutations"]) > mutations_before
    if mutated:
        state["generation"] = generation + 1
        state["performance"]["total_evolutions"] += 1

    # Save state
    _save_state(state)

    # Log
    _log_evolution("evolve_cycle", {
        "generation": state["generation"],
        "mutated": mutated,
        "mutation_count": len(state["mutations"]) - mutations_before,
        "trends": trends,
    })

    print(f"  Mutations: {len(state['mutations']) - mutations_before}")
    print(f"  State saved. Generation {state['generation']}")
    print(f"{'─' * 50}\n")

    return {
        "generation": state["generation"],
        "evolved": mutated,
        "mutations": len(state["mutations"]) - mutations_before,
        "trends": {
            "average_score": trends["average_score"],
            "peak_score": trends["peak_score"],
            "weakest_type": trends.get("weakest_type"),
            "best_hour": trends.get("best_hour"),
            "axis_averages": trends.get("axis_averages", {}),
        },
        "parameters": state["parameters"],
    }


def get_evolution_status():
    """Get current evolution state for reporting/API."""
    state = _load_state()
    return {
        "generation": state["generation"],
        "total_evolutions": state["performance"]["total_evolutions"],
        "total_clips_analyzed": state["performance"]["total_clips_analyzed"],
        "average_score": state["performance"]["average_score"],
        "peak_score": state["performance"]["peak_score"],
        "real_performance_average": state["performance"]["real_performance_average"],
        "real_videos_tracked": state["performance"]["real_videos_tracked"],
        "critique_vs_real_delta": state["performance"]["critique_vs_real_delta"],
        "parameters": state["parameters"],
        "last_updated": state["last_updated"],
    }


def get_parameter(key, default=None):
    """Public getter for a single evolution parameter.

    Used by clip_editor, seo_generator, content_selector, etc.
    to read evolved values without importing private functions.

    Args:
        key: Parameter name (e.g. 'clip_min_duration', 'title_style_preference')
        default: Value to return if key doesn't exist

    Returns:
        Parameter value, or default if not found.
    """
    state = _load_state()
    return state.get("parameters", {}).get(key, default)


def get_evolved_weights():
    """Public getter for evolved content weights.

    Returns:
        Dict of content weights for football/movie/series, or None if not evolved.
    """
    state = _load_state()
    params = state.get("parameters", {}).get("content_weights")
    if params and all(isinstance(v, (int, float)) for v in params.values()):
        return dict(params)
    return None


def get_evolved_keywords(content_type):
    """Public getter for evolved search keywords.

    Args:
        content_type: 'football', 'movie', or 'series'

    Returns:
        List of keywords, or None if not evolved yet.
    """
    state = _load_state()
    key_map = {"football": "football_keywords", "movie": "movie_keywords", "series": "series_keywords"}
    key = key_map.get(content_type, "movie_keywords")
    kws = state.get("parameters", {}).get(key)
    if kws and isinstance(kws, list):
        return list(kws)
    return None


def reset_evolution():
    """Reset the evolution engine to defaults (for testing)."""
    _save_state(deepcopy(DEFAULT_EVOLUTION_STATE))
    _log_evolution("reset", {"message": "Evolution state reset to defaults"})
    return True


if __name__ == "__main__":
    import sys
    # Fix Windows console encoding for Unicode characters
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        reset_evolution()
        print("Evolution reset.")
    elif len(sys.argv) > 1 and sys.argv[1] == "--status":
        print(json.dumps(get_evolution_status(), indent=2))
    else:
        result = evolve()
        print(json.dumps(result, indent=2, default=str))
