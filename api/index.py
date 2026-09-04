"""
api/index.py
────────────
نقطة الدخول الرسمية لـ Vercel Serverless Function.
تعمل كـ ASGI handler فوري بدون نوم وبدون أي تأخير (Zero Cold Delay).
"""

import os
import sys
import logging
import traceback
from pathlib import Path

# إضافة جميع المسارات المحتملة لضمان عمل الاستيرادات على Vercel
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent

for path in [str(project_root), str(current_dir)]:
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from bot.main import app
except Exception as exc:
    # حماية ذكية: في حال حدوث أي خطأ استيراد، يتم إظهاره بوضوح بدلاً من تعطل السيرفر 500
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI(title="Shaher Brain Diagnostic Mode")
    err_tb = traceback.format_exc()

    @app.api_route("/{path_name:path}", methods=["GET", "POST"])
    async def diagnostic_handler(path_name: str = ""):
        return JSONResponse(
            status_code=500,
            content={
                "status": "error_during_initialization",
                "detail": str(exc),
                "traceback": err_tb,
                "current_dir": str(current_dir),
                "project_root": str(project_root),
                "sys_path": sys.path[:5],
            }
        )
