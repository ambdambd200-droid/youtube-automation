"""
Clip Editor — trims, crops to 9:16 (Shorts), adds text overlays, preserves natural audio.
No background music — only original sound from the source clip.
"""
import json
import os
import subprocess
import sys
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    SHORTS_WIDTH, SHORTS_HEIGHT, FPS,
    CLIPS_DIR, CLIP_MAX_DURATION, CLIP_MIN_DURATION,
)


def get_video_info(video_path):
    """Get video metadata using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration,size",
        "-show_entries", "stream=width,height,codec_name",
        "-of", "json",
        video_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except:
        pass
    return {}


def get_video_duration(video_path):
    """Get video duration in seconds."""
    info = get_video_info(video_path)
    try:
        return float(info.get("format", {}).get("duration", 0))
    except (ValueError, TypeError):
        return 0


def get_video_dimensions(video_path):
    """Get video width and height."""
    info = get_video_info(video_path)
    streams = info.get("streams", [])
    for stream in streams:
        w = stream.get("width", 0)
        h = stream.get("height", 0)
        if w and h:
            return w, h
    return 1920, 1080


def select_clip_segment(video_path, target_duration=None):
    """Select the best segment from a video to use as a clip.

    For longer videos, picks the most interesting segment.
    For short videos, uses the whole thing.

    Returns: (start_time, duration) in seconds
    """
    duration = get_video_duration(video_path)
    if duration <= 0:
        return (0, CLIP_MIN_DURATION)

    if target_duration is None:
        target_duration = random.randint(CLIP_MIN_DURATION, min(CLIP_MAX_DURATION, int(duration)))

    # For short videos, use the whole thing
    if duration <= target_duration + 5:
        return (0, duration)

    # For longer videos, pick a random segment
    max_start = max(0, int(duration) - target_duration - 1)
    start_time = random.randint(5, max_start)  # Skip first 5 seconds (intro)

    # Sometimes pick from the middle (often the most interesting part)
    if random.random() < 0.4 and duration > 60:
        middle = duration / 2
        start_time = random.randint(
            max(5, int(middle) - target_duration),
            min(int(middle) + target_duration, int(duration) - target_duration)
        )

    return (start_time, target_duration)


def crop_to_shorts(input_path, output_path, start_time=0, duration=None):
    """Crop a video to 9:16 vertical format for YouTube Shorts.

    Uses smart cropping: picks the most action-packed region or centers.
    Preserves original audio — NO background music added.
    """
    video_duration = get_video_duration(input_path)

    if duration is None:
        duration = min(CLIP_MAX_DURATION, video_duration)

    if duration > video_duration - start_time:
        duration = video_duration - start_time

    if duration < CLIP_MIN_DURATION:
        duration = min(CLIP_MIN_DURATION, video_duration - start_time)

    # Get original dimensions
    in_w, in_h = get_video_dimensions(input_path)

    # Smart crop to 9:16 (1080x1920)
    # For landscape video: crop center portion to 9:16 ratio
    # For portrait/vertical: resize to fit

    target_ratio = SHORTS_WIDTH / SHORTS_HEIGHT  # 1080/1920 = 0.5625

    if in_w > in_h:
        # Landscape video
        # Crop height = 100%, width = height * 0.5625
        crop_height = in_h
        crop_width = int(crop_height * target_ratio * (SHORTS_HEIGHT / SHORTS_WIDTH))
        if crop_width > in_w:
            crop_width = in_w
            crop_height = int(crop_width / target_ratio * (SHORTS_WIDTH / SHORTS_HEIGHT))

        # Center crop
        x = (in_w - crop_width) // 2
        y = 0

        filter_complex = (
            f"[0:v]trim=start={start_time}:duration={duration},setpts=PTS-STARTPTS,"
            f"crop={crop_width}:{crop_height}:{x}:{y},"
            f"scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=0[vout];"
            f"[0:a]atrim=start={start_time}:duration={duration},asetpts=PTS-STARTPTS[aout]"
        )
    else:
        # Portrait or square video
        filter_complex = (
            f"[0:v]trim=start={start_time}:duration={duration},setpts=PTS-STARTPTS,"
            f"scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=1,"
            f"pad={SHORTS_WIDTH}:{SHORTS_HEIGHT}:(ow-iw)/2:(oh-ih)/2[vout];"
            f"[0:a]atrim=start={start_time}:duration={duration},asetpts=PTS-STARTPTS[aout]"
        )

    # Add subtle text overlay with the content type label
    text_overlay = ""
    if random.random() < 0.3:  # 30% of videos get a title overlay
        text_overlay = (
            f",drawtext=text='VARY':fontcolor=white:fontsize=36:"
            f"x=w-tw-20:y=h-th-20:box=1:boxcolor=black@0.4:boxborderw=8:fontfile='C\\:/Windows/Fonts/arial.ttf'"
        )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter_complex", filter_complex + text_overlay,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        "-movflags", "+faststart",
        output_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=300)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            actual_dur = get_video_duration(output_path)
            print(f"  [editor] Created Short: {output_path} ({actual_dur:.1f}s, {os.path.getsize(output_path)} bytes)", flush=True)
            return {
                "path": output_path,
                "duration": actual_dur,
                "trim_start": start_time,
                "trim_end": start_time + duration,
            }
    except subprocess.TimeoutExpired:
        print("  [editor] FFmpeg timed out", flush=True)
    except Exception as e:
        print(f"  [editor] Error: {e}", flush=True)

    return None


def add_text_overlay(video_path, output_path, text, position="bottom"):
    """Add a text overlay to a video. Used for the final polish."""
    if not os.path.exists(video_path):
        return None

    # Position
    if position == "bottom":
        x = "w-tw-20"
        y = "h-th-20"
    elif position == "top":
        x = "w-tw-20"
        y = "20"
    else:  # center
        x = "(w-tw)/2"
        y = "(h-th)/2"

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf",
        f"drawtext=text='{text}':fontcolor=white:fontsize=42:"
        f"x={x}:y={y}:box=1:boxcolor=black@0.5:boxborderw=10:"
        f"fontfile='C\\:/Windows/Fonts/arial.ttf'",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=120)
        if os.path.exists(output_path):
            return output_path
    except:
        pass
    return None


def create_clip(input_path, content_type, title=""):
    """Main entry point — creates a Short from a source clip.

    Args:
        input_path: Path to downloaded source video
        content_type: "worldcup_2026" or "movie"
        title: Title of the source video

    Returns:
        Dict with processed clip info, or None
    """
    os.makedirs(CLIPS_DIR, exist_ok=True)

    # Generate output filename
    import uuid
    clip_id = uuid.uuid4().hex[:10]
    output_path = os.path.join(CLIPS_DIR, f"{content_type}_{clip_id}.mp4")

    # Pick clip segment
    start_time, duration = select_clip_segment(input_path)

    # Crop to Shorts format
    result = crop_to_shorts(input_path, output_path, start_time, duration)

    if result:
        result["content_type"] = content_type
        result["source_title"] = title
        result["source_path"] = input_path
        return result

    return None


if __name__ == "__main__":
    # Test
    if len(sys.argv) > 1:
        result = create_clip(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "movie")
        print(json.dumps(result, indent=2, default=str) if result else "Failed")
