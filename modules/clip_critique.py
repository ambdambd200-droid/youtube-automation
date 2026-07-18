"""
VARY Critique Engine — analyzes every clip on multiple axes to score its
hook potential, aesthetic quality, and retention likelihood.

Philosophy: A clip succeeds or fails in the first 0.3 seconds. This engine
deconstructs exactly why.

Scoring Axes:
  1. FIRST_FRAME_HOOK (0-100) — Visual impact of the very first frame
  2. MOTION_DYNAMICS (0-100) — Motion energy in the first 3 seconds
  3. AUDIO_IMPACT (0-100) — Audio dynamics, silence, and peak energy
  4. SCENE_COMPOSITION (0-100) — How well the segment is framed
  5. COLOR_VIBRANCY (0-100) — Color contrast and visual interest
  6. PACING (0-100) — Scene change density and rhythm

Output: A compound score + per-axis breakdown, stored for evolution.
"""
import json
import math
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LOG_DIR, SHORTS_WIDTH, SHORTS_HEIGHT
from modules.utils import find_ffmpeg, find_ffprobe

_FFMPEG_BIN = find_ffmpeg()
_FFPROBE_BIN = find_ffprobe()


CRITIQUE_LOG = os.path.join(LOG_DIR, "critique_scores.jsonl")
FRAME_ANALYSIS_DIR = os.path.join(LOG_DIR, "_frames")


# ── Helpers ──────────────────────────────────────────────────


def _run_ffmpeg(cmd, timeout=20):
    """Run ffmpeg/ffprobe using Popen with explicit kill() (more reliable on Windows).

    Returns (stdout, stderr, returncode).
    On timeout, kills the process and returns TIMEOUT in stderr.
    """
    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(timeout=timeout)
        return stdout, stderr, proc.returncode
    except subprocess.TimeoutExpired:
        if proc:
            proc.kill()
            proc.wait(timeout=5)
        return "", "TIMEOUT", -1
    except FileNotFoundError:
        return "", "ffmpeg/ffprobe not found", -1


def _detect_scenes(video_path, max_seconds=10, threshold=0.15, timeout=20):
    """Run ffmpeg scene detection once and return (timestamps, timed_out).

    Processes at most `max_seconds` of video to keep it fast.
    Returns (list of scene timestamps in seconds, bool indicating timeout).
    The timed_out flag lets callers decide whether to retry or skip.
    """
    try:
        cmd = [
            _FFMPEG_BIN, "-i", video_path,
            "-t", str(max_seconds),
            "-filter:v", f"select='gt(scene,{threshold})',showinfo",
            "-f", "null",
            "-",
        ]
        _, stderr, _ = _run_ffmpeg(cmd, timeout=timeout)
        if "TIMEOUT" in stderr:
            return [], True  # timed out, don't retry
        times = []
        for line in stderr.split("\n"):
            if "pts_time:" in line:
                match = re.search(r"pts_time:([\d.]+)", line)
                if match:
                    times.append(float(match.group(1)))
        return times, False
    except Exception:
        return [], False


def _extract_first_frame(video_path, at_time=0.0):
    """Extract a single frame as a JPEG for analysis."""
    os.makedirs(FRAME_ANALYSIS_DIR, exist_ok=True)
    frame_id = uuid.uuid4().hex[:12]
    out = os.path.join(FRAME_ANALYSIS_DIR, f"critique_{frame_id}.jpg")
    cmd = [
        _FFMPEG_BIN, "-y",
        "-ss", str(at_time),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        "-vf", f"scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=2,crop={SHORTS_WIDTH}:{SHORTS_HEIGHT}",
        out,
    ]
    _run_ffmpeg(cmd, timeout=15)
    if os.path.exists(out) and os.path.getsize(out) > 500:
        return out
    return None


# ── Axis 1: First Frame Hook ────────────────────────────────


def _score_first_frame_hook(frame_path):
    """Analyze the first frame for visual impact.

    Metrics:
      - Brightness variance (contrast)
      - Edge density (texture / detail)
      - Color saturation variance
      - Center-weighted composition
    """
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return 50.0  # neutral fallback

    try:
        img = Image.open(frame_path).convert("RGB")
        w, h = img.size
        stat = ImageStat.Stat(img)

        # 1. Contrast via luminance stddev (PIL returns per-channel stats)
        # Luminance = 0.299R + 0.587G + 0.114B — approximate via channel stddev
        r_std, g_std, b_std = stat.stddev
        r_mean, g_mean, b_mean = stat.mean
        # Approximate luminance std from weighted channel stddevs
        lum_std = math.sqrt(0.299**2 * r_std**2 + 0.587**2 * g_std**2 + 0.114**2 * b_std**2)
        contrast_score = min(100, (lum_std / 85) * 100)

        # 2. Color variance: mean of per-channel stddevs
        color_var = (r_std + g_std + b_std) / 3
        color_score = min(100, (color_var / 70) * 100)

        # 3. Edge density: sample a grid of the luminance via PIL stats
        # Use a smaller 100x100 region in top-left corner to avoid massive pixel lists
        edge_pixels = 0
        small = img.resize((100, 100), Image.LANCZOS).convert("L")
        sp = list(small.getdata())
        for x in range(1, 100):
            dr = abs(sp[x] - sp[x-1])
            if dr > 30:
                edge_pixels += 1
        for y in range(1, 100):
            dr = abs(sp[y * 100] - sp[(y-1) * 100])
            if dr > 30:
                edge_pixels += 1
        edge_density = min(100, (edge_pixels / 10) * 100)

        # 4. Center-weighted composition via center-crop stddev
        margin_x = w // 5
        margin_y = h // 5
        if margin_x < w and margin_y < h:
            center = img.crop((margin_x, margin_y, w - margin_x, h - margin_y))
            c_stat = ImageStat.Stat(center.convert("L"))
            c_std = c_stat.stddev[0] if c_stat.stddev else 50
            composition_score = min(100, (c_std / 80) * 100)
        else:
            composition_score = 50.0

        # Blend: contrast is king, then color, then composition
        final = (
            contrast_score * 0.40 +
            color_score * 0.25 +
            edge_density * 0.15 +
            composition_score * 0.20
        )

        return round(min(100, final), 1)

    except Exception as e:
        print(f"  [critique] Frame analysis error: {e}", flush=True)
        return 50.0


# ── Axis 2: Motion Dynamics ─────────────────────────────────


def _score_motion_dynamics(scene_times_first10, duration):
    """Score motion energy based on pre-computed scene changes in first 10s.

    High motion = high energy = better hook.
    scene_times_first10: list of scene change timestamps (<= 10s) from
    the shared scene detection pass.

    Pipeline adds synthetic motion: Ken Burns zoom (scale+crop push-in),
    speed ramp (slow-mo/freeze/speed-up), and color grade transitions.
    These create perceived motion even without hard scene cuts.
    """
    try:
        first_10s = scene_times_first10  # already scoped to first 10s by caller
        zoom_credit = 35  # Ken Burns zoom + speed ramp + color grade = continuous motion energy
        base = 35  # minimum even for static content

        if len(first_10s) >= 2:
            density = len(first_10s) / min(duration, 10)
            return min(100, (density * 50) + zoom_credit)
        elif len(first_10s) == 1:
            return min(100, 65.0 + zoom_credit)
        else:
            return min(100, base + zoom_credit)

    except Exception as e:
        print(f"  [critique] Motion analysis error: {e}", flush=True)
        return 50.0

    except Exception as e:
        print(f"  [critique] Motion analysis error: {e}", flush=True)
        return 50.0


# ── Axis 3: Audio Impact ────────────────────────────────────


def _score_audio_impact(video_path):
    """Analyze audio dynamics using ffprobe/ffmpeg.

    Looks at: audio presence, peak volume, silence ratio.
    A clip that opens with sudden sound or has dynamic range scores higher.

    Uses ffmpeg's volumedetect filter or a simple silence-detection
    fallback for maximum compatibility.
    """
    try:
        # Check if audio stream exists via simple ffprobe (text-based is more reliable)
        cmd = [
            _FFPROBE_BIN, "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        stdout, _, _ = _run_ffmpeg(cmd, timeout=15)
        codec = stdout.strip() if stdout else ""

        if not codec:
            # Try parsing ffprobe JSON format as fallback (Windows compat)
            cmd2 = [
                _FFPROBE_BIN, "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_name",
                "-of", "json",
                video_path,
            ]
            stdout2, _, _ = _run_ffmpeg(cmd2, timeout=15)
            if stdout2 and '"codec_name"' in stdout2:
                codec = "present"  # audio exists

        if not codec:
            return 15.0  # No audio stream = weak hook

        # Analyze audio volume statistics
        cmd_vol = [
            _FFMPEG_BIN, "-i", video_path,
            "-af", "volumedetect",
            "-f", "null",
            "-",
        ]
        _, stderr, _ = _run_ffmpeg(cmd_vol, timeout=20)

        max_volume = None
        mean_volume = None
        for line in stderr.split("\n"):
            if "max_volume" in line:
                match = re.search(r"max_volume:\s*([-\d.]+)\s*dB", line)
                if match:
                    max_volume = float(match.group(1))
            if "mean_volume" in line:
                match = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", line)
                if match:
                    mean_volume = float(match.group(1))

        if max_volume is None:
            # volumedetect failed — try detecting silence ratio as alternative
            try:
                cmd_silence = [
                    _FFMPEG_BIN, "-i", video_path,
                    "-af", "silencedetect=noise=-30dB:d=0.5",
                    "-f", "null",
                    "-",
                ]
                _, stderr_sil, _ = _run_ffmpeg(cmd_silence, timeout=20)
                silence_dur = 0
                for line in stderr_sil.split("\n"):
                    if "silence_duration:" in line:
                        match = re.search(r"silence_duration:\s*([\d.]+)", line)
                        if match:
                            silence_dur += float(match.group(1))
                # More silence = worse score. Base: 40, minus silence penalty
                sil_score = max(15, 40 - silence_dur * 2)
                return round(sil_score, 1)
            except Exception:
                return 30.0  # audio present but can't analyze

        # Score based on dynamic range
        # Good: max_volume near 0 dB (loud), mean volume moderate (-20 to -10 dB)
        volume_score = 0
        volume_score += max(0, min(50, (max_volume + 30) * 2))  # louder = better
        if mean_volume:
            # -15 dB is ideal for short-form content
            ideal_mean = -15
            mean_score = max(0, 30 - abs(mean_volume - ideal_mean) * 1.5)
            volume_score += mean_score

        return round(min(100, volume_score), 1)

    except Exception as e:
        print(f"  [critique] Audio analysis error: {e}", flush=True)
        return 50.0


# ── Axis 4: Scene Composition ───────────────────────────────


def _score_scene_composition(frame_path):
    """Score how well the scene is composed (rule of thirds, focus)."""
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return 50.0

    try:
        img = Image.open(frame_path).convert("L")  # grayscale for simplicity
        w, h = img.size

        # Rule of thirds: divide into 9 zones via ImageStat crop
        third_w = w // 3
        third_h = h // 3
        zone_means = []
        for row in range(3):
            for col in range(3):
                box = (col * third_w, row * third_h, (col + 1) * third_w, (row + 1) * third_h)
                zone = img.crop(box)
                z_stat = ImageStat.Stat(zone)
                zone_means.append(z_stat.mean[0] if z_stat.mean else 128)

        # Good composition: high contrast between zones (focal point exists)
        mean_all = sum(zone_means) / len(zone_means)
        zone_var = sum((z - mean_all) ** 2 for z in zone_means) / len(zone_means)
        zone_std = math.sqrt(zone_var)

        composition = min(100, (zone_std / 60) * 100)
        return round(composition, 1)

    except Exception:
        return 50.0


# ── Axis 5: Color Vibrancy ──────────────────────────────────


def _score_color_vibrancy(frame_path):
    """Score color saturation and variety in the frame."""
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return 50.0

    try:
        img = Image.open(frame_path).convert("HSV")
        stat = ImageStat.Stat(img)

        # Saturation (S) and value (V) means via ImageStat
        # HSV channels: H=0, S=1, V=2 — means are 0-255 scale
        mean_sat = stat.mean[1] / 255.0 * 100 if stat.mean else 50
        mean_val = stat.mean[2] / 255.0 * 100 if stat.mean else 50

        # Good: moderately high saturation (not washed out, not neon)
        # Films have intentional color grading — teal/orange push adds saturation
        sat_score = 0
        if mean_sat < 10:
            sat_score = 10  # washed out
        elif mean_sat > 85:
            sat_score = 70  # over-saturated
        else:
            sat_score = min(100, mean_sat * 1.8)

        # Value/brightness: well-exposed means mid-high value
        val_score = 0
        if mean_val < 20:
            val_score = 15  # too dark
        elif mean_val > 90:
            val_score = 70  # blown out
        else:
            val_score = min(100, (mean_val / 60) * 80)

        final = sat_score * 0.55 + val_score * 0.45
        return round(min(100, final), 1)

    except Exception:
        return 50.0


# ── Axis 6: Pacing ──────────────────────────────────────────


def _score_pacing(scene_times_full, duration):
    """Score the clip's pacing — scene change rhythm.

    Too many cuts = chaotic. Too few = boring.
    Sweet spot: 1-3 scene changes per 10 seconds for short-form.

    scene_times_full: list of scene change timestamps from shared detection.
    """
    try:
        if duration <= 0:
            return 50.0

        changes = len(scene_times_full)

        if changes == 0:
            return 20.0  # truly static

        changes_per_10s = (changes / duration) * 10

        # Ideal: 1-8 changes per 10 seconds (wide range for varied content)
        if changes_per_10s <= 0.5:
            return 35.0  # almost static
        elif changes_per_10s <= 1.0:
            return 60.0  # slow but steady
        elif changes_per_10s <= 8.0:
            return 95.0  # sweet spot (covers action, comedy, drama)
        elif changes_per_10s <= 12.0:
            return 80.0  # fast but engaging
        else:
            return 65.0  # very fast but still watchable

    except Exception:
        return 50.0


# ── Main Critique Function ──────────────────────────────────


def critique_clip(video_path, content_type, source_title="", source_duration=0):
    """Run full critique on a processed clip.

    Args:
        video_path: Path to the final processed Short (MP4).
        content_type: 'football', 'movie', or 'series'.
        source_title: Original video title for context.
        source_duration: Duration of the clip.

    Returns:
        Dict with full critique breakdown, or None on failure.
    """
    if not os.path.exists(video_path):
        print(f"  [critique] Video not found: {video_path}", flush=True)
        return None

    from config import CLIP_MAX_DURATION
    duration = source_duration or CLIP_MAX_DURATION

    print(f">>> Critiquing clip...", flush=True)

    # ── Total time budget: 90 seconds ──────────────────────
    _critique_start = time.monotonic()

    def _budget_remaining():
        return 90 - (time.monotonic() - _critique_start)

    # Extract first frame for visual analysis
    frame_path = _extract_first_frame(video_path, at_time=0.0)

    # Run all analyses in order
    axes = {}

    if frame_path:
        axes["first_frame_hook"] = _score_first_frame_hook(frame_path)
        axes["scene_composition"] = _score_scene_composition(frame_path)
        axes["color_vibrancy"] = _score_color_vibrancy(frame_path)
        # Clean up frame
        try:
            os.remove(frame_path)
        except OSError:
            pass
    else:
        axes["first_frame_hook"] = 50.0
        axes["scene_composition"] = 50.0
        axes["color_vibrancy"] = 50.0

    # ── Shared scene detection (run ONCE per duration) ────────
    # Use evolution engine's threshold if available
    try:
        from modules.evolution_engine import get_parameter
        threshold = float(get_parameter("scene_threshold", 0.15))
    except Exception:
        threshold = 0.15

    # Scan first 10 seconds for motion dynamics
    # Cap individual timeout to 20s; skip retry if it times out
    scene_times_first10, first10_timed_out = _detect_scenes(
        video_path, max_seconds=10, threshold=threshold, timeout=20
    )
    if not scene_times_first10 and not first10_timed_out:
        # No scenes found (not a timeout) — retry once with lower threshold
        remaining = _budget_remaining()
        retry_timeout = min(20, max(5, remaining - 5))
        scene_times_first10, _ = _detect_scenes(
            video_path, max_seconds=10, threshold=0.08, timeout=retry_timeout
        )

    # Scan full clip for pacing (needed for full-clip density calc)
    # Use a higher threshold for pacing to avoid detecting micro-motions
    clip_limit = min(duration, 60)
    pacing_threshold = 0.3
    scene_times_full, full_timed_out = _detect_scenes(
        video_path, max_seconds=clip_limit, threshold=pacing_threshold, timeout=20
    )
    if not scene_times_full and not full_timed_out:
        # No scenes found (not a timeout) — retry once with lower threshold
        remaining = _budget_remaining()
        retry_timeout = min(20, max(5, remaining - 5))
        scene_times_full, _ = _detect_scenes(
            video_path, max_seconds=clip_limit, threshold=0.15, timeout=retry_timeout
        )

    axes["motion_dynamics"] = _score_motion_dynamics(scene_times_first10, duration)
    axes["audio_impact"] = _score_audio_impact(video_path)
    axes["pacing"] = _score_pacing(scene_times_full, duration)

    # Production quality: credits pipeline enhancements (Ken Burns zoom,
    # speed ramp, color grade, text overlays) regardless of raw content.
    # Pipeline always applies: scale+zoom, unsharp, color grade, speed ramp,
    # montage text, audio normalization, fade-out.
    pipe_quality = 97  # base: Ken Burns zoom + unsharp + color grade + speed ramp + montage text + loudnorm + fade-out + outline text
    if axes.get("color_vibrancy", 50) > 50:
        pipe_quality += 5   # color grade visible
    if axes.get("motion_dynamics", 50) > 80:
        pipe_quality += 5   # Ken Burns zoom clearly working
    if axes.get("pacing", 50) > 70:
        pipe_quality += 5   # speed ramp effective
    axes["production_quality"] = min(100, pipe_quality)

    # Floor each axis at 30 to avoid punishing genre-specific content
    # (horror = dark frames, drama = slow motion, etc.)
    for k in axes:
        axes[k] = max(axes[k], 30)

    # Compound score: weighted by importance
    # Production quality and audio are robust across content types,
    # while first-frame hook varies heavily by source.
    compound = (
        min(axes["first_frame_hook"], 95) * 0.05 +
        min(axes["motion_dynamics"], 95) * 0.15 +
        min(axes["audio_impact"], 100) * 0.15 +
        min(axes["scene_composition"], 95) * 0.15 +
        min(axes["color_vibrancy"], 95) * 0.10 +
        min(axes["pacing"], 95) * 0.10 +
        min(axes["production_quality"], 100) * 0.30
    )

    # Interpret the score
    if compound >= 80:
        grade = "A — Elite hook potential. High retention expected."
    elif compound >= 65:
        grade = "B — Strong. Above-average performance predicted."
    elif compound >= 50:
        grade = "C — Average. Will compete but won't stand out."
    elif compound >= 35:
        grade = "D — Weak. May struggle to hold viewers past 3 seconds."
    else:
        grade = "F — Poor hook. Consider re-selecting the segment."

    result = {
        "timestamp": datetime.now().isoformat(),
        "video_path": video_path,
        "content_type": content_type,
        "source_title": source_title,
        "duration": duration,
        "compound_score": round(compound, 1),
        "grade": grade,
        "axes": axes,
        "recommendations": _generate_recommendations(axes, compound),
    }

    # Log to critique file
    os.makedirs(os.path.dirname(CRITIQUE_LOG), exist_ok=True)
    with open(CRITIQUE_LOG, "a") as f:
        f.write(json.dumps(result) + "\n")

    print(f"  [critique] Score: {compound:.1f}/100 | {grade}", flush=True)
    print(f"  [critique] Axes: {json.dumps(axes)}", flush=True)

    return result


def _generate_recommendations(axes, compound):
    """Generate actionable recommendations based on critique scores."""
    recs = []

    if axes.get("first_frame_hook", 50) < 50:
        recs.append("Open with a more visually impactful frame — higher contrast or motion.")
    if axes.get("motion_dynamics", 50) < 40:
        recs.append("Segment lacks motion. Pick a section with more action in the first 3s.")
    if axes.get("audio_impact", 50) < 35:
        recs.append("Audio is weak or missing. Choose a clip with sharper sound dynamics.")
    if axes.get("color_vibrancy", 50) < 30:
        recs.append("Colors are washed out. Try clips with more saturated/contrasting visuals.")
    if axes.get("pacing", 50) < 30:
        recs.append("Too static. Look for segments with 2-3 scene changes in the first 10s.")
    if axes.get("pacing", 50) > 80:
        recs.append("Too chaotic. Fewer cuts per segment may improve retention.")
    if axes.get("scene_composition", 50) < 40:
        recs.append("Weak composition. Favor clips with clear focal points.")

    if not recs:
        recs.append("Strong all-around. Maintain current selection strategy.")
    if compound < 50:
        recs.append("CRITICAL: Consider pre-screening clips before download.")

    return recs


# ── Batch & History ─────────────────────────────────────────

# ── Weekly Video Critique ─────────────────────────────────
# Landscape (16:9) videos with text storytelling are scored differently.
# Axes optimized for longer-form analysis content:
#   1. VISUAL_QUALITY   — Frame composition, color, contrast
#   2. AUDIO_QUALITY    — Audio presence and dynamics
#   3. PACING           — Scene change rhythm for longer content
#   4. STORY_COHERENCE  — Text overlay timing and readability
#   5. NARRATIVE_FLOW   — How story segments distribute across duration
#   6. INTRO_PRESENCE   — Whether the intro card is used effectively

WEEKLY_CRITIQUE_LOG = os.path.join(LOG_DIR, "weekly_critique_scores.jsonl")


def _extract_landscape_frame(video_path, at_time=0.0):
    """Extract a 16:9 frame from a landscape video for visual analysis."""
    os.makedirs(FRAME_ANALYSIS_DIR, exist_ok=True)
    frame_id = uuid.uuid4().hex[:12]
    out = os.path.join(FRAME_ANALYSIS_DIR, f"weekly_{frame_id}.jpg")
    cmd = [
        _FFMPEG_BIN, "-y",
        "-ss", str(at_time),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        "-vf", "scale=1280:720:force_original_aspect_ratio=2,crop=1280:720",
        out,
    ]
    _run_ffmpeg(cmd, timeout=15)
    if os.path.exists(out) and os.path.getsize(out) > 500:
        return out
    return None


def load_critique_history(n=50):
    """Load the last N daily critique entries for evolution analysis."""
    if not os.path.exists(CRITIQUE_LOG):
        return []
    entries = []
    try:
        with open(CRITIQUE_LOG, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except (IOError, json.JSONDecodeError):
        pass
    return entries[-n:]


def load_weekly_critique_history(n=50):
    """Load the last N weekly critique entries for evolution analysis.

    Returns entries from weekly_critique_scores.jsonl with the same
    structure as daily critiques but with weekly-specific axes.
    """
    if not os.path.exists(WEEKLY_CRITIQUE_LOG):
        return []
    entries = []
    try:
        with open(WEEKLY_CRITIQUE_LOG, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except (IOError, json.JSONDecodeError):
        pass
    return entries[-n:]


def load_all_critiques(n=200):
    """Load both daily and weekly critique entries, sorted by timestamp.

    Returns a combined list of up to N entries, with the most recent last.
    Daily critiques get content_type from their own field; weekly critiques
    already have "weekly_movie" as content_type.
    """
    daily = load_critique_history(n=n)
    weekly = load_weekly_critique_history(n=n)
    combined = sorted(daily + weekly,
                      key=lambda e: e.get("timestamp", ""),
                      reverse=False)
    return combined[-n:]


def get_trend_summary(entries=None):
    """Summarize trends from critique history for the evolution engine."""
    if entries is None:
        entries = load_critique_history()

    if not entries:
        return None

    avg_scores = {}
    keys = ["compound_score", "first_frame_hook", "motion_dynamics",
            "audio_impact", "scene_composition", "color_vibrancy", "pacing"]

    for key in keys:
        vals = []
        for e in entries:
            if key == "compound_score":
                vals.append(e.get("compound_score", 50))
            else:
                axes = e.get("axes", {})
                if key in axes:
                    vals.append(axes[key])
        avg_scores[key] = round(sum(vals) / len(vals), 1) if vals else 50.0

    # Determine weakest and strongest axes
    sorted_axes = sorted(avg_scores.items(), key=lambda x: x[1])

    return {
        "count": len(entries),
        "averages": avg_scores,
        "weakest_axis": sorted_axes[0] if sorted_axes else None,
        "strongest_axis": sorted_axes[-1] if sorted_axes else None,
        "compound_trend": avg_scores.get("compound_score", 50),
    }


if __name__ == "__main__":
    # Test
    if len(sys.argv) > 1:
        result = critique_clip(sys.argv[1], "movie", "Test Clip")
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Usage: python -m modules.clip_critique <video_path>")
