@echo off
title Hot Folders - Stop
echo Stopping Hot Folders...
taskkill /F /FI "WINDOWTITLE eq HotFolders*" /FI "IMAGENAME eq python*.exe" 2>nul
echo Done!
timeout /t 2 /nobreak >nul
