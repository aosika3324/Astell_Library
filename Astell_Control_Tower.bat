@echo off
title Astell Control Tower Launcher
echo ==============================================
echo       Astell Control Tower Launcher
echo ==============================================
echo.
echo Starting Astell Control Tower UI Server...
cd /d "%~dp0"
python mcp_ui_server.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to start Astell Control Tower.
    pause
)