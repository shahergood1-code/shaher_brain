@echo off
chcp 65001 >nul
title شاهر الثاني - المشغل المحلي للتيليجرام (0$ بدون سيرفرات)
color 0A

echo ======================================================================
echo          🤖 شاهر الثاني — نظام التشغيل المحلي المباشر 🤖
echo    تشغيل التيليجرام محلياً عبر Polling (مجاني 100%% - RTX 4070 + Ollama)
echo ======================================================================
echo.

:: فحص مسار بايثون
set "PYTHON_EXE=python"
where %PYTHON_EXE% >nul 2>nul
if %errorlevel% neq 0 (
    if exist "C:\Program Files\Python312\python.exe" (
        set "PYTHON_EXE=C:\Program Files\Python312\python.exe"
    )
)

echo [1/2] جاري تشغيل البوت والاتصال بتليجرام...
echo [2/2] لإيقاف البوت في أي وقت، اضغط Ctrl + C
echo ----------------------------------------------------------------------
echo.

:loop
"%PYTHON_EXE%" bot/run_polling.py
if %errorlevel% neq 0 (
    echo.
    echo ⚠️ حدث انقطاع أو خطأ في الاتصال. إعادة المحاولة خلال 5 ثوانٍ...
    timeout /t 5 >nul
    goto loop
)

pause
