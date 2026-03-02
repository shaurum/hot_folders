@echo off
title Hot Folders
cd /d "%~dp0"

REM Check if already running
tasklist /FI "WINDOWTITLE eq HotFolders*" 2>nul | findstr /I "python" >nul 2>&1
if %errorlevel% equ 0 (
    echo Hot Folders is already running!
    timeout /t 2 /nobreak >nul
    exit /b 0
)

REM Start in background with pythonw (no console)
start "HotFolders" /MIN "%~dp0venv\Scripts\pythonw.exe" "%~dp0main.py"

echo Hot Folders started!
echo Check the system tray for the icon.
timeout /t 2 /nobreak >nul
