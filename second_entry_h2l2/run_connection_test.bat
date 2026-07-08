@echo off
REM Double-click to verify Python is linked to your MetaTrader 5 terminal.
REM Trades nothing. Run this FIRST, before run_bot.bat.
cd /d "%~dp0"
title Second Entry - MT5 connection test
echo ============================================================
echo   Second Entry (H2/L2) - MT5 connection test
echo ============================================================
echo.
python mt5_connect_test.py EURUSD
echo.
echo ------------------------------------------------------------
echo Done. Read the result above, then close this window.
pause
