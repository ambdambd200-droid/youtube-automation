import os
from dotenv import load_dotenv

load_dotenv()

N8N_API_KEY = os.getenv("N8N_API_KEY")
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678")

# Groq API (free, no payment needed)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"  # Llama 3.3 70B - free tier
if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY not set. Get a free key at https://console.groq.com")

YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./assets")
AUDIO_BACKGROUND = os.getenv("AUDIO_BACKGROUND", "")

# Paths
AUDIO_DIR = os.path.join(OUTPUT_DIR, "audio")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
VIDEOS_DIR = os.path.join(OUTPUT_DIR, "videos")
THUMBNAILS_DIR = os.path.join(OUTPUT_DIR, "thumbnails")

# English voice config for Edge-TTS
# Available English voices: en-US-JennyNeural (F), en-US-GuyNeural (M), en-GB-SoniaNeural (F), en-GB-RyanNeural (M)
TTS_VOICE = "en-US-GuyNeural"  # Male American voice - authoritative for dark history/mystery
TTS_VOICE_FEMALE = "en-US-JennyNeural"  # Female American voice

# ElevenLabs Settings
# "Marcus" is a good authoritative voice for dark history
# "George" or "Brian" are also good options
ELEVEN_VOICE_ID = "pMs7ixS9os7V3K12YxOq" # Marcus

# Video settings
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
FPS = 30

# Shorts settings
SHORT_DURATION_SECONDS = 60  # target ~1 min
SHORT_IMAGE_DISPLAY_SECONDS = 8

# Long-form settings
LONG_MIN_DURATION = 720  # 12 min
LONG_MAX_DURATION = 900  # 15 min
LONG_SEGMENTS = 6
