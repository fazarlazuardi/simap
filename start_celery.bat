@echo off
title SIMAP BAZNAS - Celery Worker (Windows Server)
echo ============================================================
echo   SIMAP BAZNAS Kabupaten Tangerang - Celery Worker Process   
echo   Running with explicit solo pool (-P solo) for Windows     
echo ============================================================
echo.

call env\Scripts\activate.bat

echo Starting Celery worker...
celery -A config worker --loglevel=INFO -P solo -E

pause
