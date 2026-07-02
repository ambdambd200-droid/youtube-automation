"""
VARY — Performance Dashboard.
Compares daily Shorts vs weekly video performance across critique scores,
real YouTube metrics, upload volume, and trends.

Usage:
    python run_performance_dashboard.py                  # Full dashboard
    python run_performance_dashboard.py --daily           # Daily Shorts only
    python run_performance_dashboard.py --weekly          # Weekly videos only
    python run_performance_dashboard.py --realtime        # Real performance (YouTube API)
    python run_performance_dashboard.py --json            # JSON output (for API/n8n)
    python run_performance_dashboard.py --trends          # Trend analysis only
"""
import json
import os
import sys
import math
from datetime import datetime, timedelta
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import LOG_DIR


# ── Data Loaders ─────────────────────────────────────────────

UPLOAD_REGISTRY = os.path.join(LOG_DIR, "upload_registry.json")
CRITIQUE_LOG = os.path.join(LOG_DIR, "critique_scores.jsonl")
WEEKLY_CRITIQUE_LOG = os.path.join(LOG_DIR, "weekly_critique_scores.jsonl")
PERFORMANCE_LOG = os.path.join(LOG_DIR, "performance_log.jsonl")
WEEKLY_PIPELINE_LOG = os.path.join(LOG_DIR, "weekly_pipeline_log.jsonl")
PIPELINE_LOG = os.path.join(LOG_DIR, "pipeline_log.jsonl")
CONTENT_HISTORY = os.path.join(LOG_DIR, "content_history.json")
EVOLUTION_STATE = os.path.join(LOG_DIR, "evolution_state.json")


def load_json(path, default=None):
    """Safely load a JSON file."""
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def load_jsonl(path):
    """Load a JSONL file into a list of dicts."""
    if not os.path.exists(path):
        return []
    entries = []
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except IOError:
        pass
    return entries


def _parse_dt_safe(iso_str, default=None):
    """Parse an ISO datetime string, returning default on failure."""
    if not iso_str:
        return default
    try:
        return datetime.fromisoformat(iso_str).replace(tzinfo=None)
    except (ValueError, TypeError):
        return default


def load_performance_log():
    """Load performance log, deduplicating to keep latest entry per video."""
    entries = load_jsonl(PERFORMANCE_LOG)
    # Keep only the latest entry per video_id
    latest = {}
    for e in entries:
        vid = e.get("video_id")
        if vid:
            latest[vid] = e  # later entries overwrite earlier ones
    return list(latest.values())


# ── Daily Critique Axis Names ───────────────────────────────

DAILY_AXES = [
    "first_frame_hook",
    "motion_dynamics",
    "audio_impact",
    "scene_composition",
    "color_vibrancy",
    "pacing",
]
DAILY_AXIS_LABELS = {
    "first_frame_hook": "First Frame Hook",
    "motion_dynamics": "Motion Dynamics",
    "audio_impact": "Audio Impact",
    "scene_composition": "Scene Composition",
    "color_vibrancy": "Color Vibrancy",
    "pacing": "Pacing",
}
WEEKLY_AXES = [
    "visual_quality",
    "audio_quality",
    "pacing",
    "story_coherence",
    "narrative_flow",
    "intro_presence",
]
WEEKLY_AXIS_LABELS = {
    "visual_quality": "Visual Quality",
    "audio_quality": "Audio Quality",
    "pacing": "Pacing",
    "story_coherence": "Story Coherence",
    "narrative_flow": "Narrative Flow",
    "intro_presence": "Intro Presence",
}


# ── Dashboard Data Builder ──────────────────────────────────

def build_dashboard_data():
    """Load all data sources and build a structured comparison."""
    registry = load_json(UPLOAD_REGISTRY, {"videos": []})
    daily_critiques = load_jsonl(CRITIQUE_LOG)
    weekly_critiques = load_jsonl(WEEKLY_CRITIQUE_LOG)
    perf_entries = load_performance_log()
    weekly_pipeline_logs = load_jsonl(WEEKLY_PIPELINE_LOG)
    daily_pipeline_logs = load_jsonl(PIPELINE_LOG)
    evolution_state = load_json(EVOLUTION_STATE, {})
    content_history = load_json(CONTENT_HISTORY, {"items": [], "total_count": 0})

    videos = registry.get("videos", [])

    # ── Split by content type ─────────────────────────────
    daily_videos = [v for v in videos if v.get("content_type") in ("movie", "football", "series")]
    weekly_videos = [v for v in videos if v.get("content_type") == "weekly_movie"]

    # ── Critique stats ────────────────────────────────────
    def critique_averages(critiques, axes):
        """Compute per-axis and compound averages from critique entries."""
        if not critiques:
            return {"count": 0, "axes": {a: 0 for a in axes}, "compound": 0}
        result = {"count": len(critiques), "axes": {}, "compound": 0}
        for axis in axes:
            vals = [c.get("axes", {}).get(axis, 50) for c in critiques]
            result["axes"][axis] = round(sum(vals) / len(vals), 1) if vals else 0
        compounds = [c.get("compound_score", 50) for c in critiques]
        result["compound"] = round(sum(compounds) / len(compounds), 1) if compounds else 0
        return result

    daily_critique_avgs = critique_averages(daily_critiques, DAILY_AXES)
    weekly_critique_avgs = critique_averages(weekly_critiques, WEEKLY_AXES)

    # Split daily critiques by sub-type
    movie_critiques = [c for c in daily_critiques if c.get("content_type") == "movie"]
    fb_critiques = [c for c in daily_critiques if c.get("content_type") == "football"]
    movie_crit_avgs = critique_averages(movie_critiques, DAILY_AXES)
    fb_crit_avgs = critique_averages(fb_critiques, DAILY_AXES)

    # ── Performance stats (real YouTube data) ─────────────
    def perf_stats(entries, content_type_filter=None):
        """Compute aggregate performance stats from YouTube data."""
        filtered = entries
        if content_type_filter:
            # Normalize to a tuple for membership check
            if isinstance(content_type_filter, str):
                filter_types = (content_type_filter,)
            else:
                filter_types = tuple(content_type_filter)
            # Match by video_id in registry
            reg_by_id = {v["video_id"]: v for v in videos}
            filtered = [e for e in entries if reg_by_id.get(e.get("video_id", ""), {}).get("content_type") in filter_types]

        if not filtered:
            return {"count": 0}

        total_views = sum(e.get("raw_stats", {}).get("view_count", 0) for e in filtered)
        total_likes = sum(e.get("raw_stats", {}).get("like_count", 0) for e in filtered)
        total_comments = sum(e.get("raw_stats", {}).get("comment_count", 0) for e in filtered)

        signals = [e.get("signals", {}) for e in filtered if e.get("signals")]
        avg_view_velocity = round(sum(s.get("view_velocity", 0) for s in signals) / len(signals), 1) if signals else 0
        avg_like_ratio = round(sum(s.get("like_ratio", 0) for s in signals) / len(signals), 2) if signals else 0
        avg_perf_score = round(sum(s.get("performance_score", 0) for s in signals) / len(signals), 1) if signals else 0
        avg_engagement = round(sum(s.get("engagement_rate", 0) for s in signals) / len(signals), 2) if signals else 0

        return {
            "count": len(filtered),
            "total_views": total_views,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "avg_view_velocity": avg_view_velocity,
            "avg_like_ratio": avg_like_ratio,
            "avg_performance_score": avg_perf_score,
            "avg_engagement_rate": avg_engagement,
        }

    daily_perf = perf_stats(perf_entries, content_type_filter=("movie", "football", "series"))
    # Weekly performance — filter for weekly_movie type
    weekly_perf = perf_stats(perf_entries, content_type_filter="weekly_movie")

    # ── Upload timeline ───────────────────────────────────
    def build_timeline(videos):
        """Build upload timeline grouped by day."""
        day_counts = Counter()
        for v in videos:
            try:
                day = datetime.fromisoformat(v.get("uploaded_at", "")).strftime("%Y-%m-%d")
                day_counts[day] += 1
            except (ValueError, TypeError):
                pass
        return dict(sorted(day_counts.items()))

    daily_timeline = build_timeline(daily_videos)
    weekly_timeline = build_timeline(weekly_videos)

    # ── Grade distribution ─────────────────────────────────
    def grade_distribution(critiques):
        grades = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        for c in critiques:
            score = c.get("compound_score", 50)
            if score >= 80:
                grades["A"] += 1
            elif score >= 65:
                grades["B"] += 1
            elif score >= 50:
                grades["C"] += 1
            elif score >= 35:
                grades["D"] += 1
            else:
                grades["F"] += 1
        return grades

    # ── Recent performance (last 7 days) ──────────────────
    seven_days_ago = datetime.now() - timedelta(days=7)
    recent_perf = []
    for e in perf_entries:
        fetched = _parse_dt_safe(e.get("fetched_at"))
        if fetched and fetched > seven_days_ago:
            recent_perf.append(e)

    def best_performers(perf_list, videos, n=5):
        """Find top N best performing videos."""
        reg_by_id = {v["video_id"]: v for v in videos}
        scored = []
        for e in perf_list:
            vid = e.get("video_id", "")
            reg = reg_by_id.get(vid, {})
            signal = e.get("signals", {})
            scored.append({
                "video_id": vid,
                "title": reg.get("seo_title", reg.get("title", vid)),
                "content_type": reg.get("content_type", "unknown"),
                "views": e.get("raw_stats", {}).get("view_count", 0),
                "performance_score": signal.get("performance_score", 0),
                "view_velocity": signal.get("view_velocity", 0),
            })
        scored.sort(key=lambda x: x["performance_score"], reverse=True)
        return scored[:n]

    top_videos = best_performers(recent_perf, videos) if recent_perf else best_performers(perf_entries, videos)

    # ── Pipeline health data ─────────────────────────────
    pipeline_health = None
    try:
        from modules.pipeline_watchdog import get_runs_summary
        pipeline_health = get_runs_summary()
    except Exception:
        pass

    # ── Evolution data ────────────────────────────────────
    evolution_params = evolution_state.get("parameters", {})
    evolution_perf = evolution_state.get("performance", {})

    return {
        "registry": {
            "total": len(videos),
            "daily": len(daily_videos),
            "weekly": len(weekly_videos),
            "daily_by_type": {
                "movie": len([v for v in daily_videos if v.get("content_type") == "movie"]),
                "football": len([v for v in daily_videos if v.get("content_type") == "football"]),
            },
        },
        "daily_critique": daily_critique_avgs,
        "weekly_critique": weekly_critique_avgs,
        "movie_critique": movie_crit_avgs,
        "fb_critique": fb_crit_avgs,
        "daily_performance": daily_perf,
        "weekly_performance": weekly_perf,
        "daily_timeline": daily_timeline,
        "weekly_timeline": weekly_timeline,
        "daily_grade_dist": grade_distribution(daily_critiques),
        "weekly_grade_dist": grade_distribution(weekly_critiques),
        "top_videos": top_videos,
        "evolution": {
            "generation": evolution_state.get("generation", 1),
            "avg_score": evolution_perf.get("average_score"),
            "peak_score": evolution_perf.get("peak_score"),
            "total_analyzed": evolution_perf.get("total_clips_analyzed", 0),
            "mutations": evolution_state.get("mutations", []),
        },
        "content_history": {
            "total_queries": content_history.get("total_count", 0),
        },
        "pipeline_health": pipeline_health,
        "weekly_pipeline_logs": len(weekly_pipeline_logs),
        "daily_pipeline_logs": len(daily_pipeline_logs),
        "last_updated": datetime.now().isoformat(),
    }


# ── Renderers ────────────────────────────────────────────────

def _bar(value, width=20, max_val=100, filled="█", empty="░"):
    """Render a horizontal bar."""
    filled_count = int((value / max_val) * width) if max_val > 0 else 0
    filled_count = min(filled_count, width)
    return filled * filled_count + empty * (width - filled_count)


def _format_number(n):
    """Format number with K/M suffix."""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def _colorize_score(score, reverse=False):
    """Return score with emoji indicator."""
    if not reverse:
        if score >= 75:
            return f"🟢 {score}"
        elif score >= 50:
            return f"🟡 {score}"
        else:
            return f"🔴 {score}"
    else:
        if score >= 75:
            return f"🔴 {score}"
        elif score >= 50:
            return f"🟡 {score}"
        else:
            return f"🟢 {score}"


def render_header(data):
    """Render the dashboard header."""
    reg = data["registry"]
    total = reg["total"]
    daily = reg["daily"]
    weekly = reg["weekly"]

    print(f"\n{'='*64}")
    print(f"  VARY — Performance Dashboard")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*64}")

    print(f"\n  📊 OVERVIEW")
    print(f"  {'─'*60}")
    print(f"  Total videos uploaded:     {total}")
    print(f"  ├─ Daily Shorts:           {daily}  ({reg['daily_by_type']['movie']} movie, {reg['daily_by_type']['football']} football)")
    print(f"  └─ Weekly Videos:          {weekly}")
    print(f"  Content queries run:       {data['content_history']['total_queries']}")
    print(f"  Evolution generation:      {data['evolution']['generation']}")


def render_critique_comparison(data):
    """Render the critique score comparison between daily and weekly."""
    dc = data["daily_critique"]
    wc = data["weekly_critique"]
    mc = data["movie_critique"]
    fbc = data["fb_critique"]

    print(f"\n  🎯 CRITIQUE SCORE COMPARISON")
    print(f"  {'─'*60}")

    # Compound scores side by side
    print(f"  {'Category':<20} {'Compound':>10} {'Videos':>8}")
    print(f"  {'─'*40}")
    print(f"  {'Daily Shorts':<20} {_colorize_score(dc['compound']):>10} {dc['count']:>8}")
    if mc["count"]:
        print(f"  {'  ├─ Movie':<20} {mc['compound']:>10} {mc['count']:>8}")
    if fbc["count"]:
        print(f"  {'  ├─ Football':<20} {fbc['compound']:>10} {fbc['count']:>8}")
    print(f"  {'Weekly Videos':<20} {_colorize_score(wc['compound']):>10} {wc['count']:>8}")

    if dc["count"] > 0 and wc["count"] > 0:
        delta = wc["compound"] - dc["compound"]
        delta_str = f"+{delta:.1f}" if delta >= 0 else f"{delta:.1f}"
        direction = "Weekly videos OUTPERFORM daily shorts" if delta > 0 else "Daily shorts OUTPERFORM weekly videos"
        print(f"  {'─'*40}")
        print(f"  Delta (weekly - daily): {delta_str}")
        print(f"  → {direction}" if abs(delta) > 0 else "  → Equal performance")

    # Grade distribution
    print(f"\n  📊 GRADE DISTRIBUTION")
    print(f"  {'─'*60}")
    dg = data["daily_grade_dist"]
    wg = data["weekly_grade_dist"]
    all_grades = ["A", "B", "C", "D", "F"]
    print(f"  {'Grade':<8} {'Daily':>8} {'Bar':<25} {'Weekly':>8} {'Bar':<25}")
    print(f"  {'─'*72}")
    for grade in all_grades:
        d_count = dg.get(grade, 0)
        w_count = wg.get(grade, 0)
        max_count = max(max(dg.values()), max(wg.values()), 1)
        d_bar = _bar(d_count, width=20, max_val=max_count, filled="█", empty="░")
        w_bar = _bar(w_count, width=20, max_val=max_count, filled="█", empty="░")
        print(f"  {grade:<8} {d_count:>8} {d_bar:<25} {w_count:>8} {w_bar:<25}")


def render_axis_breakdown(data):
    """Render per-axis breakdown for daily and weekly critiques."""
    dc = data["daily_critique"]
    wc = data["weekly_critique"]

    # Daily axes
    print(f"\n  📐 PER-AXIS BREAKDOWN")
    print(f"  {'─'*60}")

    print(f"\n  ▶ Daily Shorts Axes:")
    print(f"  {'Axis':<22} {'Score':>7} {'Bar':<30}")
    print(f"  {'─'*57}")
    for axis in DAILY_AXES:
        score = dc["axes"].get(axis, 0)
        label = DAILY_AXIS_LABELS.get(axis, axis)
        bar = _bar(score, width=24)
        color = "🟢" if score >= 65 else ("🟡" if score >= 40 else "🔴")
        print(f"  {label:<22} {color} {score:>5.1f} {bar:<24}")

    print(f"\n  ▶ Weekly Video Axes:")
    print(f"  {'Axis':<22} {'Score':>7} {'Bar':<30}")
    print(f"  {'─'*57}")
    for axis in WEEKLY_AXES:
        score = wc["axes"].get(axis, 0)
        label = WEEKLY_AXIS_LABELS.get(axis, axis)
        bar = _bar(score, width=24)
        color = "🟢" if score >= 65 else ("🟡" if score >= 40 else "🔴")
        print(f"  {label:<22} {color} {score:>5.1f} {bar:<24}")

    # Weakest / strongest axes
    if dc["count"] > 0:
        sorted_daily = sorted(DAILY_AXES, key=lambda a: dc["axes"].get(a, 0))
        print(f"\n  ▶ Daily: Strongest = {DAILY_AXIS_LABELS.get(sorted_daily[-1], sorted_daily[-1])} "
              f"({dc['axes'].get(sorted_daily[-1], 0):.1f})  |  "
              f"Weakest = {DAILY_AXIS_LABELS.get(sorted_daily[0], sorted_daily[0])} "
              f"({dc['axes'].get(sorted_daily[0], 0):.1f})")
    if wc["count"] > 0:
        sorted_weekly = sorted(WEEKLY_AXES, key=lambda a: wc["axes"].get(a, 0))
        print(f"  ▶ Weekly: Strongest = {WEEKLY_AXIS_LABELS.get(sorted_weekly[-1], sorted_weekly[-1])} "
              f"({wc['axes'].get(sorted_weekly[-1], 0):.1f})  |  "
              f"Weakest = {WEEKLY_AXIS_LABELS.get(sorted_weekly[0], sorted_weekly[0])} "
              f"({wc['axes'].get(sorted_weekly[0], 0):.1f})")


def render_performance(data):
    """Render real YouTube performance data."""
    dp = data["daily_performance"]
    wp = data["weekly_performance"]

    has_daily = dp.get("count", 0) > 0
    has_weekly = wp.get("count", 0) > 0

    if not has_daily and not has_weekly:
        print(f"\n  📈 REAL PERFORMANCE")
        print(f"  {'─'*60}")
        print(f"  No YouTube performance data yet. Run the performance poll first:")
        print(f"  $ python -m modules.performance_tracker --poll")
        return

    print(f"\n  📈 REAL PERFORMANCE (YouTube Analytics)")
    print(f"  {'─'*60}")

    if has_daily:
        print(f"\n  ▶ Daily Shorts ({dp['count']} videos with data):")
        print(f"  {'Metric':<28} {'Value':>12}")
        print(f"  {'─'*40}")
        print(f"  {'Total views':<28} {_format_number(dp['total_views']):>12}")
        print(f"  {'Total likes':<28} {_format_number(dp['total_likes']):>12}")
        print(f"  {'Total comments':<28} {_format_number(dp['total_comments']):>12}")
        print(f"  {'Avg view velocity (views/hr)':<28} {dp['avg_view_velocity']:>12.1f}")
        print(f"  {'Avg like ratio (%)':<28} {dp['avg_like_ratio']:>12.2f}")
        print(f"  {'Avg engagement rate (%)':<28} {dp['avg_engagement_rate']:>12.2f}")
        print(f"  {'Avg performance score':<28} {dp['avg_performance_score']:>12.1f}")

    if has_weekly:
        print(f"\n  ▶ Weekly Videos ({wp['count']} videos with data):")
        print(f"  {'Metric':<28} {'Value':>12}")
        print(f"  {'─'*40}")
        print(f"  {'Total views':<28} {_format_number(wp['total_views']):>12}")
        print(f"  {'Total likes':<28} {_format_number(wp['total_likes']):>12}")
        print(f"  {'Total comments':<28} {_format_number(wp['total_comments']):>12}")
        print(f"  {'Avg view velocity (views/hr)':<28} {wp['avg_view_velocity']:>12.1f}")
        print(f"  {'Avg like ratio (%)':<28} {wp['avg_like_ratio']:>12.2f}")
        print(f"  {'Avg engagement rate (%)':<28} {wp['avg_engagement_rate']:>12.2f}")
        print(f"  {'Avg performance score':<28} {wp['avg_performance_score']:>12.1f}")

    if has_daily and has_weekly:
        print(f"\n  {'─'*40}")
        print(f"  Daily vs Weekly comparison (where both have data):")
        dp_score = dp.get("avg_performance_score", 0)
        wp_score = wp.get("avg_performance_score", 0)
        if dp_score > 0 or wp_score > 0:
            delta = wp_score - dp_score
            delta_str = f"+{delta:.1f}" if delta >= 0 else f"{delta:.1f}"
            print(f"  Performance delta (weekly - daily): {delta_str}")
        # Critique vs real delta
        dc = data["daily_critique"]
        wc = data["weekly_critique"]
        if dc["count"] > 0 and dp["count"] > 0:
            crit_real_delta = dp["avg_performance_score"] - dc["compound"]
            print(f"  Daily: Critique ({dc['compound']:.1f}) vs Real ({dp['avg_performance_score']:.1f}) = Δ{crit_real_delta:+.1f}")
        if wc["count"] > 0 and wp["count"] > 0:
            crit_real_delta = wp["avg_performance_score"] - wc["compound"]
            print(f"  Weekly: Critique ({wc['compound']:.1f}) vs Real ({wp['avg_performance_score']:.1f}) = Δ{crit_real_delta:+.1f}")

    # Top performing videos
    top = data.get("top_videos", [])
    if top:
        print(f"\n  🏆 TOP PERFORMERS (recent)")
        print(f"  {'─'*60}")
        print(f"  {'#':<4} {'Title':<30} {'Type':<14} {'Views':>8} {'Score':>7}")
        print(f"  {'─'*63}")
        for i, v in enumerate(top, 1):
            title = v["title"][:28] + ".." if len(v["title"]) > 28 else v["title"]
            ctype = v["content_type"]
            if ctype == "weekly_movie":
                ctype_label = "Weekly"
            elif ctype == "football":
                ctype_label = "Football"
            else:
                ctype_label = "Movie"
            print(f"  {i:<4} {title:<30} {ctype_label:<14} {_format_number(v['views']):>8} {v['performance_score']:>6.1f}")


def render_timeline(data):
    """Render upload timeline for both daily and weekly."""
    daily_tl = data["daily_timeline"]
    weekly_tl = data["weekly_timeline"]

    if not daily_tl and not weekly_tl:
        return

    print(f"\n  📅 UPLOAD TIMELINE")
    print(f"  {'─'*60}")

    # Merge all dates
    all_dates = sorted(set(list(daily_tl.keys()) + list(weekly_tl.keys())))
    max_daily = max(daily_tl.values()) if daily_tl else 0
    max_weekly = max(weekly_tl.values()) if weekly_tl else 0
    max_col = max(max_daily, max_weekly, 1)
    bar_width = 25

    print(f"  {'Date':<12} {'Daily':>6} {'Bar':<{bar_width+2}} {'Weekly':>6}")
    print(f"  {'─'*max(12 + 6 + bar_width + 2 + 6 + 2, 40)}")
    for date in all_dates:
        d_count = daily_tl.get(date, 0)
        w_count = weekly_tl.get(date, 0)
        d_bar = _bar(d_count, width=bar_width, max_val=max_col)
        w_str = f"{w_count}" if w_count > 0 else "—"
        print(f"  {date:<12} {d_count:>6} {d_bar:<{bar_width+2}} {w_str:>6}")


def render_evolution_summary(data):
    """Render evolution engine summary."""
    evo = data["evolution"]
    if not evo:
        return

    print(f"\n  🧬 EVOLUTION ENGINE")
    print(f"  {'─'*60}")
    print(f"  Generation:                 {evo['generation']}")
    if evo["avg_score"]:
        print(f"  Average critique score:     {evo['avg_score']:.1f}")
    if evo["peak_score"]:
        print(f"  Peak critique score:        {evo['peak_score']:.1f}")
    print(f"  Total clips analyzed:       {evo['total_analyzed']}")
    mutations = evo.get("mutations", [])
    if mutations:
        print(f"  Total evolutions:           {len(mutations)}")
        # Show recent mutations
        for m in mutations[-3:]:
            axis = m.get("axis", "")
            change = m.get("change", "")
            ts = m.get("timestamp", "")[:10]
            print(f"    • [{ts}] {axis}: {change}")


def render_watchdog_summary(data):
    """Render pipeline watchdog health summary."""
    health = data.get("pipeline_health")
    if not health or health.get("total_runs", 0) == 0:
        return

    print(f"\n  🛡️ PIPELINE HEALTH")
    print(f"  {'─'*60}")

    total = health["total_runs"]
    completed = health["completed"]
    failed = health["failed"]
    running = health["running"]
    recent_fails = health.get("recent_failures_4h", 0)

    # Compute success rate
    success_rate = round((completed / total) * 100, 1)

    print(f"  Total runs tracked:         {total}")
    print(f"  Completed:                  {completed}  ({_bar(completed, width=15, max_val=max(total, 1))})")
    print(f"  Failed:                     {failed}  ({_bar(failed, width=15, max_val=max(total, 1))})")
    if running > 0:
        print(f"  Currently running:          {running}  ⏳")
    print(f"  Success rate:               {success_rate}%")

    if recent_fails > 0:
        fail_icon = "🔴" if recent_fails >= 3 else "🟡"
        print(f"  Failures (last 4h):         {fail_icon} {recent_fails}")
    else:
        print(f"  Failures (last 4h):         🟢 0")

    recovery = health.get("recovery_retries", 0)
    if recovery > 0:
        print(f"  Recovery retries:           {recovery}")

    # Recent activity (last 5 runs)
    recent = health.get("recent_activity", [])
    if recent:
        print(f"\n  ▶ Recent runs (newest first):")
        for r in recent[:5]:
            rid = r["id"]
            rtype = r.get("type", "?")
            rstatus = r["status"]
            rstage = r.get("stage", "")
            start = r.get("start", "")[11:19] if r.get("start") else ""
            icon = "✅" if rstatus == "completed" else ("❌" if rstatus == "failed" else "⏳")
            err = r.get("error", "")
            err_snip = f" — {err[:60]}" if err else ""
            print(f"    {icon} [{start}] {rtype} {rid.split('_')[-1]} — {rstage}{err_snip}")


def render_recommendations(data):
    """Generate actionable recommendations based on dashboard data."""
    dc = data["daily_critique"]
    wc = data["weekly_critique"]
    dp = data["daily_performance"]
    wp = data["weekly_performance"]

    print(f"\n  💡 RECOMMENDATIONS")
    print(f"  {'─'*60}")

    recs = []

    # Critique-based recommendations
    if dc["count"] > 0:
        sorted_daily = sorted(DAILY_AXES, key=lambda a: dc["axes"].get(a, 0))
        weakest_daily = dc["axes"].get(sorted_daily[0], 0)
        if weakest_daily < 40:
            recs.append(f"🔴 Daily Shorts: {DAILY_AXIS_LABELS.get(sorted_daily[0])} is critically low ({weakest_daily:.1f}). "
                        f"Focus on improving this in clip selection.")

    if wc["count"] > 0:
        sorted_weekly = sorted(WEEKLY_AXES, key=lambda a: wc["axes"].get(a, 0))
        weakest_weekly = wc["axes"].get(sorted_weekly[0], 0)
        if weakest_weekly < 40:
            recs.append(f"🔴 Weekly Videos: {WEEKLY_AXIS_LABELS.get(sorted_weekly[0])} is critically low ({weakest_weekly:.1f}). "
                        f"Review source material selection.")

    # Performance-based recommendations
    if dp.get("count", 0) > 0 and dp.get("avg_like_ratio", 0) < 3:
        recs.append(f"🟡 Daily Shorts like ratio is low ({dp['avg_like_ratio']:.1f}%). "
                    f"Consider adding stronger CTAs or more engaging content types.")

    if wp.get("count", 0) > 0 and wp.get("avg_like_ratio", 0) < 4:
        recs.append(f"🟡 Weekly Videos like ratio is low ({wp['avg_like_ratio']:.1f}%). "
                    f"Review storytelling quality and audio clarity.")

    # Critique vs real delta
    if dc["count"] > 0 and dp.get("count", 0) > 0:
        delta = dp["avg_performance_score"] - dc["compound"]
        if abs(delta) > 15:
            direction = "underestimates" if delta > 0 else "overestimates"
            recs.append(f"🟡 Critique engine {direction} daily performance by {abs(delta):.1f} points. "
                        f"Consider recalibrating critique weights.")

    # Content mix
    reg = data["registry"]
    if reg["daily"] > 0 and reg["weekly"] == 0:
        recs.append(f"🔵 Weekly video pipeline is set up but no weekly videos uploaded yet. "
                    f"Check the GitHub Action or run manually: python run_weekly_pipeline.py")
    elif reg["daily"] == 0:
        recs.append(f"🔵 No videos uploaded yet. Run the daily pipeline first.")

    # Pipeline health
    health = data.get("pipeline_health")
    if health:
        recent_fails = health.get("recent_failures_4h", 0)
        if recent_fails > 0:
            recs.append(f"🔴 {recent_fails} pipeline failure{'s' if recent_fails != 1 else ''} in the last 4h. "
                        f"Run recovery: python run_recovery.py")
        running = health.get("running", 0)
        if running > 0:
            recs.append(f"⏳ {running} pipeline run{'s' if running != 1 else ''} currently in progress.")
        success_rate = round((health["completed"] / max(health["total_runs"], 1)) * 100, 1)
        if health["total_runs"] >= 5 and success_rate < 70:
            recs.append(f"🟡 Pipeline success rate is {success_rate}% (below 70%). Consider reviewing logs.")

    # Evolution
    evo = data["evolution"]
    if evo["total_analyzed"] > 0 and evo["generation"] <= 2:
        recs.append(f"🟢 Evolution engine is still young (generation {evo['generation']}). "
                    f"More data will improve parameter optimization over time.")

    # General
    if dc["compound"] > 0 and dc["compound"] < 50:
        recs.append(f"🟡 Daily critique average ({dc['compound']:.1f}) is below 50. "
                    f"The evolution engine should adjust selection parameters automatically.")

    if not recs:
        recs.append("🟢 No significant issues detected. Continue current strategy.")

    for r in recs:
        print(f"  {r}")


def render_dashboard(data):
    """Render the full dashboard."""
    render_header(data)
    render_critique_comparison(data)
    render_axis_breakdown(data)
    render_performance(data)
    render_timeline(data)
    render_evolution_summary(data)
    render_watchdog_summary(data)
    render_recommendations(data)
    print(f"\n{'='*64}\n")


# ── CLI Entry Point ──────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="VARY — Performance Dashboard")
    parser.add_argument("--daily", action="store_true", help="Daily Shorts only")
    parser.add_argument("--weekly", action="store_true", help="Weekly videos only")
    parser.add_argument("--realtime", action="store_true", help="Fetch real YouTube data first")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--trends", action="store_true", help="Trend analysis only")
    args = parser.parse_args()

    # Optionally fetch realtime data first
    if args.realtime:
        print(">>> Fetching real YouTube performance data...")
        from modules.performance_tracker import poll_all_videos
        poll_all_videos()

    data = build_dashboard_data()

    if args.json:
        print(json.dumps(data, indent=2, default=str))
        return

    if args.daily:
        # Only show daily section
        dc = data["daily_critique"]
        dp = data["daily_performance"]
        print(f"\n{'='*50}")
        print(f"  VARY — Daily Shorts Performance")
        print(f"{'='*50}")
        print(f"\n  Total daily shorts uploaded: {data['registry']['daily']}")
        print(f"  Critique count:              {dc['count']}")
        print(f"  Average critique score:      {dc['compound']:.1f}")
        if dp.get("count", 0) > 0:
            print(f"  Videos with real data:       {dp['count']}")
            print(f"  Total views:                 {_format_number(dp['total_views'])}")
            print(f"  Avg view velocity:           {dp['avg_view_velocity']:.1f}/hr")
            print(f"  Avg performance score:       {dp['avg_performance_score']:.1f}")
        print(f"\n  Daily Axes:")
        for axis in DAILY_AXES:
            score = dc["axes"].get(axis, 0)
            label = DAILY_AXIS_LABELS.get(axis, axis)
            bar = _bar(score, width=20)
            print(f"    {label:<20} {score:>5.1f} {bar}")
        print()
        return

    if args.weekly:
        wc = data["weekly_critique"]
        wp = data["weekly_performance"]
        print(f"\n{'='*50}")
        print(f"  VARY — Weekly Video Performance")
        print(f"{'='*50}")
        print(f"\n  Total weekly videos uploaded: {data['registry']['weekly']}")
        print(f"  Critique count:               {wc['count']}")
        print(f"  Average critique score:       {wc['compound']:.1f}")
        if wp.get("count", 0) > 0:
            print(f"  Videos with real data:        {wp['count']}")
            print(f"  Total views:                  {_format_number(wp['total_views'])}")
            print(f"  Avg view velocity:            {wp['avg_view_velocity']:.1f}/hr")
            print(f"  Avg performance score:        {wp['avg_performance_score']:.1f}")
        print(f"\n  Weekly Axes:")
        for axis in WEEKLY_AXES:
            score = wc["axes"].get(axis, 0)
            label = WEEKLY_AXIS_LABELS.get(axis, axis)
            bar = _bar(score, width=20)
            print(f"    {label:<18} {score:>5.1f} {bar}")
        print()
        return

    if args.trends:
        print(f"\n{'='*50}")
        print(f"  VARY — Trend Analysis")
        print(f"{'='*50}")
        dc = data["daily_critique"]
        wc = data["weekly_critique"]

        # Critique score trends
        print(f"\n  Daily critique compound trend:")
        daily_crits = load_jsonl(CRITIQUE_LOG)
        if daily_crits:
            # Group by day
            by_day = defaultdict(list)
            for c in daily_crits:
                try:
                    day = datetime.fromisoformat(c.get("timestamp", "")).strftime("%Y-%m-%d")
                    by_day[day].append(c.get("compound_score", 50))
                except (ValueError, TypeError):
                    pass
            for day in sorted(by_day.keys())[-14:]:  # last 14 days
                scores = by_day[day]
                avg = sum(scores) / len(scores)
                bar = _bar(avg, width=20)
                print(f"    {day}  {avg:>5.1f} {bar}  ({len(scores)} clips)")

        print(f"\n  Weekly critique compound trend:")
        weekly_crits = load_jsonl(WEEKLY_CRITIQUE_LOG)
        if weekly_crits:
            for c in weekly_crits:
                try:
                    day = datetime.fromisoformat(c.get("timestamp", "")).strftime("%Y-%m-%d")
                    score = c.get("compound_score", 50)
                    bar = _bar(score, width=20)
                    print(f"    {day}  {score:>5.1f} {bar}")
                except (ValueError, TypeError):
                    pass
        else:
            print(f"    No weekly critique data yet.")
        print()
        return

    # Full dashboard
    render_dashboard(data)


if __name__ == "__main__":
    main()
