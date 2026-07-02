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


def _detect_scenes(video_path, max_seconds=10, threshold=0.3, timeout=20):
    """Run ffmpeg scene detection once and return (timestamps, timed_out).

    Processes at most `max_seconds` of video to keep it fast.
    Returns (list of scene timestamps in seconds, bool indicating timeout).
    The timed_out flag lets callers decide whether to retry or skip.
    """
    try:
        cmd = [
            "ffmpeg", "-i", video_path,
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


def _score_motion_dynamics(scene_times_first10, duration):
    """Score motion energy based on pre-computed scene changes in first 10s.

    High motion = high energy = better hook.
    scene_times_first10: list of scene change timestamps (<= 10s) from
    the shared scene detection pass.
    """
    try:
        first_10s = scene_times_first10  # already scoped to first 10s by caller

        if len(first_10s) >= 2:
            density = len(first_10s) / min(duration, 10)
            return min(100, (density * 30))
        elif len(first_10s) == 1:
            return 40.0  # moderate
        else:
            # No scene cuts — give a baseline score. Action content may
            # still have motion from camera movement without hard cuts.
            return 25.0

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
            "ffprobe", "-v", "error",
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
                "ffprobe", "-v", "error",
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
            "ffmpeg", "-i", video_path,
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
                    "ffmpeg", "-i", video_path,
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

        # Ideal: 1-3 changes per 10 seconds
        if changes_per_10s <= 0.5:
            return 35.0  # almost static
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
        threshold = float(get_parameter("scene_threshold", 0.3))
    except Exception:
        threshold = 0.3

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
            video_path, max_seconds=10, threshold=0.1, timeout=retry_timeout
        )

    # Scan full clip for pacing (needed for full-clip density calc)
    clip_limit = min(duration, 60)
    scene_times_full, full_timed_out = _detect_scenes(
        video_path, max_seconds=clip_limit, threshold=threshold, timeout=20
    )
    if not scene_times_full and not full_timed_out:
        # No scenes found (not a timeout) — retry once with lower threshold
        remaining = _budget_remaining()
        retry_timeout = min(20, max(5, remaining - 5))
        scene_times_full, _ = _detect_scenes(
            video_path, max_seconds=clip_limit, threshold=0.1, timeout=retry_timeout
        )

    axes["motion_dynamics"] = _score_motion_dynamics(scene_times_first10, duration)
    axes["audio_impact"] = _score_audio_impact(video_path)
    axes["pacing"] = _score_pacing(scene_times_full, duration)

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
        "ffmpeg", "-y",
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


def _score_weekly_visual_quality(frame_path):
    """Score visual quality (composition + color) on a landscape frame.

    Reuses the existing luminance/color analysis from _score_first_frame_hook
    but with landscape-appropriate weights — composition matters more for
    landscape than for portrait shorts.
    """
    if not frame_path:
        return 50.0
    try:
        from PIL import Image
    except ImportError:
        return 50.0

    try:
        img = Image.open(frame_path).convert("RGB")
        pixels = list(img.getdata())
        w, h = img.size

        # Luminance
        luminance = [0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2] for p in pixels]
        mean_l = sum(luminance) / len(luminance)
        std_l = math.sqrt(sum((l - mean_l) ** 2 for l in luminance) / len(luminance))
        contrast_score = min(100, (std_l / 85) * 100)

        # Color saturation via HSV conversion
        saturations = []
        for r, g, b in pixels:
            mx = max(r, g, b)
            mn = min(r, g, b)
            if mx == 0:
                saturations.append(0)
            else:
                saturations.append((mx - mn) / mx * 100)
        mean_sat = sum(saturations) / len(saturations)
        sat_score = min(100, mean_sat * 1.3) if mean_sat > 10 else 10

        # Landscape composition: rule of thirds, weight horizontal zones
        third_w = w // 3
        third_h = h // 3
        zones = []
        for row in range(3):
            for col in range(3):
                zone_pixels = []
                for py in range(row * third_h, min((row + 1) * third_h, h)):
                    for px in range(col * third_w, min((col + 1) * third_w, w)):
                        idx = py * w + px
                        if idx < len(luminance):
                            zone_pixels.append(luminance[idx])
                zones.append(sum(zone_pixels) / len(zone_pixels) if zone_pixels else 128)
        zone_var = sum((z - sum(zones) / len(zones)) ** 2 for z in zones) / len(zones)
        comp_score = min(100, (math.sqrt(zone_var) / 60) * 100)

        # Blend: contrast heavy, but composition matters more for landscape
        final = contrast_score * 0.35 + sat_score * 0.30 + comp_score * 0.35
        return round(min(100, final), 1)

    except Exception as e:
        print(f"  [critique] Visual analysis error: {e}", flush=True)
        return 50.0


def _score_weekly_pacing(scene_times, duration):
    """Score pacing for longer-form weekly content.

    Long-form pacing is different from Shorts:
    - 0.5-1.5 changes per 10s is ideal (slower, more deliberate)
    - Consistent spacing between changes is good
    - Too many changes = chaotic for analysis content
    - Too few = static
    """
    if duration <= 0 or not scene_times:
        return 50.0

    changes = len(scene_times)
    changes_per_10s = (changes / duration) * 10

    # Ideal for long-form: 0.3-1.0 changes per 10 seconds
    if changes_per_10s <= 0.1:
        return 30.0  # nearly static
    elif changes_per_10s <= 0.3:
        return 55.0  # slow but deliberate
    elif changes_per_10s <= 1.0:
        return 90.0  # ideal for analysis content
    elif changes_per_10s <= 2.0:
        return 70.0  # slightly fast
    elif changes_per_10s <= 4.0:
        return 45.0  # too chaotic for long-form
    else:
        return 25.0  # extremely chaotic


def _score_story_coherence(video_path, source_title, video_duration):
    """Score how well the story text overlays are likely to read.

    Analyzes:
    - Expected number of text segments from the story generator
    - Text density (segments per minute)
    - Whether the video is long enough for the text to be readable
    - Whether audio exists (for spoken-word content)
    """
    if video_duration <= 0:
        return 50.0

    # Expected text segments (from _generate_story_texts in clip_editor.py)
    # Standard: 7 segments at ratios [0.02, 0.10, 0.25, 0.40, 0.55, 0.70, 0.85]
    expected_segments = 7
    text_density = expected_segments / (video_duration / 60)  # segments per minute

    # Ideal: 1-3 text segments per minute
    if text_density > 4:
        density_score = 40  # Too many texts per minute — hard to read
    elif text_density > 2:
        density_score = 85  # Good density
    elif text_density > 1:
        density_score = 70  # Sparse but fine
    else:
        density_score = 50  # Very sparse

    # Check if audio is present (storytelling needs audio)
    audio_score = 50.0
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        stdout, _, _ = _run_ffmpeg(cmd, timeout=10)
        codec = stdout.strip() if stdout else ""
        if codec:
            # Audio present — good for narrative
            # Also check duration: is it long enough for meaningful audio?
            if video_duration >= 120:
                audio_score = 85
            elif video_duration >= 60:
                audio_score = 70
            else:
                audio_score = 55
        else:
            audio_score = 30  # No audio — weak storytelling
    except Exception:
        pass

    # Overall coherence score
    final = density_score * 0.55 + audio_score * 0.45
    return round(final, 1)


def _score_narrative_flow(video_duration):
    """Score narrative flow based on video length and structure.

    The story generator places 7 text segments at specific ratios.
    A good narrative needs:
    - Enough total duration for the story to breathe
    - Even distribution of text segments
    """
    if video_duration <= 0:
        return 50.0

    # Duration sweet spot for weekly analysis: 3-8 minutes
    if video_duration < 90:
        dur_score = 30  # Too short for meaningful analysis
    elif video_duration < 180:
        dur_score = 60  # Short but workable
    elif video_duration < 300:
        dur_score = 90  # Ideal
    elif video_duration <= 480:
        dur_score = 85  # Good, on the longer side
    else:
        dur_score = 70  # Too long—viewer fatigue

    # Text segment spacing: computed from standard ratios [0.02, 0.10, 0.25, 0.40, 0.55, 0.70, 0.85]
    # Average gap between texts: ~0.14 * duration = ~14-56 seconds for 1.5-8min video
    avg_gap = video_duration * 0.14

    if avg_gap < 5:
        gap_score = 30  # Texts too close together
    elif avg_gap < 15:
        gap_score = 70  # Good spacing
    elif avg_gap < 30:
        gap_score = 85  # Ideal spacing
    else:
        gap_score = 75  # Sparse but fine

    final = dur_score * 0.55 + gap_score * 0.45
    return round(final, 1)


def _score_intro_presence(video_path):
    """Score whether the video has an effective intro card.

    Analyzes the first 0.5s of video for characteristics of the
    VARY Weekly intro: dark background, low luminance variance.

    Returns a score based on whether the intro appears present.
    """
    try:
        # Extract a frame from the very start (0.1s in, after fade starts)
        frame = _extract_landscape_frame(video_path, at_time=0.1)
        if not frame:
            return 50.0

        from PIL import Image
        img = Image.open(frame).convert("L")
        pixels = list(img.getdata())
        mean_l = sum(pixels) / len(pixels)
        std_l = math.sqrt(sum((l - mean_l) ** 2 for l in pixels) / len(pixels))

        # Clean up frame
        try:
            os.remove(frame)
        except OSError:
            pass

        # VARY intro starts with dark background (mean_l < 40) and low variance
        if mean_l < 40 and std_l < 30:
            return 85.0  # Dark intro present
        elif mean_l < 60:
            return 65.0  # Somewhat dark — possible intro
        else:
            return 35.0  # Bright start — no intro

    except Exception:
        return 50.0


def _generate_weekly_recommendations(axes, compound):
    """Generate recommendations specific to weekly analysis videos."""
    recs = []

    if axes.get("visual_quality", 50) < 45:
        recs.append("Low visual quality. Choose clips with better composition and color.")
    if axes.get("audio_quality", 50) < 40:
        recs.append("Weak audio. Look for source content with clearer, more dynamic sound.")
    if axes.get("pacing", 50) < 35:
        recs.append("Pacing too slow or chaotic. Consider a different source segment.")
    if axes.get("story_coherence", 50) < 45:
        recs.append("Story text density is off. Consider adjusting segment duration or text count.")
    if axes.get("narrative_flow", 50) < 45:
        recs.append("Narrative flow is weak. Longer or shorter source material may help.")
    if axes.get("intro_presence", 50) < 45:
        recs.append("Intro card may not be visible. Check video start for dark background.")

    if not recs:
        recs.append("Strong weekly video. Maintain current selection and editing strategy.")
    if compound < 40:
        recs.append("CRITICAL: This source material may not work for weekly analysis format.")

    return recs


def critique_weekly_video(video_path, source_title="", source_duration=0):
    """Run full critique on a weekly landscape video.

    Scores on 6 axes optimized for longer-form analysis content:
    - Visual quality (composition, color, contrast)
    - Audio quality (presence, dynamics)
    - Pacing (scene change rhythm)
    - Story coherence (text overlay timing)
    - Narrative flow (duration appropriateness)
    - Intro presence (effective intro card)

    Args:
        video_path: Path to the processed weekly video (MP4, landscape).
        source_title: Original video title for context.
        source_duration: Duration of the video.

    Returns:
        Dict with full critique breakdown, or None on failure.
    """
    if not os.path.exists(video_path):
        print(f"  [critique] Weekly video not found: {video_path}", flush=True)
        return None

    duration = source_duration or get_video_duration(video_path)
    if duration <= 0:
        duration = 120  # fallback

    print(f">>> Critiquing weekly video...", flush=True)

    # Extract a frame from middle-third for visual analysis
    mid_time = duration * random.uniform(0.25, 0.55)
    frame_path = _extract_landscape_frame(video_path, at_time=mid_time)

    axes = {}

    # 1. Visual quality
    axes["visual_quality"] = _score_weekly_visual_quality(frame_path)

    # Clean up frame
    if frame_path:
        try:
            os.remove(frame_path)
        except OSError:
            pass

    # 2. Audio quality (reuse existing audio analysis)
    axes["audio_quality"] = _score_audio_impact(video_path)

    # 3. Pacing — scan first 120s for scene changes
    threshold = 0.3
    try:
        from modules.evolution_engine import get_parameter
        threshold = float(get_parameter("scene_threshold", 0.3))
    except Exception:
        pass

    scan_limit = min(duration, 120)
    scene_times, _ = _detect_scenes(video_path, max_seconds=scan_limit, threshold=threshold, timeout=30)
    axes["pacing"] = _score_weekly_pacing(scene_times, scan_limit)

    # 4. Story coherence
    axes["story_coherence"] = _score_story_coherence(video_path, source_title, duration)

    # 5. Narrative flow
    axes["narrative_flow"] = _score_narrative_flow(duration)

    # 6. Intro presence
    axes["intro_presence"] = _score_intro_presence(video_path)

    # Compound score: weighted for long-form analysis content
    compound = (
        axes["visual_quality"] * 0.20 +
        axes["audio_quality"] * 0.15 +
        axes["pacing"] * 0.20 +
        axes["story_coherence"] * 0.20 +
        axes["narrative_flow"] * 0.15 +
        axes["intro_presence"] * 0.10
    )

    # Interpret score for long-form content
    if compound >= 80:
        grade = "A — Excellent weekly video. Strong storytelling and production."
    elif compound >= 65:
        grade = "B — Good. Above-average weekly analysis content."
    elif compound >= 50:
        grade = "C — Average. Functional but unremarkable."
    elif compound >= 35:
        grade = "D — Weak. May struggle with retention beyond the first minute."
    else:
        grade = "F — Poor. Review source selection and editing parameters."

    result = {
        "timestamp": datetime.now().isoformat(),
        "video_path": video_path,
        "content_type": "weekly_movie",
        "source_title": source_title,
        "duration": duration,
        "compound_score": round(compound, 1),
        "grade": grade,
        "axes": axes,
        "recommendations": _generate_weekly_recommendations(axes, compound),
    }

    # Log to weekly critique file
    os.makedirs(os.path.dirname(WEEKLY_CRITIQUE_LOG), exist_ok=True)
    with open(WEEKLY_CRITIQUE_LOG, "a") as f:
        f.write(json.dumps(result) + "\n")

    print(f"  [critique] Weekly score: {compound:.1f}/100 | {grade}", flush=True)
    print(f"  [critique] Axes: {json.dumps(axes)}", flush=True)

    return result


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
