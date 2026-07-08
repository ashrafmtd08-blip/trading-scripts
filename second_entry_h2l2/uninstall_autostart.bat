@echo off
REM Double-click to stop the bot from launching automatically on startup.
title Second Entry - remove auto-start
powershell -NoProfile -Command "Remove-Item ([Environment]::GetFolderPath('Startup')+'\SecondEntryBot.lnk') -ErrorAction SilentlyContinue"
echo Auto-start shortcut removed (if it existed).
echo (This does not stop a bot that is already running -- close its window for that.)
echo.
pause
