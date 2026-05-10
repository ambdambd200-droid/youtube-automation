@echo off
TITLE YouTube Automation API Server
echo Starting YouTube Automation API Server...
echo.
echo This will start the Flask API server on http://127.0.0.1:5001
echo n8n workflows will call this server automatically.
echo.
echo Press Ctrl+C to stop the server.
echo.
cd /d "%~dp0"
python api_server.py
pause
