@echo off
title Cloudflare Tunnel Runner - SIMAP

set "EXE_PATH=%~dp0cloudflared.exe"
set "DOWNLOAD_URL=https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"

if not exist "%EXE_PATH%" (
    echo [INFO] cloudflared.exe tidak ditemukan di direktori root.
    echo [INFO] Mengunduh cloudflared.exe dari release resmi Cloudflare...
    curl.exe -L -o "%EXE_PATH%" "%DOWNLOAD_URL%"
    if not exist "%EXE_PATH%" (
        powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%DOWNLOAD_URL%' -OutFile '%EXE_PATH%' -TimeoutSec 300"
    )
    
    if not exist "%EXE_PATH%" (
        echo [ERROR] Gagal mengunduh cloudflared.exe. Silakan periksa koneksi internet Anda.
        pause
        exit /b 1
    )
    echo [OK] cloudflared.exe berhasil diunduh.
)

echo [INFO] Memeriksa server lokal di http://127.0.0.1:8000...
powershell -Command "$t = New-Object System.Net.Sockets.TcpClient; try { $t.Connect('127.0.0.1', 8000); $t.Close(); exit 0 } catch { exit 1 }"
if errorlevel 1 (
    echo [PERHATIAN] Server Django/Waitress di http://127.0.0.1:8000 BELUM BERJALAN!
    echo [PERHATIAN] Pastikan Anda sudah menjalankan 'python run_server.py' di terminal terpisah.
    echo [PERHATIAN] Atau Anda dapat menggunakan 'start_all.bat' untuk menjalankan keduanya sekaligus.
    echo.
)

echo [INFO] Memulai Cloudflare Tunnel ke http://127.0.0.1:8000...
echo [INFO] Tekan Ctrl+C untuk menghentikan tunnel.
echo.

"%EXE_PATH%" tunnel --url http://127.0.0.1:8000

if errorlevel 1 (
    echo.
    echo [ERROR] Process cloudflared terhenti.
    pause
)
