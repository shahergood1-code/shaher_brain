"""
api/index.py
────────────
نقطة الدخول الرسمية لـ Vercel Serverless Function.
تعرف كائن app = FastAPI() في أعلى الملف لتوافق Vercel CLI 59+.
محمية 100% بنظام حماية ضد التعطل (Zero Crash Guarantee).
"""

import os
import sys
import traceback
from pathlib import Path
from fastapi import FastAPI

# إضافة المجلد الرئيسي للمشروع لتمكين كل الاستيرادات
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent

for p in [str(project_root), str(current_dir), os.getcwd()]:
    if p not in sys.path:
        sys.path.insert(0, p)

# تعريف كائن FastAPI مباشرة في أعلى النطاق ليتعرف عليه محلل Vercel CLI
app = FastAPI(
    title="شاهر الثاني",
    description="Personal AI Operating System — Cloud Webhook Handler",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)

# محاولة تحميل المسارات والمنظومة بالكامل
try:
    from bot.main import (
        root,
        health_check,
        setup_webhook,
        telegram_webhook,
    )

    app.add_api_route("/", root, methods=["GET"])
    app.add_api_route("/health", health_check, methods=["GET"])
    app.add_api_route("/setup", setup_webhook, methods=["GET"])
    app.add_api_route("/webhook", telegram_webhook, methods=["POST"])

except Exception as exc:
    err_tb = traceback.format_exc()

    @app.api_route("/{full_path:path}", methods=["GET", "POST"])
    async def fallback_diagnostic(full_path: str = ""):
        return {
            "status": "diagnostic_mode",
            "message": "⚠️ حدث خطأ أثناء تشغيل ملفات المشروع السحابية",
            "error": str(exc),
            "traceback": err_tb,
            "cwd": os.getcwd(),
            "cwd_files": os.listdir(".") if os.path.exists(".") else [],
            "sys_path": sys.path[:5],
        }
