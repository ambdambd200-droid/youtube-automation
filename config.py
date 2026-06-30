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

# ── Alerts / Webhooks ───────────────────────────────────────
# Used by pipeline_watchdog to alert when pipeline retries are exhausted.
# Set to a Discord webhook URL (https://discord.com/api/webhooks/...) or
# a Slack webhook URL (https://hooks.slack.com/services/...).
# If not set, alerts are silently skipped.
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")

# ── yt-dlp Auth ───────────────────────────────────────────────
# Path to cookies.txt file exported from browser, used when YouTube
# demands sign-in in CI/headless environments. See:
# https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-
YT_COOKIES_FILE = os.getenv("YT_COOKIES_FILE", "")

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
# Day-dependent optimal posting times based on audience analysis.
# Three shorts per day at times optimized for each weekday.
# Day format: 0=Sunday, 1=Monday, ..., 6=Saturday
# Times are in UTC. Convert to local for your audience.
POSTING_TIMES_BY_DAY = {
    6: [(11, 0), (14, 0), (19, 0)],   # Saturday:  11:00, 14:00, 19:00 UTC
    0: [(10, 0), (13, 0), (18, 0)],   # Sunday:    10:00, 13:00, 18:00 UTC
    1: [(12, 0), (15, 0), (19, 0)],   # Monday:    12:00, 15:00, 19:00 UTC
    2: [(12, 0), (16, 0), (20, 0)],   # Tuesday:   12:00, 16:00, 20:00 UTC
    3: [(12, 0), (14, 0), (18, 0)],   # Wednesday: 12:00, 14:00, 18:00 UTC
    4: [(12, 0), (15, 0), (20, 0)],   # Thursday:  12:00, 15:00, 20:00 UTC
    5: [(10, 0), (13, 0), (21, 0)],   # Friday:    10:00, 13:00, 21:00 UTC
}

# Legacy fixed times (used as fallback)
POSTING_TIMES_UTC_DEFAULT = [(7, 33), (17, 55), (22, 18)]


def get_posting_times():
    """Return today's posting times based on the day of the week.

    Checks the evolution engine for AI-optimized times first.
    Falls back to static day-dependent defaults if not evolved yet.
    """
    today = datetime.now().weekday()  # 0=Monday, 6=Sunday
    # Convert: Python Monday=0..Sunday=6 -> our dict Saturday=6..Friday=5
    # Python: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
    # Our:    Sat=6, Sun=0, Mon=1, Tue=2, Wed=3, Thu=4, Fri=5
    our_day = (today + 1) % 7  # Shift: Mon(0)->1, ..., Sun(6)->0

    # Check evolution engine for learned optimal times first
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

# Ensure directories exist
for d in [DOWNLOADS_DIR, CLIPS_DIR, THUMBNAILS_DIR, THUMBNAILS_VARIANTS_DIR, LOG_DIR]:
    os.makedirs(d, exist_ok=True)
