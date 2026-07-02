"""
VARY — Configuration for clip-based YouTube Shorts automation.
Daily random clips from football, movies, and series.
"""
import os
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
load_dotenv()

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
CLIP_MAX_DURATION = 60
CLIP_MIN_DURATION = 15

# ── Content Types & Selection ────────────────────────────────
CONTENT_TYPES = ["football", "movie", "series"]

# Equal weight by default — evolution engine adjusts over time
CONTENT_WEIGHTS = {
    "football": 0.34,
    "movie": 0.33,
    "series": 0.33,
}

# ── Keywords ─────────────────────────────────────────────────
FOOTBALL_KEYWORDS = [
    "football best moments",
    "football insane skills",
    "football incredible goal",
    "football amazing save",
    "football match highlight",
    "football viral clip",
    "football top plays",
]

MOVIE_KEYWORDS = [
    "iconic movie scene",
    "best movie moments",
    "classic film scene",
    "cinematic masterpiece scene",
    "movie trailer epic",
    "film scene amazing",
]

SERIES_KEYWORDS = [
    "tv series best scene",
    "tv show viral moment",
    "series most iconic scene",
    "tv series epic moment",
    "show best scene ever",
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
