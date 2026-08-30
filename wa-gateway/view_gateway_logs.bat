@echo off
title SIMAP BAZNAS - WA Gateway Real-Time Logs Console (PM2)
echo ============================================================
echo   SIMAP BAZNAS WhatsApp Gateway - Real-Time Logs Console   
echo   Press Ctrl+C to stop log streaming                       
echo ============================================================
echo.

cd /d "%~dp0"

call npx pm2 logs wa-gateway

pause
