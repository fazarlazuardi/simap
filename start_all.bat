@echo off
title SIMAP Production Server & Cloudflare Tunnel Starter
cd /d "%~dp0"

echo ======================================================================
echo   SIMAP BAZNAS - SERVER PRODUCTION & CLOUDFLARE TUNNEL RUNNER
echo ======================================================================
echo.

REM Cek apakah server pada 127.0.0.1:8000 sudah berjalan
powershell -Command "$t = New-Object System.Net.Sockets.TcpClient; try { $t.Connect('127.0.0.1', 8000); $t.Close(); exit 0 } catch { exit 1 }"
if errorlevel 1 (
    echo [INFO] Server Waitress belum aktif. Membuka server pada window baru...
    if exist "%~dp0env\Scripts\activate.bat" (
        start "SIMAP Waitress Production Server" cmd /k "cd /d "%~dp0" && call env\Scripts\activate.bat && python run_server.py"
    ) else (
        start "SIMAP Waitress Production Server" cmd /k "cd /d "%~dp0" && python run_server.py"
    )
    echo [INFO] Menunggu server siap pada port 8000...
    timeout /t 4 /nobreak >nul
) else (
    echo [OK] Server Waitress di http://127.0.0.1:8000 sudah aktif.
)

echo.
echo [INFO] Memulai Cloudflare Tunnel...
call "%~dp0start_tunnel.bat"
