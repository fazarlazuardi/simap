@echo off
title SIMAP BAZNAS - Start WA Gateway (PM2)
echo Starting WhatsApp Gateway PM2 service...
cd /d "%~dp0wa-gateway"
call npx pm2 start ecosystem.config.js
call npx pm2 save
pause
