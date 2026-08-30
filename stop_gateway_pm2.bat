@echo off
title SIMAP BAZNAS - Stop WA Gateway (PM2)
echo Stopping WhatsApp Gateway PM2 service...
cd /d "%~dp0wa-gateway"
call npx pm2 stop wa-gateway
pause
