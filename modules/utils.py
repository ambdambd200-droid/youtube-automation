"""
VARY — Shared utility functions.
Consolidates cross-cutting concerns like font path resolution and ffmpeg location.
"""
import os
import platform
import subprocess


def get_font_path():
    """Get a suitable font path for the current platform, escaped for ffmpeg.

    Searches common system font locations and returns the first match.
    The returned path uses ffmpeg-compatible colon escaping on Windows.

    Returns:
        Absolute font path string escaped for ffmpeg drawtext,
        or None if no font is found.
    """
    system = platform.system()
    candidates = []

    if system == "Windows":
        candidates = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
        ]
    elif system == "Darwin":
        candidates = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
        ]

    for font in candidates:
        if os.path.exists(font):
            if system == "Windows":
                return font.replace(":", "\\:")
            return font

    raise FileNotFoundError("No suitable font found for drawtext in any search path")


_FFMPEG_PATH = None
_FFPROBE_PATH = None


def find_ffmpeg():
    """Find ffmpeg executable, caching result.

    Searches WinGet install path first, then falls back to PATH.
    """
    global _FFMPEG_PATH
    if _FFMPEG_PATH:
        return _FFMPEG_PATH

    candidates = ["ffmpeg"]
    # WinGet search path
    wget_base = (
        r"C:\Users\A\AppData\Local\Microsoft\WinGet\Packages"
        r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
    )
    if os.path.exists(wget_base):
        for d in sorted(os.listdir(wget_base), reverse=True):
            if d.startswith("ffmpeg-") and d.endswith("-full_build"):
                exe = os.path.join(wget_base, d, "bin", "ffmpeg.exe")
                if os.path.exists(exe):
                    candidates.insert(0, exe)
                    break

    for c in candidates:
        try:
            r = subprocess.run([c, "-version"], capture_output=True, timeout=5)
            if r.returncode == 0:
                _FFMPEG_PATH = c
                return c
        except Exception:
            continue
    return "ffmpeg"


def find_ffprobe():
    """Find ffprobe executable, caching result."""
    global _FFPROBE_PATH
    if _FFPROBE_PATH:
        return _FFPROBE_PATH

    candidates = ["ffprobe"]
    wget_base = (
        r"C:\Users\A\AppData\Local\Microsoft\WinGet\Packages"
        r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
    )
    if os.path.exists(wget_base):
        for d in sorted(os.listdir(wget_base), reverse=True):
            if d.startswith("ffmpeg-") and d.endswith("-full_build"):
                exe = os.path.join(wget_base, d, "bin", "ffprobe.exe")
                if os.path.exists(exe):
                    candidates.insert(0, exe)
                    break

    for c in candidates:
        try:
            r = subprocess.run([c, "-version"], capture_output=True, timeout=5)
            if r.returncode == 0:
                _FFPROBE_PATH = c
                return c
        except Exception:
            continue
    return "ffprobe"
