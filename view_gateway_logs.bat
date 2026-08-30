@echo off
title SIMAP BAZNAS - WA Gateway Real-Time Logs Console (PM2)
echo Launching PM2 real-time logs window for WA Gateway...
cd /d "%~dp0wa-gateway"
call npx pm2 logs wa-gateway
pause
