@echo off
setlocal enabledelayedexpansion

title SIMAP BAZNAS - Automated MySQL Database Backup Engine

echo ============================================================
echo   SIMAP BAZNAS - Automated MySQL Database Backup Engine     
echo ============================================================
echo.

set "BACKUP_DIR=C:\Apps\simap\backups\database"

:: Ensure target backup directory exists
if not exist "%BACKUP_DIR%" (
    mkdir "%BACKUP_DIR%"
    echo [MKDIR] Created backup target folder: %BACKUP_DIR%
)

:: Generate YYYY-MM-DD_HHMM timestamp using PowerShell for locale independence
for /f "tokens=*" %%a in ('powershell -Command "Get-Date -Format 'yyyy-MM-dd_HHmm'"') do set "TIMESTAMP=%%a"

set "BACKUP_FILE=%BACKUP_DIR%\backup_simap_db_%TIMESTAMP%.sql"

:: Default MySQL connection credentials
set "DB_USER=root"
set "DB_PASS="
set "DB_NAME=simap_db"
set "DB_HOST=127.0.0.1"
set "DB_PORT=3306"

:: Read settings from .env file if available
if exist "%~dp0.env" (
    for /f "usebackq tokens=1,2 delims==" %%i in ("%~dp0.env") do (
        if "%%i"=="DB_USER" set "DB_USER=%%j"
        if "%%i"=="DB_PASSWORD" set "DB_PASS=%%j"
        if "%%i"=="DB_NAME" set "DB_NAME=%%j"
        if "%%i"=="DB_HOST" set "DB_HOST=%%j"
        if "%%i"=="DB_PORT" set "DB_PORT=%%j"
    )
)

echo [BACKUP] Initiating database dump at %TIMESTAMP%...
echo [BACKUP] Destination: %BACKUP_FILE%

if defined DB_PASS (
    mysqldump --host=%DB_HOST% --port=%DB_PORT% --user=%DB_USER% --password=%DB_PASS% --routines --triggers --single-transaction %DB_NAME% > "%BACKUP_FILE%"
) else (
    mysqldump --host=%DB_HOST% --port=%DB_PORT% --user=%DB_USER% --routines --triggers --single-transaction %DB_NAME% > "%BACKUP_FILE%"
)

if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] MySQL Database backup saved: %BACKUP_FILE%
) else (
    echo [WARNING] mysqldump command returned code %ERRORLEVEL%. Please verify MySQL PATH or .env credentials.
)

:: Auto-Purge mechanism: Delete backups older than 30 days
echo.
echo [PURGE] Auto-purging backup files older than 30 days in %BACKUP_DIR%...
forfiles /p "%BACKUP_DIR%" /s /m *.sql /d -30 /c "cmd /c echo Deleting: @file && del @path" 2>nul
echo [PURGE] Retention maintenance complete.

echo.
echo ============================================================
echo   Database Backup Completed
echo ============================================================
