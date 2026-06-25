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


def extract_frame(video_path, output_path, at_time=None):
    """Extract a frame from a video at the best time."""
    if at_time is None:
        # Pick a random frame from the middle third (most interesting)
        try:
            duration_cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path,
            ]
            result = subprocess.run(duration_cmd, capture_output=True, text=True, timeout=15)
            duration = float(result.stdout.strip())
            # Pick from 25% to 65% into the video
            at_time = random.uniform(duration * 0.25, duration * 0.65)
        except (ValueError, subprocess.TimeoutExpired):
            at_time = 5.0

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(at_time),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        "-vf", f"scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=2,crop={SHORTS_WIDTH}:{SHORTS_HEIGHT}",
        output_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
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
        content_type: "worldcup_2026" or "movie"

    Returns:
        Dict with 3 thumbnail paths, or None
    """
    os.makedirs(THUMBNAILS_DIR, exist_ok=True)
    os.makedirs(THUMBNAILS_VARIANTS_DIR, exist_ok=True)

    # Extract a base frame
    import uuid
    frame_id = uuid.uuid4().hex[:8]
    frame_path = os.path.join(THUMBNAILS_DIR, f"frame_{frame_id}.jpg")

    if not extract_frame(video_path, frame_path):
        print("  [thumbnail] Failed to extract frame", flush=True)
        return None

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


if __name__ == "__main__":
    # Test
    if len(sys.argv) > 1:
        result = generate_thumbnails(sys.argv[1], "Test Clip", "movie")
        print(json.dumps(result, indent=2, default=str) if result else "Failed")
