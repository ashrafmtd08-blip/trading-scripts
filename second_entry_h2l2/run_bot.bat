@echo off
REM Double-click to start the trading bot. It restarts itself if it ever stops,
REM so it keeps running 24/7 on the VPS. Close this window (or Ctrl+C) to stop.
REM
REM Reminder: the bot ships with DRY_RUN = True (logs only). Set DRY_RUN = False
REM in mt5_live_bot.py once you have watched the dry-run log on your DEMO account.
cd /d "%~dp0"
title Second Entry (H2/L2) - live bot

:loop
echo ============================================================
echo   [%date% %time%]  starting bot...
echo ============================================================
python mt5_live_bot.py
echo.
echo [%date% %time%]  bot stopped (exit code %errorlevel%).
echo Restarting in 30 seconds -- press Ctrl+C now to quit for good.
timeout /t 30 >nul
goto loop
