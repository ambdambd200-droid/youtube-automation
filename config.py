"""
VARY — Configuration for clip-based YouTube Shorts automation.
Daily random clips from movies, matches, and the internet.
"""
import os
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
CONTENT_WEIGHTS = {
    "worldcup_2026": 0.40,   # 40% World Cup moments
    "movie": 0.60,           # 60% random movie scenes
}

# ── World Cup Sources ────────────────────────────────────────
WORLDCUP_KEYWORDS = [
    "world cup 2026 best moments",
    "world cup 2026 highlight",
    "world cup 2026 controversial",
    "world cup 2026 amazing goal",
    "world cup 2026 viral moment",
]

# ── Movie Keywords (for sourcing) ─────────────────────────────
MOVIE_KEYWORDS = [
    "iconic movie scene",
    "best movie moments",
    "classic film scene",
    "cinematic masterpiece scene",
]

# ── Channel Branding ─────────────────────────────────────────
CHANNEL_NAME = "VARY"
CHANNEL_TAGLINE = "Daily Clips. Infinite Variety."
CHANNEL_DESCRIPTION = """VARY brings you daily short videos featuring the best moments from movies, sports, and the internet. Random. Curated. Never the same.

Every day, a new clip — from iconic movie scenes to viral World Cup moments. Natural sound only. No filler.

🎬 New Shorts every day
🌍 Movies • World Cup • Internet
🎯 No music, just pure moments"""

# ── SEO ──────────────────────────────────────────────────────
DEFAULT_TAGS = [
    "VARY", "shorts", "YouTube shorts", "daily shorts",
    "movie clips", "movie scenes", "world cup 2026",
    "viral clips", "random clips", "daily video",
]

# Ensure directories exist
for d in [DOWNLOADS_DIR, CLIPS_DIR, THUMBNAILS_DIR, THUMBNAILS_VARIANTS_DIR, LOG_DIR]:
    os.makedirs(d, exist_ok=True)
