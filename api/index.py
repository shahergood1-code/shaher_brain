"""
api/index.py
────────────
نقطة الدخول الرسمية لـ Vercel Serverless Function.
تعرف كائن app = FastAPI() بشكل مباشر في أعلى الملف لتوافق Vercel CLI 59+.
"""

import sys
from pathlib import Path
from fastapi import FastAPI

# إضافة مجلد المشروع إلى مسارات بايثون
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# تعريف كائن FastAPI مباشرة في أعلى النطاق ليتعرف عليه محلل Vercel CLI بدقة
app = FastAPI(
    title="شاهر الثاني",
    description="Personal AI Operating System — Cloud Webhook Handler",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)

# استيراد المسارات من bot/main.py وتثبيتها على الـ app
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
