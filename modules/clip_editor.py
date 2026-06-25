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
from modules.utils import get_font_path


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
    except Exception:
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


def detect_scenes(video_path):
    """Use ffmpeg scene detection to find interesting scene changes.

    Returns a list of scene change timestamps (in seconds), sorted ascending.
    Returns empty list on failure (falls back to random selection).
    """
    try:
        cmd = [
            "ffmpeg", "-i", video_path,
            "-filter:v", "select='gt(scene,0.3)',showinfo",
            "-f", "null",
            "-",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        # Parse showinfo output to extract scene change timestamps
        scenes = []
        for line in result.stderr.split("\n"):
            if "pts_time:" in line:
                import re
                match = re.search(r"pts_time:([\d.]+)", line)
                if match:
                    t = float(match.group(1))
                    if t > 1.0:  # Skip the very first frame
                        scenes.append(t)
        return scenes
    except Exception as e:
        print(f"  [editor] Scene detection skipped: {e}", flush=True)
        return []


def select_clip_segment(video_path, target_duration=None, content_type="movie"):
    """Select the best segment from a video to use as a clip.

    Uses scene detection to find the most visually interesting segments.
    Respects evolution engine's scene threshold if available.
    For short videos, uses the whole thing. Falls back to random selection.

    Returns: (start_time, duration) in seconds
    """
    duration = get_video_duration(video_path)
    if duration <= 0:
        return (0, CLIP_MIN_DURATION)

    if target_duration is None:
        # Use evolved clip duration bounds from evolution engine
        try:
            from modules.evolution_engine import get_parameter
            evo_min = get_parameter("clip_min_duration", CLIP_MIN_DURATION)
            evo_max = get_parameter("clip_max_duration", CLIP_MAX_DURATION)
            target_duration = random.randint(
                max(CLIP_MIN_DURATION, int(evo_min)),
                min(CLIP_MAX_DURATION, min(int(evo_max), int(duration)))
            )
        except Exception:
            target_duration = random.randint(CLIP_MIN_DURATION, min(CLIP_MAX_DURATION, int(duration)))

    # For short videos, use the whole thing
    if duration <= target_duration + 10:
        return (0, duration)

    # Try scene detection first
    scenes = detect_scenes(video_path)

    if scenes:
        # We have scene changes — find the densest cluster of scene changes
        # within a window of target_duration seconds
        best_start = 5  # default: skip intro
        best_density = 0

        for i, scene_time in enumerate(scenes):
            window_end = scene_time + target_duration
            # Count how many scenes fall within this window
            density = sum(1 for s in scenes if scene_time <= s <= window_end)
            if density > best_density and scene_time + target_duration < duration:
                # Weight by how far into the video (middle is usually better)
                middle_bonus = 1.0 - abs(scene_time - duration / 2) / (duration / 2)
                weighted = density * (0.7 + 0.3 * middle_bonus)
                if weighted > best_density:
                    best_density = weighted
                    best_start = scene_time

        # Add a small random offset for variety
        offset = random.uniform(-3, 3)
        best_start = max(1, min(best_start + offset, duration - target_duration - 1))
        print(f"  [editor] Scene-smart segment: {best_start:.1f}s - {best_start + target_duration:.1f}s ({len(scenes)} scenes detected)", flush=True)
        return (best_start, target_duration)

    # Fallback: pick a random segment
    print(f"  [editor] No scenes detected, using random segment", flush=True)
    max_start = max(1, int(duration) - target_duration - 1)
    start_time = random.randint(5, max_start) if max_start > 5 else 1

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
        font_path = get_font_path()
        text_overlay = (
            f",drawtext=text='VARY':fontcolor=white:fontsize=36:"
            f"x=w-tw-20:y=h-th-20:box=1:boxcolor=black@0.4:boxborderw=8:fontfile='{font_path}'"
        )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter_complex", filter_complex + text_overlay,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-preset", "medium",    # Good balance of speed and compression
        "-crf", "23",           # Standard quality (lower = better, 23 is default)
        "-c:a", "aac",
        "-b:a", "192k",         # Higher audio bitrate for cleaner sound
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        "-movflags", "+faststart",
        "-profile:v", "high",
        "-level", "4.1",
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

    font_path = get_font_path()

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf",
        f"drawtext=text='{text}':fontcolor=white:fontsize=42:"
        f"x={x}:y={y}:box=1:boxcolor=black@0.5:boxborderw=10:"
        f"fontfile='{font_path}'",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=120)
        if os.path.exists(output_path):
            return output_path
    except Exception:
        pass
    return None


def remux_to_compatible(input_path):
    """Re-mux a downloaded WebM file to a compatible MP4 if needed.

    YouTube downloads are often VP9/Opus WebM format, which ffmpeg
    sometimes struggles with for complex filter operations. This converts
    to a standard H.264/AAC MP4 as a pre-processing step.

    Returns:
        Path to compatible file (same as input if already compatible).
    """
    ext = os.path.splitext(input_path)[1].lower()
    # Only re-mux if it's a webm file
    if ext not in (".webm", ".mkv"):
        return input_path

    if ext == ".webm":
        # Quick re-mux to a temporary MP4 for smoother editing
        import uuid
        temp_id = uuid.uuid4().hex[:8]
        temp_path = os.path.join(CLIPS_DIR, f"_temp_{temp_id}.mp4")

        print(f"  [editor] Re-muxing WebM to MP4 for compatibility...", flush=True)
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            temp_path,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 10000:
                print(f"  [editor] Re-muxed to: {temp_path} ({os.path.getsize(temp_path)} bytes)", flush=True)
                return temp_path
            else:
                print(f"  [editor] Re-mux failed, trying original file", flush=True)
                if result.returncode != 0:
                    print(f"  [editor] FFmpeg stderr: {result.stderr[-500:]}", flush=True)
        except Exception as e:
            print(f"  [editor] Re-mux error: {e}", flush=True)

    return input_path


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

    # Pre-process: re-mux WebM to MP4 for compatibility
    working_input = remux_to_compatible(input_path)

    # Pick clip segment — pass content_type so evolution can tune selection
    start_time, duration = select_clip_segment(working_input, content_type=content_type)

    # Crop to Shorts format
    result = crop_to_shorts(working_input, output_path, start_time, duration)

    # Clean up temp file if created
    if working_input != input_path and os.path.exists(working_input):
        try:
            os.remove(working_input)
        except Exception:
            pass

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
