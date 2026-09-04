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

from fastapi.responses import JSONResponse
from fastapi import Request

@app.exception_handler(Exception)
async def api_global_exception_handler(request: Request, exc: Exception):
    import traceback
    return JSONResponse(
        status_code=200,
        content={
            "status": "error_handled",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
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
    err_msg = str(exc)

    @app.api_route("/{full_path:path}", methods=["GET", "POST"])
    async def fallback_diagnostic(full_path: str = ""):
        is_missing_bot = "No module named 'bot'" in err_msg or "No module named" in err_msg
        help_text = (
            "⚠️ مجلدات المشروع (bot, brain) غير موجودة في حزمة Vercel لأن إعداد 'Root Directory' في Vercel مضبوط على api بدلاً من المجلد الرئيسي (./). "
            "الحل: ادخل على إعدادات Vercel -> Settings -> General -> Root Directory واحذف api واجعله ./ ثم اضغط Save."
            if is_missing_bot else "خطأ أثناء تشغيل السيرفر"
        )
        return {
            "status": "action_required" if is_missing_bot else "error",
            "message": help_text,
            "error_detail": err_msg,
            "cwd": os.getcwd(),
            "cwd_files": os.listdir(".") if os.path.exists(".") else [],
            "solution": "غيّر Root Directory في Vercel إلى ./ لتمكين السيرفر من قراءة bot و brain",
        }
