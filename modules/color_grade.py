"""
VARY Color Grading Pipeline — Visual Alchemy
Blueprint Section 3: Lighting, Color, and Optics
  Phase 1: The "Unified Canvas" Color Correction (White Balance + DR Compression)
  Phase 2: The "VARY" Signature Grade (Teal & Orange + Saturation + S-Curve)
  Phase 3: Optical Enhancements (Unsharp Mask + Film Grain)
"""
import os
import sys
import subprocess
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    CLIPS_DIR,
    SHORTS_WIDTH, SHORTS_HEIGHT,
    COLOR_SHADOW_LIFT, COLOR_TEAL_SHADOWS, COLOR_ORANGE_MIDTONES,
    COLOR_GLOBAL_SATURATION, COLOR_VIBRANCE_BOOST,
    COLOR_GRAIN_INTENSITY, COLOR_GRAIN_SIZE,
    COLOR_SHARPEN_RADIUS, COLOR_SHARPEN_AMOUNT,
    RENDER_CODEC, RENDER_PROFILE, RENDER_LEVEL,
    RENDER_CRF, RENDER_PIX_FMT, RENDER_MOVFLAGS,
    RENDER_INTERMEDIATE_PRESET,
)


def _run_ffmpeg(cmd, description="color", timeout=120):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            print(f"  [color] {description} failed: {result.stderr[:200]}", flush=True)
            return None
        return result
    except subprocess.TimeoutExpired:
        print(f"  [color] {description} timed out", flush=True)
    except Exception as e:
        print(f"  [color] {description} error: {e}", flush=True)
    return None


def apply_white_balance_lock(input_path, output_path):
    """Phase 1: White Balance Lock using colorchannelmixer.
    Normalizes color temperature — shifts toward neutral grays.
    """
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf",
        "colorchannelmixer=rr=1.05:rg=0.02:rb=-0.07:"
        "gr=0.01:gg=1.00:gb=-0.01:"
        "br=-0.05:bg=-0.02:bb=1.07",
        "-c:v", RENDER_CODEC, "-preset", RENDER_INTERMEDIATE_PRESET,
        "-crf", str(RENDER_CRF),
        "-c:a", "copy",
        "-pix_fmt", RENDER_PIX_FMT,
        output_path,
    ]
    result = _run_ffmpeg(cmd, "white balance lock")
    if result and os.path.exists(output_path):
        print(f"  [color] White balance locked (neutral grays)", flush=True)
        return output_path
    return None


def apply_dynamic_range_compression(input_path, output_path):
    """Phase 1: Dynamic Range Compression (HDR Effect).
    Lift shadows to #101010, compress highlights to retain detail.
    Uses 'curves' filter for precise control.
    """
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf",
        "curves=all='0/0.04 0.5/0.5 1/0.96'",
        "-c:v", RENDER_CODEC, "-preset", RENDER_INTERMEDIATE_PRESET,
        "-crf", str(RENDER_CRF),
        "-c:a", "copy",
        "-pix_fmt", RENDER_PIX_FMT,
        output_path,
    ]
    result = _run_ffmpeg(cmd, "dynamic range compression")
    if result and os.path.exists(output_path):
        print(f"  [color] DR compressed (shadows lifted, highlights compressed)", flush=True)
        return output_path
    return None


def apply_teal_orange_grade(input_path, output_path):
    """Phase 2: VARY Signature Grade — Teal & Orange Separation.
    Shadows pushed toward teal/cyan, midtones/highlights toward warm orange.
    Uses colorbalance for shadow/midtone/highlight separation.
    """
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf",
        "colorbalance=rs=-0.02:gs=0.04:bs=0.08:"
        "rm=0.06:gm=-0.02:bm=-0.04:"
        "rh=0.03:gh=-0.01:bh=0.01",
        "-c:v", RENDER_CODEC, "-preset", RENDER_INTERMEDIATE_PRESET,
        "-crf", str(RENDER_CRF),
        "-c:a", "copy",
        "-pix_fmt", RENDER_PIX_FMT,
        output_path,
    ]
    result = _run_ffmpeg(cmd, "teal & orange grade")
    if result and os.path.exists(output_path):
        print(f"  [color] Teal & Orange grade applied (shadows<-teal, skin<-warm)", flush=True)
        return output_path
    return None


def apply_saturation_vibrance(input_path, output_path):
    """Phase 2: Saturation strategy — reduce global, boost vibrance.
    Global sat -10%, vibrance +15% (boosts only dull colors).
    """
    # Vibrance approximation using eq filter: saturation + vibrance
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf",
        f"eq=saturation={1.0 + COLOR_GLOBAL_SATURATION}:"
        f"gamma={1.0 + COLOR_VIBRANCE_BOOST * 0.2}",
        "-c:v", RENDER_CODEC, "-preset", RENDER_INTERMEDIATE_PRESET,
        "-crf", str(RENDER_CRF),
        "-c:a", "copy",
        "-pix_fmt", RENDER_PIX_FMT,
        output_path,
    ]
    result = _run_ffmpeg(cmd, "saturation/vibrance")
    if result and os.path.exists(output_path):
        print(f"  [color] Sat {COLOR_GLOBAL_SATURATION*100:+.0f}% Vib {COLOR_VIBRANCE_BOOST*100:+.0f}%", flush=True)
        return output_path
    return None


def apply_s_curve_contrast(input_path, output_path):
    """Phase 2: S-Curve contrast — darken darks, brighten brights."""
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf",
        "curves=all='0/0 0.25/0.2 0.5/0.5 0.75/0.78 1/1'",
        "-c:v", RENDER_CODEC, "-preset", RENDER_INTERMEDIATE_PRESET,
        "-crf", str(RENDER_CRF),
        "-c:a", "copy",
        "-pix_fmt", RENDER_PIX_FMT,
        output_path,
    ]
    result = _run_ffmpeg(cmd, "S-curve contrast")
    if result and os.path.exists(output_path):
        print(f"  [color] S-Curve applied (punch added)", flush=True)
        return output_path
    return None


def apply_unsharp_mask(input_path, output_path):
    """Phase 3: Micro-contrast sharpening via 3x3 convolution kernel.
    Sharpens edges without halos using a simple sharpen kernel.
    Falls back to eq contrast boost if convolution is unavailable.
    """
    # 3x3 sharpen kernel: center-weighted difference
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf",
        "convolution='0 -1 0 -1 5 -1 0 -1 0:"
        "0 -1 0 -1 5 -1 0 -1 0:"
        "0 -1 0 -1 5 -1 0 -1 0:"
        "0 -1 0 -1 5 -1 0 -1 0'",
        "-c:v", RENDER_CODEC, "-preset", RENDER_INTERMEDIATE_PRESET,
        "-crf", str(RENDER_CRF),
        "-c:a", "copy",
        "-pix_fmt", RENDER_PIX_FMT,
        output_path,
    ]
    result = _run_ffmpeg(cmd, "sharpen convolution")
    if result and os.path.exists(output_path):
        print(f"  [color] Sharpened (3x3 convolution kernel)", flush=True)
        return output_path
    # Fallback: simple contrast boost
    print(f"  [color] Convolution unavailable, trying contrast fallback...", flush=True)
    cmd2 = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", "eq=contrast=1.15",
        "-c:v", RENDER_CODEC, "-preset", RENDER_INTERMEDIATE_PRESET,
        "-crf", str(RENDER_CRF),
        "-c:a", "copy",
        "-pix_fmt", RENDER_PIX_FMT,
        output_path,
    ]
    result2 = _run_ffmpeg(cmd2, "sharpen contrast fallback")
    if result2 and os.path.exists(output_path):
        return output_path
    return None


def apply_film_grain(input_path, output_path):
    """Phase 3: Film grain using noise filter (mono, low intensity).
    Adds subtle texture to prevent digital flatness.
    """
    intensity = max(1, min(50, int(COLOR_GRAIN_INTENSITY * 2)))
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf",
        f"noise=alls={intensity}:allf=t+u",
        "-c:v", RENDER_CODEC, "-preset", RENDER_INTERMEDIATE_PRESET,
        "-crf", str(RENDER_CRF),
        "-c:a", "copy",
        "-pix_fmt", RENDER_PIX_FMT,
        output_path,
    ]
    result = _run_ffmpeg(cmd, "film grain")
    if result and os.path.exists(output_path):
        print(f"  [color] Film grain injected ({COLOR_GRAIN_INTENSITY}% intensity)", flush=True)
        return output_path
    # Fallback: subtle noise via addroi (no-op visual, just continue)
    print(f"  [color] Noise filter unavailable, skipping grain", flush=True)
    return None


def apply_vignette(input_path, output_path):
    """Phase 3 (aux): Vignette — darken corners by 40% to tunnel focus."""
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf",
        "vignette=PI/4:max_eval=frame",
        "-c:v", RENDER_CODEC, "-preset", RENDER_INTERMEDIATE_PRESET,
        "-crf", str(RENDER_CRF),
        "-c:a", "copy",
        "-pix_fmt", RENDER_PIX_FMT,
        output_path,
    ]
    result = _run_ffmpeg(cmd, "vignette")
    if result and os.path.exists(output_path):
        print(f"  [color] Vignette applied (corners darkened)", flush=True)
        return output_path
    return None


def full_color_pipeline(input_path, output_path=None):
    """Run the complete color grading pipeline per Blueprint Section 3.
    Single-pass combined filter for all 5 core steps (eliminates 4 re-encodes).
    Falls back to per-step approach if combined filter fails.

    Order:
      1. White Balance Lock (colorchannelmixer)
      2. Dynamic Range Compression (curves lift)
      3. Teal & Orange Grade (colorbalance)
      4. Saturation/Vibrance (eq)
      5. S-Curve Contrast (curves)
    """
    if output_path is None:
        grade_id = uuid.uuid4().hex[:8]
        output_path = os.path.join(CLIPS_DIR, f"graded_{grade_id}.mp4")

    vf = (
        "colorchannelmixer=rr=1.05:rg=0.02:rb=-0.07:"
        "gr=0.01:gg=1.00:gb=-0.01:"
        "br=-0.05:bg=-0.02:bb=1.07,"
        "curves=all='0/0.04 0.5/0.5 1/0.96',"
        "colorbalance=rs=-0.02:gs=0.04:bs=0.08:"
        "rm=0.06:gm=-0.02:bm=-0.04:"
        "rh=0.03:gh=-0.01:bh=0.01,"
        f"eq=saturation={1.0 + COLOR_GLOBAL_SATURATION}:"
        f"gamma={1.0 + COLOR_VIBRANCE_BOOST * 0.2},"
        "curves=all='0/0 0.25/0.2 0.5/0.5 0.75/0.78 1/1'"
    )

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", vf,
        "-c:v", RENDER_CODEC, "-preset", "fast",
        "-crf", str(RENDER_CRF),
        "-c:a", "copy",
        "-pix_fmt", RENDER_PIX_FMT,
        output_path,
    ]

    print(f"  [color] Full pipeline (single pass): {os.path.basename(input_path)}", flush=True)

    single_ok = False
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            print(f"  [color] Pipeline complete (single pass): {os.path.basename(output_path)}", flush=True)
            single_ok = True
        else:
            print(f"  [color] Single-pass failed (rc={result.returncode}), trying safe filters...", flush=True)
            if result.stderr:
                print(f"  [color] stderr: {result.stderr[:200]}", flush=True)
    except Exception as e:
        print(f"  [color] Single-pass error: {e}, trying safe filters...", flush=True)


    if single_ok:
        return output_path

    # Fallback: per-step approach (individual re-encodes)
    print(f"  [color] Running per-step pipeline (8 steps)...", flush=True)
    work_dir = os.path.join(CLIPS_DIR, "_color_work")
    os.makedirs(work_dir, exist_ok=True)
    stage_id = uuid.uuid4().hex[:6]

    current = input_path

    steps = [
        ("white_balance", apply_white_balance_lock),
        ("dr_compress", apply_dynamic_range_compression),
        ("teal_orange", apply_teal_orange_grade),
        ("sat_vib", apply_saturation_vibrance),
        ("s_curve", apply_s_curve_contrast),
        ("sharpen", apply_unsharp_mask),
        ("grain", apply_film_grain),
        ("vignette", apply_vignette),
    ]

    for step_name, step_fn in steps:
        temp = os.path.join(work_dir, f"{step_name}_{stage_id}.mp4")
        result = step_fn(current, temp)
        if result:
            current = result
        else:
            print(f"  [color] Skipped {step_name} (failed)", flush=True)

    import shutil
    shutil.copy2(current, output_path)

    for f in os.listdir(work_dir):
        try:
            os.remove(os.path.join(work_dir, f))
        except Exception:
            pass

    if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
        print(f"  [color] Pipeline complete (per-step): {os.path.basename(output_path)}", flush=True)
        return output_path

    print(f"  [color] Pipeline failed — returning original", flush=True)
    return input_path
