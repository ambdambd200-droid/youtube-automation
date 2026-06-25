"""
VARY — Configuration for clip-based YouTube Shorts automation.
Daily random clips from movies, matches, and the internet.
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

# ── Output Directories ───────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.getenv("OUTPUT_DIR", os.path.join(BASE_DIR, "assets"))
DOWNLOADS_DIR = os.path.join(OUTPUT_DIR, "downloads")    # Raw clips — deleted after processing
CLIPS_DIR = os.path.join(OUTPUT_DIR, "clips")             # Final processed Shorts
THUMBNAILS_DIR = os.path.join(OUTPUT_DIR, "thumbnails")   # Generated thumbnails
THUMBNAILS_VARIANTS_DIR = os.path.join(THUMBNAILS_DIR, "variants")  # A/B test variants
LOG_DIR = os.path.join(OUTPUT_DIR, "logs")                # History logs (never deleted)

# ── Video Settings ───────────────────────────────────────────
SHORTS_WIDTH = 1080
SHORTS_HEIGHT = 1920
FPS = 30
CLIP_MAX_DURATION = 60   # Max seconds for Shorts
CLIP_MIN_DURATION = 15   # Min seconds

# ── Content Selection Weights ────────────────────────────────
# When the World Cup is active, 40% WC / 60% movie.
# When it's over, 100% movie (auto-transition).
CONTENT_WEIGHTS_ACTIVE = {
    "worldcup_2026": 0.40,
    "movie": 0.60,
}
CONTENT_WEIGHTS_POST_WC = {
    "movie": 1.0,
}

def get_content_weights():
    """Return appropriate weights based on whether the World Cup is active."""
    if is_world_cup_active():
        return CONTENT_WEIGHTS_ACTIVE
    return CONTENT_WEIGHTS_POST_WC

# ── World Cup Sources ────────────────────────────────────────
# FIFA World Cup 2026 runs from June 8 to July 3, 2026
WORLD_CUP_START_DATE = "2026-06-08"
WORLD_CUP_END_DATE = "2026-07-03"

WORLDCUP_KEYWORDS = [
    "world cup 2026 best moments",
    "world cup 2026 highlight",
    "world cup 2026 controversial",
    "world cup 2026 amazing goal",
    "world cup 2026 viral moment",
]

def is_world_cup_active():
    """Check if the FIFA World Cup 2026 is currently in progress."""
    today = date.today()
    start = datetime.strptime(WORLD_CUP_START_DATE, "%Y-%m-%d").date()
    end = datetime.strptime(WORLD_CUP_END_DATE, "%Y-%m-%d").date()
    return start <= today <= end + timedelta(days=2)  # 2-day grace period after final

# ── Movie Keywords (for sourcing) ─────────────────────────────
MOVIE_KEYWORDS = [
    "iconic movie scene",
    "best movie moments",
    "classic film scene",
    "cinematic masterpiece scene",
]

# ── Channel Branding ─────────────────────────────────────────
CHANNEL_NAME = "VARY"
CHANNEL_TAGLINE = "three times daily. one clip at a time."

CHANNEL_DESCRIPTION = """Welcome to VARY! ⚽🎬

Your ultimate destination where the thrill of football meets the magic of cinema. 🌍

🔹 World Cup Highlights: Relive the most iconic moments, stunning goals, and dramatic saves from the FIFA World Cup. Experience the passion of the global game in short, electrifying clips. 🏆🥅

🔸 Random Movie Scenes: Dive into a curated mix of unforgettable scenes from top foreign films. From action-packed sequences to emotional dramas, enjoy a random cinematic journey every time you tune in. 🎥🍿

VARY – Where sports excitement and movie mastery collide. ✨"""

def get_channel_description():
    """Return the channel description."""
    return CHANNEL_DESCRIPTION

# ── SEO ──────────────────────────────────────────────────────
DEFAULT_TAGS = [
    "VARY", "shorts", "YouTube shorts", "daily shorts",
    "movie clips", "movie scenes", "world cup 2026",
    "viral clips", "random clips", "daily video",
]

# ── Posting Schedule ────────────────────────────────────────
# Three shorts per day at UTC times
POSTING_TIMES_UTC = [
    (7, 33),   # 07:33 UTC — morning
    (17, 55),  # 17:55 UTC — afternoon
    (22, 18),  # 22:18 UTC — night
]

# Ensure directories exist
for d in [DOWNLOADS_DIR, CLIPS_DIR, THUMBNAILS_DIR, THUMBNAILS_VARIANTS_DIR, LOG_DIR]:
    os.makedirs(d, exist_ok=True)
