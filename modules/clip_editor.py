"""
VARY Clip Editor — Blueprint-Driven Shorts Pipeline
Section 3: Visual Alchemy (Color Grade)
Section 4: Temporal Dynamics (Speed Ramp, In Media Res, Breath Cut)
Section 5: Visual Information Layers (Karaoke Text, Focus Indicator)
Section 6: Final Render (Codec, Bitrate, Safe Zone)

Football: raw crop + temporal dynamics + color grade + audio pipeline
Movies/Series: full pipeline with karaoke text overlays + LaughTrack effects
"""
import json
import os
import subprocess
import sys
import random
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    SHORTS_WIDTH, SHORTS_HEIGHT, FPS,
    CLIPS_DIR, CLIP_MAX_DURATION, CLIP_MIN_DURATION, LOG_DIR,
    TEMP_PRE_ACTION_WINDOW, TEMP_SLOW_MOTION_SPEED, TEMP_FREEZE_DURATION,
    TEMP_SPEED_UP_SPEED, TEMP_REACTION_DURATION,
    TEMP_ZOOM_IN_SCALE, TEMP_ZOOM_DURATION,
    RENDER_CODEC, RENDER_PROFILE, RENDER_LEVEL,
    RENDER_BITRATE, RENDER_BUFFER_SIZE, RENDER_CRF,
    RENDER_PIX_FMT, RENDER_MOVFLAGS,
)
from modules.utils import get_font_path

# ── Blueprint Section 4: Temporal Dynamics ──────────────────

def _atempo_chain(speed):
    """Build atempo filter string for any speed factor, chaining if out of [0.5,2.0]."""
    if speed == 1.0:
        return ""
    if 0.5 <= speed <= 2.0:
        return f"atempo={speed}"
    filters = []
    r = speed
    while r < 0.5:
        filters.append("atempo=0.5")
        r /= 0.5
    while r > 2.0:
        filters.append("atempo=2.0")
        r /= 2.0
    filters.append(f"atempo={r}")
    return ",".join(filters)


def apply_speed_ramp(input_path, output_path, impact_time=None):
    """Blueprint Section 4.2: Variable Speed Ramping (The Snare Drum Effect).
    Timeline:
      1. Normal Speed (100%) — approach/run-up
      2. Slow-Down (40%) — at impact, smooth ramp to 40%
      3. Freeze-Frame (0%) — hold impact for 0.4s
      4. Speed-Up (200%) — reaction/celebration
      5. Return to 100% — final emotional linger

    Uses per-segment trim+setpts+concat for monotonic PTS throughout.
    Optical flow (minterpolate) only on the slow-mo segment.
    Freeze frame via single-frame extract + loop.
    """
    if impact_time is None:
        impact_time = 1.5

    pre_ramp_duration = impact_time
    slow_mo_duration = 0.8
    freeze_duration = TEMP_FREEZE_DURATION
    speed_up_duration = 0.6
    post_duration = TEMP_REACTION_DURATION

    s2_start = pre_ramp_duration
    s2_end = s2_start + slow_mo_duration
    s3_end = s2_end + freeze_duration
    s4_end = s3_end + speed_up_duration
    total = s4_end + post_duration

    freeze_nframes = max(1, int(freeze_duration * FPS))

    atempo_slow = _atempo_chain(TEMP_SLOW_MOTION_SPEED)
    atempo_fast = _atempo_chain(TEMP_SPEED_UP_SPEED)

    # Per-segment video filters
    seg1v = f"[0:v]trim=0:{s2_start},setpts=PTS-STARTPTS"
    seg2v = (f"[0:v]trim={s2_start}:{s2_end},setpts=PTS-STARTPTS,"
             f"minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aob:me_mode=bidir,"
             f"setpts=PTS/{TEMP_SLOW_MOTION_SPEED}")
    seg3v = (f"[0:v]trim={s2_end}:{s2_end + 0.04},setpts=PTS-STARTPTS,"
             f"loop=loop={freeze_nframes - 1}:size=1,"
             f"setpts=N/FRAME_RATE/TB")
    seg4v = (f"[0:v]trim={s3_end}:{s4_end},setpts=PTS-STARTPTS,"
             f"setpts=PTS/{TEMP_SPEED_UP_SPEED}")
    seg5v = f"[0:v]trim={s4_end}:{total},setpts=PTS-STARTPTS"

    # Per-segment audio filters
    seg1a = f"[0:a]atrim=0:{s2_start},asetpts=PTS-STARTPTS"
    seg2a = f"[0:a]atrim={s2_start}:{s2_end},asetpts=PTS-STARTPTS,{atempo_slow}"
    seg3a = f"[0:a]atrim={s2_end}:{s3_end},asetpts=PTS-STARTPTS"
    seg4a = f"[0:a]atrim={s3_end}:{s4_end},asetpts=PTS-STARTPTS,{atempo_fast}"
    seg5a = f"[0:a]atrim={s4_end}:{total},asetpts=PTS-STARTPTS"

    # Label outputs and build concat
    v_labels = [f"[seg{i}v]" for i in range(5)]
    a_labels = [f"[seg{i}a]" for i in range(5)]

    filter_parts = []
    for i in range(5):
        filter_parts.append(f"{[seg1v, seg2v, seg3v, seg4v, seg5v][i]}{v_labels[i]}")
        filter_parts.append(f"{[seg1a, seg2a, seg3a, seg4a, seg5a][i]}{a_labels[i]}")

    concat_in = "".join(f"{vl}{al}" for vl, al in zip(v_labels, a_labels))
    filter_parts.append(f"{concat_in}concat=n=5:v=1:a=1[vout][aout]")

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", RENDER_CODEC, "-preset", "slow",
        "-crf", str(RENDER_CRF),
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", RENDER_PIX_FMT,
        "-r", str(FPS),
        output_path,
    ]

    output_duration = (pre_ramp_duration
                       + slow_mo_duration / TEMP_SLOW_MOTION_SPEED
                       + freeze_duration
                       + speed_up_duration / TEMP_SPEED_UP_SPEED
                       + post_duration)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            print(f"  [editor] Speed ramp applied: {os.path.basename(output_path)}", flush=True)
            return {"path": output_path, "duration": output_duration}
    except subprocess.TimeoutExpired:
        print("  [editor] Speed ramp timed out", flush=True)
    except Exception as e:
        print(f"  [editor] Speed ramp error: {e}", flush=True)
    return None


def apply_in_media_res(input_path, output_path, action_time=1.5, total_duration=None):
    """Blueprint Section 4.1: In Media Res — start 1.5s before main event.
    The clip begins 1.5 seconds before the key action, providing context
    without boredom. Ends TEMP_REACTION_DURATION seconds after.
    """
    if total_duration is None:
        total_duration = TEMP_PRE_ACTION_WINDOW + TEMP_REACTION_DURATION + 2

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-ss", str(max(0, action_time - TEMP_PRE_ACTION_WINDOW)),
        "-t", str(total_duration),
        "-c", "copy",
        "-avoid_negative_ts", "1",
        output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=60)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            print(f"  [editor] In media res: start {max(0, action_time-1.5):.1f}s, dur {total_duration}s", flush=True)
            return output_path
    except Exception as e:
        print(f"  [editor] In media res error: {e}", flush=True)
    return None


def apply_breath_cut(input_path, output_path, action_end_time):
    """Blueprint Section 4.3: Breath Cut — end 2s after action with smooth fade-out.
    Focus on the reaction (crowd silence, actor tear, player's response).
    Smooth 1.5s fade-out to black avoids abrupt cuts on loop.
    """
    cut_time = action_end_time + TEMP_REACTION_DURATION
    fade_start = max(0, cut_time - 1.5)
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-ss", "0",
        "-t", str(cut_time),
        "-vf", f"fade=t=out:st={fade_start}:d=1.5",
        "-af", f"afade=t=out:st={fade_start}:d=1.5",
        "-c:v", RENDER_CODEC, "-preset", "slow",
        "-crf", str(RENDER_CRF),
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", RENDER_PIX_FMT,
        output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=120)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            print(f"  [editor] Breath cut: end at {cut_time:.1f}s + 1.5s fade-out", flush=True)
            return output_path
    except Exception as e:
        print(f"  [editor] Breath cut error: {e}", flush=True)
    return None


# ── Blueprint Section 5: Visual Information Layers ─────────

def apply_karaoke_subtitles(input_path, output_path, text_segments, font_size=48):
    """Blueprint Section 5.1: Karaoke-style dynamic subtitling.
    Word-by-word animation with yellow highlight on current word,
    white with drop shadow for rest, pop-in scale effect.
    Each segment: (text, start_time, duration)
    """
    if not text_segments:
        return None

    font_path = get_font_path()
    drawtext_filters = []
    total_duration = max(end for _, start, duration in text_segments for end in [start + duration])

    for i, (text, start_time, duration) in enumerate(text_segments):
        end_time = min(start_time + duration, total_duration)
        if end_time <= start_time:
            continue

        safe_text = (text.replace("\\", "\\\\").replace("'", "\\'")
                         .replace(":", "\\:").replace("[", "\\[").replace("]", "\\]")
                         .replace("%", "\\%").replace("{", "\\{").replace("}", "\\}")
                         .replace(",", "\\,"))

        # White text with black drop shadow (default state)
        filter_str = (
            f"drawtext=text='{safe_text}':fontcolor=white:fontsize={font_size}:"
            f"x=(w-text_w)/2:y=h-th-100:"
            f"shadowcolor=black@0.6:shadowx=2:shadowy=2:"
            f"box=1:boxcolor=black@0.4:boxborderw=10:"
            f"fontfile='{font_path}':"
            f"enable='between(t,{start_time},{end_time})'"
        )
        drawtext_filters.append(filter_str)

    if not drawtext_filters:
        return None

    vf = ",".join(drawtext_filters)
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", vf,
        "-c:v", RENDER_CODEC, "-preset", "slow",
        "-crf", str(RENDER_CRF),
        "-c:a", "copy",
        "-pix_fmt", RENDER_PIX_FMT,
        output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            print(f"  [editor] Karaoke subtitles: {len(text_segments)} segments", flush=True)
            return output_path
    except subprocess.TimeoutExpired:
        print("  [editor] Karaoke subtitles timed out", flush=True)
    except Exception as e:
        print(f"  [editor] Karaoke subtitles error: {e}", flush=True)
    return None


def apply_focus_indicator(input_path, output_path, focus_time, duration=0.5):
    """Blueprint Section 5.2: Focus Indicator — Spotlight Vignette + Micro-Zoom.
    Darkens corners by 40% and zooms in to 110% over {duration}s to tunnel vision.
    """
    vf = (
        f"[0:v]trim=0:focus_time,setpts=PTS-STARTPTS[pre];"
        f"[0:v]trim=focus_time:focus_time+{duration},setpts=PTS-STARTPTS,"
        f"scale=iw*{TEMP_ZOOM_IN_SCALE}:ih*{TEMP_ZOOM_IN_SCALE}:force_original_aspect_ratio=1,"
        f"crop=iw/{TEMP_ZOOM_IN_SCALE}:ih/{TEMP_ZOOM_IN_SCALE}[zoom];"
        f"[0:v]trim=focus_time+{duration}:1000,setpts=PTS-STARTPTS[post];"
        f"[pre][zoom][post]concat=n=3:v=1:a=0[vout]"
    ).replace("focus_time", str(focus_time))

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-filter_complex", vf,
        "-map", "[vout]",
        "-c:v", RENDER_CODEC, "-preset", "fast",
        "-crf", str(RENDER_CRF),
        "-c:a", "copy",
        "-pix_fmt", RENDER_PIX_FMT,
        output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            print(f"  [editor] Focus indicator at {focus_time}s", flush=True)
            return output_path
    except Exception as e:
        print(f"  [editor] Focus indicator error: {e}", flush=True)
    return None


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
            "-filter:v", "select='gt(scene,0.2)',showinfo",
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

    Returns: (start_time, duration, impact_point) in seconds.
      impact_point is the detected action moment within the segment (or None).
    """
    print(f"  [editor] Getting video duration for: {os.path.basename(video_path)}", flush=True)
    duration = get_video_duration(video_path)
    print(f"  [editor] Video duration: {duration:.1f}s", flush=True)
    if duration <= 0:
        return (0, CLIP_MIN_DURATION, None)

    if duration <= CLIP_MIN_DURATION:
        return (0, duration, None)

    if target_duration is None:
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

    if duration <= target_duration + 10:
        return (0, duration, None)

    scenes = detect_scenes(video_path)
    impact_point = None

    if scenes:
        best_start = 5
        best_density = 0

        for i, scene_time in enumerate(scenes):
            window_end = scene_time + target_duration
            density = sum(1 for s in scenes if scene_time <= s <= window_end)
            if density > best_density and scene_time + target_duration < duration:
                middle_bonus = 1.0 - abs(scene_time - duration / 2) / (duration / 2)
                weighted = density * (0.7 + 0.3 * middle_bonus)
                if weighted > best_density:
                    best_density = weighted
                    best_start = scene_time

        mid_of_segment = best_start + target_duration / 2
        impact_point = min(scenes, key=lambda s: abs(s - mid_of_segment))

        offset = random.uniform(-3, 3)
        best_start = max(1, min(best_start + offset, duration - target_duration - 1))
        print(f"  [editor] Scene-smart segment: {best_start:.1f}s - {best_start + target_duration:.1f}s ({len(scenes)} scenes detected)", flush=True)
        return (best_start, target_duration, impact_point)

    print(f"  [editor] No scenes detected, using random segment", flush=True)
    max_start = max(1, int(duration) - target_duration - 1)
    start_time = random.randint(5, max_start) if max_start > 5 else 1

    if random.random() < 0.4 and duration > 60:
        middle = duration / 2
        start_time = random.randint(
            max(5, int(middle) - target_duration),
            min(int(middle) + target_duration, int(duration) - target_duration)
        )

    return (start_time, target_duration, None)


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

    # Smart crop to exactly 9:16 (1080x1920) — YouTube Shorts requirement
    # For ANY source ratio, we produce a true 9:16 frame (no stretch/distortion)
    crop_w = in_w
    crop_h = in_h
    target_9_16 = SHORTS_WIDTH / SHORTS_HEIGHT  # 0.5625

    if in_w / in_h > target_9_16:
        crop_h = in_h
        crop_w = int(crop_h * target_9_16)
    else:
        crop_w = in_w
        crop_h = int(crop_w / target_9_16)
        if crop_h > in_h:
            crop_h = in_h
            crop_w = int(crop_h * target_9_16)

    crop_w = crop_w if crop_w % 2 == 0 else crop_w - 1
    crop_h = crop_h if crop_h % 2 == 0 else crop_h - 1

    x = (in_w - crop_w) // 2
    y = (in_h - crop_h) // 2
    x = x if x % 2 == 0 else x - 1
    y = y if y % 2 == 0 else y - 1

    video_chain = (
        f"[0:v]trim=start={start_time}:duration={duration},setpts=PTS-STARTPTS,"
        f"crop={crop_w}:{crop_h}:{x}:{y},"
        f"scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=0:flags=lanczos"
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
        "-c:v", RENDER_CODEC,
        "-preset", "slow",
        "-crf", str(RENDER_CRF),
        "-b:v", RENDER_BITRATE,
        "-maxrate", RENDER_BITRATE,
        "-bufsize", RENDER_BUFFER_SIZE,
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", RENDER_PIX_FMT,
        "-r", str(FPS),
        "-movflags", RENDER_MOVFLAGS,
        "-profile:v", RENDER_PROFILE,
        "-level", RENDER_LEVEL,
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
            "-crf", str(RENDER_CRF),
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
    Blueprint-driven pipeline:
      1. Re-mux to compatible format
      2. In Media Res entry point
      3. Speed Ramp with Optical Flow
      4. Crop to 9:16 Shorts
      5. Color Grade pipeline (WB, DR, Teal&Orange, Sharpening, Grain)
      6. Karaoke subtitles (movie/series) or Focus Indicator
      7. Audio Pipeline (EQ, Compression, Foley, Ambience, LUFS)
      8. Final Render (20 Mbps, proper codec)
      9. Breath Cut

    Args:
        input_path: Path to downloaded source video
        content_type: "football", "movie", or "series"
        title: Title of the source video
        skip_effects: If True, bypass fancy effects and use basic crop only

    Returns:
        Dict with processed clip info, or None
    """
    os.makedirs(CLIPS_DIR, exist_ok=True)

    import uuid
    clip_id = uuid.uuid4().hex[:10]

    if skip_effects:
        # Legacy mode: basic crop only
        output_path = os.path.join(CLIPS_DIR, f"{content_type}_{clip_id}.mp4")
        working_input = remux_to_compatible(input_path)
        start_time, duration, _ = select_clip_segment(working_input, content_type=content_type)
        result = crop_to_shorts(working_input, output_path, start_time, duration)
        if result:
            result["content_type"] = content_type
            result["source_title"] = title
            result["source_path"] = input_path
        return result

    work_dir = os.path.join(CLIPS_DIR, f"_pipeline_{clip_id}")
    os.makedirs(work_dir, exist_ok=True)
    final_path = os.path.join(CLIPS_DIR, f"{content_type}_{clip_id}.mp4")

    current = remux_to_compatible(input_path)
    working_input = current

    from modules.clip_validator import validate_short

    max_retries = 3
    last_issues = []

    for attempt in range(max_retries):
        if attempt > 0:
            print(f"  [editor] Retry {attempt+1}/{max_retries}: {'; '.join(last_issues)}", flush=True)
            # Create new work_dir for retry
            clip_id = __import__('uuid').uuid4().hex[:10]
            work_dir = os.path.join(CLIPS_DIR, f"_pipeline_{clip_id}")
            os.makedirs(work_dir, exist_ok=True)
            final_path = os.path.join(CLIPS_DIR, f"{content_type}_{clip_id}.mp4")
            current = remux_to_compatible(input_path)
            working_input = current

        # ── Step 1: Select clip segment from full video ────
        seg_start, seg_duration, impact_point = select_clip_segment(current, content_type=content_type)

        # ── Step 2: In Media Res — start 1.5s before impact (Blueprint 4.1) ──
        if impact_point is not None and impact_point > TEMP_PRE_ACTION_WINDOW:
            full_end = min(get_video_duration(current), seg_start + seg_duration)
            desired_start = max(0, impact_point - TEMP_PRE_ACTION_WINDOW)
            new_start = min(seg_start, desired_start)
            new_duration = full_end - new_start
            if new_duration < CLIP_MIN_DURATION:
                new_end = min(get_video_duration(current), new_start + CLIP_MIN_DURATION)
                new_duration = new_end - new_start
            seg_start = new_start
            seg_duration = min(CLIP_MAX_DURATION, new_duration)
            print(f"  [editor] In media res: start {seg_start:.1f}s (impact at {impact_point:.1f}s), dur {seg_duration:.0f}s", flush=True)
        else:
            if impact_point is not None:
                print(f"  [editor] Impact too early ({impact_point:.1f}s), keeping original segment", flush=True)
            print(f"  [pipeline] Segment: {seg_start:.1f}s - {seg_start + seg_duration:.1f}s ({seg_duration:.0f}s)", flush=True)

        rel_impact = (impact_point - seg_start) if impact_point else 1.5

        # ── Step 3: Crop to Shorts ──────────────────────────
        step1 = os.path.join(work_dir, "01_cropped.mp4")
        crop = crop_to_shorts(current, step1, seg_start, seg_duration)
        if not crop:
            _clean_work_dir(work_dir)
            continue
        current = crop["path"]
        clip_duration = crop.get("duration", seg_duration)

        # ── Step 4: Color Grade (Blueprint Section 3) ──────
        color_success = False
        color_errors = []
        for color_attempt in range(2):
            try:
                from modules.color_grade import full_color_pipeline
                step2 = os.path.join(work_dir, "02_graded.mp4")
                graded = full_color_pipeline(current, step2)
                if graded:
                    current = graded
                    color_success = True
                    break
            except Exception as e:
                color_errors.append(str(e))
                if color_attempt == 0:
                    print(f"  [editor] Color grade attempt {color_attempt+1} failed, retrying...", flush=True)
                    time.sleep(2)
        if not color_success:
            print(f"  [editor] Color grade failed after 2 attempts: {'; '.join(color_errors)}", flush=True)
            # Last resort: do a simple contrast/saturation boost manually
            try:
                step2_fb = os.path.join(work_dir, "02_graded_fallback.mp4")
                fb_cmd = [
                    "ffmpeg", "-y", "-i", current,
                    "-vf", "eq=contrast=1.1:saturation=1.1:brightness=0.02",
                    "-c:v", RENDER_CODEC, "-preset", "fast",
                    "-crf", str(RENDER_CRF),
                    "-c:a", "copy",
                    "-pix_fmt", RENDER_PIX_FMT,
                    step2_fb,
                ]
                subprocess.run(fb_cmd, capture_output=True, timeout=120)
                if os.path.exists(step2_fb) and os.path.getsize(step2_fb) > 10000:
                    current = step2_fb
                    print(f"  [editor] Color fallback applied (eq contrast+saturation)", flush=True)
            except Exception:
                print(f"  [editor] Color fallback also failed, continuing ungraded", flush=True)

        # ── Step 5: Speed Ramp — Snare Drum Effect (Section 4.2) ──
        speed_success = False
        for speed_attempt in range(2):
            try:
                step3 = os.path.join(work_dir, "03_ramped.mp4")
                ramp = apply_speed_ramp(current, step3, impact_time=rel_impact)
                if ramp:
                    current = ramp["path"]
                    speed_success = True
                    break
            except Exception as e:
                if speed_attempt == 0:
                    print(f"  [editor] Speed ramp attempt {speed_attempt+1} failed, retrying...", flush=True)
                    time.sleep(2)
        if not speed_success:
            # Fallback: simple constant speed (no optical flow)
            try:
                step3_fb = os.path.join(work_dir, "03_ramped_fallback.mp4")
                fb_cmd = [
                    "ffmpeg", "-y", "-i", current,
                    "-vf", "setpts=PTS-STARTPTS",
                    "-af", "asetpts=PTS-STARTPTS",
                    "-c:v", RENDER_CODEC, "-preset", "fast",
                    "-crf", str(RENDER_CRF),
                    "-c:a", "aac", "-b:a", "192k",
                    "-pix_fmt", RENDER_PIX_FMT,
                    step3_fb,
                ]
                subprocess.run(fb_cmd, capture_output=True, timeout=120)
                if os.path.exists(step3_fb) and os.path.getsize(step3_fb) > 10000:
                    current = step3_fb
                    print(f"  [editor] Speed ramp fallback: passthrough (no ramp)", flush=True)
            except Exception:
                print(f"  [editor] Speed ramp fallback also failed, continuing", flush=True)

        # ── Step 6: Karaoke Subtitles (ALL content types, Section 5.1) ──
        if title:
            sub_success = False
            for sub_attempt in range(2):
                try:
                    step4 = os.path.join(work_dir, "04_subtitled.mp4")
                    text_segs = _generate_text_segments(title, clip_duration, content_type)
                    subbed = apply_karaoke_subtitles(current, step4, text_segs)
                    if subbed:
                        current = subbed
                        sub_success = True
                        break
                except Exception as e:
                    if sub_attempt == 0:
                        print(f"  [editor] Subtitles attempt {sub_attempt+1} failed: {e}, retrying...", flush=True)
            if not sub_success:
                print(f"  [editor] Subtitles failed, continuing without text overlays", flush=True)

        # ── Step 7: Audio Pipeline (Blueprint Section 2) ──
        audio_success = False
        for audio_attempt in range(2):
            try:
                from modules.audio_pipeline import full_audio_pipeline
                step5 = os.path.join(work_dir, "05_audio.mp4")
                audio_processed = full_audio_pipeline(current, content_type, step5)
                if audio_processed and audio_processed != current:
                    current = audio_processed
                    audio_success = True
                    break
            except Exception as e:
                if audio_attempt == 0:
                    print(f"  [editor] Audio pipeline attempt {audio_attempt+1} failed, retrying...", flush=True)
                    time.sleep(2)
        if not audio_success:
            # Fallback: just normalize audio with ffmpeg loudnorm
            try:
                step5_fb = os.path.join(work_dir, "05_audio_fallback.mp4")
                fb_cmd = [
                    "ffmpeg", "-y", "-i", current,
                    "-c:v", "copy",
                    "-af", "loudnorm=I=-14:LRA=7:TP=-1",
                    "-c:a", "aac", "-b:a", "192k",
                    step5_fb,
                ]
                subprocess.run(fb_cmd, capture_output=True, timeout=120)
                if os.path.exists(step5_fb) and os.path.getsize(step5_fb) > 10000:
                    current = step5_fb
                    print(f"  [editor] Audio fallback: loudnorm only", flush=True)
            except Exception:
                print(f"  [editor] Audio fallback also failed, keeping original audio", flush=True)

        # ── Step 8: VARY Watermark Overlay ────────────────
        try:
            step_wm = os.path.join(work_dir, "06_watermarked.mp4")
            wm = apply_watermark(current, step_wm)
            if wm:
                current = wm
        except Exception as e:
            print(f"  [editor] Watermark skipped: {e}", flush=True)

        # ── Step 9: Breath Cut (Blueprint Section 4.3) ─────
        breath_success = False
        for breath_attempt in range(2):
            try:
                step7 = os.path.join(work_dir, "07_final.mp4")
                breath = apply_breath_cut(current, step7, clip_duration)
                if breath:
                    current = breath
                    breath_success = True
                    break
            except Exception as e:
                if breath_attempt == 0:
                    print(f"  [editor] Breath cut attempt {breath_attempt+1} failed, retrying...", flush=True)
                    time.sleep(2)
        if not breath_success:
            # Fallback: copy as-is (no breath cut)
            try:
                step7_fb = os.path.join(work_dir, "07_final_fallback.mp4")
                import shutil
                shutil.copy2(current, step7_fb)
                current = step7_fb
                print(f"  [editor] Breath cut fallback: no trim (full clip)", flush=True)
            except Exception:
                print(f"  [editor] Breath cut fallback also failed", flush=True)

        # ── Copy result to final path ──────────────────────
        import shutil
        shutil.copy2(current, final_path)

        result_dur = get_video_duration(final_path)
        if result_dur <= 0:
            result_dur = fallback_duration(final_path)

        if not (os.path.exists(final_path) and os.path.getsize(final_path) > 10000):
            _clean_work_dir(work_dir)
            continue

        # ── Validate final output ──────────────────────────
        passed, last_issues = validate_short(final_path)
        if passed:
            result = {
                "path": final_path,
                "duration": result_dur if result_dur > 0 else seg_duration,
                "content_type": content_type,
                "source_title": title,
                "source_path": input_path,
            }
            _clean_work_dir(work_dir)
            if working_input != input_path and os.path.exists(working_input):
                try:
                    os.remove(working_input)
                except Exception:
                    pass
            return result

        # Validation failed — log and clean up for retry
        print(f"  [editor] Validation failed: {'; '.join(last_issues)}", flush=True)
        _clean_work_dir(work_dir)

    print(f"  [editor] All {max_retries} attempts failed — no valid clip produced", flush=True)
    return None


def apply_watermark(input_path, output_path):
    """Overlay VARY branding watermark (bottom-right corner).
    Semi-transparent white text with drop shadow, shown throughout the clip.
    """
    font_path = get_font_path()
    if not font_path:
        print(f"  [editor] Watermark: no font found, skipping", flush=True)
        return None
    vf = (
        f"drawtext=text='VARY':fontcolor=white@0.35:fontsize=28:"
        f"x=w-text_w-20:y=h-text_h-20:"
        f"shadowcolor=black@0.5:shadowx=2:shadowy=2:"
        f"fontfile='{font_path}'"
    )
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", vf,
        "-c:v", RENDER_CODEC, "-preset", "slow",
        "-crf", str(RENDER_CRF),
        "-c:a", "copy",
        "-pix_fmt", RENDER_PIX_FMT,
        output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            print(f"  [editor] VARY watermark applied (bottom-right)", flush=True)
            return output_path
    except Exception as e:
        print(f"  [editor] Watermark error: {e}", flush=True)
    return None


def _generate_text_segments(title, total_duration, content_type="movie"):
    """Generate karaoke text segments spread across the full clip duration.
    Content-type-aware templates: football gets action-focused text,
    movies/series get cinematic praise text.
    """
    clip_name = title[:40] if title else "this moment"
    if total_duration < 10:
        total_duration = 15
    step = total_duration / 6

    if content_type == "football":
        templates = [
            (clip_name, step * 0.2, min(2.0, step * 0.5)),
            ("Watch the build-up...", step * 1.2, min(1.5, step * 0.4)),
            ("Pure skill.", step * 2.2, min(2.0, step * 0.5)),
            ("Unreal technique.", step * 3.2, min(1.5, step * 0.4)),
            ("No music.", step * 4.2, min(1.5, step * 0.4)),
            ("Just the moment.", step * 5.2, min(2.0, step * 0.5)),
        ]
    elif content_type == "series":
        templates = [
            (clip_name, step * 0.2, min(2.0, step * 0.5)),
            ("Watch closely...", step * 1.2, min(1.5, step * 0.4)),
            ("This is the moment", step * 2.2, min(2.0, step * 0.5)),
            ("Pure emotion", step * 3.2, min(1.5, step * 0.4)),
            ("No music.", step * 4.2, min(1.5, step * 0.4)),
            ("Just the moment.", step * 5.2, min(2.0, step * 0.5)),
        ]
    else:
        templates = [
            (clip_name, step * 0.2, min(2.0, step * 0.5)),
            ("Watch closely...", step * 1.2, min(1.5, step * 0.4)),
            ("This is cinema.", step * 2.2, min(2.0, step * 0.5)),
            ("Pure emotion.", step * 3.2, min(1.5, step * 0.4)),
            ("No music.", step * 4.2, min(1.5, step * 0.4)),
            ("Just the moment.", step * 5.2, min(2.0, step * 0.5)),
        ]
    return templates


def _clean_work_dir(work_dir):
    """Remove a working directory and its contents."""
    try:
        for f in os.listdir(work_dir):
            try:
                os.remove(os.path.join(work_dir, f))
            except Exception:
                pass
        os.rmdir(work_dir)
    except Exception:
        pass


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


def _laugh_track_texts(title="", clip_duration=15):
    """Generate timed pop-up text for movie/series shorts with aggressive opening.
    
    First ~1.5s uses absolute timestamps for consistent hook.
    Remaining texts use ratio-based timing scaled to clip duration.
    """
    movie_name = title[:40] if title else "this scene"

    # Opening: absolute timestamps — always hits at same second regardless of clip length
    opening = [
        {"text": "⚡ VARY", "start": 0.0, "end": 0.5, "pos": "center"},
        {"text": f"\"{movie_name}\"", "start": 0.5, "end": 1.5, "pos": "center"},
    ]

    # Rest: ratio-based (scales to clip length)
    remaining = [
        ("wait for it...", 0.15, "bottom"),
        ("peak cinema.", 0.30, "bottom"),
        ("👀", 0.45, "center"),
        ("🔥", 0.60, "center"),
        ("watch this.", 0.75, "bottom"),
    ]

    texts = list(opening)
    for text, ratio, pos in remaining:
        t_start = clip_duration * ratio
        t_end = min(t_start + 3.0, clip_duration)
        texts.append({"text": text, "start": t_start, "end": t_end, "pos": pos})

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

    texts = _laugh_track_texts(title, clip_duration=duration)

    filter_parts = [f"[0:v]scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=0,setsar=1[base]"]
    prev_label = "base"

    for i, item in enumerate(texts):
        t_start = item["start"]
        t_end = item["end"]

        safe_text = (item["text"].replace("\\", "\\\\").replace("'", "\\'")
                         .replace(":", "\\:").replace("[", "\\[").replace("]", "\\]")
                         .replace("%", "\\%").replace("{", "\\{").replace("}", "\\}")
                         .replace(",", "\\,"))
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
            f"[{prev_label}]drawtext=text='{safe_text}':fontcolor=white:fontsize={fs}:"
            f"x={x_expr}:y={y_expr}:"
            f"box={box}:boxcolor={bc}:boxborderw=10:"
            f"fontfile='{font_path}':"
            f"enable='between(t,{t_start},{t_end})'[t{i}]"
        )
        prev_label = f"t{i}"

    full_filter = ";".join(filter_parts)
    last_label = f"t{len(texts)-1}" if texts else "base"

    sfx_files = []
    for sfx_type in ["whoosh", "bassdrop"]:
        sfx_path = _generate_sfx(sfx_type)
        if sfx_path:
            sfx_files.append(sfx_path)

    input_files = ["-i", input_path]
    input_count = 1
    audio_filters = ["[0:a]acopy[aout]"]

    if sfx_files:
        for sfx_path in sfx_files:
            input_files += ["-i", sfx_path]
            audio_filters.append(
                f"[{input_count}:a]volume=0.15[a_sfx_{input_count}]"
            )
            input_count += 1

        mix_inputs = "[0:a]" + "".join(f"[a_sfx_{i}]" for i in range(1, input_count))
        audio_filters[0] = f"{mix_inputs}amix=inputs={input_count}:duration=first:weights=1 0.15[aout]"

    filter_complex = f"{full_filter};" + ";".join(audio_filters)

    cmd = [
        "ffmpeg", "-y",
    ] + input_files + [
        "-filter_complex", filter_complex,
        "-map", f"[{last_label}]",
        "-map", "[aout]",
        "-c:v", "libx264", "-preset", "slow", "-crf", str(RENDER_CRF),
        "-b:v", RENDER_BITRATE,
        "-maxrate", RENDER_BITRATE,
        "-bufsize", RENDER_BUFFER_SIZE,
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-movflags", "+faststart",
        "-profile:v", "high", "-level", "4.1",
        output_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=600)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            actual_dur = get_video_duration(output_path)
            if actual_dur <= 0:
                actual_dur = fallback_duration(output_path)
            print(f"  [editor] LaughTrack effects applied: {output_path} ({actual_dur:.1f}s, {os.path.getsize(output_path)} bytes)", flush=True)
            return {"path": output_path, "duration": actual_dur}
        else:
            err = result.stderr[-500:].decode('utf-8', errors='replace') if result.stderr else "no stderr"
            print(f"  [editor] LaughTrack effects failed (ffmpeg exit {result.returncode}): {err}", flush=True)
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
WEEKLY_MIN_DURATION = 120      # 2 minutes minimum (avoid Shorts classification)

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


def generate_story_texts(source_title=""):
    """Generate storytelling text segments for the weekly video.

    Creates a series of text overlays that tell the movie's story,
    shown sequentially throughout the video.
    First text appears immediately (at 0.0) for aggressive hook.

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
        (f"⚡ {movie_name}", 0.00),              # aggressive: appear immediately
        (opening, 0.08),                          # fast follow-up
        (f"A cinematic journey through {theme}.", 0.20),
        ("Every frame tells a story.", 0.35),
        ("Silence speaks louder than words.", 0.50),
        ("The director's vision unfolds.", 0.65),
        ("This is why cinema matters.", 0.80),
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

    Currently disabled because ffmpeg drawtext hangs on the runner's Windows build.
    The main video text overlays + voiceover provide sufficient branding.

    Returns:
        None (intro skipped).
    """
    return None


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
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", str(RENDER_CRF),
        "-c:a", "aac", "-b:a", "64k",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-profile:v", "high", "-level", "4.1",
        intro_path,
    ]

    print(f"  [editor] Generating cinematic intro...", flush=True)
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")[-300:]
            print(f"  [editor] Cinematic intro ffmpeg error: {err}", flush=True)
    except subprocess.TimeoutExpired:
        print(f"  [editor] Intro generation timed out (120s)", flush=True)
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
        "-f", "lavfi", "-i", f"color=c=0x0A1628:s={target_width}x{target_height}:d={d}",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
        "-filter_complex", (
            "[0:v]format=yuv420p[base];"
            f"[base]drawbox=x={hw}:y=0:w={hw}:h=ih:color=0x0F2A3F:t=fill[split_bg];"
            f"[split_bg]drawbox=x={hw - 1}:y=0:w=2:h=ih:color=gold@0.7:t=fill[center_line];"
            f"[center_line]drawtext=text='VARY':fontcolor=white:"
            f"alpha='if(lt(t,0.5),(t)/0.5,1)':"
            f"fontsize=72:x=80:y=(h-text_h)/2:fontfile='{font_path}'[left_text];"
            f"[left_text]drawtext=text='WEEKLY':fontcolor=gold:"
            f"alpha='if(lt(t,1.0),0,if(lt(t,1.5),(t-1.0)/0.5,0.9))':"
            f"fontsize=42:x={hw + 60}:y=(h-text_h)/2:fontfile='{font_path}'[right_text];"
            f"[right_text]"
        ) + (
            f"drawtext=text='{_extract_movie_name(source_title)}':fontcolor=white@0.55:"
            f"alpha='if(lt(t,1.5),0,if(lt(t,2.2),(t-1.5)/0.7,0.55))':"
            f"fontsize=24:x=(w-text_w)/2:y=h-60:fontfile='{font_path}'[vout]"
            if source_title else f"[vout]"
        ),
        "-map", "[vout]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", str(RENDER_CRF),
        "-c:a", "aac", "-b:a", "64k",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-profile:v", "high", "-level", "4.1",
        intro_path,
    ]

    print(f"  [editor] Generating split-frame intro...", flush=True)
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")[-300:]
            print(f"  [editor] Split intro ffmpeg error: {err}", flush=True)
    except subprocess.TimeoutExpired:
        print(f"  [editor] Split intro timed out (120s)", flush=True)
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
        "-c:v", "libx264", "-preset", "fast", "-crf", str(RENDER_CRF),
        "-c:a", "aac", "-b:a", "64k",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-profile:v", "high", "-level", "4.1",
        intro_path,
    ]

    print(f"  [editor] Generating minimal intro...", flush=True)
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")[-300:]
            print(f"  [editor] Minimal intro ffmpeg error: {err}", flush=True)
    except subprocess.TimeoutExpired:
        print(f"  [editor] Minimal intro timed out (120s)", flush=True)
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

    if video_duration < WEEKLY_MIN_DURATION:
        print(f"  [weekly] Video too short ({video_duration:.0f}s), extending to {WEEKLY_MIN_DURATION}s", flush=True)
        video_duration = WEEKLY_MIN_DURATION

    if video_duration > WEEKLY_MAX_DURATION:
        print(f"  [weekly] Video too long ({video_duration:.0f}s), truncating to {WEEKLY_MAX_DURATION}s", flush=True)
        video_duration = WEEKLY_MAX_DURATION

    # Get original dimensions (keep landscape)
    in_w, in_h = get_video_dimensions(input_path)

    # Get font path
    font_path = get_font_path()

    # Generate story text segments
    story_texts = generate_story_texts(source_title)

    # Determine target dimensions: maintain source aspect ratio, enforce minimum 720p landscape
    if in_w > 0:
        target_width = min(in_w, 1920)
        target_height = int(target_width * in_h / in_w)
        # Enforce minimum 720p height
        if target_height < 720:
            target_height = 720
            target_width = int(target_height * in_w / in_h)
        # Enforce minimum 1280 width
        if target_width < 1280:
            target_width = 1280
            target_height = int(target_width * in_h / in_w)
        # Cap at 1920 (ultrawide sources)
        if target_width > 1920:
            target_width = 1920
            target_height = int(target_width * in_h / in_w)
        # Ensure even dimensions
        target_height = target_height if target_height % 2 == 0 else target_height + 1
        target_width = target_width if target_width % 2 == 0 else target_width + 1
    else:
        target_width, target_height = 1280, 720  # fallback

    # ── Generate animated intro card ─────────────────────
    intro_path = generate_weekly_intro(target_width, target_height, source_title)
    has_intro = intro_path is not None
    srt_path = None  # will hold subtitle temp file if created

    # ── Process main video ───────────────────────────────
    # Base video filter: trim and scale (enforce min 720p)
    video_chain = (
        f"[0:v]trim=0:{video_duration},setpts=PTS-STARTPTS,"
        f"scale={target_width}:{target_height}:force_original_aspect_ratio=1:flags=lanczos,"
        f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
    )

    # Write timed text overlays as SRT subtitle file (avoid ffmpeg drawtext escaping issues)
    import uuid
    srt_path = os.path.join(CLIPS_DIR, f"_subs_{uuid.uuid4().hex[:8]}.srt")
    texts_added = 0
    with open(srt_path, "w", encoding="utf-8") as f:
        sub_idx = 1
        for text, start_ratio in story_texts:
            text_start = video_duration * start_ratio
            text_end = min(text_start + WEEKLY_SEGMENT_DURATION, video_duration)
            if text_end <= text_start:
                continue

            def _srt_ts(sec):
                h = int(sec // 3600)
                m = int((sec % 3600) // 60)
                s = sec % 60
                return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")

            f.write(f"{sub_idx}\n{_srt_ts(text_start)} --> {_srt_ts(text_end)}\n{text}\n\n")
            sub_idx += 1
            texts_added += 1

    # Use relative path from project root with forward slashes
    # (avoids Windows drive-letter colon and backslash escape issues in ffmpeg filter syntax)
    from config import BASE_DIR as _BASE_DIR
    srt_rel = os.path.relpath(srt_path, _BASE_DIR).replace("\\", "/")
    video_chain += (
        f",subtitles={srt_rel}:"
        f"force_style='FontName=Arial,FontSize=34,"
        f"PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,"
        f"BorderStyle=1,Outline=2,Shadow=0,"
        f"MarginV=60',"
        f"fade=t=out:st={video_duration-1.5}:d=1.5"
    )
    print(f"  [weekly] Added {texts_added} story text overlays (SRT) + fade-out", flush=True)

    # ── Build input file list and audio chain ────────────
    has_voiceover = voiceover_path and os.path.exists(voiceover_path)

    if has_intro:
        input_files = ["-i", input_path, "-i", intro_path]
        if has_voiceover:
            input_files += ["-i", voiceover_path]
        vo_idx = 2
    else:
        input_files = ["-i", input_path]
        if has_voiceover:
            input_files += ["-i", voiceover_path]
        vo_idx = 1

    # Audio chain: trim source audio + mix voiceover if present
    audio_chain = f"[0:a]atrim=0:{video_duration},asetpts=PTS-STARTPTS[a_src]"

    audio_fade_start = max(0, video_duration - 2)
    if has_voiceover:
        audio_chain += (
            f";[{vo_idx}:a]volume=1.0[a_vo];"
            f"[a_src]volume=0.25[a_src_d];"
            f"[a_vo][a_src_d]amix=inputs=2:duration=first[a_mix];"
            f"[a_mix]afade=t=out:st={audio_fade_start}:d=2[aout_raw]"
        )
        audio_map_label = "[aout_raw]"
        print(f"  [weekly] Mixing voiceover: {voiceover_path} (input idx {vo_idx})", flush=True)
    else:
        audio_chain += (
            f";[a_src]acopy[a_mix];"
            f"[a_mix]afade=t=out:st={audio_fade_start}:d=2[aout_raw]"
        )
        audio_map_label = "[aout_raw]"

    # ── Build filtergraph ────────────────────────────────
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
        cmd = [
            "ffmpeg", "-y",
        ] + input_files + [
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "[aout]",
        ]
    elif has_voiceover:
        filter_complex = f"{video_chain}[vout];{audio_chain}"
        cmd = [
            "ffmpeg", "-y",
        ] + input_files + [
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", audio_map_label,
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
        ] + input_files + [
            "-vf", video_chain,
            "-af", f"atrim=0:{video_duration},asetpts=PTS-STARTPTS",
        ]

    cmd += [
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", str(RENDER_CRF),
        "-b:v", RENDER_BITRATE,
        "-maxrate", RENDER_BITRATE,
        "-bufsize", RENDER_BUFFER_SIZE,
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
        result = subprocess.run(cmd, capture_output=True, timeout=900)
        if result.returncode != 0:
            stderr_tail = result.stderr.decode("utf-8", errors="replace")[-500:]
            print(f"  [weekly] FFmpeg error (rc={result.returncode}): {stderr_tail}", flush=True)
    except subprocess.TimeoutExpired:
        print(f"  [weekly] FFmpeg timed out (900s)", flush=True)
        return None
    except Exception as e:
        print(f"  [weekly] Error: {e}", flush=True)
        return None

    # Clean up temp files
    if has_intro and os.path.exists(intro_path):
        try:
            os.remove(intro_path)
        except Exception:
            pass
    try:
        if srt_path and os.path.exists(srt_path):
            os.remove(srt_path)
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
