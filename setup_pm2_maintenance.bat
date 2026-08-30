@echo off
title SIMAP BAZNAS - PM2 Automated Log Rotation Setup

echo ============================================================
echo   SIMAP BAZNAS - PM2 Automated Log Rotation Setup Engine   
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/5] Installing pm2-logrotate module...
call npx pm2 install pm2-logrotate

echo.
echo [2/5] Setting maximum log file size limit (10M)...
call npx pm2 set pm2-logrotate:max_size 10M

echo.
echo [3/5] Setting log retention count (50 rotated files)...
call npx pm2 set pm2-logrotate:retain 50

echo.
echo [4/5] Enabling log compression (gzip)...
call npx pm2 set pm2-logrotate:compress true

echo.
echo [5/5] Saving current PM2 process list & configuration...
call npx pm2 save

echo.
echo ============================================================
echo   PM2 Log Rotation Configured Successfully!
echo ============================================================
pause
