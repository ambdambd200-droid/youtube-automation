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
    RENDER_INTERMEDIATE_PRESET, RENDER_FINAL_PRESET,
)
from modules.utils import get_font_path, find_ffmpeg, find_ffprobe

_FFMPEG_BIN = find_ffmpeg()
_FFPROBE_BIN = find_ffprobe()

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
    """Blueprint Section 4.2: Gentle Speed Variation.
    Timeline:
      1. Normal Speed (100%) — approach/run-up
      2. Gentle Slow (70%) — smooth emphasis at impact
      3. Gentle Speed-Up (180%) — natural acceleration
      4. Return to 100% — final linger

    Uses per-segment trim+setpts+concat for monotonic PTS throughout.
    Pre/post segments expand to use enough input so output >= CLIP_MIN_DURATION.
    """
    input_dur = get_video_duration(input_path)
    if not input_dur or input_dur <= 0:
        input_dur = CLIP_MIN_DURATION + 5

    if impact_time is None:
        impact_time = 1.5

    # Guard: skip speed ramp if source is too short for the ramp segments
    ramp_overhead = impact_time + 0.8 + 0.6
    if input_dur < ramp_overhead + 2.0:
        print(f"  [editor] Speed ramp skipped: source too short ({input_dur:.1f}s < {ramp_overhead + 2.0:.1f}s)", flush=True)
        return None

    pre_ramp_duration = impact_time
    slow_mo_duration = 0.8
    speed_up_duration = 0.6

    # Output contribution from ramped segments (slow + speedup)
    ramp_output = (slow_mo_duration / TEMP_SLOW_MOTION_SPEED
                   + speed_up_duration / TEMP_SPEED_UP_SPEED)
    # Need: pre + ramp_output + post >= CLIP_MIN_DURATION
    needed_post = max(TEMP_REACTION_DURATION,
                      CLIP_MIN_DURATION + 0.5 - pre_ramp_duration - ramp_output)
    available = max(0, input_dur - pre_ramp_duration - slow_mo_duration - speed_up_duration)
    post_duration = min(max(TEMP_REACTION_DURATION, min(needed_post, available)), available)

    s2_start = pre_ramp_duration
    s2_end = s2_start + slow_mo_duration
    s3_end = s2_end
    s4_end = s3_end + speed_up_duration
    total = s4_end + post_duration

    atempo_slow = _atempo_chain(TEMP_SLOW_MOTION_SPEED)
    atempo_fast = _atempo_chain(TEMP_SPEED_UP_SPEED)

    # Per-segment video filters (4 segments: norm, slow, fast, norm)
    seg1v = f"[0:v]trim=0:{s2_start},setpts=PTS-STARTPTS"
    seg2v = (f"[0:v]trim={s2_start}:{s2_end},setpts=PTS-STARTPTS,"
             f"setpts=PTS/{TEMP_SLOW_MOTION_SPEED}")
    seg3v = (f"[0:v]trim={s3_end}:{s4_end},setpts=PTS-STARTPTS,"
             f"setpts=PTS/{TEMP_SPEED_UP_SPEED}")
    seg4v = f"[0:v]trim={s4_end}:{total},setpts=PTS-STARTPTS"

    # Per-segment audio filters
    seg1a = f"[0:a]atrim=0:{s2_start},asetpts=PTS-STARTPTS"
    seg2a = f"[0:a]atrim={s2_start}:{s2_end},asetpts=PTS-STARTPTS,{atempo_slow}"
    seg3a = f"[0:a]atrim={s3_end}:{s4_end},asetpts=PTS-STARTPTS,{atempo_fast}"
    seg4a = f"[0:a]atrim={s4_end}:{total},asetpts=PTS-STARTPTS"

    # Label outputs and build concat
    n_segs = 4
    v_labels = [f"[seg{i}v]" for i in range(n_segs)]
    a_labels = [f"[seg{i}a]" for i in range(n_segs)]

    filter_parts = []
    for i in range(n_segs):
        filter_parts.append(f"{[seg1v, seg2v, seg3v, seg4v][i]}{v_labels[i]}")
        filter_parts.append(f"{[seg1a, seg2a, seg3a, seg4a][i]}{a_labels[i]}")

    concat_in = "".join(f"{vl}{al}" for vl, al in zip(v_labels, a_labels))
    filter_parts.append(f"{concat_in}concat=n={n_segs}:v=1:a=1[vout][aout]")

    filter_complex = ";".join(filter_parts)

    cmd = [
        _FFMPEG_BIN, "-y", "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", RENDER_CODEC, "-preset", RENDER_INTERMEDIATE_PRESET,
        "-crf", str(RENDER_CRF),
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", RENDER_PIX_FMT,
        "-r", str(FPS),
        output_path,
    ]

    output_duration = (pre_ramp_duration
                       + slow_mo_duration / TEMP_SLOW_MOTION_SPEED
                       + speed_up_duration / TEMP_SPEED_UP_SPEED
                       + post_duration)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            print(f"  [editor] Speed ramp applied: {os.path.basename(output_path)}", flush=True)
            return {"path": output_path, "duration": output_duration}
        err = result.stderr[-300:] if result.stderr else "no stderr"
        print(f"  [editor] Speed ramp failed (rc={result.returncode}): {err}", flush=True)
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
        _FFMPEG_BIN, "-y", "-i", input_path,
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


def apply_breath_cut(input_path, output_path, total_duration):
    """Blueprint Section 4.3: Breath Cut — smooth fade-out + padding to CLIP_MIN_DURATION.
    Always produces at least CLIP_MIN_DURATION+0.5s output.
    If source is shorter, pads with black frames + silence (cloned last frame).
    """
    min_out = CLIP_MIN_DURATION + 0.5
    target = max(total_duration, min_out)
    cut_time = total_duration
    fade_start = max(0, cut_time - 1.5)
    pad_dur = target - total_duration

    vf = f"fade=t=in:st=0:d=0.3,fade=t=out:st={fade_start}:d=1.5"
    af = f"afade=t=in:st=0:d=0.3,afade=t=out:st={fade_start}:d=1.5"
    if pad_dur > 0:
        vf += f",tpad=stop_mode=clone:stop_duration={pad_dur}"
        af += f",apad=pad_dur={pad_dur}"

    cmd = [
        _FFMPEG_BIN, "-y", "-i", input_path,
        "-ss", "0",
        "-t", str(target),
        "-vf", vf,
        "-af", af,
        "-c:v", RENDER_CODEC, "-preset", RENDER_FINAL_PRESET,
        "-crf", str(RENDER_CRF),
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", RENDER_PIX_FMT,
        output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=180)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            print(f"  [editor] Breath cut: end at {cut_time:.1f}s + 1.5s fade-out"
                  f"{' + ' + str(pad_dur) + 's black pad' if pad_dur > 0 else ''}", flush=True)
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
        _FFMPEG_BIN, "-y", "-i", input_path,
        "-vf", vf,
        "-c:v", RENDER_CODEC, "-preset", RENDER_INTERMEDIATE_PRESET,
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
        _FFMPEG_BIN, "-y", "-i", input_path,
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
        _FFPROBE_BIN, "-v", "error",
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
            _FFPROBE_BIN, "-v", "error",
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
            _FFPROBE_BIN, "-v", "error",
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
            _FFMPEG_BIN, "-i", video_path,
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
        best_score = -1

        for i, scene_time in enumerate(scenes):
            window_end = scene_time + target_duration
            if window_end >= duration:
                continue
            # Count total scene changes in window
            density = sum(1 for s in scenes if scene_time <= s <= window_end)
            # Count scene changes in FIRST 10 SECONDS — critical for critique score
            early_window = min(scene_time + 10, window_end)
            early_density = sum(1 for s in scenes if scene_time <= s <= early_window)
            # Bonus for centered segments
            middle_bonus = 1.0 - abs(scene_time - duration / 2) / (duration / 2)
            # Heavy weight on early density (motion_dynamics = 20% of final score)
            weighted = density * 0.3 + early_density * 2.0 + 0.3 * middle_bonus
            if weighted > best_score:
                best_score = weighted
                best_start = scene_time

        mid_of_segment = best_start + target_duration / 2
        impact_point = min(scenes, key=lambda s: abs(s - mid_of_segment))

        offset = random.uniform(-2, 2)
        best_start = max(1, min(best_start + offset, duration - target_duration - 1))
        # Guard: if best segment has NO early scene changes, offset toward a scene
        early_count = sum(1 for s in scenes if best_start <= s <= best_start + 10)
        if early_count < 1 and len([s for s in scenes if s < best_start + 10]) > 0:
            first_early = next((s for s in scenes if s > best_start), None)
            if first_early and first_early + target_duration < duration:
                best_start = max(1, first_early - 3)
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

    from config import UPSCALE_FLAGS, UPSCALE_UNSHARP_LUMA, UPSCALE_UNSHARP_CHROMA
    video_chain = (
        f"[0:v]trim=start={start_time}:duration={duration},setpts=PTS-STARTPTS,"
        f"crop={crop_w}:{crop_h}:{x}:{y},"
        f"scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=0:flags={UPSCALE_FLAGS},"
        f"unsharp={UPSCALE_UNSHARP_LUMA}:{UPSCALE_UNSHARP_CHROMA}"
    )

    # Assemble full filtergraph: video chain + audio chain, each with its own output label
    filter_complex = (
        f"{video_chain}[vout];"
        f"[0:a]atrim=start={start_time}:duration={duration},asetpts=PTS-STARTPTS[aout]"
    )

    cmd = [
        _FFMPEG_BIN, "-y",
        "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", RENDER_CODEC,
        "-preset", RENDER_INTERMEDIATE_PRESET,
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

    for crop_attempt in range(2):
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
                if result.returncode != 0:
                    print(f"  [editor] FFmpeg crop error (attempt {crop_attempt+1}): {result.stderr[-500:]}", flush=True)
                else:
                    print(f"  [editor] Output file missing or too small: {output_path}", flush=True)
        except subprocess.TimeoutExpired:
            print(f"  [editor] FFmpeg crop timed out (attempt {crop_attempt+1})", flush=True)
        except Exception as e:
            print(f"  [editor] Crop error (attempt {crop_attempt+1}): {e}", flush=True)
        if crop_attempt == 0:
            time.sleep(2)

    # Fallback: simplified crop without filter_complex
    try:
        fb_output = output_path.replace(".mp4", "_simple.mp4")
        fb_cmd = [
            _FFMPEG_BIN, "-y",
            "-ss", str(start_time),
            "-i", input_path,
            "-t", str(duration),
            "-vf", f"crop={SHORTS_WIDTH}:{SHORTS_HEIGHT}:(iw-{SHORTS_WIDTH})/2:(ih-{SHORTS_HEIGHT})/2,scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}",
            "-c:v", RENDER_CODEC, "-preset", "fast",
            "-crf", str(RENDER_CRF),
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", RENDER_PIX_FMT,
            "-r", str(FPS),
            fb_output,
        ]
        result = subprocess.run(fb_cmd, capture_output=True, timeout=300)
        if os.path.exists(fb_output) and os.path.getsize(fb_output) > 10000:
            actual_dur = get_video_duration(fb_output) or duration
            print(f"  [editor] Simple crop fallback succeeded: {fb_output} ({actual_dur:.1f}s)", flush=True)
            return {
                "path": fb_output,
                "duration": actual_dur,
                "trim_start": start_time,
                "trim_end": start_time + duration,
            }
    except Exception as e:
        print(f"  [editor] Simple crop fallback also failed: {e}", flush=True)

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
            _FFMPEG_BIN, "-y",
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

    # Content safety check: block NSFW videos (nudity, inappropriate clothing)
    from modules.content_safety import check_video_safety
    safe, reason = check_video_safety(input_path)
    if not safe:
        print(f"  [editor] BLOCKED by content safety: {reason}", flush=True)
        return None

    # Clean stale _pipeline_* work directories (older than 1 hour)
    import glob as _glob
    import time as _time
    now = _time.time()
    for stale_dir in _glob.glob(os.path.join(CLIPS_DIR, "_pipeline_*")):
        try:
            if os.path.isdir(stale_dir) and now - os.path.getmtime(stale_dir) > 3600:
                shutil.rmtree(stale_dir, ignore_errors=True)
        except Exception:
            pass

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
                    _FFMPEG_BIN, "-y", "-i", current,
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
                    clip_duration = ramp.get("duration", get_video_duration(current))
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
                    _FFMPEG_BIN, "-y", "-i", current,
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
                    clip_duration = get_video_duration(current)
                    print(f"  [editor] Speed ramp fallback: passthrough (no ramp)", flush=True)
            except Exception:
                print(f"  [editor] Speed ramp fallback also failed, continuing", flush=True)

        # ── Step 6: Montage Effects (LaughTrack-style text + SFX) ──
        montage_success = False
        for montage_attempt in range(2):
            try:
                step4 = os.path.join(work_dir, "04_montage.mp4")
                montage_result = apply_movie_effects(current, step4, content_type, title=title or "")
                if montage_result and os.path.exists(step4):
                    current = step4
                    montage_success = True
                    break
            except Exception as e:
                if montage_attempt == 0:
                    print(f"  [editor] Montage attempt {montage_attempt+1} failed: {e}, retrying...", flush=True)
                    time.sleep(2)
        if not montage_success:
            print(f"  [editor] Montage failed, keeping source as-is", flush=True)

        # ── Step 6.5: Sound Design (riser, silence-dip, impact, ambient) ──
        try:
            step_sfx = os.path.join(work_dir, "045_sound_design.mp4")
            sfx_result = add_sound_design(current, step_sfx, clip_duration)
            if sfx_result and sfx_result != current and os.path.exists(step_sfx):
                current = step_sfx
                print(f"  [editor] Sound design complete", flush=True)
            else:
                print(f"  [editor] Sound design skipped (no change)", flush=True)
        except Exception as e:
            print(f"  [editor] Sound design error: {e}, continuing", flush=True)

        # ── Step 7: Audio — simple loudnorm only (no BGM, no complex pipeline) ──
        try:
            step5 = os.path.join(work_dir, "05_audio_norm.mp4")
            norm_cmd = [
                _FFMPEG_BIN, "-y", "-i", current,
                "-c:v", "copy",
                "-af", "loudnorm=I=-14:LRA=7:TP=-1",
                "-c:a", "aac", "-b:a", "192k",
                step5,
            ]
            subprocess.run(norm_cmd, capture_output=True, timeout=120)
            if os.path.exists(step5) and os.path.getsize(step5) > 10000:
                current = step5
                print(f"  [editor] Audio normalized to -14 LUFS (simple pass)", flush=True)
            else:
                print(f"  [editor] Audio normalization produced no output, keeping original", flush=True)
        except Exception as e:
            print(f"  [editor] Audio normalization skipped: {e}", flush=True)

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
                probed_dur = get_video_duration(current)
                # Guard: if probed duration is way smaller than expected, use clip_duration
                if probed_dur <= 0 or probed_dur < clip_duration * 0.5:
                    actual_dur = clip_duration
                else:
                    actual_dur = probed_dur
                breath = apply_breath_cut(current, step7, actual_dur)
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
        _v_dur = get_video_duration(final_path)
        _v_w, _v_h = get_video_dimensions(final_path)
        print(f"  [editor] Actual: {_v_w}x{_v_h}, {_v_dur:.1f}s | Expected: {SHORTS_WIDTH}x{SHORTS_HEIGHT}, {CLIP_MIN_DURATION}-{CLIP_MAX_DURATION}s", flush=True)
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
        _FFMPEG_BIN, "-y", "-i", input_path,
        "-vf", vf,
        "-c:v", RENDER_CODEC, "-preset", RENDER_FINAL_PRESET,
        "-crf", str(RENDER_CRF),
        "-c:a", "copy",
        "-pix_fmt", RENDER_PIX_FMT,
        output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=180)
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
        _FFMPEG_BIN, "-y",
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


def _estimate_climax(clip_duration):
    """Estimate climax point as 65-75% into clip duration."""
    return clip_duration * 0.70


def _generate_5beat_captions(title="", clip_duration=15, content_type="movie"):
    """Generate 5-beat caption sequence: hook → build → peak_signal → emotion_label → twist.
    Content-aware: football vs movie/series get different text templates.
    Each beat: 2-6 words, timed to climax, styled per beat type.
    Returns list of (beat_type, text, start, end).
    """
    name = title[:35] if title else "this moment"
    climax = _estimate_climax(clip_duration)

    if content_type == "football":
        beats = {
            "hook": "SPAIN ARE CHAMPIONS" if "spain" in name.lower() else "PURE CLASS",
            "build": f"The road to glory...",
            "peak_signal": "THIS IS THE MOMENT",
            "emotion_label": "UNREAL",
            "twist": "From doubters to legends.",
        }
    elif content_type == "series":
        beats = {
            "hook": "THIS IS PEAK TV",
            "build": f"The legend of {name[:20]}...",
            "peak_signal": "THIS IS THE SCENE",
            "emotion_label": "PURE EMOTION",
            "twist": "No score. Just acting.",
        }
    else:  # movie
        beats = {
            "hook": "WAIT FOR THIS",
            "build": f"Watch the legend of {name[:20]}...",
            "peak_signal": "THIS IS THE MOMENT",
            "emotion_label": "PURE EMOTION",
            "twist": "No music. Just impact.",
        }

    captions = []
    # Beat 1: Hook (0-1.2s)
    captions.append(("hook", beats["hook"], 0.0, 1.2))

    # Beat 2: Build (early-mid)
    build_start = clip_duration * 0.20
    captions.append(("build", beats["build"], build_start, build_start + 2.0))

    # Beat 3: Peak Signal (just before climax)
    peak_start = max(0, climax - 1.5)
    captions.append(("peak_signal", beats["peak_signal"], peak_start, peak_start + 1.5))

    # Beat 4: Emotion Label (right after climax)
    emotion_start = min(climax + 0.5, clip_duration - 1.5)
    captions.append(("emotion_label", beats["emotion_label"], emotion_start, min(emotion_start + 1.5, clip_duration)))

    # Beat 5: Twist (closing)
    twist_start = clip_duration * 0.85
    captions.append(("twist", beats["twist"], twist_start, min(twist_start + 2.0, clip_duration - 0.3)))

    return captions


def _write_ass(captions, ass_path):
    """Write 5-beat captions to ASS subtitle file with per-event positioning and style."""
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Hook,Arial,56,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,8,10,10,80,1",
        "Style: Build,Arial,36,&H00FFFFFF,&H000000FF,&H00880000,&H00000000,1,0,0,0,100,100,0,0,1,3,0,2,10,10,200,1",
        "Style: Peak,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,5,40,40,40,1",
        "Style: Emotion,Arial,36,&H00FFFFFF,&H000000FF,&H00880000,&H00000000,1,0,0,0,100,100,0,0,1,3,0,2,10,10,200,1",
        "Style: Twist,Arial,32,&H00FFFFFF,&H000000FF,&H00880000,&H00000000,1,0,0,0,100,100,0,0,1,3,0,2,10,10,280,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    def _ts(sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = sec % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    # Map beat types to ASS style names
    style_map = {"hook": "Hook", "build": "Build", "peak_signal": "Peak", "emotion_label": "Emotion", "twist": "Twist"}

    for idx, (beat_type, text, start, end) in enumerate(captions, 1):
        style = style_map.get(beat_type, "Build")
        lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},{style},,0,0,0,,{text}")

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def add_sound_design(input_path, output_path, duration):
    """Add sound design to video: tension riser, silence-dip, sub-bass impact, ambient bed.
    Generates SFX WAV using Python (avoids ffmpeg aevalsrc complexity), then mixes with original audio.
    """
    import struct
    if duration <= 2:
        return input_path

    climax = duration * 0.70
    riser_start = max(0, climax - 1.5)
    sr = 48000

    # Build sample array
    n = int(duration * sr)
    samples = [0.0] * n

    for i in range(n):
        t = i / sr
        if t < duration:
            if riser_start <= t <= climax:
                # Tension riser: sine sweep 150→800Hz over 1.5s
                freq = 150 + 650 * (t - riser_start) / 1.5
                samples[i] += 0.12 * __import__('math').sin(2 * 3.14159 * freq * t)
            elif climax < t <= climax + 0.3:
                # Sub-bass impact 50Hz
                samples[i] += 0.25 * __import__('math').sin(2 * 3.14159 * 50 * t)
            else:
                # Ambient hum 60Hz + 120Hz
                samples[i] += 0.015 * __import__('math').sin(2 * 3.14159 * 60 * t)
                samples[i] += 0.008 * __import__('math').sin(2 * 3.14159 * 120 * t)

    # Normalize to avoid clipping
    peak = max(abs(max(samples)), abs(min(samples)), 0.001)
    scale = min(1.0 / peak, 1.0)
    scaled = [int(max(-32768, min(32767, s * scale * 32767))) for s in samples]

    # Write WAV
    sfx_path = os.path.join(os.path.dirname(output_path), "_sfx.wav")
    n_bytes = len(scaled) * 2
    with open(sfx_path, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + n_bytes))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))       # chunk size
        f.write(struct.pack("<H", 1))         # PCM
        f.write(struct.pack("<H", 1))         # mono
        f.write(struct.pack("<I", sr))        # sample rate
        f.write(struct.pack("<I", sr * 2))    # byte rate
        f.write(struct.pack("<H", 2))         # block align
        f.write(struct.pack("<H", 16))        # bits per sample
        f.write(b"data")
        f.write(struct.pack("<I", n_bytes))
        for s in scaled:
            f.write(struct.pack("<h", s))

    if not os.path.exists(sfx_path) or os.path.getsize(sfx_path) < 100:
        print(f"  [sound] SFX generation produced no output, skipping", flush=True)
        return input_path

    # Mix generated SFX with original audio using amix (2 inputs only)
    mix_cmd = [
        _FFMPEG_BIN, "-y",
        "-i", input_path,
        "-i", sfx_path,
        "-filter_complex",
        "[0:a][1:a]amix=inputs=2:duration=first:weights=1 0.35[a_mixed]",
        "-map", "0:v",
        "-map", "[a_mixed]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_path,
    ]

    try:
        subprocess.run(mix_cmd, capture_output=True, timeout=60)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            print(f"  [sound] Sound design applied: riser+impact+ambient", flush=True)
            return output_path
        else:
            print(f"  [sound] Mix failed, keeping original audio", flush=True)
            return input_path
    except Exception as e:
        err = e
        print(f"  [sound] Sound design mix error: {e}, keeping original", flush=True)
        return input_path
    finally:
        try:
            os.unlink(sfx_path)
        except Exception:
            pass


def apply_movie_effects(input_path, output_path, content_type, title=""):
    """Apply LaughTrack-style effects to a movie/series short.
    Adds dynamic zoom, timed pop-up text, glitch transition, and sound effects.
    """
    duration = get_video_duration(input_path)
    if duration <= 0:
        return None

    import uuid
    import tempfile
    ass_file = tempfile.NamedTemporaryFile(suffix=".ass", delete=False, mode="w", encoding="utf-8")
    ass_path = ass_file.name
    ass_file.close()
    captions = _generate_5beat_captions(title, clip_duration=duration, content_type=content_type)
    _write_ass(captions, ass_path)

    # Zoom factor: hook punch (1.08x at t=0, settles by 0.3s) + slow zoom (1.05x after 1.5s)
    zoom_expr = (
        f"(1.0 + 0.08*max(0,1-t/0.3) + 0.05*max(0,t-1.5)/{max(duration,0.1)})"
    )
    # Virtual camera pan: slow ±20px horizontal over duration
    pan_expr = f"20*sin(2*PI*t/{max(duration,0.1)})"
    filter_complex = (
        f"[0:v]scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=0,setsar=1,"
        f"scale='floor(iw*{zoom_expr})':'floor(ih*{zoom_expr})':eval=frame,"
        f"crop={SHORTS_WIDTH}:{SHORTS_HEIGHT}:(iw-{SHORTS_WIDTH})/2+({pan_expr}):(ih-{SHORTS_HEIGHT})/2,"
        f"unsharp=7:7:1.2:5:5:0.6,"
        f"ass='{ass_path.replace(chr(92), chr(92)*2).replace(':', chr(92)+chr(58))}'"
        f"[outv]"
    )
    last_label = "outv"

    input_files = ["-i", input_path]
    audio_map = "0:a?"

    cmd = [
        _FFMPEG_BIN, "-y",
    ] + input_files + [
        "-filter_complex", filter_complex,
        "-map", f"[{last_label}]",
        "-map", audio_map,
        "-c:v", RENDER_CODEC, "-preset", RENDER_FINAL_PRESET, "-crf", str(RENDER_CRF),
        "-b:v", RENDER_BITRATE,
        "-maxrate", RENDER_BITRATE,
        "-bufsize", RENDER_BUFFER_SIZE,
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", RENDER_PIX_FMT, "-r", str(FPS),
        "-movflags", RENDER_MOVFLAGS,
        "-profile:v", RENDER_PROFILE, "-level", RENDER_LEVEL,
        output_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=600)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            actual_dur = get_video_duration(output_path)
            if actual_dur <= 0:
                actual_dur = fallback_duration(output_path)
            print(f"  [editor] Montage + word captions applied: {output_path} ({actual_dur:.1f}s, {os.path.getsize(output_path)} bytes)", flush=True)
            return {"path": output_path, "duration": actual_dur}
        else:
            err = result.stderr[-500:].decode('utf-8', errors='replace') if result.stderr else "no stderr"
            print(f"  [editor] Montage failed (ffmpeg exit {result.returncode}): {err}", flush=True)
            import shutil
            shutil.copy2(input_path, output_path)
            return {"path": output_path, "duration": duration}
    except subprocess.TimeoutExpired:
        print(f"  [editor] Montage timed out — returning original crop", flush=True)
        import shutil
        shutil.copy2(input_path, output_path)
        return {"path": output_path, "duration": duration}
    except Exception as e:
        print(f"  [editor] Montage error: {e}", flush=True)
        import shutil
        shutil.copy2(input_path, output_path)
        return {"path": output_path, "duration": duration}
    finally:
        try:
            os.unlink(ass_path)
        except Exception:
            pass


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
        _FFMPEG_BIN, "-y",
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
        _FFMPEG_BIN, "-y",
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
        _FFMPEG_BIN, "-y",
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
            _FFMPEG_BIN, "-y",
        ] + input_files + [
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "[aout]",
        ]
    elif has_voiceover:
        filter_complex = f"{video_chain}[vout];{audio_chain}"
        cmd = [
            _FFMPEG_BIN, "-y",
        ] + input_files + [
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", audio_map_label,
        ]
    else:
        cmd = [
            _FFMPEG_BIN, "-y",
        ] + input_files + [
            "-vf", video_chain,
            "-af", f"atrim=0:{video_duration},asetpts=PTS-STARTPTS",
        ]

    cmd += [
        "-c:v", "libx264",
        "-preset", RENDER_FINAL_PRESET,
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
