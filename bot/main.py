"""
bot/main.py
────────────
نقطة الدخول الرئيسية — FastAPI app.

Routes:
  POST /webhook  — يستقبل updates من Telegram
  GET  /health   — health check لـ Vercel
  GET  /setup    — يسجل الـ webhook URL في Telegram (يتشغل مرة واحدة بعد الـ deploy)

مهم: Vercel بيستخدم الـ app object مباشرة كـ ASGI handler.
"""

import os
import json
import hmac
import hashlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import JSONResponse
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

# ── Logging Setup ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("shaher")

# ── Bot Instance ──
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
bot = Bot(token=TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None


app = FastAPI(
    title="شاهر الثاني",
    description="Personal AI Operating System",
    version="1.0.0",
    docs_url=None,   # نخفي Swagger في الإنتاج
    redoc_url=None,
)


# ── Global Exception Handler (Never return generic 500) ────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=200,
        content={
            "status": "error_handled",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
    )


# ── Root Welcome Endpoint ─────────────────────────────────
@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "شاهر الثاني — Shaher Brain",
        "message": "البوت السحابي يعمل بكفاءة 100% 🚀",
        "endpoints": {
            "health": "/health",
            "setup": "/setup?secret=shaher-setup-2024",
            "webhook": "/webhook (POST)"
        }
    }


# ── Health Check ──────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "شاهر الثاني",
        "version": "1.0.0",
        "bot_configured": bool(TELEGRAM_TOKEN),
        "supabase_configured": bool(os.getenv("SUPABASE_URL")),
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY_BRAIN")),
    }


# ── Webhook Setup (يتشغل مرة واحدة بعد الـ deploy) ───────
@app.get("/setup")
async def setup_webhook(secret: str = ""):
    """
    يسجل الـ webhook URL في Telegram.
    محمي بـ secret query param عشان ما يتشغلش بشكل عشوائي.
    مثال: https://your-app.vercel.app/setup?secret=YOUR_SECRET
    """
    setup_secret = os.getenv("SETUP_SECRET", "shaher-setup-2024")
    if secret != setup_secret:
        raise HTTPException(status_code=403, detail="Forbidden")

    if not bot:
        raise HTTPException(status_code=500, detail="Bot not configured")

    webhook_url = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")
    if not webhook_url:
        raise HTTPException(status_code=500, detail="WEBHOOK_BASE_URL not set")

    full_webhook = f"{webhook_url}/webhook"

    result = await bot.set_webhook(
        url=full_webhook,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )

    return {
        "success": result,
        "webhook_url": full_webhook,
        "message": "✅ Webhook set successfully" if result else "❌ Failed to set webhook",
    }


# ── Telegram Webhook ──────────────────────────────────────
@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    يستقبل كل updates من Telegram ويمررها لـ telegram_handler.
    """
    if not bot:
        logger.error("Bot not configured — missing TELEGRAM_BOT_TOKEN")
        return Response(content="ok", status_code=200)

    try:
        body = await request.body()
        update_data = json.loads(body)
    except Exception as e:
        logger.error(f"Failed to parse Telegram update: {e}")
        return Response(content="ok", status_code=200)

    # نعالج الـ update في الخلفية (non-blocking) عشان نرد فورًا بـ 200
    # Telegram بيعيد الإرسال لو مرجعلوش 200 خلال 10 ثواني
    try:
        from bot.telegram_handler import handle_update
        await handle_update(update_data, bot)
    except Exception as e:
        logger.error(f"Error handling update: {e}", exc_info=True)

    # لازم نرد بـ 200 دايمًا حتى لو فيه error
    return Response(content="ok", status_code=200)


# ── للتشغيل المحلي (development) ─────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "bot.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
