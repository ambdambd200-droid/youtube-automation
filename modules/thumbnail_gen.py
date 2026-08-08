"""
Thumbnail Generator — vidIQ-style A/B testing variants with CTR optimization.

Generates multiple thumbnail variants per video:
1. Face + Emotion (high CTR) — detects faces, crops to emotion
2. Text + Hook (clickbait-style) — bold text overlay with hook phrase
3. Scene + Color Grade (cinematic) — key frame with color profile
4. Split Screen (before/after) — for transformation/analysis content

Features:
- A/B test variants (generates 4 per video)
- Auto face detection + emotion crop
- vidIQ-style text placement (rule of thirds)
- Color profile consistency with video
- CTR prediction based on thumbnail elements
"""
import os
import json
import random
import subprocess
import tempfile
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SHORTS_WIDTH, SHORTS_HEIGHT, THUMBNAILS_DIR, THUMBNAILS_VARIANTS_DIR
from modules.utils import find_ffmpeg, get_font_path

_FFMPEG = find_ffmpeg()


def extract_key_frames(video_path, num_frames=5):
    """Extract candidate frames for thumbnail at key moments."""
    frames = []
    duration = get_video_duration(video_path)
    if duration <= 0:
        return frames

    # Extract frames at: 0.5s, 25%, 50%, 75%, pre-end
    timestamps = [
        0.5,
        duration * 0.25,
        duration * 0.5,
        duration * 0.75,
        max(0.5, duration - 1.0),
    ]

    for i, ts in enumerate(timestamps[:num_frames]):
        out_path = os.path.join(tempfile.gettempdir(), f"thumb_frame_{i}_{os.path.basename(video_path)}.jpg")
        cmd = [
            _FFMPEG, "-y", "-ss", str(ts), "-i", video_path,
            "-vframes", "1", "-q:v", "2",
            "-vf", f"scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=decrease,pad={SHORTS_WIDTH}:{SHORTS_HEIGHT}:(ow-iw)/2:(oh-ih)/2",
            out_path,
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=15)
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
                frames.append(out_path)
        except Exception:
            pass

    return frames


def get_video_duration(video_path):
    """Get video duration using ffprobe."""
    try:
        from modules.utils import find_ffprobe
        ffprobe = find_ffprobe()
        import json as _json
        cmd = [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", video_path]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
        data = _json.loads(out)
        return float(data.get("format", {}).get("duration", 0))
    except Exception:
        return 0


def detect_face_region(frame_path):
    """Detect face region using OpenCV (if available) — returns (x, y, w, h) or None."""
    try:
        import cv2
        img = cv2.imread(frame_path)
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        if len(faces) > 0:
            # Return largest face
            faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
            return faces[0]
    except Exception:
        pass
    return None


def crop_to_face(frame_path, output_path, face_region=None):
    """Crop frame to face region (emotion-focused) or center."""
    if face_region:
        x, y, w, h = face_region
        # Expand to include emotion area (forehead to chin)
        expand = 0.3
        x = max(0, int(x - w * expand))
        y = max(0, int(y - h * expand))
        w = min(frame_width - x, int(w * (1 + 2 * expand)))
        h = min(frame_height - y, int(h * (1 + 2 * expand)))
    else:
        # Center crop
        import cv2
        img = cv2.imread(frame_path)
        if img is None:
            return False
        frame_height, frame_width = img.shape[:2]
        x = (frame_width - SHORTS_WIDTH) // 2
        y = (frame_height - SHORTS_HEIGHT) // 2
        w, h = SHORTS_WIDTH, SHORTS_HEIGHT

    cmd = [
        _FFMPEG, "-y", "-i", frame_path,
        "-vf", f"crop={w}:{h}:{x}:{y},scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}",
        "-q:v", "2", output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=10)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception:
        return False


def add_text_overlay(frame_path, output_path, text, position="top", color="white", font_size=80):
    """Add bold text overlay with outline (vidIQ style)."""
    font = get_font_path()
    if position == "top":
        y_expr = "50"
    elif position == "bottom":
        y_expr = f"h-100"
    else:
        y_expr = "(h-th)/2"

    # Escape text for drawtext
    safe_text = text.replace("'", "\\'").replace(":", "\\:")
    
    cmd = [
        _FFMPEG, "-y", "-i", frame_path,
        "-vf", f"drawtext=fontfile='{font}':text='{safe_text}':fontsize={font_size}:fontcolor={color}:x=(w-tw)/2:y={y_expr}:box=1:boxcolor=black@0.7:boxborderw=10:borderw=3:bordercolor=black",
        "-q:v", "2", output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=15)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception:
        return False


def apply_color_profile(frame_path, output_path, profile_name="teal_orange"):
    """Apply color profile to thumbnail for consistency with video."""
    try:
        from modules.color_profiles import get_filter_string
        filter_str = get_filter_string(profile_name, 1.2)  # Slightly stronger for thumb
        cmd = [
            _FFMPEG, "-y", "-i", frame_path,
            "-vf", filter_str,
            "-q:v", "2", output_path,
        ]
        subprocess.run(cmd, capture_output=True, timeout=15)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception:
        return False


def generate_thumbnail_variants(video_path, hook_text="", color_profile="teal_orange", video_id=""):
    """
    Generate 4 A/B test thumbnail variants:
    1. Face + Emotion (high CTR)
    2. Text + Hook (clickbait-style)
    3. Scene + Color Grade (cinematic)
    4. Split/Contrast (before-after style)
    
    Returns list of generated thumbnail paths.
    """
    os.makedirs(THUMBNAILS_VARIANTS_DIR, exist_ok=True)
    
    frames = extract_key_frames(video_path, num_frames=5)
    if not frames:
        return []
    
    variants = []
    base_name = video_id or os.path.basename(video_path).replace(".", "_")
    
    # Variant 1: Face + Emotion
    for i, frame in enumerate(frames):
        face = detect_face_region(frame)
        if face:
            out = os.path.join(THUMBNAILS_VARIANTS_DIR, f"{base_name}_v1_face.jpg")
            if crop_to_face(frame, out, face):
                variants.append(("face_emotion", out))
                break
    
    # Variant 2: Text + Hook
    if hook_text:
        for frame in frames[:3]:
            out = os.path.join(THUMBNAILS_VARIANTS_DIR, f"{base_name}_v2_text.jpg")
            # Short hook text for thumbnail
            short_hook = hook_text[:40] + "..." if len(hook_text) > 40 else hook_text
            if add_text_overlay(frame, out, short_hook, position="top", color="yellow", font_size=70):
                variants.append(("text_hook", out))
                break
    
    # Variant 3: Scene + Color Grade
    for frame in frames[1:4]:
        out = os.path.join(THUMBNAILS_VARIANTS_DIR, f"{base_name}_v3_cinematic.jpg")
        if apply_color_profile(frame, out, color_profile):
            variants.append(("cinematic", out))
            break
    
    # Variant 4: High contrast / split tone
    for frame in frames[2:]:
        out = os.path.join(THUMBNAILS_VARIANTS_DIR, f"{base_name}_v4_contrast.jpg")
        cmd = [
            _FFMPEG, "-y", "-i", frame,
            "-vf", "eq=contrast=1.3:brightness=0.05:saturation=1.4,curves=preset=strong_contrast",
            "-q:v", "2", out,
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=15)
            if os.path.exists(out) and os.path.getsize(out) > 1000:
                variants.append(("high_contrast", out))
                break
        except Exception:
            pass
    
    # Save variant metadata for A/B testing
    meta = {
        "video_id": video_id,
        "variants": [{"type": v[0], "path": v[1]} for v in variants],
        "hook_text": hook_text,
        "color_profile": color_profile,
    }
    meta_path = os.path.join(THUMBNAILS_VARIANTS_DIR, f"{base_name}_meta.json")
    try:
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
    except Exception:
        pass
    
    return [v[1] for v in variants]


def predict_ctr_score(variant_type, has_face=False, has_text=False, color_vibrant=False):
    """
    Predict CTR score based on thumbnail elements (vidIQ-inspired heuristic).
    Returns 0-100 score.
    """
    base_scores = {
        "face_emotion": 75,
        "text_hook": 70,
        "cinematic": 60,
        "high_contrast": 65,
    }
    score = base_scores.get(variant_type, 50)
    
    if has_face:
        score += 10
    if has_text:
        score += 8
    if color_vibrant:
        score += 5
    
    # Penalties
    if variant_type == "text_hook" and not has_face:
        score -= 5  # Text-only can look spammy
    
    return min(95, max(30, score))


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python thumbnail_gen.py <video_path> [hook_text]")
        sys.exit(1)
    
    video = sys.argv[1]
    hook = sys.argv[2] if len(sys.argv) > 2 else ""
    variants = generate_thumbnail_variants(video, hook)
    print(f"Generated {len(variants)} variants:")
    for v in variants:
        print(f"  {v}")