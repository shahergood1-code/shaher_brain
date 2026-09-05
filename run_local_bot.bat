@echo off
cd /d "%~dp0"
chcp 65001 >nul
title Shaher II OS - Local Bot Runner (RTX 4070)
color 0A

echo ======================================================================
echo    [Shaher II OS] - Autonomous Content Engine and Telegram Runner
echo    RTX 4070 + Faster-Whisper + Ollama Local Engine (0$ Cost)
echo ======================================================================
echo.

:: Detect Python Path
set "PYTHON_EXE=python"
where %PYTHON_EXE% >nul 2>nul
if %errorlevel% neq 0 (
    if exist "C:\Program Files\Python312\python.exe" (
        set "PYTHON_EXE=C:\Program Files\Python312\python.exe"
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    )
)

echo [*] Starting Shaher II Local Telegram Polling...
echo [*] Press Ctrl+C in this window to stop the bot.
echo ----------------------------------------------------------------------
echo.

:loop
"%PYTHON_EXE%" bot\run_polling.py
if %errorlevel% neq 0 (
    echo.
    echo [*] Process interrupted or disconnected. Retrying in 5 seconds...
    timeout /t 5 >nul
    goto loop
)

pause
