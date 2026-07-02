# VARY — Daily Clip Automation

Automated YouTube Shorts channel that posts daily random clips from movies, World Cup matches, and the internet. Powered by n8n + Python.

## Content

Every day, the pipeline randomly selects between:
- **🎬 Movie Scenes** — Iconic, viral, and memorable scenes from old and new movies
- **⚽ World Cup 2026** — Controversial moments, amazing goals, viral match highlights

No music. Natural sound only. Pure moments.

## Architecture

```
n8n (scheduled trigger)  →  Flask API (port 5001)
                                │
                    ┌───────────┴───────────┐
                    │   Pipeline Steps       │
                    │                        │
                    │  1. Select Content     │
                    │  2. Download Clip      │
                    │  3. Edit to Shorts     │
                    │  4. Generate Thumbnails│
                    │  5. Generate SEO       │
                    │  6. Upload to YouTube  │
                    │  7. Cleanup Space      │
                    └────────────────────────┘
```

## Module Structure

```
├── config.py                    # Configuration
├── api_server.py                # Flask API (called by n8n)
├── run_pipeline.py              # Standalone pipeline runner
├── create_workflows.py          # Creates n8n workflows
├── start_api_server.bat         # One-click server start
├── .env                         # API keys (create this)
├── modules/
│   ├── content_selector.py      # Random content type selection
│   ├── clip_downloader.py       # YouTube clip download (yt-dlp)
│   ├── clip_editor.py           # Trim, crop to 9:16, keep natural audio
│   ├── thumbnail_generator.py   # Frame extraction + A/B variants
│   ├── seo_generator.py         # Titles, descriptions, tags
│   ├── space_manager.py         # Delete source files after processing
│   └── youtube_uploader.py      # YouTube Data API v3 upload
└── assets/
    ├── downloads/               # Raw clips (deleted after processing)
    ├── clips/                   # Final processed Shorts
    ├── thumbnails/              # Generated thumbnails + variants
    └── logs/                    # History logs (never deleted)
```

## Setup Instructions

### 1. Prerequisites

- Python 3.8+
- [ffmpeg](https://ffmpeg.org/) (must be in PATH)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (install via `pip install yt-dlp`)

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

If no requirements.txt exists, install:
```bash
pip install flask python-dotenv yt-dlp moviepy Pillow google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### 3. Configure .env

Create a `.env` file in the project root:

```env
# YouTube API (required for uploading)
YOUTUBE_CLIENT_ID=your_client_id
YOUTUBE_CLIENT_SECRET=your_client_secret
YOUTUBE_REFRESH_TOKEN=your_refresh_token

# n8n (if using n8n orchestration)
N8N_API_KEY=your_n8n_key
N8N_BASE_URL=http://localhost:5678
```

### 4. YouTube API Setup

1. Go to https://console.cloud.google.com/apis/credentials
2. Create an OAuth 2.0 Client ID (Desktop app type)
3. Add `YOUTUBE_CLIENT_ID` and `YOUTUBE_CLIENT_SECRET` to `.env`
4. Run: `python -m modules.youtube_uploader --auth-flow`
5. Follow the browser login to authorize your VARY channel

### 5. Run a Pipeline Test

```bash
# Run with random content selection
python run_pipeline.py

# Force movie content
python run_pipeline.py --type movie

# Force World Cup content
python run_pipeline.py --type football

# Custom search query
python run_pipeline.py --query "world cup controversial moment 2026"
```

### 6. Start API Server (for n8n)

```bash
start_api_server.bat
# Or: python api_server.py
```

### 7. Create n8n Workflows

```bash
python create_workflows.py
```

This creates a daily scheduled workflow in n8n that runs the full pipeline automatically.

## Channel Branding

- **Name**: VARY
- **Tagline**: Daily Clips. Infinite Variety.
- **Schedule**: Daily YouTube Shorts

## Space Management

The pipeline automatically deletes source video files after processing to save disk space. Only the final Short clip and thumbnails are kept. Old clips are cleaned up after 7 days.

## Note

The old "Depths" (Arabic dark explainer) content has been fully replaced. This is now a clip-based curation channel.
