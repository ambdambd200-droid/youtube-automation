"""
VARY Content Safety — NSFW filter for video clips.
Detects nudity and inappropriate clothing using:
  Layer 1: OpenCV HSV skin detection (always available)
  Layer 2: NudeNet ONNX (optional, if dependencies installed)

Returns (is_safe, reason) where is_safe=False if NSFW content detected.
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CLIPS_DIR

# HSV skin color ranges (tunable)
SKIN_LOWER_HSV = (0, 20, 60)
SKIN_UPPER_HSV = (20, 150, 255)
SKIN2_LOWER_HSV = (170, 20, 60)
SKIN2_UPPER_HSV = (180, 150, 255)

SKIN_EXPOSURE_THRESHOLD = 0.18       # 18%+ avg skin = likely NSFW
SKIN_PEAK_THRESHOLD = 0.25           # 25%+ on any frame = risky
SKIN_PEAK_MIN_FRAMES = 3             # need at least this many peak frames to block
SKIN_WARNING_THRESHOLD = 0.10        # 10-18% = borderline
SAFETY_SAMPLE_INTERVAL = 30          # sample every 30th frame (~1fps at 30fps)
SAFETY_MAX_FRAMES = 60               # max frames to check per video


def _find_ffmpeg():
    """Find ffmpeg executable."""
    candidates = [
        "ffmpeg",
        r"C:\Users\A\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe",
    ]
    # Try to find via WinGet directory
    try:
        base = r"C:\Users\A\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
        for d in os.listdir(base):
            if d.startswith("ffmpeg-") and d.endswith("-full_build"):
                exe = os.path.join(base, d, "bin", "ffmpeg.exe")
                if os.path.exists(exe):
                    candidates.insert(0, exe)
    except Exception:
        pass
    for c in candidates:
        try:
            r = subprocess.run([c, "-version"], capture_output=True, timeout=5)
            if r.returncode == 0:
                return c
        except Exception:
            continue
    return "ffmpeg"


def _extract_frames(video_path, output_dir, interval=15, max_frames=20):
    """Extract evenly-spaced frames from video using ffmpeg."""
    ffmpeg_bin = _find_ffmpeg()
    safe_path = video_path.replace(":", "").replace("'", "")
    if not os.path.exists(safe_path):
        safe_path = video_path

    # Use scene detection - take 1 frame per scene for better coverage
    cmd = [
        ffmpeg_bin, "-y", "-i", safe_path,
        "-vf", f"fps=1/{interval},scale=320:-1",
        "-frames:v", str(max_frames),
        "-q:v", "5",
        os.path.join(output_dir, "frame_%04d.jpg"),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=120)
        frames = sorted([
            os.path.join(output_dir, f)
            for f in os.listdir(output_dir)
            if f.startswith("frame_") and f.endswith(".jpg")
        ])
        return frames
    except Exception as e:
        print(f"  [safety] Frame extraction failed: {e}", flush=True)
        return []


def _skin_percentage(frame):
    """Calculate percentage of skin-colored pixels in frame."""
    import cv2
    import numpy as np
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, SKIN_LOWER_HSV, SKIN_UPPER_HSV)
    mask2 = cv2.inRange(hsv, SKIN2_LOWER_HSV, SKIN2_UPPER_HSV)
    mask = cv2.bitwise_or(mask1, mask2)
    skin_pixels = cv2.countNonZero(mask)
    total_pixels = frame.shape[0] * frame.shape[1]
    return skin_pixels / total_pixels if total_pixels > 0 else 0


def _check_skin_exposure(video_path):
    """Check skin exposure percentage across sampled frames."""
    try:
        import cv2
    except ImportError:
        print(f"  [safety] cv2 not installed — skipping skin check", flush=True)
        return True, ""

    work_dir = tempfile.mkdtemp()
    try:
        frames = _extract_frames(video_path, work_dir, interval=5, max_frames=SAFETY_MAX_FRAMES)
        if not frames:
            print(f"  [safety] No frames extracted — skipping skin check", flush=True)
            return True, ""

        scores = []
        for f in frames:
            img = cv2.imread(f)
            if img is None:
                continue
            pct = _skin_percentage(img)
            scores.append(pct)

        if not scores:
            return True, ""

        avg_skin = sum(scores) / len(scores)
        max_skin = max(scores)
        peak_frames = sum(1 for s in scores if s >= SKIN_PEAK_THRESHOLD)
        print(f"  [safety] Skin exposure: avg={avg_skin:.1%}, max={max_skin:.1%}, "
              f"peaks={peak_frames}/{len(scores)} frames", flush=True)

        if avg_skin >= SKIN_EXPOSURE_THRESHOLD:
            return False, f"NSFW: avg skin {avg_skin:.0%} across {len(scores)} frames"
        if peak_frames >= SKIN_PEAK_MIN_FRAMES:
            return False, f"NSFW: {peak_frames} frames >{SKIN_PEAK_THRESHOLD:.0%} skin"
        if avg_skin >= SKIN_WARNING_THRESHOLD or max_skin >= SKIN_WARNING_THRESHOLD + 0.05:
            return True, f"borderline: avg skin {avg_skin:.0%}, max {max_skin:.0%} (proceeding)"

        return True, f"safe: avg skin {avg_skin:.0%}"
    finally:
        for f in os.listdir(work_dir):
            try:
                os.remove(os.path.join(work_dir, f))
            except Exception:
                pass
        try:
            os.rmdir(work_dir)
        except Exception:
            pass


def _check_nudenet(video_path):
    """Optional NudeNet check for detailed body part detection."""
    try:
        from nudenet import NudeDetector
    except ImportError:
        return True, ""

    detector = NudeDetector()
    work_dir = tempfile.mkdtemp()
    try:
        frames = _extract_frames(video_path, work_dir, interval=10, max_frames=15)
        if not frames:
            return True, ""

        nsfw_labels = {
            "BUTTOCKS_EXPOSED", "FEMALE_GENITALIA_EXPOSED",
            "MALE_GENITALIA_EXPOSED", "ANUS_EXPOSED",
            "FEMALE_BREAST_EXPOSED", "MALE_BREAST_EXPOSED",
            "FEMALE_CROTCH_EXPOSED", "MALE_CROTCH_EXPOSED",
        }
        risky_labels = {
            "FEMALE_BREAST_COVERED", "BUTTOCKS_COVERED",
            "FEMALE_CROTCH_COVERED", "MALE_CROTCH_COVERED",
            "ARMPITS_COVERED", "BELLY_COVERED",
        }

        total_hits = 0
        for f in frames:
            results = detector.detect(f)
            for r in results:
                label = r.get("class", "")
                score = r.get("score", 0)
                if label in nsfw_labels and score > 0.4:
                    total_hits += 1
                    print(f"  [safety] NudeNet: {label} ({score:.2f})", flush=True)
                elif label in risky_labels and score > 0.6:
                    total_hits += 0.5

        if total_hits >= 3:
            return False, f"NudeNet: {total_hits} NSFW detections"
        if total_hits >= 1:
            return True, f"NudeNet: {total_hits} minor detections (proceeding)"

        return True, ""
    except Exception as e:
        print(f"  [safety] NudeNet error: {e}", flush=True)
        return True, ""
    finally:
        for f in os.listdir(work_dir):
            try:
                os.remove(os.path.join(work_dir, f))
            except Exception:
                pass
        try:
            os.rmdir(work_dir)
        except Exception:
            pass


def check_video_safety(video_path, use_nudenet=True):
    """Full safety check: skin exposure + optional NudeNet.

    Returns:
        (is_safe: bool, reason: str)
    """
    if not os.path.exists(video_path):
        print(f"  [safety] Video not found: {video_path}", flush=True)
        return True, ""

    print(f"  [safety] Checking: {os.path.basename(video_path)}", flush=True)

    safe, reason = _check_skin_exposure(video_path)
    if not safe:
        print(f"  [safety] BLOCKED: {reason}", flush=True)
        return False, reason

    if use_nudenet:
        safe2, reason2 = _check_nudenet(video_path)
        if not safe2:
            print(f"  [safety] BLOCKED: {reason2}", flush=True)
            return False, reason2
        if reason2:
            reason = reason2

    print(f"  [safety] OK: {reason}" if reason else f"  [safety] OK", flush=True)
    return True, reason


def cleanup_safety_files():
    """Clean up any residual safety analysis files."""
    pass
