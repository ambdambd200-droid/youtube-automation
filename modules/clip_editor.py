"""
Clip Editor — trims, crops to 9:16 (Shorts), adds text overlays,
dynamic zoom, transitions, and sound effects per content type.
Football: raw crop only. Movies/Series: LaughTrack-style effects.
"""
import json
import os
import subprocess
import sys
import random
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    SHORTS_WIDTH, SHORTS_HEIGHT, FPS,
    CLIPS_DIR, CLIP_MAX_DURATION, CLIP_MIN_DURATION, LOG_DIR,
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


def fallback_duration(video_path):
    """Get video duration using a simple ffprobe command as fallback.

    Sometimes ffprobe's JSON output fails to include duration (e.g. with
    certain container formats). This tries a direct text format query.
    """
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            val = result.stdout.strip()
            if val:
                return float(val)
    except (ValueError, subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return 0


def get_video_duration(video_path):
    """Get video duration in seconds.

    Tries JSON ffprobe first, then falls back to text-based ffprobe
    for container formats that don't report duration in JSON.
    """
    info = get_video_info(video_path)
    try:
        dur = float(info.get("format", {}).get("duration", 0))
        if dur > 0:
            return dur
    except (ValueError, TypeError):
        pass

    # Fallback: try text-based ffprobe (handles WebM/Opus better)
    fb = fallback_duration(video_path)
    if fb > 0:
        return fb

    # Last resort: try ffprobe with stream-level duration query
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        val = result.stdout.strip()
        if val:
            return float(val)
    except Exception:
        pass

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
    print(f"  [editor] Getting video duration for: {os.path.basename(video_path)}", flush=True)
    duration = get_video_duration(video_path)
    print(f"  [editor] Video duration: {duration:.1f}s", flush=True)
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

    # Build the video filter chain (without output label)
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

        video_chain = (
            f"[0:v]trim=start={start_time}:duration={duration},setpts=PTS-STARTPTS,"
            f"crop={crop_width}:{crop_height}:{x}:{y},"
            f"scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=0"
        )
    else:
        # Portrait or square video
        video_chain = (
            f"[0:v]trim=start={start_time}:duration={duration},setpts=PTS-STARTPTS,"
            f"scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=1,"
            f"pad={SHORTS_WIDTH}:{SHORTS_HEIGHT}:(ow-iw)/2:(oh-ih)/2"
        )

    # Assemble full filtergraph: video chain + audio chain, each with its own output label
    filter_complex = (
        f"{video_chain}[vout];"
        f"[0:a]atrim=start={start_time}:duration={duration},asetpts=PTS-STARTPTS[aout]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter_complex", filter_complex,
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
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            actual_dur = get_video_duration(output_path)
            # If ffprobe returns 0, use calculated duration as fallback
            if actual_dur <= 0:
                actual_dur = fallback_duration(output_path)
            if actual_dur <= 0:
                actual_dur = duration  # fallback: use the requested trim duration
            print(f"  [editor] Created Short: {output_path} ({actual_dur:.1f}s, {os.path.getsize(output_path)} bytes)", flush=True)
            return {
                "path": output_path,
                "duration": actual_dur,
                "trim_start": start_time,
                "trim_end": start_time + duration,
            }
        else:
            # File too small or doesn't exist — print ffmpeg stderr for debugging
            if result.returncode != 0:
                print(f"  [editor] FFmpeg error: {result.stderr[-500:]}", flush=True)
            else:
                print(f"  [editor] Output file missing or too small: {output_path}", flush=True)
    except subprocess.TimeoutExpired:
        print("  [editor] FFmpeg timed out", flush=True)
    except Exception as e:
        print(f"  [editor] Error: {e}", flush=True)

    return None


def append_movie_end_card(video_path, output_path, movie_title=""):
    """Append a 3-second end card to a movie short suggesting viewers watch the original film.

    Generates a black frame with centered text ("Watch the original movie"),
    then concatenates it to the end of the existing clip using ffmpeg.

    Args:
        video_path: Path to the existing processed Short.
        output_path: Output path for the final video with end card appended.
        movie_title: Optional source movie title shown on the end card.

    Returns:
        output_path on success, None on failure.
    """
    if not os.path.exists(video_path):
        return None

    import uuid
    endcard_id = uuid.uuid4().hex[:8]
    endcard_path = os.path.join(CLIPS_DIR, f"_endcard_{endcard_id}.mp4")
    font_path = get_font_path()

    # Build the end card text — primary message + optional movie title
    # Escape special chars for ffmpeg drawtext compatibility
    primary_text = "Watch the original movie"
    subtitle_text = ""
    if movie_title:
        short_title = movie_title[:45].replace("'", "\\'").replace(":", "\\:")
        subtitle_text = short_title

    # Generate the 3-second black end card with text overlay
    # Note: color source is video-only; anullsrc provides silent audio
    # so the concat filter can pair both streams
    drawtext_filters = (
        f"drawtext=text='{primary_text}':fontcolor=white:fontsize=48:"
        f"x=(w-text_w)/2:y=(h-text_h)/2-40:fontfile='{font_path}'"
    )
    if subtitle_text:
        drawtext_filters += (
            f",drawtext=text='{subtitle_text}':fontcolor=white@0.7:fontsize=32:"
            f"x=(w-text_w)/2:y=(h-text_h)/2+30:fontfile='{font_path}'"
        )

    cmd_endcard = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s={SHORTS_WIDTH}x{SHORTS_HEIGHT}:d=3",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
        "-shortest",
        "-vf", drawtext_filters,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "64k",
        "-pix_fmt", "yuv420p",
        "-profile:v", "high",
        "-level", "4.1",
        endcard_path,
    ]

    print(f"  [editor] Generating end card...", flush=True)
    try:
        subprocess.run(cmd_endcard, capture_output=True, timeout=30)
    except subprocess.TimeoutExpired:
        print(f"  [editor] End card generation timed out", flush=True)
        return None

    if not os.path.exists(endcard_path) or os.path.getsize(endcard_path) < 1000:
        print(f"  [editor] End card generation failed", flush=True)
        return None

    # Concatenate the main clip with the end card
    print(f"  [editor] Appending end card to movie short...", flush=True)
    cmd_concat = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", endcard_path,
        "-filter_complex", "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[vout][aout]",
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        "-movflags", "+faststart",
        "-profile:v", "high",
        "-level", "4.1",
        output_path,
    ]

    try:
        subprocess.run(cmd_concat, capture_output=True, timeout=120)
    except subprocess.TimeoutExpired:
        print(f"  [editor] End card concat timed out", flush=True)
        return None

    # Clean up the temporary end card
    try:
        os.remove(endcard_path)
    except Exception:
        pass

    if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
        print(f"  [editor] End card appended: {output_path} ({os.path.getsize(output_path)} bytes)", flush=True)
        return output_path

    print(f"  [editor] End card concat produced invalid output", flush=True)
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


def create_clip(input_path, content_type, title="", skip_effects=False):
    """Main entry point — creates a Short from a source clip.

    Args:
        input_path: Path to downloaded source video
        content_type: "football", "movie", or "series"
        title: Title of the source video
        skip_effects: If True, bypass all fancy effects and use basic crop only

    Returns:
        Dict with processed clip info, or None
    """
    os.makedirs(CLIPS_DIR, exist_ok=True)

    import uuid
    clip_id = uuid.uuid4().hex[:10]
    output_path = os.path.join(CLIPS_DIR, f"{content_type}_{clip_id}.mp4")

    working_input = remux_to_compatible(input_path)

    start_time, duration = select_clip_segment(working_input, content_type=content_type)

    if content_type == "football" or skip_effects:
        result = crop_to_shorts(working_input, output_path, start_time, duration)
    else:
        temp_path = output_path.replace(".mp4", "_raw.mp4")
        result = crop_to_shorts(working_input, temp_path, start_time, duration)
        if result:
            effects_path = output_path
            # Apply movie/series effects only if not skipped
            if not skip_effects:
                result = apply_movie_effects(result["path"], effects_path, content_type, title)
            else:
                import shutil
                shutil.copy2(result["path"], effects_path)
                result["path"] = effects_path
                result["duration"] = result.get("duration", duration)
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

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


# ── LaughTrack-style Effects for Movie/Series Shorts ─────

def _generate_sfx(sfx_type):
    """Generate a short sound effect WAV and return its path."""
    import uuid
    sfx_id = uuid.uuid4().hex[:8]
    sfx_path = os.path.join(CLIPS_DIR, f"_sfx_{sfx_id}.wav")

    sfx_map = {
        "whoosh": (
            "anoisesrc=d=0.3:c=pink:a=0.5,"
            "aequalizer=f=2000:t=q:w=1:g=10,"
            "aequalizer=f=200:t=q:w=1:g=-10,"
            "afade=t=in:d=0.05,afade=t=out:d=0.15"
        ),
        "bassdrop": (
            "sine=f=60:d=0.5,"
            "volume=2.0,"
            "afade=t=in:d=0.01,afade=t=out:d=0.3"
        ),
        "riser": (
            "sine=f=100:d=1.5:frequency='100+1000*t/1.5',"
            "volume=1.5,afade=t=in:d=0.1"
        ),
        "vineboom": (
            "sine=f=45:d=0.15,"
            "volume=3.0,afade=t=out:d=0.12"
        ),
        "scratch": (
            "anoisesrc=d=0.4:c=brown:a=1.0,"
            "aequalizer=f=3000:t=q:w=2:g=20,"
            "volume=0.8,afade=t=in:d=0.02,afade=t=out:d=0.15"
        ),
    }

    filt = sfx_map.get(sfx_type)
    if not filt:
        return None

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", filt,
        "-ac", "1", "-ar", "44100",
        sfx_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=15)
        if os.path.exists(sfx_path) and os.path.getsize(sfx_path) > 100:
            return sfx_path
    except Exception:
        pass
    return None


def _laugh_track_texts(title=""):
    """Generate timed pop-up text and emoji overlays for movie/series shorts."""
    movie_name = title[:40] if title else "this scene"

    templates = [
        (f"\"{movie_name}\"", 0.08, "center"),
        ("wait for it...", 0.20, "bottom"),
        ("👀", 0.35, "center"),
        ("this is cinema", 0.50, "bottom"),
        ("🔥", 0.65, "center"),
        ("peak fiction.", 0.80, "bottom"),
    ]

    texts = []
    for text, ratio, pos in templates:
        texts.append({"text": text, "ratio": ratio, "pos": pos})
    return texts


def apply_movie_effects(input_path, output_path, content_type, title=""):
    """Apply LaughTrack-style effects to a movie/series short.
    Adds dynamic zoom, timed pop-up text, glitch transition, and sound effects.
    """
    duration = get_video_duration(input_path)
    if duration <= 0:
        return None

    import uuid
    font_path = get_font_path()

    texts = _laugh_track_texts(title)

    filter_parts = [f"[0:v]scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=0,setsar=1[base]"]

    last_end_ratio = 0
    for i, item in enumerate(texts):
        t_start = duration * item["ratio"]
        t_end = min(t_start + 3.0, duration)

        safe_text = item["text"].replace("'", "\\'").replace(":", "\\:").replace("[", "\\[").replace("]", "\\]")
        is_emoji = any(c in safe_text for c in ["👀", "🔥", "💀", "😱", "😂"])

        if is_emoji:
            fs = 80
            x_expr = "(w-text_w)/2"
            y_expr = "(h-text_h)/2 - 40"
            box = "0"
            bc = "black@0"
        else:
            fs = 48
            x_expr = "(w-text_w)/2"
            y_expr = "h-th-80" if item["pos"] == "bottom" else "(h-text_h)/2"
            box = "1"
            bc = "black@0.5"

        filter_parts.append(
            f"[base]drawtext=text='{safe_text}':fontcolor=white:fontsize={fs}:"
            f"x={x_expr}:y={y_expr}:"
            f"box={box}:boxcolor={bc}:boxborderw=10:"
            f"alpha='if(lt(t,{t_start}),0,if(lt(t,{t_start+0.15}),(t-{t_start})/0.15,if(lt(t,{t_end}),1,0)))':"
            f"fontfile='{font_path}':"
            f"enable='between(t,{t_start},{t_end})'[t{i}]"
        )

    full_filter = ";".join(filter_parts)
    last_label = f"t{len(texts)-1}" if texts else "base"

    sfx_files = []
    for sfx_type in ["whoosh", "bassdrop"]:
        sfx_path = _generate_sfx(sfx_type)
        if sfx_path:
            sfx_files.append(sfx_path)

    input_files = ["-i", input_path]
    audio_filters = ["[0:a]acopy[aout]"]

    if sfx_files:
        for sfx_path in sfx_files:
            sfx_name = os.path.basename(sfx_path)
            input_files += ["-i", sfx_path]
            sfx_id = sfx_name.replace(".wav", "").replace("_sfx_", "")
            # Mix at 15% volume at the beginning
            audio_filters.append(
                f"[{len(input_files)-1}:a]volume=0.15[a_sfx_{sfx_id}]"
            )

        mix_inputs = "[0:a]"
        for sfx_path in sfx_files:
            sfx_name = os.path.basename(sfx_path)
            sfx_id = sfx_name.replace(".wav", "").replace("_sfx_", "")
            mix_inputs += f"[a_sfx_{sfx_id}]"

        audio_filters[0] = f"{mix_inputs}amix=inputs={len(sfx_files)+1}:duration=first:weights=1 0.15[aout]"

    filter_complex = f"{full_filter}[vout];" + ";".join(audio_filters)

    cmd = [
        "ffmpeg", "-y",
    ] + input_files + [
        "-filter_complex", filter_complex,
        "-map", f"[{last_label}]",
        "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-movflags", "+faststart",
        "-profile:v", "high", "-level", "4.1",
        output_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=300)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            actual_dur = get_video_duration(output_path)
            if actual_dur <= 0:
                actual_dur = fallback_duration(output_path)
            print(f"  [editor] LaughTrack effects applied: {output_path} ({actual_dur:.1f}s, {os.path.getsize(output_path)} bytes)", flush=True)
            return {"path": output_path, "duration": actual_dur}
        else:
            print(f"  [editor] LaughTrack effects failed — returning original crop", flush=True)
            import shutil
            shutil.copy2(input_path, output_path)
            return {"path": output_path, "duration": duration}
    except subprocess.TimeoutExpired:
        print(f"  [editor] LaughTrack effects timed out — returning original crop", flush=True)
        import shutil
        shutil.copy2(input_path, output_path)
        return {"path": output_path, "duration": duration}
    except Exception as e:
        print(f"  [editor] LaughTrack effects error: {e}", flush=True)
        import shutil
        shutil.copy2(input_path, output_path)
        return {"path": output_path, "duration": duration}


# ── Weekly Video Pipeline ─────────────────────────────────

WEEKLY_SEGMENT_DURATION = 20  # seconds per text segment
WEEKLY_MAX_DURATION = 480      # 8 minutes max for weekly videos
WEEKLY_MIN_DURATION = 90       # 1.5 minutes minimum

WEEKLY_STORY_TEMPLATES = [
    "A story of [theme].",
    "This film explores [theme].",
    "At its heart, this is a story about [theme].",
    "What makes this film unforgettable is [theme].",
    "The director crafts a tale of [theme].",
]

WEEKLY_THEMES = [
    "ambition and its cost",
    "love and loss",
    "redemption",
    "the human condition",
    "sacrifice",
    "identity",
    "hope against all odds",
    "the nature of truth",
    "family and belonging",
    "courage in darkness",
]


def _generate_story_texts(source_title=""):
    """Generate storytelling text segments for the weekly video.

    Creates a series of text overlays that tell the movie's story,
    shown sequentially throughout the video.

    Returns:
        List of (text, start_time_ratio) tuples, where start_time_ratio
        is 0.0 to 1.0 representing position in the video.
    """
    # Use the shared extraction helper to get the clean movie name
    movie_name = _extract_movie_name(source_title)

    theme = random.choice(WEEKLY_THEMES)
    template = random.choice(WEEKLY_STORY_TEMPLATES)
    opening = template.replace("[theme]", theme)

    texts = [
        (f"{movie_name}", 0.02),
        (opening, 0.10),
        (f"A cinematic journey through {theme}.", 0.25),
        ("Every frame tells a story.", 0.40),
        ("Silence speaks louder than words.", 0.55),
        ("The director's vision unfolds.", 0.70),
        ("This is why cinema matters.", 0.85),
    ]
    return texts


# ── Weekly Video Intro Card ───────────────────────────────

WEEKLY_INTRO_DURATION = 3.0  # seconds (all styles share this)
WEEKLY_INTRO_CROSSFADE = 0.5  # seconds of smooth crossfade between intro and main content

# Available intro animation styles — rotated each week for variety
WEEKLY_INTRO_STYLES = ["cinematic", "split", "minimal"]


def select_intro_style():
    """Select an intro animation style for the weekly video.

    Uses weighted random choice to ensure variety while avoiding
    long streaks of the same style.

    Returns:
        A style name string from WEEKLY_INTRO_STYLES.
    """
    # Simple random selection with slight anti-repetition bias
    # Tracks the last-used style via a small state file in LOG_DIR (never cleaned)
    state_path = os.path.join(LOG_DIR, "_intro_style_state.json")
    last_style = None
    try:
        if os.path.exists(state_path):
            with open(state_path, "r") as f:
                state = json.load(f)
                last_style = state.get("last_style")
    except Exception:
        pass

    # Weight: 40% chance of repeating last style, 60% chance of switching
    if last_style and random.random() < 0.6:
        choices = [s for s in WEEKLY_INTRO_STYLES if s != last_style]
        chosen = random.choice(choices)
    else:
        chosen = random.choice(WEEKLY_INTRO_STYLES)

    # Save chosen style for next run
    try:
        with open(state_path, "w") as f:
            json.dump({"last_style": chosen, "updated": datetime.now().isoformat()}, f)
    except Exception:
        pass

    return chosen


def generate_weekly_intro(target_width, target_height, source_title=""):
    """Generate an animated intro card for weekly videos.

    Rotates between multiple animation styles each week for variety.
    Currently available styles:
      - cinematic: Deep blue, fading text, gold accents, movie name
      - split: Two-tone background, VARY/WEEKLY on each side, gold divider
      - minimal: Almost-black, scale-up VARY, understated underline

    Returns:
        Path to the generated intro MP4, or None on failure.
    """
    style = select_intro_style()
    print(f"  [editor] Weekly intro style: {style}", flush=True)

    style_map = {
        "cinematic": _generate_intro_cinematic,
        "split": _generate_intro_split,
        "minimal": _generate_intro_minimal,
    }

    func = style_map.get(style, _generate_intro_cinematic)
    return func(target_width, target_height, source_title)


def _extract_movie_name(source_title):
    """Extract the clean movie name from a YouTube video title."""
    name = source_title
    for prefix in ["Why ", "The Story of ", "Understanding ", "Analysis of ",
                    "The Genius of ", "How ", "What Makes ", "The Art of "]:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    for suffix in [" is a masterpiece", " is brilliant", " works", " changed cinema",
                    " — A Film Analysis", " explained"]:
        if suffix in name:
            name = name[:name.index(suffix)]
            break
    # Remove parenthetical notes and trailing punctuation
    for sep in ["(", "[", " - ", " — ", " | "]:
        if sep in name:
            name = name[:name.index(sep)]
    name = name.strip().strip(":;-,")
    return name[:40] if name else ""


def _generate_intro_cinematic(target_width, target_height, source_title=""):
    """Style 1: Cinematic — deep blue background, fading VARY text,
    gold WEEKLY subtitle, horizontal accent line, movie name at bottom.

    The original intro style. Classic, elegant, brand-forward.
    """
    import uuid
    intro_id = uuid.uuid4().hex[:8]
    intro_path = os.path.join(CLIPS_DIR, f"_intro_{intro_id}.mp4")
    font_path = get_font_path()
    d = WEEKLY_INTRO_DURATION

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0x0A0E28:s={target_width}x{target_height}:d={d}",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
        "-filter_complex", (
            "[0:v]format=yuv420p[base];"
            f"[base]drawbox=x='iw/2-100':y='ih/2-100':w=200:h=200:color=white@0.03:t=fill[base1];"
            f"[base1]drawbox=x='(iw-300)/2':y='ih/2-25':"
            f"w='if(gte(t,0.8),300,1)':h=2:color=gold@0.6:t=fill[base2];"
            f"[base2]drawtext=text='VARY':fontcolor=white:"
            f"alpha='if(lt(t,0.3),0,if(lt(t,1.0),(t-0.3)/0.7,1))':"
            f"fontsize=80:x=(w-text_w)/2:y=(h-text_h)/2-60:fontfile='{font_path}'[base3];"
            f"[base3]drawtext=text='WEEKLY':fontcolor=gold:"
            f"alpha='if(lt(t,1.2),0,if(lt(t,1.8),(t-1.2)/0.6,0.9))':"
            f"fontsize=44:x=(w-text_w)/2:y=(h+text_h)/2-40:fontfile='{font_path}'[base4];"
            f"[base4]"
        ) + (
            f"drawtext=text='{_extract_movie_name(source_title)}':fontcolor=white:"
            f"alpha='if(lt(t,2.0),0,if(lt(t,2.5),(t-2.0)/0.5,0.6))':"
            f"fontsize=28:x=(w-text_w)/2:y=h-80:fontfile='{font_path}'[vout]"
            if source_title else f"[vout]"
        ),
        "-map", "[vout]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "64k",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-profile:v", "high", "-level", "4.1",
        intro_path,
    ]

    print(f"  [editor] Generating cinematic intro...", flush=True)
    try:
        subprocess.run(cmd, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        print(f"  [editor] Intro generation timed out", flush=True)
        return None
    except Exception as e:
        print(f"  [editor] Intro generation error: {e}", flush=True)
        return None

    if os.path.exists(intro_path) and os.path.getsize(intro_path) > 5000:
        print(f"  [editor] Cinematic intro: {intro_path}", flush=True)
        return intro_path
    return None


def _generate_intro_split(target_width, target_height, source_title=""):
    """Style 2: Split Frame — two-tone background (navy + teal),
    VARY on the left in white, WEEKLY on the right in gold,
    with an animated vertical gold divider.
    """
    import uuid
    intro_id = uuid.uuid4().hex[:8]
    intro_path = os.path.join(CLIPS_DIR, f"_intro_{intro_id}.mp4")
    font_path = get_font_path()
    d = WEEKLY_INTRO_DURATION
    hw = target_width // 2

    cmd = [
        "ffmpeg", "-y",
        # Base: dark navy (left half)
        "-f", "lavfi", "-i", f"color=c=0x0A1628:s={target_width}x{target_height}:d={d}",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
        "-filter_complex", (
            "[0:v]format=yuv420p[base];"
            # Right half overlay (dark teal)
            f"[base]drawbox=x={hw}:y=0:w={hw}:h=ih:color=0x0F2A3F:t=fill[split_bg];"
            # Vertical divider line at center — draws from 0.2s to 0.7s
            f"[split_bg]drawbox=x={hw - 1}:y=0:"
            f"w=2:h='if(lt(t,0.2),1,if(lt(t,0.7),ih*(t-0.2)/0.5,ih))':color=gold@0.7:t=fill[center_line];"
            # VARY on the left side — fades in from 0.3s
            f"[center_line]drawtext=text='VARY':fontcolor=white:"
            f"alpha='if(lt(t,0.3),0,if(lt(t,0.8),(t-0.3)/0.5,1))':"
            f"fontsize=72:x=80:y=(h-text_h)/2:fontfile='{font_path}'[left_text];"
            # WEEKLY on the right side — fades in from 0.8s
            f"[left_text]drawtext=text='WEEKLY':fontcolor=gold:"
            f"alpha='if(lt(t,0.8),0,if(lt(t,1.3),(t-0.8)/0.5,0.9))':"
            f"fontsize=42:x={hw + 60}:y=(h-text_h)/2:fontfile='{font_path}'[right_text];"
            f"[right_text]"
        ) + (
            # Movie name at bottom center
            f"drawtext=text='{_extract_movie_name(source_title)}':fontcolor=white@0.55:"
            f"alpha='if(lt(t,1.8),0,if(lt(t,2.5),(t-1.8)/0.7,0.55))':"
            f"fontsize=24:x=(w-text_w)/2:y=h-60:fontfile='{font_path}'[vout]"
            if source_title else f"[vout]"
        ),
        "-map", "[vout]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "64k",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-profile:v", "high", "-level", "4.1",
        intro_path,
    ]

    print(f"  [editor] Generating split-frame intro...", flush=True)
    try:
        subprocess.run(cmd, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        print(f"  [editor] Split intro timed out", flush=True)
        return None
    except Exception as e:
        print(f"  [editor] Split intro error: {e}", flush=True)
        return None

    if os.path.exists(intro_path) and os.path.getsize(intro_path) > 5000:
        print(f"  [editor] Split intro: {intro_path}", flush=True)
        return intro_path
    return None


def _generate_intro_minimal(target_width, target_height, source_title=""):
    """Style 3: Minimal — almost-black background, scale-up VARY with
    underline animation, small WEEKLY text below. Clean and modern.
    """
    import uuid
    intro_id = uuid.uuid4().hex[:8]
    intro_path = os.path.join(CLIPS_DIR, f"_intro_{intro_id}.mp4")
    font_path = get_font_path()
    d = WEEKLY_INTRO_DURATION

    cmd = [
        "ffmpeg", "-y",
        # Base: very dark gray (almost black)
        "-f", "lavfi", "-i", f"color=c=0x080808:s={target_width}x{target_height}:d={d}",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
        "-filter_complex", (
            "[0:v]format=yuv420p[base];"
            # Subtle vignette via a large drawbox with low opacity
            f"[base]drawbox=x='(iw-400)/2':y='(ih-200)/2':w=400:h=200:color=white@0.02:t=fill[base1];"
            # "VARY" with scale-up effect (fontsize grows from 48 to 80) + fade in
            f"[base1]drawtext=text='VARY':fontcolor=white:"
            f"alpha='if(lt(t,0.2),0,if(lt(t,0.9),(t-0.2)/0.7,1))':"
            f"fontsize='if(lt(t,0.8),48+(t/0.8)*32,80)':"
            f"x=(w-text_w)/2:y=(h-text_h)/2-30:fontfile='{font_path}'[base2];"
            # Thin gold underline — draws from center from 0.6s to 1.3s
            f"[base2]drawbox=x='(iw-280)/2':y='ih/2+15':"
            f"w='if(lt(t,0.6),1,if(lt(t,1.3),280*(t-0.6)/0.7,280))'"
            f":h=2:color=gold@0.6:t=fill[base3];"
            # "WEEKLY" small caps — fades in from 1.4s
            f"[base3]drawtext=text='WEEKLY':fontcolor=gold:"
            f"alpha='if(lt(t,1.4),0,if(lt(t,2.0),(t-1.4)/0.6,0.8))':"
            f"fontsize=30:x=(w-text_w)/2:y='ih/2+40':fontfile='{font_path}'[vout]"
        ),
        "-map", "[vout]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "64k",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-profile:v", "high", "-level", "4.1",
        intro_path,
    ]

    print(f"  [editor] Generating minimal intro...", flush=True)
    try:
        subprocess.run(cmd, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        print(f"  [editor] Minimal intro timed out", flush=True)
        return None
    except Exception as e:
        print(f"  [editor] Minimal intro error: {e}", flush=True)
        return None

    if os.path.exists(intro_path) and os.path.getsize(intro_path) > 5000:
        print(f"  [editor] Minimal intro: {intro_path}", flush=True)
        return intro_path
    return None


def create_weekly_video(input_path, output_path, source_title="", voiceover_path=None):
    """Create a weekly landscape video with voiceover narration.

    Prepends an animated 3-second "VARY Weekly" intro card.
    Keeps the original landscape aspect ratio (no 9:16 crop).
    Mixes in a male voiceover track if provided, with text overlays as backup.

    Args:
        input_path: Path to downloaded source video
        output_path: Output path for the weekly video
        source_title: Title of the source video for context
        voiceover_path: Optional path to pre-recorded voiceover audio file

    Returns:
        Dict with path, duration on success, or None on failure
    """
    if not os.path.exists(input_path):
        print(f"  [weekly] Input not found: {input_path}", flush=True)
        return None

    video_duration = get_video_duration(input_path)
    if video_duration <= 0:
        video_duration = WEEKLY_MIN_DURATION

    # Use the full video if it's under max duration
    if video_duration > WEEKLY_MAX_DURATION:
        print(f"  [weekly] Video too long ({video_duration:.0f}s), truncating to {WEEKLY_MAX_DURATION}s", flush=True)
        video_duration = WEEKLY_MAX_DURATION

    # Get original dimensions (keep landscape)
    in_w, in_h = get_video_dimensions(input_path)

    # Get font path
    font_path = get_font_path()

    # Generate story text segments
    story_texts = _generate_story_texts(source_title)

    # Determine target dimensions enforcing minimum 720p
    target_width = min(in_w, 1920)
    if in_w > 0:
        # Scale by width first
        scale_factor = target_width / in_w
        target_height = int(in_h * scale_factor)
        # Enforce minimum 720p height — if scaling to 1920w gives <720h,
        # scale based on height instead to maintain quality
        if target_height < 720:
            target_height = 720
            target_width = int(in_w * (720 / in_h))
            # Clamp to original width and reasonable max
            target_width = min(target_width, in_w)
        # Ensure even dimensions (required by libx264)
        target_height = target_height if target_height % 2 == 0 else target_height + 1
        target_width = target_width if target_width % 2 == 0 else target_width + 1
    else:
        target_width, target_height = 1280, 720  # Minimum 720p fallback

    # ── Generate animated intro card ─────────────────────
    intro_path = generate_weekly_intro(target_width, target_height, source_title)
    has_intro = intro_path is not None

    # ── Process main video ───────────────────────────────
    # Base video filter: trim and scale (enforce min 720p)
    video_chain = (
        f"[0:v]trim=0:{video_duration},setpts=PTS-STARTPTS,"
        f"scale={target_width}:{target_height}:force_original_aspect_ratio=1,"
        f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
    )

    # Add timed text overlays using drawtext with enable=between(t,start,end)
    # Each text segment appears for WEEKLY_SEGMENT_DURATION seconds
    texts_added = 0
    for text, start_ratio in story_texts:
        text_start = video_duration * start_ratio
        text_end = min(text_start + WEEKLY_SEGMENT_DURATION, video_duration)

        if text_end <= text_start:
            continue

        # Escape special characters for ffmpeg
        safe_text = text.replace("'", "\\'").replace(":", "\\:").replace("[", "\\[").replace("]", "\\]")

        # Bottom-aligned text overlay with semi-transparent background box
        video_chain += (
            f",drawtext=text='{safe_text}':fontcolor=white:fontsize=38:"
            f"x=(w-text_w)/2:y=h-th-80:"
            f"box=1:boxcolor=black@0.55:boxborderw=14:"
            f"fontfile='{font_path}':"
            f"enable='between(t,{text_start},{text_end})'"
        )
        texts_added += 1

    print(f"  [weekly] Added {texts_added} story text overlays", flush=True)

    # Audio chain: trim to match video duration
    audio_chain = f"[0:a]atrim=0:{video_duration},asetpts=PTS-STARTPTS[a_src]"

    # Handle voiceover if provided
    has_voiceover = voiceover_path and os.path.exists(voiceover_path)
    if has_voiceover:
        input_files = ["-i", input_path, "-i", voiceover_path]
        # Voiceover at 100%, original audio ducked to 25%
        audio_chain += f";[2:a]volume=1.0[a_vo];[a_src]volume=0.25[a_src_d];[a_vo][a_src_d]amix=inputs=2:duration=first:weights=1 0.25[aout_raw]"
        audio_map_label = "[aout_raw]"
        print(f"  [weekly] Mixing voiceover: {voiceover_path}", flush=True)
    else:
        input_files = ["-i", input_path]
        audio_chain += f";[a_src]acopy[aout_raw]"
        audio_map_label = "[aout_raw]"

    # ── Concatenate intro + main video with smooth crossfade ──
    if has_intro:
        crossfade_dur = WEEKLY_INTRO_CROSSFADE
        xfade_offset = WEEKLY_INTRO_DURATION - crossfade_dur
        filter_complex = (
            f"{video_chain}[vmain];{audio_chain};"
            f"[1:v]format=yuv420p[intro_v];"
            f"[intro_v][vmain]xfade=transition=fade:"
            f"duration={crossfade_dur}:offset={xfade_offset}[vout];"
            f"[1:a][{audio_map_label}]acrossfade=d={crossfade_dur}[aout]"
        )
        input_files = ["-i", input_path, "-i", intro_path]
        if has_voiceover:
            input_files += [voiceover_path]
        audio_map = "[aout]"
    else:
        filter_complex = f"{video_chain}[vout];{audio_chain}"
        if not has_voiceover:
            input_files = ["-i", input_path]
        audio_map = audio_map_label

    # Build ffmpeg command
    cmd = [
        "ffmpeg", "-y",
    ] + input_files + [
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", audio_map,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "22",  # Slightly better quality for longer content
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        "-movflags", "+faststart",
        "-profile:v", "high",
        "-level", "4.1",
        output_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=600)
    except subprocess.TimeoutExpired:
        print(f"  [weekly] FFmpeg timed out (600s)", flush=True)
        return None
    except Exception as e:
        print(f"  [weekly] Error: {e}", flush=True)
        return None

    # Clean up the intro temp file
    if has_intro and os.path.exists(intro_path):
        try:
            os.remove(intro_path)
        except Exception:
            pass

    # Calculate final duration including intro minus crossfade overlap
    final_duration = video_duration + (WEEKLY_INTRO_DURATION - (WEEKLY_INTRO_CROSSFADE if has_intro else 0))

    if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
        actual_dur = get_video_duration(output_path)
        if actual_dur <= 0:
            actual_dur = fallback_duration(output_path)
        if actual_dur <= 0:
            actual_dur = final_duration
        print(f"  [weekly] Created weekly video: {output_path} ({actual_dur:.1f}s, {os.path.getsize(output_path)} bytes)", flush=True)
        return {
            "path": output_path,
            "duration": actual_dur,
        }

    print(f"  [weekly] Output invalid", flush=True)
    return None


if __name__ == "__main__":
    # Test
    if len(sys.argv) > 1:
        result = create_clip(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "movie")
        print(json.dumps(result, indent=2, default=str) if result else "Failed")
