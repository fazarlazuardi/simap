@echo off
title SIMAP BAZNAS - Stop WA Gateway (PM2)
echo ============================================================
echo   SIMAP BAZNAS WhatsApp Gateway - PM2 Stop Script           
echo ============================================================
echo.

cd /d "%~dp0"

echo Stopping wa-gateway PM2 process...
call npx pm2 stop wa-gateway

echo.
echo ============================================================
echo   WA Gateway process stopped successfully                   
echo ============================================================
echo.
pause
