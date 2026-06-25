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
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LOG_DIR, SHORTS_WIDTH, SHORTS_HEIGHT


CRITIQUE_LOG = os.path.join(LOG_DIR, "critique_scores.jsonl")
FRAME_ANALYSIS_DIR = os.path.join(LOG_DIR, "_frames")


# ── Helpers ──────────────────────────────────────────────────


def _run_ffmpeg(cmd, timeout=60):
    """Run ffmpeg/ffprobe and return (stdout, stderr, returncode)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT", -1
    except FileNotFoundError:
        return "", "ffmpeg/ffprobe not found", -1


def _extract_first_frame(video_path, at_time=0.0):
    """Extract a single frame as a JPEG for analysis."""
    os.makedirs(FRAME_ANALYSIS_DIR, exist_ok=True)
    frame_id = uuid.uuid4().hex[:12]
    out = os.path.join(FRAME_ANALYSIS_DIR, f"critique_{frame_id}.jpg")
    cmd = [
        "ffmpeg", "-y",
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
        from PIL import Image
    except ImportError:
        return 50.0  # neutral fallback

    try:
        img = Image.open(frame_path).convert("RGB")
        pixels = list(img.getdata())
        w, h = img.size

        # Convert to per-channel arrays
        r_vals = [p[0] for p in pixels]
        g_vals = [p[1] for p in pixels]
        b_vals = [p[2] for p in pixels]

        # 1. Brightness variance (standard deviation of luminance)
        luminance = [0.299 * r + 0.587 * g + 0.114 * b for r, g, b in pixels]
        mean_l = sum(luminance) / len(luminance)
        var_l = sum((l - mean_l) ** 2 for l in luminance) / len(luminance)
        std_l = math.sqrt(var_l)

        # High variance = high contrast = good hook
        contrast_score = min(100, (std_l / 85) * 100)

        # 2. Color variance (chromatic interest)
        r_var = sum((v - (sum(r_vals) / len(r_vals))) ** 2 for v in r_vals) / len(r_vals)
        g_var = sum((v - (sum(g_vals) / len(g_vals))) ** 2 for v in g_vals) / len(g_vals)
        b_var = sum((v - (sum(b_vals) / len(b_vals))) ** 2 for v in b_vals) / len(b_vals)
        color_var = (math.sqrt(r_var) + math.sqrt(g_var) + math.sqrt(b_var)) / 3
        color_score = min(100, (color_var / 70) * 100)

        # 3. Edge density via simple horizontal gradient
        edge_pixels = 0
        for y in range(min(100, h)):
            for x in range(1, min(100, w)):
                idx = y * w + x
                idx_prev = y * w + (x - 1)
                dr = abs(pixels[idx][0] - pixels[idx_prev][0])
                dg = abs(pixels[idx][1] - pixels[idx_prev][1])
                db = abs(pixels[idx][2] - pixels[idx_prev][2])
                if dr + dg + db > 120:  # threshold for "edge"
                    edge_pixels += 1
        edge_density = min(100, (edge_pixels / 500) * 100)

        # 4. Center composition (weight center 60% higher)
        center_region = []
        margin_x = w // 5
        margin_y = h // 5
        for py in range(margin_y, h - margin_y):
            for px in range(margin_x, w - margin_x):
                idx = py * w + px
                center_region.append(luminance[idx])
        center_mean = sum(center_region) / len(center_region) if center_region else 128
        center_var = sum((l - center_mean) ** 2 for l in center_region) / len(center_region)
        center_std = math.sqrt(center_var)
        composition_score = min(100, (center_std / 80) * 100)

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


def _score_motion_dynamics(video_path, duration):
    """Analyze motion energy in the first 3 seconds using scene detection.

    High motion = high energy = better hook.
    """
    try:
        # Use default scene threshold (matching clip_editor's 0.3)
        threshold = 0.3
        cmd = [
            "ffmpeg", "-i", video_path,
            "-filter:v", f"select='gt(scene,{threshold})',showinfo",
            "-f", "null",
            "-",
        ]
        _, stderr, _ = _run_ffmpeg(cmd, timeout=120)

        # Parse scene changes in first few seconds
        scene_times = []
        for line in stderr.split("\n"):
            if "pts_time:" in line:
                match = re.search(r"pts_time:([\d.]+)", line)
                if match:
                    t = float(match.group(1))
                    if t <= min(duration, 10):
                        scene_times.append(t)

        # More scene changes in first few seconds = more motion = better hook
        if len(scene_times) >= 2:
            # At least 2 scene changes means real motion
            density = len(scene_times) / min(duration, 10)
            return min(100, (density * 30))
        elif len(scene_times) == 1:
            return 40.0  # moderate
        else:
            # No scene changes detected — try optical flow approximation
            # via analyzing frame-to-frame pixel difference
            return 30.0  # low motion, low hook probability

    except Exception as e:
        print(f"  [critique] Motion analysis error: {e}", flush=True)
        return 50.0


# ── Axis 3: Audio Impact ────────────────────────────────────


def _score_audio_impact(video_path):
    """Analyze audio dynamics using ffprobe/ffmpeg.

    Looks at: audio presence, peak volume, silence ratio.
    A clip that opens with sudden sound or has dynamic range scores higher.
    """
    try:
        # Check if audio stream exists
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name",
            "-of", "json",
            video_path,
        ]
        stdout, _, _ = _run_ffmpeg(cmd, timeout=15)

        if not stdout or '"codec_name"' not in stdout:
            return 10.0  # No audio = very weak hook

        # Analyze audio volume statistics using ebur128 or volumedetect
        cmd2 = [
            "ffmpeg", "-i", video_path,
            "-af", "volumedetect",
            "-f", "null",
            "-",
        ]
        _, stderr, _ = _run_ffmpeg(cmd2, timeout=60)

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
        from PIL import Image
    except ImportError:
        return 50.0

    try:
        img = Image.open(frame_path).convert("L")  # grayscale for simplicity
        w, h = img.size
        pixels = list(img.getdata())

        # Rule of thirds: divide into 9 zones, check interest distribution
        third_w = w // 3
        third_h = h // 3

        zones = []
        for row in range(3):
            for col in range(3):
                zone_pixels = []
                for py in range(row * third_h, (row + 1) * third_h):
                    for px in range(col * third_w, (col + 1) * third_w):
                        idx = py * w + px
                        if idx < len(pixels):
                            zone_pixels.append(pixels[idx])
                zones.append(sum(zone_pixels) / len(zone_pixels) if zone_pixels else 128)

        # Good composition: high contrast between zones (focal point exists)
        zone_var = sum((z - sum(zones) / len(zones)) ** 2 for z in zones) / len(zones)
        zone_std = math.sqrt(zone_var)

        composition = min(100, (zone_std / 60) * 100)
        return round(composition, 1)

    except Exception:
        return 50.0


# ── Axis 5: Color Vibrancy ──────────────────────────────────


def _score_color_vibrancy(frame_path):
    """Score color saturation and variety in the frame."""
    try:
        from PIL import Image
    except ImportError:
        return 50.0

    try:
        img = Image.open(frame_path).convert("HSV")
        pixels = list(img.getdata())

        # Extract saturation (S) and value (V) channels
        saturations = [p[1] / 255.0 * 100 for p in pixels]
        values = [p[2] / 255.0 * 100 for p in pixels]

        mean_sat = sum(saturations) / len(saturations)
        mean_val = sum(values) / len(values)

        # Good: moderately high saturation (not washed out, not neon)
        sat_score = 0
        if mean_sat < 10:
            sat_score = 10  # washed out
        elif mean_sat > 80:
            sat_score = 60  # over-saturated
        else:
            sat_score = min(100, mean_sat * 1.3)

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


def _score_pacing(video_path, duration):
    """Score the clip's pacing — scene change rhythm.

    Too many cuts = chaotic. Too few = boring.
    Sweet spot: 1-3 scene changes per 10 seconds for short-form.
    """
    try:
        cmd = [
            "ffmpeg", "-i", video_path,
            "-filter:v", "select='gt(scene,0.3)',showinfo",
            "-f", "null",
            "-",
        ]
        _, stderr, _ = _run_ffmpeg(cmd, timeout=120)

        changes = 0
        for line in stderr.split("\n"):
            if "pts_time:" in line:
                changes += 1

        if duration <= 0:
            return 50.0

        changes_per_10s = (changes / duration) * 10

        # Ideal: 1-3 changes per 10 seconds
        if changes_per_10s <= 0.5:
            return 25.0  # too static
        elif changes_per_10s <= 1.0:
            return 60.0  # slow but steady
        elif changes_per_10s <= 3.0:
            return 95.0  # sweet spot
        elif changes_per_10s <= 5.0:
            return 75.0  # slightly fast
        else:
            return 40.0  # too chaotic

    except Exception:
        return 50.0


# ── Main Critique Function ──────────────────────────────────


def critique_clip(video_path, content_type, source_title="", source_duration=0):
    """Run full critique on a processed clip.

    Args:
        video_path: Path to the final processed Short (MP4).
        content_type: 'movie' or 'worldcup_2026'.
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

    axes["motion_dynamics"] = _score_motion_dynamics(video_path, duration)
    axes["audio_impact"] = _score_audio_impact(video_path)
    axes["pacing"] = _score_pacing(video_path, duration)

    # Compound score: weighted by importance
    # First frame hook is weighted highest — it determines click-through
    compound = (
        axes["first_frame_hook"] * 0.35 +
        axes["motion_dynamics"] * 0.20 +
        axes["audio_impact"] * 0.15 +
        axes["scene_composition"] * 0.10 +
        axes["color_vibrancy"] * 0.10 +
        axes["pacing"] * 0.10
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


def load_critique_history(n=50):
    """Load the last N critique entries for evolution analysis."""
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
