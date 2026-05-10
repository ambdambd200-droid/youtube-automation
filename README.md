# YouTube Automation System

Automated Arabic dark explainer YouTube channel powered by n8n + Python.

## Architecture

```
n8n (trigger + orchestration)
  └── HTTP Requests ──► Python Flask API (port 5001)
                           ├── /generate-script    (Claude API)
                           ├── /generate-tts       (Edge-TTS)
                           ├── /fetch-images        (Wikipedia/Pexels)
                           ├── /assemble-video      (moviepy + FFmpeg)
                           └── /generate-thumbnail  (Pillow)
```

## Setup Instructions

### 1. Start the API Server
Run this in a terminal (keep it running):
```
start_api_server.bat
```
Or manually: `python api_server.py`
The server runs on http://127.0.0.1:5001

### 2. n8n Workflows
Two workflows are already created in n8n:
- **"YouTube Daily Short - Automation"** — triggers daily
- **"YouTube Weekly Long-Form - Automation"** — triggers weekly

Open n8n UI at http://localhost:5678 to view/edit them.

### 3. YouTube API Setup
To enable YouTube uploads:
1. Go to https://console.cloud.google.com/apis/credentials
2. Create a new OAuth 2.0 Client ID (Desktop app type)
3. Add YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET to `.env`
4. Run: `python -m modules.youtube_uploader --auth-flow`
5. Follow the browser login to authorize

### 4. Configuration (.env)
| Variable | Required | Description |
|----------|----------|-------------|
| N8N_API_KEY | ✓ | n8n API key (already set) |
| CLAUDE_API_KEY | ✓ | OpenRouter/Claude API key (already set) |
| YOUTUBE_CLIENT_ID | For uploads | Google OAuth client ID |
| YOUTUBE_CLIENT_SECRET | For uploads | Google OAuth client secret |
| PEXELS_API_KEY | Optional | For better stock images |

## Module Structure
```
n8n/
  ├── api_server.py           # Flask API for n8n to call
  ├── config.py               # Configuration
  ├── start_api_server.bat    # One-click server start
  ├── .env                    # API keys
  ├── modules/
  │   ├── script_generator.py   # Claude-powered Arabic script writing
  │   ├── tts_generator.py      # Edge-TTS voiceover (free)
  │   ├── image_fetcher.py      # Wikipedia/Pexels image search
  │   ├── video_assembler.py    # moviepy video composition
  │   ├── thumbnail_generator.py # Pillow thumbnail maker
  │   └── youtube_uploader.py   # YouTube Data API uploader
  ├── assets/
  │   ├── audio/              # Generated voiceover files
  │   ├── images/             # Downloaded images
  │   ├── videos/             # Final video output
  │   └── thumbnails/         # Generated thumbnails
  └── workflows/              # Exported n8n workflow JSON
```

## Manual Testing
To test individual steps:
```bash
python -c "from modules.script_generator import generate_on_this_day_script; print(generate_on_this_day_script()['script'][:200])"
```
