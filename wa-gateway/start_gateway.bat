@echo off
title SIMAP WA Gateway Service (Baileys Node.js)
cd /d "%~dp0"

echo ======================================================================
echo   MEMULAI WHATSAPP GATEWAY SERVICE UNTUK SIMAP BAZNAS
echo ======================================================================
echo.

IF NOT EXIST "node_modules" (
    echo [INFO] node_modules belum ditemukan. Menjalankan npm install...
    call npm install
)

echo [INFO] Menjalankan Node WA Gateway Server (index.js)...
node index.js
pause
