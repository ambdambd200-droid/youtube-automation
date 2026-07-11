@echo off
title VARY Dashboard Server
echo ========================================
echo   VARY — Dashboard & API Server
echo ========================================
echo.
echo Starting Flask server on http://localhost:5001
echo Open your browser to http://localhost:5001
echo Close this window to stop the server.
echo.

cd /d "%~dp0.."
py -3.12 api_server.py

if errorlevel 1 (
    echo.
    echo [ERROR] Server failed to start. Make sure Flask is installed:
    echo   py -3.12 -m pip install flask
    pause
)
