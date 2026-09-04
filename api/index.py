"""
api/index.py
────────────
نقطة الدخول الرسمية لـ Vercel Serverless Function.
تدعم التوجيه المرن لكافة المسارات (/ و /api و /health و /setup و /webhook).
"""

import os
import sys
import traceback
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# إضافة مسار المشروع بالكامل
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent

for p in [str(project_root), str(current_dir), os.getcwd()]:
    if p not in sys.path:
        sys.path.insert(0, p)

app = FastAPI(
    title="شاهر الثاني",
    description="Personal AI Operating System — Cloud Webhook Handler",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)

# معالج الأخطاء العام لمنع كراش 500
@app.exception_handler(Exception)
async def api_global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=200,
        content={
            "status": "error_handled",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
    )

# Middleware لتصحيح بادئات Vercel Rewrites تلقائياً
@app.middleware("http")
async def normalize_vercel_paths(request: Request, call_next):
    raw_path = request.scope.get("path", "")
    for prefix in ["/api/index.py", "/api/index", "/api"]:
        if raw_path == prefix or raw_path == f"{prefix}/":
            request.scope["path"] = "/"
            break
        elif raw_path.startswith(f"{prefix}/"):
            request.scope["path"] = raw_path[len(prefix):]
            break
    return await call_next(request)

# استيراد وتسجيل المسارات
try:
    from bot.main import (
        root,
        health_check,
        setup_webhook,
        telegram_webhook,
    )

    # تسجيل المسارات الأصلية ومسارات البادئة /api للتوافق الكامل
    for pfx in ["", "/api"]:
        app.add_api_route(f"{pfx}/" if pfx else "/", root, methods=["GET"])
        if pfx:
            app.add_api_route(pfx, root, methods=["GET"])
        app.add_api_route(f"{pfx}/health", health_check, methods=["GET"])
        app.add_api_route(f"{pfx}/setup", setup_webhook, methods=["GET"])
        app.add_api_route(f"{pfx}/webhook", telegram_webhook, methods=["POST"])

    # توجيه أي مسار GET غير معروف إلى الصفحة الترحيبية بدلاً من Not Found
    @app.api_route("/{full_path:path}", methods=["GET"])
    async def catch_all_get(full_path: str = ""):
        return await root()

except Exception as exc:
    err_tb = traceback.format_exc()
    err_msg = str(exc)

    @app.api_route("/{full_path:path}", methods=["GET", "POST"])
    async def fallback_diagnostic(full_path: str = ""):
        return {
            "status": "error",
            "error": err_msg,
            "traceback": err_tb,
            "cwd": os.getcwd(),
        }
