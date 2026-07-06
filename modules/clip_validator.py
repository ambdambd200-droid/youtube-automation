import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SHORTS_WIDTH, SHORTS_HEIGHT, CLIP_MIN_DURATION, CLIP_MAX_DURATION


def get_video_duration(video_path):
    import subprocess
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", video_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return float(result.stdout.strip())
    except Exception:
        return 0


def get_video_dimensions(video_path):
    import subprocess
    import json
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height", "-of", "json", video_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        data = json.loads(result.stdout)
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
