@echo off
REM Double-click ONCE to make the bot launch automatically every time this VPS
REM starts / you log in -- so it survives reboots without you doing anything.
REM (Undo any time with uninstall_autostart.bat.)
cd /d "%~dp0"
title Second Entry - install auto-start

set "TARGET=%~dp0run_bot.bat"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\SecondEntryBot.lnk'); $s.TargetPath='%TARGET%'; $s.WorkingDirectory='%~dp0'; $s.WindowStyle=1; $s.Description='Second Entry H2L2 trading bot'; $s.Save()"

if %errorlevel%==0 (
  echo.
  echo   Done. The bot will now start automatically on every login/reboot.
  echo   For that to help while you are away, set this VPS to auto-login.
) else (
  echo.
  echo   Could not create the Startup shortcut. Try running as Administrator.
)
echo.
pause
