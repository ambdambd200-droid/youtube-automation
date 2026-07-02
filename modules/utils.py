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
        Absolute font path string, escaped for ffmpeg drawtext.
    """
    system = platform.system()

    if system == "Windows":
        fonts = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
        ]
        for font in fonts:
            if os.path.exists(font):
                # ffmpeg drawtext on Windows needs escaped colon: C\:/path
                return font.replace(":", "\\:")
        return "C\\:/Windows/Fonts/arial.ttf"

    if system == "Darwin":
        fonts = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ]
        for font in fonts:
            if os.path.exists(font):
                return font
        return "/System/Library/Fonts/Helvetica.ttc"

    # Linux / default
    fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    for font in fonts:
        if os.path.exists(font):
            return font
    return "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
