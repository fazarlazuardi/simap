@echo off
title SIMAP BAZNAS - Start WA Gateway (PM2)
echo ============================================================
echo   SIMAP BAZNAS WhatsApp Gateway - PM2 Start Script          
echo ============================================================
echo.

cd /d "%~dp0"

echo Launching wa-gateway under PM2...
call npx pm2 start ecosystem.config.js
call npx pm2 save

echo.
echo ============================================================
echo   WA Gateway process successfully managed by PM2           
echo   To view logs, run: npx pm2 logs wa-gateway               
echo ============================================================
echo.
pause
