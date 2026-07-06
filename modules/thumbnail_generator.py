"""
Thumbnail Generator — creates YouTube Shorts thumbnails from video frames.
Generates 3 variants for A/B testing.
"""
import json
import os
import subprocess
import sys
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import THUMBNAILS_DIR, THUMBNAILS_VARIANTS_DIR, SHORTS_WIDTH, SHORTS_HEIGHT
from modules.utils import get_font_path


def extract_peak_action_frame(video_path, output_path):
    """Blueprint Section 1.3: Extract the Peak Action Frame.
    Uses ffmpeg's 'thumbnail' filter to find the frame with highest
    kinetic energy / visual interest from the video stream.
    Falls back to middle-third random frame if detection fails.
    """
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"thumbnail=n=30,scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=2:flags=lanczos,crop={SHORTS_WIDTH}:{SHORTS_HEIGHT}",
        "-vframes", "1",
        "-q:v", "1",
        "-frames:v", "1",
        output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return output_path
    except Exception:
        pass

    # Fallback: middle-third random frame
    return extract_frame(video_path, output_path)


def extract_frame(video_path, output_path, at_time=None):
    """Extract a frame from a video at the best time."""
    if at_time is None:
        try:
            duration_cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path,
            ]
            result = subprocess.run(duration_cmd, capture_output=True, text=True, timeout=15)
            duration = float(result.stdout.strip())
            at_time = random.uniform(duration * 0.25, duration * 0.65)
        except (ValueError, subprocess.TimeoutExpired):
            at_time = 5.0

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(at_time),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        "-vf", f"scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=2:flags=lanczos,crop={SHORTS_WIDTH}:{SHORTS_HEIGHT}",
        output_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return output_path
    except Exception:
        pass
    return None


def apply_contrast_enhancement(frame_path, output_path):
    """Blueprint Section 1.3: Contrast Enhancement for thumbnail.
    Crush shadows (darker), pop highlights (brighter) for HDR-like punch.
    """
    cmd = [
        "ffmpeg", "-y", "-i", frame_path,
        "-vf",
        "curves=all='0/0.02 0.5/0.5 1/0.98', "
        "eq=contrast=1.15:brightness=0.02:saturation=1.1",
        "-q:v", "1",
        output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=15)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 500:
            return output_path
    except Exception:
        pass
    return None


def create_thumbnail_variant_1(frame_path, output_path, text, content_type):
    """Style 1: Clean frame with bottom text bar — bold title overlay."""
    if not os.path.exists(frame_path):
        return None

    font_path = get_font_path()

    overlay_text = text[:60].replace("'", "\\'").replace(":", "\\:")

    cmd = [
        "ffmpeg", "-y",
        "-i", frame_path,
        "-vf",
        f"drawtext=text='{overlay_text}':fontcolor=white:fontsize=48:"
        f"x=(w-text_w)/2:y=h-th-80:box=1:boxcolor=black@0.6:boxborderw=15:"
        f"fontfile='{font_path}',"
        f"drawtext=text='VARY':fontcolor=white@0.7:fontsize=28:"
        f"x=20:y=20:box=1:boxcolor=black@0.4:boxborderw=8:"
        f"fontfile='{font_path}'",
        "-q:v", "2",
        output_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
        if os.path.exists(output_path):
            return output_path
    except Exception:
        pass
    return None


def create_thumbnail_variant_2(frame_path, output_path, text, content_type):
    """Style 2: Split with emoji/icon, text on left side."""
    if not os.path.exists(frame_path):
        return None

    font_path = get_font_path()

    overlay_text = text[:40].replace("'", "\\'").replace(":", "\\:")
    icon = "🎬" if content_type == "movie" else "⚽"

    cmd = [
        "ffmpeg", "-y",
        "-i", frame_path,
        "-vf",
        f"drawtext=text='{icon}':fontcolor=white:fontsize=72:"
        f"x=40:y=(h-th)/2-60:fontfile='{font_path}',"
        f"drawtext=text='{overlay_text}':fontcolor=white:fontsize=38:"
        f"x=120:y=(h-text_h)/2:box=1:boxcolor=black@0.5:boxborderw=12:"
        f"fontfile='{font_path}'",
        "-q:v", "2",
        output_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
        if os.path.exists(output_path):
            return output_path
    except Exception:
        pass
    return None


def create_thumbnail_variant_3(frame_path, output_path, text, content_type):
    """Style 3: Full bleed with top/bottom bars, minimal text."""
    if not os.path.exists(frame_path):
        return None

    font_path = get_font_path()

    # Create a more dramatic version with gradients (via ffmpeg)
    overlay_text = text[:50].replace("'", "\\'").replace(":", "\\:")

    cmd = [
        "ffmpeg", "-y",
        "-i", frame_path,
        "-vf",
        f"drawbox=x=0:y=h-120:w=iw:h=120:color=black@0.5:t=fill,"
        f"drawtext=text='{overlay_text}':fontcolor=white:fontsize=42:"
        f"x=(w-text_w)/2:y=h-th+15:fontfile='{font_path}',"
        f"drawtext=text='VARY':fontcolor=gold:fontsize=32:"
        f"x=(w-text_w)/2:y=20:box=1:boxcolor=black@0.5:boxborderw=10:"
        f"fontfile='{font_path}'",
        "-q:v", "2",
        output_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
        if os.path.exists(output_path):
            return output_path
    except Exception:
        pass
    return None


def generate_thumbnails(video_path, title, content_type):
    """Generate 3 thumbnail variants for A/B testing.

    Args:
        video_path: Path to the processed Short video
        title: Video title for text overlay
        content_type: "football", "movie", or "series"

    Returns:
        Dict with 3 thumbnail paths, or None
    """
    os.makedirs(THUMBNAILS_DIR, exist_ok=True)
    os.makedirs(THUMBNAILS_VARIANTS_DIR, exist_ok=True)

    # Blueprint Section 1.3: Extract Peak Action Frame
    import uuid
    frame_id = uuid.uuid4().hex[:8]
    frame_path = os.path.join(THUMBNAILS_DIR, f"frame_{frame_id}.jpg")

    raw_path = os.path.join(THUMBNAILS_DIR, f"raw_{frame_id}.jpg")
    peak = extract_peak_action_frame(video_path, raw_path)

    if not peak:
        print("  [thumbnail] Failed to extract peak frame", flush=True)
        return None

    # Apply contrast enhancement (crush shadows, pop highlights)
    enhanced = apply_contrast_enhancement(raw_path, frame_path) or raw_path
    if enhanced != frame_path:
        import shutil
        shutil.copy2(raw_path, frame_path)

    # Clean up raw
    try:
        if os.path.exists(raw_path):
            os.remove(raw_path)
    except Exception:
        pass

    variants = {}

    # Variant 1: Bold bottom text
    v1_path = os.path.join(THUMBNAILS_VARIANTS_DIR, f"thumb_{frame_id}_v1.jpg")
    if create_thumbnail_variant_1(frame_path, v1_path, title, content_type):
        variants["v1"] = v1_path

    # Variant 2: Left-aligned with icon
    v2_path = os.path.join(THUMBNAILS_VARIANTS_DIR, f"thumb_{frame_id}_v2.jpg")
    if create_thumbnail_variant_2(frame_path, v2_path, title, content_type):
        variants["v2"] = v2_path

    # Variant 3: Dramatic with gradient
    v3_path = os.path.join(THUMBNAILS_VARIANTS_DIR, f"thumb_{frame_id}_v3.jpg")
    if create_thumbnail_variant_3(frame_path, v3_path, title, content_type):
        variants["v3"] = v3_path

    # Clean up the raw frame
    try:
        os.remove(frame_path)
    except Exception:
        pass

    if variants:
        print(f"  [thumbnail] Generated {len(variants)} variants: {list(variants.keys())}", flush=True)
        return variants

    return None


# ── Landscape (16:9) Thumbnails for Weekly Videos ──────────

LANDSCAPE_THUMB_WIDTH = 1280
LANDSCAPE_THUMB_HEIGHT = 720


def extract_landscape_frame(video_path, output_path, at_time=None):
    """Extract a 16:9 frame from a landscape video for thumbnails."""
    if at_time is None:
        try:
            duration_cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path,
            ]
            result = subprocess.run(duration_cmd, capture_output=True, text=True, timeout=15)
            duration = float(result.stdout.strip())
            at_time = random.uniform(duration * 0.25, duration * 0.65)
        except (ValueError, subprocess.TimeoutExpired):
            at_time = 5.0

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(at_time),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        "-vf", f"scale={LANDSCAPE_THUMB_WIDTH}:{LANDSCAPE_THUMB_HEIGHT}:force_original_aspect_ratio=1:flags=lanczos,"
                f"pad={LANDSCAPE_THUMB_WIDTH}:{LANDSCAPE_THUMB_HEIGHT}:(ow-iw)/2:(oh-ih)/2",
        output_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return output_path
    except Exception:
        pass
    return None


def create_landscape_thumbnail_v1(frame_path, output_path, movie_name):
    """Landscape v1: Centered title over dark backdrop with film strip accent."""
    if not os.path.exists(frame_path):
        return None

    font_path = get_font_path()
    safe_text = movie_name[:50].replace("'", "\\'").replace(":", "\\:")

    cmd = [
        "ffmpeg", "-y",
        "-i", frame_path,
        "-vf",
        f"drawbox=x=0:y=h-100:w=iw:h=100:color=black@0.6:t=fill,"
        f"drawtext=text='{safe_text}':fontcolor=white:fontsize=48:"
        f"x=(w-text_w)/2:y=h-th+15:fontfile='{font_path}',"
        f"drawtext=text='VARY Weekly':fontcolor=gold:fontsize=28:"
        f"x=(w-text_w)/2:y=20:box=1:boxcolor=black@0.5:boxborderw=10:"
        f"fontfile='{font_path}'",
        "-q:v", "2",
        output_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
        if os.path.exists(output_path):
            return output_path
    except Exception:
        pass
    return None


def create_landscape_thumbnail_v2(frame_path, output_path, movie_name):
    """Landscape v2: Left-aligned title with film strip icon on right."""
    if not os.path.exists(frame_path):
        return None

    font_path = get_font_path()
    safe_text = movie_name[:40].replace("'", "\\'").replace(":", "\\:")

    cmd = [
        "ffmpeg", "-y",
        "-i", frame_path,
        "-vf",
        f"drawtext=text='🎬':fontcolor=white:fontsize=72:"
        f"x=(w-tw-40):y=(h-th)/2-60:fontfile='{font_path}',"
        f"drawtext=text='{safe_text}':fontcolor=white:fontsize=42:"
        f"x=40:y=(h-text_h)/2-50:box=1:boxcolor=black@0.5:boxborderw=14:"
        f"fontfile='{font_path}',"
        f"drawtext=text='Story Analysis':fontcolor=gold@0.8:fontsize=28:"
        f"x=40:y=(h+text_h)/2-30:fontfile='{font_path}'",
        "-q:v", "2",
        output_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
        if os.path.exists(output_path):
            return output_path
    except Exception:
        pass
    return None


def create_landscape_thumbnail_v3(frame_path, output_path, movie_name):
    """Landscape v3: Minimal — semi-transparent bottom bar, clean text."""
    if not os.path.exists(frame_path):
        return None

    font_path = get_font_path()
    safe_text = movie_name[:50].replace("'", "\\'").replace(":", "\\:")

    # Subtle top and bottom bars + centered text
    cmd = [
        "ffmpeg", "-y",
        "-i", frame_path,
        "-vf",
        f"drawbox=x=0:y=0:w=iw:h=80:color=black@0.4:t=fill,"
        f"drawbox=x=0:y=h-90:w=iw:h=90:color=black@0.4:t=fill,"
        f"drawtext=text='{safe_text}':fontcolor=white:fontsize=44:"
        f"x=(w-text_w)/2:y=h-70:fontfile='{font_path}',"
        f"drawtext=text='VARY':fontcolor=white@0.8:fontsize=30:"
        f"x=20:y=25:fontfile='{font_path}'",
        "-q:v", "2",
        output_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
        if os.path.exists(output_path):
            return output_path
    except Exception:
        pass
    return None


def generate_weekly_thumbnails(video_path, movie_name):
    """Generate 3 landscape thumbnail variants for weekly videos.

    Args:
        video_path: Path to the processed weekly video.
        movie_name: Name of the movie for text overlays.

    Returns:
        Dict with 3 thumbnail paths, or None.
    """
    os.makedirs(THUMBNAILS_DIR, exist_ok=True)
    os.makedirs(THUMBNAILS_VARIANTS_DIR, exist_ok=True)

    import uuid
    frame_id = uuid.uuid4().hex[:8]
    frame_path = os.path.join(THUMBNAILS_DIR, f"weekly_frame_{frame_id}.jpg")

    if not extract_landscape_frame(video_path, frame_path):
        print("  [thumbnail] Failed to extract landscape frame", flush=True)
        return None

    variants = {}

    v1_path = os.path.join(THUMBNAILS_VARIANTS_DIR, f"weekly_thumb_{frame_id}_v1.jpg")
    if create_landscape_thumbnail_v1(frame_path, v1_path, movie_name):
        variants["v1"] = v1_path

    v2_path = os.path.join(THUMBNAILS_VARIANTS_DIR, f"weekly_thumb_{frame_id}_v2.jpg")
    if create_landscape_thumbnail_v2(frame_path, v2_path, movie_name):
        variants["v2"] = v2_path

    v3_path = os.path.join(THUMBNAILS_VARIANTS_DIR, f"weekly_thumb_{frame_id}_v3.jpg")
    if create_landscape_thumbnail_v3(frame_path, v3_path, movie_name):
        variants["v3"] = v3_path

    try:
        os.remove(frame_path)
    except Exception:
        pass

    if variants:
        print(f"  [thumbnail] Generated {len(variants)} landscape variants: {list(variants.keys())}", flush=True)
        return variants

    return None


if __name__ == "__main__":
    # Test
    if len(sys.argv) > 1:
        import sys
        if len(sys.argv) >= 3 and sys.argv[1] == "--weekly":
            result = generate_weekly_thumbnails(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "Movie")
        else:
            result = generate_thumbnails(sys.argv[1], "Test Clip", "movie")
        print(json.dumps(result, indent=2, default=str) if result else "Failed")
