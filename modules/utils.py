"""
VARY — Shared utility functions.
Consolidates cross-cutting concerns like font path resolution.
"""
import os
import platform


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

    return None
