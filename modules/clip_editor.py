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


def _generate_tts_wav(text, output_path, voice="en-US-GuyNeural"):
    """Generate TTS audio WAV for hook voiceover using edge-tts.
    Returns True on success.

    Voice is now selected from a 4-voice pool via vibe_of_the_day.pick_vibe()
    Pacing hint ("snappy" or "narrative") modifies rate/pitch:
      - snappy:    rate=+8%, pitch=+0Hz  (faster, more energetic)
      - narrative: rate=-3%, pitch=-2Hz  (slower, calmer)

    Fallback chain: requested voice → other voices in pool → Windows SAPI.
    Edge-tts voices sometimes 503; rotating through the pool keeps narration
    present in the output instead of falling back to silent SFX-only audio.
    """
    pacing = "snappy"
    try:
        from modules.vibe_of_the_day import pick_vibe
        pacing = pick_vibe().get("tts_pacing", "snappy")
    except Exception:
        pass

    if pacing == "narrative":
        rate = "-3%"
        pitch = "-2Hz"
    else:
        # محور 2: slower rate (was +8%) for clearer voiceover over original audio
        rate = "+5%"
        pitch = "+0Hz"

    if not text:
        return False

    # Build voice pool: requested voice first, then other voices in order
    try:
        from modules.vibe_of_the_day import VOICES
        voice_pool = [voice] + [v for v in VOICES if v != voice]
    except Exception:
        voice_pool = [voice, "en-US-GuyNeural", "en-US-JennyNeural", "en-US-AriaNeural", "en-US-MichelleNeural"]

    # Try each voice — first one that returns audio wins
    for v in voice_pool:
        try:
            import edge_tts
            import asyncio
            asyncio.run(edge_tts.Communicate(text, v, rate=rate, pitch=pitch).save(output_path))
            if os.path.exists(output_path) and os.path.getsize(output_path) > 200:
                if v != voice:
                    print(f"  [tts] Voice fallback: {voice} failed, used {v}", flush=True)
                return True
        except Exception:
            continue
        # Without rate/pitch (some voice+rate combos fail)
        try:
            import edge_tts
            import asyncio
            asyncio.run(edge_tts.Communicate(text, v).save(output_path))
            if os.path.exists(output_path) and os.path.getsize(output_path) > 200:
                if v != voice:
                    print(f"  [tts] Voice fallback (plain): {voice} failed, used {v}", flush=True)
                return True
        except Exception:
            continue

    print(f"  [tts] All edge-tts voices failed, trying PowerShell SAPI", flush=True)
    # Final fallback: Windows built-in speech
    try:
        safe = text.replace("'", "''").replace('"', '`"')
        ps = (
            f'Add-Type -AssemblyName System.Speech;'
            f'$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;'
            f'$s.SetOutputToWaveFile("{output_path}");'
            f'$s.SelectVoice("Microsoft David Desktop");'
            f'$s.Speak("{safe}");'
            f'$s.Dispose()'
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=30)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 200
    except Exception as e:
        print(f"  [tts] SAPI fallback failed: {e}", flush=True)
        return False

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


def apply_speed_ramp(input_path, output_path, impact_time=None, target_duration=None):
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
    # Need: pre + ramp_output + post >= target_duration
    min_post = target_duration if target_duration else CLIP_MIN_DURATION + 0.5
    needed_post = max(TEMP_REACTION_DURATION,
                      min_post - pre_ramp_duration - ramp_output)
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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
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


def apply_breath_cut(input_path, output_path, total_duration, max_duration=None):
    """Blueprint Section 4.3: Breath Cut — smooth fade-out + retention loop.
    Last 1.5s fades into first 2s of clip for seamless rewatch loop.
    If max_duration is set, caps total output at that value (for shorts).
    """
    import shutil
    if max_duration:
        target = max(total_duration, 3.0)
        target = min(target, max_duration - 2.0)
    else:
        min_out = CLIP_MIN_DURATION + 0.5
        target = max(total_duration, min_out)
    cut_time = total_duration
    fade_start = max(0, cut_time - 1.5)

    loop_dur = min(2.0, total_duration * 0.15)

    # Two-pass: first add fade + CTA, then append loop tail
    pass1 = os.path.join(os.path.dirname(output_path), "_breath_pass1.mp4")
    vf = f"fade=t=in:st=0:d=0.3,fade=t=out:st={fade_start}:d=1.5"
    af = f"afade=t=in:st=0:d=0.3,afade=t=out:st={fade_start}:d=1.5"
    if target > total_duration:
        pad = target - total_duration
        vf += f",tpad=stop_mode=clone:stop_duration={pad}"
        af += f",apad=pad_dur={pad}"

    cmd1 = [
        _FFMPEG_BIN, "-y", "-i", input_path,
        "-ss", "0", "-t", str(target),
        "-vf", vf, "-af", af,
        "-c:v", RENDER_CODEC, "-preset", RENDER_FINAL_PRESET,
        "-crf", str(RENDER_CRF),
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", RENDER_PIX_FMT,
        pass1,
    ]
    try:
        subprocess.run(cmd1, capture_output=True, timeout=180)
        if not os.path.exists(pass1) or os.path.getsize(pass1) < 10000:
            shutil.copy2(input_path, output_path)
            print(f"  [editor] Breath cut pass1 failed, returning original", flush=True)
            return output_path
    except Exception as e:
        print(f"  [editor] Breath cut pass1 error: {e}, returning original", flush=True)
        shutil.copy2(input_path, output_path)
        return output_path

    # Pass 2: append first 2 seconds as loop tail
    # Concat: pass1 (faded out) → first loop_dur seconds of original (faded in)
    loop_start = input_path
    loop_tail = os.path.join(os.path.dirname(output_path), "_breach_loop_tail.mp4")
    cmd_loop = [
        _FFMPEG_BIN, "-y", "-i", loop_start,
        "-ss", "0", "-t", str(loop_dur),
        "-vf", "fade=t=in:st=0:d=0.3",
        "-af", "afade=t=in:st=0:d=0.3",
        "-c:v", RENDER_CODEC, "-preset", "fast",
        "-crf", str(RENDER_CRF + 2),
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", RENDER_PIX_FMT,
        loop_tail,
    ]
    try:
        subprocess.run(cmd_loop, capture_output=True, timeout=60)
    except Exception:
        pass

    if os.path.exists(loop_tail) and os.path.getsize(loop_tail) > 5000:
        concat_file = os.path.join(os.path.dirname(output_path), "_breach_concat.txt")
        try:
            with open(concat_file, "w") as cf:
                cf.write(f"file '{pass1.replace(chr(92), chr(92)+chr(92))}'\n")
                cf.write(f"file '{loop_tail.replace(chr(92), chr(92)+chr(92))}'\n")
            cmd_concat = [
                _FFMPEG_BIN, "-y", "-f", "concat", "-safe", "0",
                "-i", concat_file,
                "-c", "copy",
                output_path,
            ]
            subprocess.run(cmd_concat, capture_output=True, timeout=60)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
                print(f"  [editor] Breath cut: end at {cut_time:.1f}s + 1.5s fade-out"
                      f" + {loop_dur:.1f}s loop tail", flush=True)
                return output_path
        except Exception:
            pass
        finally:
            for _f in [concat_file, loop_tail]:
                try:
                    os.unlink(_f)
                except Exception:
                    pass

    # Fallback: return pass1 if loop fails
    shutil.copy2(pass1, output_path)
    print(f"  [editor] Breath cut: end at {cut_time:.1f}s + 1.5s fade-out"
          f" (no loop)", flush=True)
    return output_path


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


def select_clip_segment(video_path, target_duration=None, content_type="movie", min_duration=None, max_duration=None):
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

    _min = min_duration or CLIP_MIN_DURATION
    _max = max_duration or CLIP_MAX_DURATION

    if duration <= 0:
        return (0, _min, None)

    if duration <= _min:
        return (0, duration, None)

    if target_duration is None:
        try:
            from modules.evolution_engine import get_parameter
            evo_min = get_parameter("clip_min_duration", _min)
            evo_max = get_parameter("clip_max_duration", _max)
            target_duration = random.randint(
                max(_min, int(evo_min)),
                min(_max, min(int(evo_max), int(duration)))
            )
        except Exception:
            target_duration = random.randint(_min, min(_max, int(duration)))

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

            # FIRST-FRAME HOOK CHECK: extract and score frame at candidate start
            hook_bonus = 0.0
            try:
                from modules.clip_critique import _score_first_frame_hook, extract_peak_action_frame_clip
                # Extract single frame at candidate start for hook analysis
                import tempfile, os as _os
                frame_f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                frame_path = frame_f.name
                frame_f.close()
                cmd = [
                    _FFMPEG_BIN, "-y", "-ss", str(scene_time),
                    "-i", video_path,
                    "-vframes", "1", "-q:v", "2",
                    frame_path,
                ]
                import subprocess as _sp
                _sp.run(cmd, capture_output=True, timeout=15)
                if _os.path.exists(frame_path) and _os.path.getsize(frame_path) > 1000:
                    hook = _score_first_frame_hook(frame_path)
                    hook_bonus = min(1.0, hook / 100.0)  # normalize 0-1
                    print(f"  [editor] Candidate @ {scene_time:.1f}s: hook={hook:.1f}, density={density}, early={early_density}", flush=True)
                if _os.path.exists(frame_path):
                    try: _os.unlink(frame_path)
                    except: pass
            except Exception:
                pass

            # Combine: 60% hook, 40% scene dynamics
            final_score = weighted * 0.4 + hook_bonus * 100 * 0.6

            if final_score > best_score:
                best_score = final_score
                best_start = scene_time

        mid_of_segment = best_start + target_duration / 2
        impact_point = min(scenes, key=lambda s: abs(s - mid_of_segment))

        # Apply jitter but ensure first frame hook stays strong
        offset = random.uniform(-1, 1)
        candidate_start = max(1, min(best_start + offset, duration - target_duration - 1))
        # Re-check first frame hook at the jittered start
        try:
            from modules.clip_critique import _score_first_frame_hook
            import tempfile, os as _os, subprocess as _sp
            frame_f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            frame_path = frame_f.name
            frame_f.close()
            _sp.run([_FFMPEG_BIN, "-y", "-ss", str(candidate_start), "-i", video_path,
                     "-vframes", "1", "-q:v", "2", frame_path], capture_output=True, timeout=15)
            if _os.path.exists(frame_path) and _os.path.getsize(frame_path) > 1000:
                hook_at_candidate = _score_first_frame_hook(frame_path)
                if hook_at_candidate < 50:
                    candidate_start = best_start  # snap back to keep strong hook
            if _os.path.exists(frame_path):
                try: _os.unlink(frame_path)
                except: pass
        except Exception:
            pass
        best_start = candidate_start

        # Guard: if best segment has NO early scene changes, offset toward a scene
        early_count = sum(1 for s in scenes if best_start <= s <= best_start + 10)
        if early_count < 1 and len([s for s in scenes if s < best_start + 10]) > 0:
            first_early = next((s for s in scenes if s > best_start), None)
            if first_early and first_early + target_duration < duration:
                best_start = max(1, first_early - 3)
        print(f"  [editor] Scene-smart segment: {best_start:.1f}s - {best_start + target_duration:.1f}s ({len(scenes)} scenes detected, best_score={best_score:.2f})", flush=True)
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

    # Detect action center to keep subject in frame (not just centered crop)
    # When action is on the left or right edge, centered crop would clip it out.
    # Use cropdetect on the segment, then offset x to keep the action visible.
    x = (in_w - crop_w) // 2  # default: centered
    action_center = None
    try:
        from modules.smart_crop import detect_action_center
        # Run on the actual segment we care about
        action_center = detect_action_center(input_path, start_time, duration)
    except Exception:
        pass

    if action_center is not None:
        # Map [0.25, 0.75] -> [0, in_w]
        action_x_px = int(action_center * in_w)
        # Try to center the crop on the action
        x = action_x_px - crop_w // 2
        # Clamp to valid range so crop doesn't fall off edges
        x = max(0, min(in_w - crop_w, x))

    y = (in_h - crop_h) // 2
    x = x if x % 2 == 0 else x - 1
    y = y if y % 2 == 0 else y - 1

    if action_center is not None and abs(action_center - 0.5) > 0.1:
        print(f"  [crop] Smart crop: action_center={action_center:.2f} (x_offset={x - (in_w - crop_w) // 2}px from center)", flush=True)

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


def create_clip(input_path, content_type, title="", skip_effects=False, force_short=False):
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

    # VARY: pick duration range for this specific clip (short or long mode)
    from config import get_clip_duration_range
    var_min, var_max = get_clip_duration_range(content_type, force_short=force_short)
    print(f"  [editor] VARY duration: {var_min}-{var_max}s ({content_type}, force_short={force_short})", flush=True)

    if skip_effects:
        # Legacy mode: basic crop only
        output_path = os.path.join(CLIPS_DIR, f"{content_type}_{clip_id}.mp4")
        working_input = remux_to_compatible(input_path)
        start_time, duration, _ = select_clip_segment(working_input, content_type=content_type, min_duration=var_min, max_duration=var_max)
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
        seg_start, seg_duration, impact_point = select_clip_segment(current, content_type=content_type, min_duration=var_min, max_duration=var_max)

        # ── Step 2: In Media Res — start 1.5s before impact (Blueprint 4.1) ──
        # BUT: we selected seg_start for its STRONG FIRST FRAME.
        # Only shift earlier if impact_point is very early in the segment (< 3s).
        # Otherwise keep the selected start as the first frame (the hook).
        if impact_point is not None and impact_point > seg_start:
            impact_relative = impact_point - seg_start
            if impact_relative < 3.0:
                # Impact too early - shift start slightly earlier to give context
                desired_start = max(0, impact_point - TEMP_PRE_ACTION_WINDOW)
                new_start = min(seg_start, desired_start)
                new_duration = min(var_max, full_end - new_start) if 'full_end' in dir() else min(var_max, get_video_duration(current) - new_start)
                if new_duration >= var_min:
                    seg_start = new_start
                    seg_duration = new_duration
                    print(f"  [editor] In media res (early impact): start {seg_start:.1f}s (impact at {impact_point:.1f}s), dur {seg_duration:.0f}s", flush=True)
                else:
                    print(f"  [editor] In media res skipped: shift would make clip too short", flush=True)
            else:
                # Impact is well within segment - KEEP the selected start as first frame (the hook)
                print(f"  [editor] In media res (hook preserved): start {seg_start:.1f}s (impact at {impact_point:.1f}s, +{impact_relative:.1f}s), dur {seg_duration:.0f}s", flush=True)
        else:
            if impact_point is not None:
                print(f"  [editor] Impact before segment start ({impact_point:.1f}s), keeping original segment", flush=True)
            print(f"  [pipeline] Segment: {seg_start:.1f}s - {seg_start + seg_duration:.1f}s ({seg_duration:.0f}s)", flush=True)

        rel_impact = (impact_point - seg_start) if impact_point and impact_point > seg_start else 1.5

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
                ramp = apply_speed_ramp(current, step3, impact_time=rel_impact, target_duration=clip_duration)
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

        # ── Step 6: Montage Effects (captions + zoom + TTS hook) ──
        # VARY: pick daily vibe combo (voice, hook, caption style, zoom curve, color profile)
        vibe = None
        try:
            from modules.vibe_of_the_day import pick_vibe
            vibe = pick_vibe()
            print(f"  [vibe] Today: voice={vibe['voice'].split('-')[-1]} caption={vibe['caption']} color={vibe['color']} zoom={vibe['zoom']}", flush=True)
        except Exception:
            print(f"  [vibe] pick_vibe failed, using defaults", flush=True)

        montage_success = False
        hook_text = None
        for montage_attempt in range(2):
            try:
                step4 = os.path.join(work_dir, "04_montage.mp4")
                montage_result = apply_movie_effects(current, step4, content_type, title=title or "", vibe=vibe)
                if montage_result and os.path.exists(step4):
                    current = step4
                    hook_text = montage_result.get("hook_text")
                    montage_success = True
                    break
            except Exception as e:
                if montage_attempt == 0:
                    print(f"  [editor] Montage attempt {montage_attempt+1} failed: {e}, retrying...", flush=True)
                    time.sleep(2)
        if not montage_success:
            print(f"  [editor] Montage failed, falling back to ramped video (step3)", flush=True)
            # Fallback: use step3 (ramped) which exists and is valid
            step3_fb = os.path.join(work_dir, "03_ramped.mp4")
            if os.path.exists(step3_fb):
                import shutil
                # Retry copy up to 5 times with delay — Windows holds files after ffmpeg exits
                for retry in range(5):
                    try:
                        time.sleep(0.5 + retry * 0.5)
                        shutil.copy2(step3_fb, current)
                        break
                    except PermissionError:
                        if retry == 4:
                            print(f"  [editor] File copy still locked after 5 retries, using fallback path", flush=True)
                            # Last resort: copy via stream read/write
                            with open(step3_fb, "rb") as src, open(current, "wb") as dst:
                                dst.write(src.read())
            # Also generate a basic TTS for sound design if we have hook text
            hook_text = "watch this."

        # ── Step 6.5: Generate Analysis Narration (Mandatory for Transformative Use) ──
        # Creates 3-sentence analytical commentary covering ~70% of clip duration
        analysis_tts_path = None
        try:
            analysis_segments = generate_analysis_narration(title or "", clip_duration, content_type)
            if analysis_segments:
                print(f"  [narration] Generated {len(analysis_segments)} analysis segments", flush=True)
                # Generate TTS for each segment with pitch shift (already handled in add_sound_design)
                # We'll combine them into a single narration track
                import asyncio
                import edge_tts
                import random
                
                # Pick voice from vibe or random
                voice = "en-US-AriaNeural"
                if vibe and vibe.get("voice"):
                    voice = vibe["voice"]
                
                segment_files = []
                # Build voice pool with fallback — edge-tts voices sometimes 503
                try:
                    from modules.vibe_of_the_day import VOICES
                    voice_pool = [voice] + [v for v in VOICES if v != voice]
                except Exception:
                    voice_pool = [voice, "en-US-GuyNeural", "en-US-JennyNeural", "en-US-AriaNeural", "en-US-MichelleNeural"]
                for i, (text, start_time) in enumerate(analysis_segments):
                    seg_path = os.path.join(work_dir, f"_analysis_tts_{i}.wav")
                    # Apply pitch shift for Content ID evasion (integer Hz)
                    pitch_shift = random.choice([-5, -4, -3, 3, 4, 5])
                    pitch_str = f"{pitch_shift:+d}Hz"
                    rate_str = "+5%"  # محور 2: clearer voiceover (was +8%)
                    # Try selected voice first, then fall back through the pool
                    seg_ok = False
                    for v in voice_pool:
                        try:
                            asyncio.run(edge_tts.Communicate(text, v, rate=rate_str, pitch=pitch_str).save(seg_path))
                            if os.path.exists(seg_path) and os.path.getsize(seg_path) > 200:
                                if v != voice:
                                    print(f"  [narration] Voice fallback for segment {i}: {voice} -> {v}", flush=True)
                                seg_ok = True
                                break
                        except Exception:
                            continue
                    if seg_ok:
                        segment_files.append((seg_path, start_time))
                
                if segment_files:
                    # Combine into single narration track with silence between
                    analysis_tts_path = os.path.join(work_dir, "_analysis_narration.wav")
                    # Build ffmpeg concat with delays
                    concat_inputs = []
                    filter_parts = []
                    for idx, (seg_path, start_time) in enumerate(segment_files):
                        concat_inputs.extend(["-i", seg_path])
                        filter_parts.append(f"[{idx}:a]adelay={int(start_time*1000)}|{int(start_time*1000)}[a{idx}]")
                    
                    if len(segment_files) == 1:
                        shutil.copy2(segment_files[0][0], analysis_tts_path)
                    else:
                        concat_filter = "".join(f"[a{idx}]" for idx in range(len(segment_files)))
                        concat_filter += f"amix=inputs={len(segment_files)}:duration=longest:weights={' '.join(['1']*len(segment_files))}[an]"
                        mix_cmd = [
                            _FFMPEG_BIN, "-y",
                        ] + concat_inputs + [
                            "-filter_complex", "".join(filter_parts) + ";" + concat_filter,
                            "-map", "[an]",
                            "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "1",
                            analysis_tts_path,
                        ]
                        subprocess.run(mix_cmd, capture_output=True, timeout=60)
                    
                    if os.path.exists(analysis_tts_path) and os.path.getsize(analysis_tts_path) > 500:
                        print(f"  [narration] Analysis narration created: {len(segment_files)} segments", flush=True)
                    else:
                        analysis_tts_path = None
        except Exception as e:
            print(f"  [narration] Generation failed: {e}", flush=True)
            analysis_tts_path = None

        # ── Step 6.5: Sound Design (riser + impact + ambient + TTS hook + analysis narration) ──
        try:
            step_sfx = os.path.join(work_dir, "045_sound_design.mp4")
            tts_path = os.path.join(work_dir, "_hook_tts.wav")
            sfx_result = add_sound_design(
                current, step_sfx, clip_duration,
                hook_tts_path=tts_path if hook_text else None,
                analysis_tts_path=analysis_tts_path,
                original_audio_path=input_path,  # Phase 1: layer source audio at 7%
            )
            if sfx_result and sfx_result != current and os.path.exists(step_sfx):
                current = step_sfx
                print(f"  [editor] Sound design complete", flush=True)
            else:
                print(f"  [editor] Sound design skipped (no change)", flush=True)
        except Exception as e:
            print(f"  [editor] Sound design error: {e}, continuing", flush=True)

        # ── Step 7: Audio — two-pass loudnorm (محور 2: more accurate than single-pass) ──
        try:
            import json as _json
            step5 = os.path.join(work_dir, "05_audio_norm.mp4")
            # Pass 1: measure loudness
            measure_cmd = [
                _FFMPEG_BIN, "-y", "-i", current,
                "-af", "loudnorm=I=-14:LRA=7:TP=-1:print_format=json",
                "-f", "null", "-",
            ]
            r = subprocess.run(measure_cmd, capture_output=True, text=True, timeout=120)
            # Parse measured values from stderr
            measured = None
            if r.stderr:
                # Find JSON object in stderr
                json_start = r.stderr.rfind("{")
                json_end = r.stderr.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    try:
                        measured = _json.loads(r.stderr[json_start:json_end])
                    except _json.JSONDecodeError:
                        measured = None
            # Pass 2: apply measured values for precise normalization
            if measured and "input_i" in measured:
                apply_cmd = [
                    _FFMPEG_BIN, "-y", "-i", current,
                    "-c:v", "copy",
                    "-af", (f"loudnorm=I=-14:LRA=7:TP=-1:"
                            f"measured_I={measured['input_i']}:"
                            f"measured_TP={measured['input_tp']}:"
                            f"measured_LRA={measured['input_lra']}:"
                            f"measured_thresh={measured['input_thresh']}:"
                            f"offset={measured['target_offset']}:"
                            f"linear=true"),
                    "-c:a", "aac", "-b:a", "192k",
                    step5,
                ]
            else:
                # Fallback to single-pass if measurement failed
                apply_cmd = [
                    _FFMPEG_BIN, "-y", "-i", current,
                    "-c:v", "copy",
                    "-af", "loudnorm=I=-14:LRA=7:TP=-1",
                    "-c:a", "aac", "-b:a", "192k",
                    step5,
                ]
            subprocess.run(apply_cmd, capture_output=True, timeout=120)
            if os.path.exists(step5) and os.path.getsize(step5) > 10000:
                current = step5
                print(f"  [editor] Audio normalized to -14 LUFS (two-pass)", flush=True)
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
                breath = apply_breath_cut(current, step7, actual_dur, max_duration=var_max)
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
        passed, last_issues = validate_short(final_path, max_duration=var_max, min_duration=var_min)
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
        print(f"  [editor] Actual: {_v_w}x{_v_h}, {_v_dur:.1f}s | Expected: {SHORTS_WIDTH}x{SHORTS_HEIGHT}, {var_min}-{var_max}s", flush=True)
        _clean_work_dir(work_dir)

    print(f"  [editor] All {max_retries} attempts failed — no valid clip produced", flush=True)
    return None


def apply_watermark(input_path, output_path):
    """Overlay VARY branding watermark (bottom-right corner).
    Semi-transparent white text with drop shadow, shown only in the LAST
    1.5 seconds of the clip (محور 4: less intrusive — was full-clip).
    """
    font_path = get_font_path()
    if not font_path:
        print(f"  [editor] Watermark: no font found, skipping", flush=True)
        return None
    # Get video duration so we can fade in watermark over the last 1.5s
    duration = get_video_duration(input_path)
    if duration <= 1.5:
        # Clip too short — skip watermark (would cover entire clip)
        print(f"  [editor] Watermark skipped: clip too short ({duration:.1f}s)", flush=True)
        # Just copy the file
        import shutil
        try:
            shutil.copy2(input_path, output_path)
            return output_path
        except Exception:
            return None
    # Watermark enabled only when t > duration - 1.5 (last 1.5 seconds)
    # fade in from 0% to 35% opacity over the first 0.3s of the watermark window
    enable_start = max(0, duration - 1.5)
    fade_duration = 0.3
    vf = (
        f"drawtext=text='VARY':fontcolor=white@0.35:fontsize=28:"
        f"x=w-text_w-20:y=h-text_h-20:"
        f"shadowcolor=black@0.5:shadowx=2:shadowy=2:"
        f"fontfile='{font_path}':"
        f"enable='gte(t,{enable_start:.2f})':"
        f"alpha='if(lt(t,{enable_start + fade_duration:.2f}),(t-{enable_start:.2f})/{fade_duration:.2f},1)'"
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
            print(f"  [editor] VARY watermark applied (last 1.5s only)", flush=True)
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


# ── Analysis Narration Generator (Content ID: Transformative Use) ──
# Generates 3-sentence analytical narration for every clip.
# Mandatory overlay — transforms "clip" into "criticism/commentary".

_NARRATION_TEMPLATES = [
    # Opening hook
    "This moment from {title} reveals {insight}.",
    "Notice how {title} uses {technique} to {effect}.",
    "The director of {title} employs {technique} to convey {emotion}.",
    "What makes this {title} scene work is {insight}.",
    "In {title}, this beat demonstrates {principle}.",
    # Technical breakdown
    "The {technique} here creates {effect} by {mechanism}.",
    "Watch the {element} — it signals {meaning}.",
    "The {color_lighting_composition} tells us {insight}.",
    # Payoff
    "This is why {title} resonates: {payoff}.",
    "Masterclass in {craft}: {summary}.",
]

_TECHNIQUES = [
    "lighting", "composition", "camera movement", "color palette", "sound design",
    "pacing", "mise-en-scène", "framing", "depth of field", "blocking",
    "visual metaphor", "symbolism", "contrast", "negative space", "leading lines"
]

_EFFECTS = [
    "builds tension", "reveals character", "establishes mood", "foreshadows",
    "subverts expectation", "creates intimacy", "emphasizes isolation",
    "heightens stakes", "conveys internal state", "anchors the theme"
]

_INSIGHTS = [
    "the power of visual storytelling", "how cinema manipulates perception",
    "the language of film", "directorial intent", "cinematic grammar",
    "show don't tell", "economy of expression", "emotional architecture"
]


def generate_analysis_narration(title, clip_duration, content_type="movie"):
    """Generate 3-sentence analytical narration for transformative use.
    
    Returns: list of (text, start_time) tuples for TTS generation.
    Total narration covers ~60-80% of clip duration.
    """
    import random
    clean_title = title.split("(")[0].split("|")[0].split("-")[0].strip()
    if len(clean_title) > 40:
        clean_title = clean_title[:40] + "..."
    
    # Pick 3 distinct templates
    templates = random.sample(_NARRATION_TEMPLATES, 3)
    technique = random.choice(_TECHNIQUES)
    effect = random.choice(_EFFECTS)
    insight = random.choice(_INSIGHTS)
    
    color_lighting_composition = random.choice(["color grading", "lighting", "composition"])
    principle = random.choice(["economy of expression", "visual storytelling", "cinematic grammar", "dramatic structure", "character motivation"])
    mechanism = random.choice(["guiding the eye", "controlling pace", "creating contrast", "building atmosphere", "focusing attention"])
    sentences = []
    for tmpl in templates:
        s = tmpl.format(
            title=clean_title,
            technique=technique,
            effect=effect,
            insight=insight,
            principle=principle,
            mechanism=mechanism,
            emotion=random.choice(["tension", "melancholy", "awe", "dread", "hope", "irony"]),
            element=random.choice(["light", "shadow", "color", "movement", "sound", "silence"]),
            meaning=random.choice(["danger", "transformation", "memory", "loss", "power", "vulnerability"]),
            payoff=insight,
            craft=random.choice(["cinematography", "editing", "direction", "visual storytelling", "scene construction"]),
            summary=f"{technique} serving {effect}",
            color_lighting_composition=color_lighting_composition,
        )
        sentences.append(s)
    
    # Distribute across clip (start at 10%, middle, end at 85%)
    dur = clip_duration
    segments = [
        (sentences[0], dur * 0.10),
        (sentences[1], dur * 0.45),
        (sentences[2], dur * 0.80),
    ]
    return segments

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


def _generate_5beat_captions(title="", clip_duration=15, content_type="movie", hook_phrase=None):
    """Generate 5-beat caption sequence: hook → build → peak_signal → emotion_label → twist.
    Uses curiosity-gap hooks that trigger emotional reactions (WOW, WTF, OHH, YEAH).
    For long clips (>28s), adds intermediate beats for pacing.
    Content-aware: football vs movie/series get different text templates.
    If hook_phrase is provided (from vibe_of_the_day.pick_vibe()), it replaces the hardcoded hook.
    Returns (captions_list, tts_text).
    Each caption: (beat_type, text, start, end).
    tts_text is the hook text for voiceover (shorter, spoken version).
    """
    name = title[:35] if title else "this moment"
    climax = _estimate_climax(clip_duration)
    is_long = clip_duration > 28

    # Build hook text from vibe phrase if provided
    caps_hook = hook_phrase.upper().rstrip(".") + "..." if hook_phrase else None
    tts_hook = hook_phrase if hook_phrase else None

    if content_type == "football":
        beats = {
            "hook": caps_hook or "WATCH HOW HE DID THIS...",
            "hook_tts": tts_hook or "Watch how he did this",
            "build": "The pass was IMPOSSIBLE...",
            "build_mid": "Defenders left in the DUST." if is_long else None,
            "peak_signal": "BUT HE DID IT ANYWAY",
            "emotion_label": "ABSOLUTE MADMAN",
            "twist": "This is why they call him magic.",
            "twist_end": "History made." if is_long else None,
        }
    elif content_type == "series":
        beats = {
            "hook": caps_hook or "SHE DIDN'T SEE THIS COMING",
            "hook_tts": tts_hook or "She didn't see this coming",
            "build": "Episodes of build-up lead to THIS...",
            "build_mid": "The warning signs were there." if is_long else None,
            "peak_signal": "THIS CHANGES EVERYTHING",
            "emotion_label": "TRUST NO ONE",
            "twist": "The best plot twist on television.",
            "twist_end": "You'll never watch it the same way." if is_long else None,
        }
    else:  # movie
        beats = {
            "hook": caps_hook or "THEY HAD NO IDEA...",
            "hook_tts": tts_hook or "They had no idea",
            "build": f"{name[:20]} is about to strike...",
            "build_mid": f"One wrong move and it's over." if is_long else None,
            "peak_signal": "THIS IS THE MOMENT",
            "emotion_label": "NO WAY",
            "twist": "The ending changes EVERYTHING.",
            "twist_end": "Absolute cinema." if is_long else None,
        }

    captions = []
    captions.append(("hook", beats["hook"], 0.0, 1.2))

    if is_long:
        captions.append(("build", beats["build"], max(1.5, clip_duration * 0.10), max(1.5, clip_duration * 0.10) + 1.8))
        if beats["build_mid"]:
            mid_start = clip_duration * 0.30
            captions.append(("build", beats["build_mid"], mid_start, mid_start + 2.0))
    else:
        build_start = clip_duration * 0.20
        captions.append(("build", beats["build"], build_start, build_start + 2.0))

    peak_start = max(0, climax - 1.5)
    captions.append(("peak_signal", beats["peak_signal"], peak_start, peak_start + 1.5))

    emotion_start = min(climax + 0.5, clip_duration - 1.5)
    captions.append(("emotion_label", beats["emotion_label"], emotion_start, min(emotion_start + 1.5, clip_duration)))

    twist_start = clip_duration * 0.80 if is_long else clip_duration * 0.85
    captions.append(("twist", beats["twist"], twist_start, min(twist_start + 2.0, clip_duration - 0.3)))

    if is_long and beats["twist_end"]:
        end_start = clip_duration * 0.92
        captions.append(("twist", beats["twist_end"], end_start, min(end_start + 2.0, clip_duration - 0.2)))

    cta_start = max(clip_duration - 3.0, clip_duration * 0.85)
    cta_options = [
        "What do you think? \\NSubscribe for more \\N🔥👇",
        "Comment below 👇 \\NSubscribe 🔔",
        "Would you try this? \\N👇 Comment \\NSubscribe 🔔",
        "Rate this 1-10 👇 \\NSubscribe for daily clips 🔔",
    ]
    import random as _r
    captions.append(("cta", _r.choice(cta_options), cta_start, clip_duration))

    return captions, beats["hook_tts"]


def _write_ass(captions, ass_path, caption_style="bold_center"):
    """Write 5-beat captions to ASS subtitle file — supports 5 style sets.

    Styles (from vibe_of_the_day.pick_vibe()):
      bold_center      — current default: Arial bold, center-screen, stacked-caps
      serif_top        — Georgia serif, top-third placement, italic peak
      glitch_mono      — Courier New mono, color cycling on Peak, random blink on emotion
      typewriter_reveal — thin Arial, staggered late starts for reveal effect
      marker_circle    — Arial bold at bottom, circle-boxed, smaller font
    """
    style_header = ""
    alignment_base = 5  # center
    margin_v_base = 300

    if caption_style == "bold_center":
        style_header = (
            "Style: Hook,Arial,72,&H00FFFFFF,&H00FFFF00,&H00000000,&H80000000,1,0,0,0,100,100,10,0,1,4,2,5,0,0,400,1\n"
            "Style: Build,Arial,48,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,1,0,0,0,100,100,5,0,1,3,1,5,0,0,350,1\n"
            "Style: Peak,Arial,64,&H00FFFF00,&H00FF4444,&H00000000,&H80000000,1,0,0,0,100,100,10,0,1,4,2,5,0,0,300,1\n"
            "Style: Emotion,Arial,52,&H00FF8800,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,5,0,1,3,1,5,0,0,320,1\n"
            "Style: Twist,Arial,44,&H00FFFFFF,&H00FF44FF,&H00000000,&H80000000,1,0,0,0,100,100,5,0,1,3,1,5,0,0,350,1\n"
            "Style: CTA,Arial,40,&H00FFFFFF,&H00FF4444,&H00000000,&H80000000,1,0,0,0,100,100,5,0,1,3,1,2,0,0,100,1\n"
        )
    elif caption_style == "serif_top":
        style_header = (
            "Style: Hook,Georgia,68,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,0,1,0,0,100,100,6,0,1,3,1,8,0,0,100,1\n"
            "Style: Build,Georgia,44,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,0,1,0,0,100,100,3,0,1,2,1,8,0,0,120,1\n"
            "Style: Peak,Georgia,60,&H00FFFF00,&H00FF4444,&H00000000,&H80000000,0,1,0,0,100,100,8,0,1,3,1,8,0,0,100,1\n"
            "Style: Emotion,Georgia,48,&H00FF8800,&H00FFFFFF,&H00000000,&H80000000,0,1,0,0,100,100,3,0,1,2,1,8,0,0,110,1\n"
            "Style: Twist,Georgia,40,&H00FFFFFF,&H00FF44FF,&H00000000,&H80000000,0,1,0,0,100,100,3,0,1,2,1,8,0,0,130,1\n"
            "Style: CTA,Georgia,36,&H00FFFFFF,&H00FF4444,&H00000000,&H80000000,0,1,0,0,100,100,3,0,1,2,1,2,0,0,80,1\n"
        )
    elif caption_style == "glitch_mono":
        style_header = (
            "Style: Hook,Courier New,68,&H00FFFFFF,&H0000FF00,&H00000000,&H80000000,1,0,0,0,100,100,8,0,1,3,1,5,0,0,300,1\n"
            "Style: Build,Courier New,44,&H00C0C0C0,&H0000FF00,&H00000000,&H80000000,1,0,0,0,100,100,3,0,1,2,1,5,0,0,280,1\n"
            "Style: Peak,Courier New,56,&H0030FF30,&H00FF00FF,&H00000000,&H80000000,1,0,0,0,100,100,9,0,1,3,1,5,0,0,260,1\n"
            "Style: Emotion,Courier New,48,&H00FF4488,&H0030FF30,&H00000000,&H80000000,1,0,0,0,100,100,3,0,1,2,1,5,0,0,290,1\n"
            "Style: Twist,Courier New,40,&H00C0C0C0,&H00FF00FF,&H00000000,&H80000000,1,0,0,0,100,100,3,0,1,2,1,5,0,0,310,1\n"
            "Style: CTA,Courier New,36,&H00FFFFFF,&H0030FF30,&H00000000,&H80000000,1,0,0,0,100,100,3,0,1,2,1,2,0,0,100,1\n"
        )
    elif caption_style == "typewriter_reveal":
        # Smaller fonts with left-alignment — text appears letter-by-letter (done via timing)
        style_header = (
            "Style: Hook,Arial,56,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,12,0,1,2,1,4,0,0,320,1\n"
            "Style: Build,Arial,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,8,0,1,2,1,4,0,0,300,1\n"
            "Style: Peak,Arial,50,&H00FFFF88,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,12,0,1,2,1,4,0,0,280,1\n"
            "Style: Emotion,Arial,42,&H00FFCC88,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,8,0,1,2,1,4,0,0,300,1\n"
            "Style: Twist,Arial,36,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,8,0,1,2,1,4,0,0,310,1\n"
            "Style: CTA,Arial,32,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,8,0,1,2,1,2,0,0,100,1\n"
        )
    elif caption_style == "marker_circle":
        # Bold bottom placement, smaller font, boxed with rounded-marker feel via thick border
        style_header = (
            "Style: Hook,Arial,58,&H00FFFFFF,&H00FF8800,&H00000000,&H80000000,1,0,0,0,100,100,6,0,3,4,2,2,0,0,600,1\n"
            "Style: Build,Arial,40,&H00FFFFFF,&H00FF8800,&H00000000,&H80000000,1,0,0,0,100,100,3,0,3,3,1,2,0,0,580,1\n"
            "Style: Peak,Arial,52,&H00FFFF44,&H00FF4400,&H00000000,&H80000000,1,0,0,0,100,100,6,0,3,4,2,2,0,0,560,1\n"
            "Style: Emotion,Arial,44,&H00FFCC00,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,3,0,3,3,1,2,0,0,580,1\n"
            "Style: Twist,Arial,36,&H00FFFFFF,&H00FF8800,&H00000000,&H80000000,1,0,0,0,100,100,3,0,3,3,1,2,0,0,600,1\n"
            "Style: CTA,Arial,32,&H00FFFFFF,&H00FF4400,&H00000000,&H80000000,1,0,0,0,100,100,3,0,3,3,1,2,0,0,580,1\n"
        )

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    ]
    # Append style lines (strip trailing newline then split so we don't get blank lines)
    for s in style_header.strip().split("\n"):
        lines.append(s)
    lines += [
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    def _ts(sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = sec % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    style_map = {"hook": "Hook", "build": "Build", "peak_signal": "Peak", "emotion_label": "Emotion", "twist": "Twist", "cta": "CTA"}

    for idx, (beat_type, text, start, end) in enumerate(captions, 1):
        style = style_map.get(beat_type, "Build")
        lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},{style},,0,0,0,,{text}")

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _get_wav_duration(wav_path):
    """Get duration of a WAV file in seconds."""
    import wave as _w
    try:
        with _w.open(wav_path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / rate if rate > 0 else 0
    except Exception:
        return 0


def add_sound_design(input_path, output_path, duration, hook_tts_path=None, analysis_tts_path=None, original_audio_path=None):
    """Add sound design to video: tension riser, sub-bass impact, ambient bed, TTS hook voiceover.
    COMPLETELY STRIPS ORIGINAL AUDIO — replaces with generated SFX + pitched TTS to evade Content ID.
    Random pitch shift (±3-5 semitones) breaks audio fingerprint matching.

    If `original_audio_path` is provided, a low-volume (7%) copy of the source
    audio is pitch-shifted and mixed under the new audio design — gives the
    cinematic feel of the original scene without dominating the voiceover.
    """
    import struct
    import shutil
    import random
    if duration <= 2:
        return _strip_audio_add_sfx(input_path, output_path, duration, hook_tts_path)

    _orig_input = input_path
    import wave as _wave
    sr = 48000
    n = int(duration * sr)
    math_mod = __import__('math')

    # Random pitch shift for Content ID evasion: ±2 to ±3 semitones
    # (was ±3-5; reduced for more natural voice — original audio is now primary
    # at 65% volume, so heavy pitch shift would make it sound unnatural)
    pitch_shift_semitones = random.uniform(-3, -2) if random.random() < 0.5 else random.uniform(2, 3)
    pitch_ratio = 2 ** (pitch_shift_semitones / 12.0)
    print(f"  [sound] Content ID evasion: pitch shift {pitch_shift_semitones:.1f} semitones (ratio {pitch_ratio:.3f})", flush=True)

    # Build SFX sample array (mono)
    # Phase 2 fix: replaced sine sweep (150→800Hz, felt "accelerating") with
    # constant 80Hz sub-bass + noise-burst impact. Sub-bass adds weight without
    # the "speed-up" perception; noise burst replaces pure sine impact for
    # more cinematic feel.
    climax = duration * 0.70
    riser_start = max(0, climax - 1.5)
    samples = [0.0] * n

    for i in range(n):
        t = i / sr
        if t < duration:
            if riser_start <= t <= climax:
                # Constant sub-bass (no sweep — was triggering "accelerating" perception)
                samples[i] += 0.10 * math_mod.sin(2 * 3.14159 * 80 * t)
            elif climax < t <= climax + 0.3:
                # Noise burst impact (was: 0.25 * sin(50Hz) — too synthetic)
                noise = (math_mod.sin(t * 1234.5) + math_mod.sin(t * 567.8)) * 0.5
                samples[i] += 0.18 * noise
            else:
                # Ambient drone (no sweep — was: 60Hz + 120Hz sine, too clean)
                samples[i] += 0.010 * math_mod.sin(2 * 3.14159 * 60 * t)
                samples[i] += 0.005 * math_mod.sin(2 * 3.14159 * 95 * t)

    peak = max(abs(max(samples)), abs(min(samples)), 0.001)
    scale = min(1.0 / peak, 1.0)
    scaled = [int(max(-32768, min(32767, s * scale * 32767))) for s in samples]

    sfx_path = os.path.join(os.path.dirname(output_path), "_sfx.wav")
    with _wave.open(sfx_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for s in scaled:
            wf.writeframes(struct.pack("<h", s))

    if not os.path.exists(sfx_path) or os.path.getsize(sfx_path) < 200:
        print(f"  [sound] SFX generation produced no output", flush=True)
        return _strip_audio_add_sfx(input_path, output_path, duration, hook_tts_path)

    # Prepare TTS with pitch shift
    tts_final_path = None
    if hook_tts_path and os.path.exists(hook_tts_path) and os.path.getsize(hook_tts_path) > 200:
        tts_final_path = os.path.join(os.path.dirname(output_path), "_tts_pitched.wav")
        tts_pitch_cmd = [
            _FFMPEG_BIN, "-y", "-i", hook_tts_path,
            "-af", f"asetrate=44100*{pitch_ratio},aresample=44100,atempo={1/pitch_ratio}",
            "-ac", "1",
            tts_final_path,
        ]
        try:
            subprocess.run(tts_pitch_cmd, capture_output=True, timeout=30)
            if not (os.path.exists(tts_final_path) and os.path.getsize(tts_final_path) > 200):
                tts_final_path = hook_tts_path
        except Exception:
            tts_final_path = hook_tts_path

    # Pitch-shift SFX
    sfx_pitched = os.path.join(os.path.dirname(output_path), "_sfx_pitched.wav")
    sfx_pitch_cmd = [
        _FFMPEG_BIN, "-y", "-i", sfx_path,
        "-af", f"asetrate=48000*{pitch_ratio},aresample=48000,atempo={1/pitch_ratio}",
        sfx_pitched,
    ]
    try:
        subprocess.run(sfx_pitch_cmd, capture_output=True, timeout=30)
        if os.path.exists(sfx_pitched) and os.path.getsize(sfx_pitched) > 200:
            sfx_path = sfx_pitched
    except Exception:
        pass

    # Generate ambient bed — brown noise + lowpass + reverb (warmer than pink;
    # gives the "cinematic" bed feel without drowning the original audio)
    bed_path = os.path.join(os.path.dirname(output_path), "_bed.wav")
    bed_cmd = [
        _FFMPEG_BIN, "-y",
        "-f", "lavfi", "-i",
        f"anoisesrc=d={duration}:c=brown:a=0.20,lowpass=f=400,volume=0.35,aecho=0.8:0.9:500:0.3",
        "-ar", "48000", "-ac", "1",
        bed_path,
    ]
    try:
        subprocess.run(bed_cmd, capture_output=True, timeout=15)
        if not (os.path.exists(bed_path) and os.path.getsize(bed_path) > 200):
            bed_path = None
    except Exception:
        bed_path = None

    # Phase 1 fix: extract original audio from source, apply same pitch shift,
    # and bake in 7% volume. This restores cinematic feel without Content ID
    # risk (pitch shift is the same evasion as TTS/SFX).
    orig_shifted_path = None
    if original_audio_path and os.path.exists(original_audio_path):
        work_dir = os.path.dirname(output_path)
        src_audio = os.path.join(work_dir, "_src_audio.wav")
        # Extract mono audio from source video
        extract_cmd = [
            _FFMPEG_BIN, "-y", "-i", original_audio_path,
            "-vn", "-ac", "1", "-ar", "48000",
            "-t", str(duration),
            src_audio,
        ]
        try:
            r = subprocess.run(extract_cmd, capture_output=True, timeout=30)
            if r.returncode == 0 and os.path.exists(src_audio) and os.path.getsize(src_audio) > 200:
                # Apply pitch shift + 65% volume (primary cinematic layer).
                # Audio strategy pivot: original movie audio is now the dominant
                # sound (was 7% background); TTS becomes commentary overlay.
                orig_shifted_path = os.path.join(work_dir, "_orig_shifted.wav")
                shift_cmd = [
                    _FFMPEG_BIN, "-y", "-i", src_audio,
                    "-af", f"asetrate=48000*{pitch_ratio},aresample=48000,atempo={1/pitch_ratio},volume=0.65",
                    "-ar", "48000", "-ac", "1",
                    orig_shifted_path,
                ]
                r2 = subprocess.run(shift_cmd, capture_output=True, timeout=30)
                if r2.returncode != 0 or not (os.path.exists(orig_shifted_path) and os.path.getsize(orig_shifted_path) > 200):
                    orig_shifted_path = None
                else:
                    print(f"  [sound] Original audio layered at 65% (pitch-shifted for Content ID evasion)", flush=True)
        except Exception as e:
            print(f"  [sound] Original audio extraction failed: {e}", flush=True)
            orig_shifted_path = None

    # ── Two-pass audio mix (محور 1+2 fix) ──
    # Pass 1: mix all audio sources into a single WAV using filter_complex
    # Pass 2: mux video (stream copy) + mixed audio (AAC encode)
    # This avoids the "-c:v copy + filter_complex" conflict that caused
    # "Streamcopy requested for output stream fed from a complex filtergraph" errors.

    work_dir = os.path.dirname(output_path)
    mixed_audio_path = os.path.join(work_dir, "_mixed_audio.wav")

    # Define audio source flags BEFORE mix logic
    has_tts = tts_final_path and os.path.exists(tts_final_path) and os.path.getsize(tts_final_path) > 200
    tts_dur = _get_wav_duration(tts_final_path) if has_tts else 0

    has_analysis = analysis_tts_path and os.path.exists(analysis_tts_path) and os.path.getsize(analysis_tts_path) > 200
    analysis_dur = _get_wav_duration(analysis_tts_path) if has_analysis else 0

    # Build audio-only mix inputs and filter
    audio_inputs = []
    audio_filter_parts = []
    audio_idx = 0

    # Original audio PRIMARY (65% baked into pitch-shifted file, 0.85 in mix for headroom)
    if orig_shifted_path:
        audio_inputs.extend(["-i", orig_shifted_path])
        audio_filter_parts.append(f"[{audio_idx}:a]volume=0.85[a{audio_idx}]")
        audio_idx += 1

    # TTS voiceover (30% — commentary level over original)
    if has_tts:
        audio_inputs.extend(["-i", tts_final_path])
        audio_filter_parts.append(f"[{audio_idx}:a]volume=0.30[a{audio_idx}]")
        audio_idx += 1

    # SFX subtle (5% — original audio carries cinematic weight)
    audio_inputs.extend(["-i", sfx_path])
    audio_filter_parts.append(f"[{audio_idx}:a]volume=0.05[a{audio_idx}]")
    audio_idx += 1

    # Analysis narration (30% — voiceover level)
    if has_analysis:
        audio_inputs.extend(["-i", analysis_tts_path])
        delay_ms = int(tts_dur * 1000)
        audio_filter_parts.append(f"[{audio_idx}:a]adelay={delay_ms}|{delay_ms},volume=0.30[a{audio_idx}]")
        audio_idx += 1

    # Ambient bed (8% — warmth)
    if bed_path:
        audio_inputs.extend(["-i", bed_path])
        audio_filter_parts.append(f"[{audio_idx}:a]volume=0.08[a{audio_idx}]")
        audio_idx += 1

    if audio_idx == 0:
        # No audio sources at all — fallback
        print(f"  [sound] No audio sources, stripping audio", flush=True)
        return _strip_audio_add_sfx(input_path, output_path, duration, hook_tts_path)

    # Combine all audio sources
    audio_indices = list(range(audio_idx))
    amix_inputs = "".join(f"[a{i}]" for i in audio_indices)
    nb_audio = len(audio_indices)
    audio_filter_parts.append(f"{amix_inputs}amix=inputs={nb_audio}:duration=longest[a_mixed]")

    # Pass 1: mix audio to WAV
    mix_audio_cmd = [
        _FFMPEG_BIN, "-y",
    ] + audio_inputs + [
        "-filter_complex", ";".join(audio_filter_parts),
        "-map", "[a_mixed]",
        "-ar", "48000", "-ac", "2",
        mixed_audio_path,
    ]

    try:
        result = subprocess.run(mix_audio_cmd, capture_output=True, timeout=60)
        if result.returncode != 0 or not (os.path.exists(mixed_audio_path) and os.path.getsize(mixed_audio_path) > 200):
            err = result.stderr[-300:].decode("utf-8", errors="replace") if result.stderr else "no stderr"
            print(f"  [sound] Audio mix failed: {err}", flush=True)
            return _strip_audio_add_sfx(input_path, output_path, duration, hook_tts_path)
    except Exception as e:
        print(f"  [sound] Audio mix error: {e}", flush=True)
        return _strip_audio_add_sfx(input_path, output_path, duration, hook_tts_path)

    # Pass 2: mux video (copy) + mixed audio (AAC)
    mux_cmd = [
        _FFMPEG_BIN, "-y",
        "-i", input_path,
        "-i", mixed_audio_path,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-map", "0:v", "-map", "1:a",
        "-shortest",
        output_path,
    ]

    try:
        result = subprocess.run(mux_cmd, capture_output=True, timeout=60)
        if result.returncode != 0:
            err = result.stderr[-300:].decode("utf-8", errors="replace") if result.stderr else "no stderr"
            print(f"  [sound] Mux failed: {err}", flush=True)
            return _strip_audio_add_sfx(input_path, output_path, duration, hook_tts_path)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            label = "pitched SFX"
            if has_tts: label += " + pitched TTS"
            if has_analysis: label += " + analysis narration"
            if orig_shifted_path: label += " + original audio (65%)"
            print(f"  [sound] Sound design applied ({label})", flush=True)
            return output_path
        else:
            print(f"  [sound] Mix failed, stripping audio and adding SFX only", flush=True)
            return _strip_audio_add_sfx(input_path, output_path, duration, hook_tts_path)
    except Exception as e:
        print(f"  [sound] Mix error: {e}, stripping audio", flush=True)
        return _strip_audio_add_sfx(input_path, output_path, duration, hook_tts_path)
    finally:
        for p in [sfx_path, tts_final_path, mixed_audio_path]:
            try:
                if p and os.path.exists(p):
                    os.unlink(p)
            except Exception:
                pass


def _strip_audio_add_sfx(input_path, output_path, duration, hook_tts_path=None):
    """Fallback: strip audio track, add only generated SFX (+ TTS if available)."""
    try:
        # Generate minimal SFX
        import wave as _wave
        import struct as _struct
        import math as _math
        sr = 48000
        n = int(duration * sr)
        samples = [0.0] * n
        climax = duration * 0.70
        riser_start = max(0, climax - 1.5)
        for i in range(n):
            t = i / sr
            if t < duration:
                if riser_start <= t <= climax:
                    freq = 150 + 650 * (t - riser_start) / 1.5
                    samples[i] += 0.12 * _math.sin(2 * 3.14159 * freq * t)
                elif climax < t <= climax + 0.3:
                    samples[i] += 0.25 * _math.sin(2 * 3.14159 * 50 * t)
                else:
                    samples[i] += 0.015 * _math.sin(2 * 3.14159 * 60 * t)
                    samples[i] += 0.008 * _math.sin(2 * 3.14159 * 120 * t)
        peak = max(abs(max(samples)), abs(min(samples)), 0.001)
        scale = min(1.0 / peak, 1.0)
        scaled = [int(max(-32768, min(32767, s * scale * 32767))) for s in samples]
        sfx_path = os.path.join(os.path.dirname(output_path), "_sfx_fb.wav")
        with _wave.open(sfx_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            for s in scaled:
                wf.writeframes(_struct.pack("<h", s))

        # Pitch shift SFX
        pitch_shift = random.uniform(-5, -3) if random.random() < 0.5 else random.uniform(3, 5)
        pitch_ratio = 2 ** (pitch_shift / 12.0)
        sfx_pitched = os.path.join(os.path.dirname(output_path), "_sfx_fb_pitched.wav")
        sfx_pitch_cmd = [
            _FFMPEG_BIN, "-y", "-i", sfx_path,
            "-af", f"asetrate=48000*{pitch_ratio},aresample=48000,atempo={1/pitch_ratio}",
            sfx_pitched,
        ]
        subprocess.run(sfx_pitch_cmd, capture_output=True, timeout=30)
        if os.path.exists(sfx_pitched) and os.path.getsize(sfx_pitched) > 200:
            sfx_path = sfx_pitched

        # Build mix command
        has_tts = hook_tts_path and os.path.exists(hook_tts_path) and os.path.getsize(hook_tts_path) > 200
        if has_tts:
            tts_pitched = os.path.join(os.path.dirname(output_path), "_tts_fb_pitched.wav")
            tts_pitch_cmd = [
                _FFMPEG_BIN, "-y", "-i", hook_tts_path,
                "-af", f"asetrate=44100*{pitch_ratio},aresample=44100,atempo={1/pitch_ratio}",
                "-ac", "1", tts_pitched,
            ]
            subprocess.run(tts_pitch_cmd, capture_output=True, timeout=30)
            if os.path.exists(tts_pitched) and os.path.getsize(tts_pitched) > 200:
                tts_path = tts_pitched
            else:
                tts_path = hook_tts_path
            tts_dur = _get_wav_duration(tts_path)
            sfx_vol = f"volume='if(between(t,0,{tts_dur}),0.08,0.35)':eval=frame"
            mix_cmd = [
                _FFMPEG_BIN, "-y", "-i", tts_path, "-i", sfx_path,
                "-filter_complex",
                f"[1:a]{sfx_vol}[sfx_ducked];[0:a][sfx_ducked]amix=inputs=2:duration=first:weights=1 1.5[a_mixed]",
                "-map", "0:v", "-map", "[a_mixed]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", output_path,
            ]
        else:
            mix_cmd = [
                _FFMPEG_BIN, "-y", "-i", input_path, "-i", sfx_path,
                "-filter_complex",
                "[1:a]volume=0.35[sfx_v];[0:v]copy[v];[sfx_v]anull[a]",
                "-map", "[v]", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", output_path,
            ]

        subprocess.run(mix_cmd, capture_output=True, timeout=60)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            print(f"  [sound] Fallback applied: original audio stripped, SFX only", flush=True)
            return output_path
    except Exception as e:
        print(f"  [sound] Fallback error: {e}", flush=True)
    return input_path


def _build_zoom_expr(zoom_name, duration):
    """Build an ffmpeg zoom expression for the named zoom curve.

    Curves from vibe_of_the_day.pick_vibe():
      ease_in_aggressive — hook punch 1.05→1.20 over 3s, then settle at 1.03
      steady_build       — gentle 1.08→1.15 over 4s, continuous drift
      punch_cut          — instant 1.00→1.18 at 1.5s mark, then hold

    Returns an ffmpeg-compatible expression string.
    """
    base = "1.0"

    if zoom_name == "ease_in_aggressive":
        return (
            f"(1.05"
            f" + 0.15*max(0,1-t/3.0)"               # punch over 3s
            f" + 0.04*max(0,t-1.5)/{max(duration,0.1)}" # slow drift
            f" - 0.02*(1/(1+10*max(0,t-3))))"      # settle (was: {1/(1+10*max(0,t-3))} — Python evaluated at f-string time)
        )
    elif zoom_name == "steady_build":
        return (
            f"(1.08"
            f" + 0.07*min(t/4.0,1)"                 # linear build over 4s
            f" + 0.03*max(0,t-2)/{max(duration,0.1)}" # slow drift after 2s
            f")"
        )
    elif zoom_name == "punch_cut":
        # Instant punch at 1.5s: scale snaps from 1.00 to 1.18
        # Use smoothstep instead of nested if for encoder compatibility
        return (
            f"1.0 + 0.18 * max(0, min(1, (t-1.5)*10)) * (1 - min(1, max(0, (t-1.6)*10)))"
            f" + 0.12 * max(0, 1 - (t-1.6)/5.0)"  # slow settle
        )
    else:
        # Fallback: classic hook punch + micro-pulses (current default)
        pulse_t1 = duration * 0.30
        pulse_t2 = duration * 0.60
        return (
            f"(1.0"
            f" + 0.15*max(0,1-t/0.3)"
            f" + 0.06*max(0,1-abs(t-{pulse_t1})/0.2)"
            f" + 0.06*max(0,1-abs(t-{pulse_t2})/0.2)"
            f" + 0.04*max(0,t-1.5)/{max(duration,0.1)})"
        )


def apply_movie_effects(input_path, output_path, content_type, title="", vibe=None):
    """Apply effects to a short: dynamic zoom, ASS captions, TTS voiceover hook.

    vibe dict (from vibe_of_the_day.pick_vibe()) controls:
      hook    → caption opener + TTS spoken text
      caption → ASS style set (bold_center, serif_top, glitch_mono, typewriter_reveal, marker_circle)
      zoom    → zoom curve (ease_in_aggressive, steady_build, punch_cut)
      color   → color profile filter injected into filter_complex (teal_orange, warm_sunset, cool_noir)
      patterns → pattern interrupts (stubbed for now — wired as placeholder)

    Returns dict with path, duration, hook_text (for sound design mixing).
    """
    duration = get_video_duration(input_path)
    if duration <= 0:
        return None

    vibe = vibe or {}
    hook_phrase = vibe.get("hook")
    caption_style = vibe.get("caption", "bold_center")
    zoom_name = vibe.get("zoom", "ease_in_aggressive")
    color_name = vibe.get("color")
    color_intensity = vibe.get("color_intensity", 1.0)

    import uuid
    import tempfile
    ass_file = tempfile.NamedTemporaryFile(suffix=".ass", delete=False, mode="w", encoding="utf-8")
    ass_path = ass_file.name
    ass_file.close()
    captions, hook_tts = _generate_5beat_captions(title, clip_duration=duration, content_type=content_type, hook_phrase=hook_phrase)
    _write_ass(captions, ass_path, caption_style=caption_style)
    print(f"  [vibe] Caption style: {caption_style} | Hook: {hook_tts}", flush=True)

    # Generate TTS WAV for hook voiceover — use voice_studio for best quality
    work_dir = os.path.dirname(output_path)
    tts_path = os.path.join(work_dir, "_hook_tts.wav")
    # voice_studio: gTTS (natural) → edge-tts (fallback) + audio processing
    from modules.voice_studio import generate_hook_voice
    tts_ok = generate_hook_voice(hook_tts, tts_path, process=True)
    if not tts_ok:
        # Fallback to edge-tts
        tts_ok = _generate_tts_wav(hook_tts, tts_path)
    if tts_ok:
        print(f"  [tts] Hook voiceover generated: \"{hook_tts}\"", flush=True)
    else:
        print(f"  [tts] Hook voiceover failed, continuing without", flush=True)

    # Zoom curve expression
    zoom_expr = _build_zoom_expr(zoom_name, duration)
    print(f"  [vibe] Zoom curve: {zoom_name}", flush=True)

    # Micro-shake on pulse points (30% / 60% of duration)
    pulse_t1 = duration * 0.30
    pulse_t2 = duration * 0.60
    shake_expr = (
        f"12*sin(12*PI*t)*exp(-3*abs(t-{pulse_t1}))"
        f" + 12*sin(15*PI*t)*exp(-3*abs(t-{pulse_t2}))"
    )

    # Color profile: inject into filter chain if named
    color_part = ""
    if color_name:
        try:
            from modules.color_profiles import get_filter_string
            color_part = get_filter_string(color_name, color_intensity) + ","
            print(f"  [vibe] Color profile: {color_name} (intensity {color_intensity})", flush=True)
        except Exception:
            pass

    # Pattern interrupts (placeholder — ASS handles text; video-level glitch
    # stubs will be added in a future pass via ffmpeg tpad/edgedetect/hue changes)
    if vibe.get("patterns"):
        print(f"  [vibe] Pattern set selected: {vibe['patterns']} (stub — not applied to video yet)", flush=True)

    # Content ID Evasion: Visual Fingerprint Break
    # 1. Micro-noise (1%) — breaks exact pixel hash
    # 2. Micro-crop 2% — breaks spatial alignment
    # 3. Color jitter ±0.02 — breaks color histogram hash
    # 4. GOP randomization — breaks frame-sequence hash
    # 5. Slight zoom 1.02x — breaks scale fingerprint
    fid = random.randint(1000, 9999)
    noise_seed = fid * 7
    crop_x = f"2*sin(t*{noise_seed}*0.01)"  # micro jitter
    crop_y = f"2*cos(t*{noise_seed}*0.013)"
    color_jitter = f"eq=brightness={random.uniform(-0.015,0.015):.4f}:contrast={1+random.uniform(-0.02,0.02):.4f}:saturation={1+random.uniform(-0.02,0.02):.4f}"
    # Micro-zoom 1.02x + crop to hide edges
    evasion_zoom = "1.02"

    # ── Mirevon-style Fast Cuts + Montage: single-pass with filter_complex ──
    # Key insight: crop_to_shorts uses filter_complex with BOTH video and audio outputs
    # and maps both [vout] and [aout] — this works. We do the same here.
    # Mirevon style: rapid cuts every ~2.5s, micro-zoom punches via dynamic crop.

    zoom_factor = 1.02
    
    # Build video filter chain with Mirevon-style dynamics
    vf_parts = [
        f"scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=0",
        "setsar=1",
        f"scale=trunc(iw*{zoom_factor}/2)*2:trunc(ih*{zoom_factor}/2)*2:flags=lanczos",
        f"crop={SHORTS_WIDTH}:{SHORTS_HEIGHT}:(iw-{SHORTS_WIDTH})/2:(ih-{SHORTS_HEIGHT})/2",
    ]
    
    # Mirevon-style: dynamic zoom punches using crop with time-based expressions
    # This creates the "fast cuts + zoom punch" effect without zoompan
    # We use multiple crop stages with between(t,start,end) for punch-in/out
    # Base crop (centered)
    base_crop_x = f"(iw-{SHORTS_WIDTH})/2"
    base_crop_y = f"(ih-{SHORTS_HEIGHT})/2"
    
    # Add micro-zoom punches at 30% and 60% of duration
    punch_t1 = duration * 0.30
    punch_t2 = duration * 0.60
    punch_dur = 0.5  # 0.5s punch duration
    punch_zoom = 1.15  # 15% zoom-in for punch
    
    # Dynamic crop: zoom in at punch points, with micro-jitter
    # crop=w:h:x:y where w,h = zoomed size, x,y = centered
    # We chain multiple crop filters with enable=between(t,start,end)
    vf_parts.append(
        f"crop="
        f"'{SHORTS_WIDTH}*if(between(t,{punch_t1},{punch_t1+punch_dur}),{punch_zoom},1)':"
        f"'{SHORTS_HEIGHT}*if(between(t,{punch_t1},{punch_t1+punch_dur}),{punch_zoom},1)':"
        f"'(iw-ow)/2+2*sin(t*7):(ih-oh)/2+2*cos(t*13)'"
    )
    vf_parts.append(
        f"crop="
        f"'{SHORTS_WIDTH}*if(between(t,{punch_t2},{punch_t2+punch_dur}),{punch_zoom},1)':"
        f"'{SHORTS_HEIGHT}*if(between(t,{punch_t2},{punch_t2+punch_dur}),{punch_zoom},1)':"
        f"'(iw-ow)/2+2*sin(t*11):(ih-oh)/2+2*cos(t*17)'"
    )
    
    # Color grading + evasion
    vf_parts.extend([
        f"eq=brightness={random.uniform(-0.015,0.015):.4f}:contrast={1+random.uniform(-0.02,0.02):.4f}:saturation={1+random.uniform(-0.02,0.02):.4f}",
        "noise=alls=1:allf=t+u",
        "unsharp=5:5:0.8:3:3:0.4",
    ])

    # Add subtitles/captions if ass file exists
    if ass_path and os.path.exists(ass_path):
        escaped_path = ass_path.replace("\\", "/").replace(":", "\\:")
        vf_parts.append(f"subtitles='{escaped_path}'")

    video_chain = ",".join(vf_parts)

    # Audio pass-through (anull = pass through unchanged)
    filter_complex = (
        f"[0:v]{video_chain}[vout];"
        f"[0:a]anull[aout]"
    )

    gop_size = random.randint(12, 25)
    cmd = [
        _FFMPEG_BIN, "-y",
        "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", RENDER_CODEC, "-preset", RENDER_FINAL_PRESET, "-crf", str(RENDER_CRF),
        "-g", str(gop_size), "-keyint_min", "1", "-sc_threshold", "0",
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
            print(f"  [editor] Montage + captions applied ({caption_style}): {output_path} ({actual_dur:.1f}s, {os.path.getsize(output_path)} bytes)", flush=True)
            return {"path": output_path, "duration": actual_dur, "hook_text": hook_tts if tts_ok else None}
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
        # Clean up temp file
        try:
            if os.path.exists(video_only_path):
                os.unlink(video_only_path)
        except Exception:
            pass
        try:
            if ass_path and os.path.exists(ass_path):
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


def generate_chapter_markers(story_texts, video_duration, intro_duration=0):
    """
    Generate YouTube chapter markers from story text segments.
    
    Args:
        story_texts: List of (text, start_ratio) tuples
        video_duration: Total video duration in seconds
        intro_duration: Intro duration to offset (if any)
    
    Returns:
        List of (timestamp, title) for YouTube description chapters.
    """
    chapters = []
    for i, (text, ratio) in enumerate(story_texts):
        # Calculate timestamp
        timestamp = intro_duration + ratio * (video_duration - intro_duration)
        if timestamp < 0:
            timestamp = 0
        
        # Format: "0:00 Title" or "00:00:00 Title" for >1hr
        hours = int(timestamp // 3600)
        minutes = int((timestamp % 3600) // 60)
        seconds = int(timestamp % 60)
        
        if hours > 0:
            ts_str = f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            ts_str = f"{minutes}:{seconds:02d}"
        
        # Clean title for chapter
        title = text.replace("⚡ ", "").strip()
        if len(title) > 80:
            title = title[:77] + "..."
        
        chapters.append((ts_str, title))
    
    return chapters


def format_chapters_for_description(chapters):
    """Format chapters for YouTube description (timestamp Title format)."""
    lines = ["\nCHAPTERS:"]
    for ts, title in chapters:
        lines.append(f"{ts} {title}")
    return "\n".join(lines)


def generate_weekly_description(source_title, story_texts, video_duration, hooks=None):
    """
    Generate vidIQ-optimized description for weekly long-form video.
    
    Includes:
    - Hook-first opening (first 2 lines critical for CTR)
    - SEO keywords
    - Chapter markers
    - Hashtags
    - Call to action
    """
    movie_name = _extract_movie_name(source_title)
    chapters = generate_chapter_markers(story_texts, video_duration)
    
    # Hook-first description (first 2 lines = 125 chars visible in search)
    hook_line = hooks[0] if hooks else f"Why {movie_name} is a masterpiece of cinema"
    desc = f"{hook_line}\n\n"
    desc += f"A deep dive into {movie_name} — scene by scene analysis, cinematography breakdown, and the storytelling secrets that make it unforgettable.\n\n"
    
    # Chapters
    desc += format_chapters_for_description(chapters)
    desc += "\n\n"
    
    # SEO keywords
    desc += "KEYWORDS: "
    keywords = [
        f"{movie_name} analysis", f"{movie_name} breakdown", "film analysis",
        "cinema breakdown", "movie explained", "cinematography analysis",
        "film theory", "visual storytelling", "director style"
    ]
    desc += ", ".join(keywords) + "\n\n"
    
    # Hashtags
    desc += "#cinema #filmanalysis #moviedbreakdown #cinematography #filmtheory "
    desc += f"#{movie_name.replace(' ', '')} #VARY\n\n"
    
    # CTA
    desc += "🔔 Subscribe for a short every night, a long every week.\n"
    desc += "🎬 Suggest the next film in comments!\n"
    
    return desc


if __name__ == "__main__":
    # Test
    if len(sys.argv) > 1:
        result = create_clip(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "movie")
        print(json.dumps(result, indent=2, default=str) if result else "Failed")
