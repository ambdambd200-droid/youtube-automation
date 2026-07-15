@echo off
echo ============================================
echo   GitHub Actions Runner Cleanup
echo ============================================
echo.
echo [1/4] Killing runner processes...
taskkill /F /IM "Runner.Listener.exe" 2>nul
taskkill /F /IM "Runner.Worker.exe" 2>nul
timeout /t 2 /nobreak >nul
taskkill /F /IM "Runner.Listener.exe" 2>nul
taskkill /F /IM "Runner.Worker.exe" 2>nul
echo.
echo [2/4] Deleting all runner services...
sc delete "actions.runner.ambdambd200-droid-youtube-automation.DESKTOP-IKGR1UE" 2>nul
sc delete "actions.runner.ambdambd200-droid-youtube-automation.windows-runner" 2>nul
sc delete "actions.runner.ambdambd200-droid-youtube-automation" 2>nul
echo.
echo [3/4] Cleaning session files...
del /f /q "C:\actions-runner\.runner" 2>nul
del /f /q "C:\actions-runner\.credentials" 2>nul
del /f /q "C:\actions-runner\.credentials_rsaparams" 2>nul
echo.
echo [4/4] Done! 
echo.
echo NEXT STEPS:
echo   1. cd C:\actions-runner
echo   2. config.cmd --url https://github.com/ambdambd200-droid/youtube-automation --token YOUR_TOKEN
echo   3. run.cmd
echo.
pause
