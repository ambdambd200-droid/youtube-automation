"""
VARY — Configuration for clip-based YouTube Shorts automation.
Daily random clips from football, movies, and series.
"""
import os
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
load_dotenv()
# Fallback: read directly from the known local path (self-hosted runner)
_local_env = r"C:\Users\A\Desktop\Movies\.env"
if os.path.exists(_local_env):
    load_dotenv(_local_env, override=True)

# ── YouTube API ──────────────────────────────────────────────
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")

# ── n8n ──────────────────────────────────────────────────────
N8N_API_KEY = os.getenv("N8N_API_KEY")
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678")

# ── Alerts / Webhooks ───────────────────────────────────────
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")

# ── yt-dlp Auth ───────────────────────────────────────────────
YT_COOKIES_FILE = os.getenv("YT_COOKIES_FILE", "")

# ── Output Directories ───────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.getenv("OUTPUT_DIR", os.path.join(BASE_DIR, "assets"))
DOWNLOADS_DIR = os.path.join(OUTPUT_DIR, "downloads")
CLIPS_DIR = os.path.join(OUTPUT_DIR, "clips")
THUMBNAILS_DIR = os.path.join(OUTPUT_DIR, "thumbnails")
THUMBNAILS_VARIANTS_DIR = os.path.join(THUMBNAILS_DIR, "variants")
LOG_DIR = os.path.join(OUTPUT_DIR, "logs")

# ── Video Settings ───────────────────────────────────────────
SHORTS_WIDTH = 1080
SHORTS_HEIGHT = 1920
FPS = 30
CLIP_MAX_DURATION = 60       # Max 60s for YouTube Shorts
CLIP_MIN_DURATION = 15

# ── Blueprint Render Specs (Section 6: The Final Render) ──
SAFE_ZONE_WIDTH = 1080       # Content box width within 1080x1920
SAFE_ZONE_HEIGHT = 1350      # Content box height (leaves 285px top/bottom padding)
RENDER_CODEC = "libx264"     # H.264 baseline, H.265 (libx265) preferred
RENDER_PROFILE = "high"
RENDER_LEVEL = "4.1"
RENDER_BITRATE = "20000k"    # 20 Mbps upload bitrate to outsmart YouTube compression
RENDER_BUFFER_SIZE = "40000k"
RENDER_CRF = 14              # Near-lossless master (lower = better, 14 is visually lossless)
RENDER_PIX_FMT = "yuv420p"
RENDER_MOVFLAGS = "+faststart"

# ── Audio Specs (Section 2: Acoustic Engineering) ─────────
AUDIO_TARGET_LUFS = -14.0    # YouTube loudness standard
AUDIO_TRUE_PEAK = -1.0       # dBTP true peak limit
AUDIO_SAMPLE_RATE = 48000
AUDIO_BITRATE = "192k"
AUDIO_CODEC = "aac"
AUDIO_EQ_HIGHPASS = 80       # HP filter at 80Hz
AUDIO_EQ_LOWPASS = 12000     # LP filter at 12kHz
AUDIO_PRESENCE_BOOST = 3     # +3dB at 3-5kHz presence range
AUDIO_COMPRESSION_RATIO = 4  # 4:1 compression ratio
AUDIO_DUCK_DB = -6           # -6dB ducking on impact
AUDIO_DUCK_DURATION = 0.5    # 0.5 second duck duration

# ── Video Color Specs (Section 3: Visual Alchemy) ─────────
COLOR_SHADOW_LIFT = "#101010"  # Lift black point to avoid pure black
COLOR_TEAL_SHADOWS = 0.15     # Push shadows toward teal/cyan
COLOR_ORANGE_MIDTONES = 0.12  # Push midtones toward warm orange
COLOR_GLOBAL_SATURATION = -0.10  # Reduce global saturation by 10%
COLOR_VIBRANCE_BOOST = 0.15   # Increase vibrance by 15%
COLOR_GRAIN_INTENSITY = 5     # Film grain intensity (0-100)
COLOR_GRAIN_SIZE = 0.3        # Film grain size
COLOR_SHARPEN_RADIUS = 0.5    # Unsharp mask radius
COLOR_SHARPEN_AMOUNT = 50     # Unsharp mask amount

# ── Temporal Specs (Section 4: Temporal Dynamics) ─────────
TEMP_PRE_ACTION_WINDOW = 1.5  # Start 1.5s before main event
TEMP_SLOW_MOTION_SPEED = 0.4 # 40% speed at impact
TEMP_FREEZE_DURATION = 0.4   # Freeze frame for 0.4s (10-12 frames)
TEMP_SPEED_UP_SPEED = 2.0    # 200% speed after impact
TEMP_REACTION_DURATION = 2.0 # End 2s after action for reaction
TEMP_ZOOM_IN_SCALE = 1.10    # Micro-zoom 110% for focus
TEMP_ZOOM_DURATION = 0.5     # Zoom over 0.5 seconds

# ── Content Types & Selection ────────────────────────────────
CONTENT_TYPES = ["football", "movie", "series"]

# Equal weight by default — evolution engine adjusts over time
CONTENT_WEIGHTS = {
    "movie": 0.34,
    "football": 0.33,
    "series": 0.33,
}

# ── Keywords ─────────────────────────────────────────────────
FOOTBALL_KEYWORDS = [
    # Classic football moments
    "World Cup 2026 best moments",
    "World Cup 2026 amazing goal",
    "World Cup 2026 highlight",
    "World Cup 2026 incredible play",
    "World Cup 2026 skills",
    "football World Cup 2026 moment",
    "World Cup 2026 top plays",
    # News-style / trending
    "football news today",
    "breaking football news",
    "transfer news today football",
    "goal updates today",
    "football trending now",
    "viral football clip today",
    "match of the day highlights",
    "football what's new today",
    "soccer news this week",
    "crazy football moment just now",
]

MOVIE_KEYWORDS = [
    # Classic movie moments
    "iconic movie scene 4k",
    "best movie moments 4k",
    "cinematic movie scene",
    "movie clip epic scene",
    "famous movie scene hd",
    "award winning film scene",
    "hollywood movie iconic moment",
    "blockbuster movie scene",
    "film scene masterpiece hd",
    # News-style / trending
    "movie news today",
    "upcoming movie 2026",
    "cinema news this week",
    "film release today",
    "trending movie clip now",
    "viral film scene today",
    "whats new in cinema 2026",
    "new movie trailer moment",
    "breaking movie news",
    "film industry news today",
]

SERIES_KEYWORDS = [
    # Classic series moments
    "tv series best scene hd",
    "tv show iconic moment",
    "series most famous scene",
    "tv series epic moment hd",
    "tv show dramatic scene",
    "hit series best clip",
    # News-style / trending
    "tv series news today",
    "new series 2026 trending",
    "show trending this week",
    "tv show what's new today",
    "series viral moment today",
    "breaking tv news today",
]

# ── Channel Branding ─────────────────────────────────────────
CHANNEL_NAME = "VARY"
CHANNEL_TAGLINE = "three times daily. one clip at a time."

CHANNEL_DESCRIPTION = """Welcome to VARY — three times daily, one clip at a time. ⚽🎬📺

Your daily destination for the best clips from football, movies, and TV series.

⚽ Football — raw match moments, incredible goals, insane skills, and viral plays
🎬 Movies — unforgettable scenes, cinematic masterpieces, iconic moments
📺 Series — the most iconic TV moments, viral scenes, show highlights

Every short is handpicked for maximum impact. No filler, just the best moments from the worlds of sports and entertainment.

VARY — three times daily. one clip at a time."""


def get_channel_description():
    """Return the channel description."""
    return CHANNEL_DESCRIPTION

DEFAULT_TAGS = [
    "VARY", "shorts", "YouTube shorts", "daily shorts",
    "football shorts", "movie clips", "tv series clips",
    "viral clips", "random clips", "daily video",
    "sports", "cinema", "television",
]

# ── Posting Schedule ────────────────────────────────────────
POSTING_TIMES_BY_DAY = {
    6: [(8, 0),  (14, 0), (19, 0)],
    0: [(8, 0),  (14, 0), (19, 0)],
    1: [(8, 0),  (14, 0), (19, 0)],
    2: [(8, 0),  (14, 0), (19, 0)],
    3: [(8, 0),  (14, 0), (19, 0)],
    4: [(8, 0),  (14, 0), (19, 0)],
    5: [(8, 0),  (14, 0), (19, 0)],
}

POSTING_TIMES_UTC_DEFAULT = [(8, 0), (14, 0), (19, 0)]


def get_posting_times():
    """Return today's posting times based on the day of the week."""
    today = datetime.now().weekday()
    our_day = (today + 1) % 7

    try:
        from modules.evolution_engine import get_evolved_posting_times
        evolved = get_evolved_posting_times()
        if evolved and our_day in evolved:
            return evolved[our_day]
    except Exception:
        pass

    return POSTING_TIMES_BY_DAY.get(our_day, POSTING_TIMES_UTC_DEFAULT)


def get_posting_times_formatted():
    """Get formatted posting times string for channel description."""
    times = get_posting_times()
    return " · ".join(f"{h:02d}:{m:02d} utc" for h, m in times)

for d in [DOWNLOADS_DIR, CLIPS_DIR, THUMBNAILS_DIR, THUMBNAILS_VARIANTS_DIR, LOG_DIR]:
    os.makedirs(d, exist_ok=True)
