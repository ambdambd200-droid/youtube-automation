import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SHORTS_WIDTH, SHORTS_HEIGHT, CLIP_MIN_DURATION, CLIP_MAX_DURATION


WEEKLY_MIN_DURATION = 120     # 2 min minimum (avoid YouTube Shorts classification)
WEEKLY_MAX_DURATION = 480     # 8 min max (sync with clip_editor)
WEEKLY_MIN_WIDTH = 1280       # 720p minimum
WEEKLY_MIN_HEIGHT = 720


def _run_ffprobe(cmd):
    import subprocess
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return result.stdout.strip()
    except Exception:
        return ""


def get_video_duration(video_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", video_path]
    try:
        return float(_run_ffprobe(cmd))
    except (ValueError, TypeError):
        return 0


def get_video_dimensions(video_path):
    import json
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height", "-of", "json", video_path]
    raw = _run_ffprobe(cmd)
    if not raw:
        return (0, 0)
    try:
        data = json.loads(raw)
        streams = data.get("streams", [])
        if streams:
            s = streams[0]
            return (int(s["width"]), int(s["height"]))
    except Exception:
        pass
    return (0, 0)


def validate_short(video_path):
    dur = get_video_duration(video_path)
    w, h = get_video_dimensions(video_path)
    issues = []

    if dur < CLIP_MIN_DURATION:
        issues.append(f"duration {dur:.0f}s < {CLIP_MIN_DURATION}s")
    elif dur > CLIP_MAX_DURATION:
        issues.append(f"duration {dur:.0f}s > {CLIP_MAX_DURATION}s")

    if w != SHORTS_WIDTH or h != SHORTS_HEIGHT:
        issues.append(f"resolution {w}x{h} != {SHORTS_WIDTH}x{SHORTS_HEIGHT}")

    ratio = w / h if h > 0 else 0
    expected = SHORTS_WIDTH / SHORTS_HEIGHT
    if abs(ratio - expected) > 0.01:
        issues.append(f"aspect ratio {ratio:.4f} != {expected:.4f}")

    return (len(issues) == 0, issues)


def validate_weekly(video_path):
    dur = get_video_duration(video_path)
    w, h = get_video_dimensions(video_path)
    issues = []

    if dur < WEEKLY_MIN_DURATION:
        issues.append(f"duration {dur:.0f}s < {WEEKLY_MIN_DURATION}s (min for long-form)")
    if dur > WEEKLY_MAX_DURATION:
        issues.append(f"duration {dur:.0f}s > {WEEKLY_MAX_DURATION}s (max for long-form)")

    if w < WEEKLY_MIN_WIDTH or h < WEEKLY_MIN_HEIGHT:
        issues.append(f"resolution {w}x{h} < {WEEKLY_MIN_WIDTH}x{WEEKLY_MIN_HEIGHT} minimum")

    if w <= h:
        issues.append(f"portrait/square {w}x{h} — weekly must be landscape")

    ratio = w / h if h > 0 else 0
    if abs(ratio - 16/9) > 0.15 and abs(ratio - 4/3) > 0.15:
        issues.append(f"aspect ratio {ratio:.3f} not close to 16:9 or 4:3")

    return (len(issues) == 0, issues)
