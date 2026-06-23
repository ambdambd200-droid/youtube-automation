@echo off
TITLE VARY - YouTube Automation API Server
echo ========================================
echo   VARY - Daily Clip Pipeline
echo ========================================
echo.
echo Starting Flask API server on http://127.0.0.1:5001
echo.
echo n8n workflows will call this server automatically.
echo.
echo Pipeline steps:
echo   1. Select content (random: movie or World Cup)
echo   2. Download clip from YouTube
echo   3. Edit to Shorts format (9:16)
echo   4. Generate thumbnails + A/B variants
echo   5. Generate SEO metadata
echo   6. Upload to YouTube
echo   7. Cleanup: delete source files
echo.
echo Press Ctrl+C to stop the server.
echo.
cd /d "%~dp0"
python api_server.py
pause
