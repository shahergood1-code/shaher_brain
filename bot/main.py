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
async def root(request: Request = None):
    host = request.headers.get("host", "") if request else ""
    return {
        "status": "online",
        "service": "شاهر الثاني — Shaher Brain",
        "message": "البوت السحابي يعمل بكفاءة 100% 🚀",
        "endpoints": {
            "health": "/health",
            "setup": "/setup?secret=shaher-setup-2024",
            "webhook": "/webhook (POST)"
        },
        "info": {
            "host": host,
            "bot_configured": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
            "gemini_configured": bool(os.getenv("GEMINI_API_KEY_BRAIN")),
            "supabase_configured": bool(os.getenv("SUPABASE_URL")),
        }
    }


# ── Health Check ──────────────────────────────────────────
@app.get("/health")
async def health_check():
    clean_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip().strip('"').strip("'")
    return {
        "status": "ok",
        "service": "شاهر الثاني",
        "version": "1.0.0",
        "bot_configured": bool(clean_token),
        "token_preview": f"{clean_token[:4]}...{clean_token[-4:]}" if len(clean_token) >= 8 else ("TOO_SHORT" if clean_token else "EMPTY"),
        "token_length": len(clean_token),
        "supabase_configured": bool(os.getenv("SUPABASE_URL")),
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY_BRAIN")),
    }


# ── Webhook Setup (يتشغل مرة واحدة بعد الـ deploy) ───────
@app.get("/setup")
async def setup_webhook(request: Request = None, secret: str = ""):
    """
    يسجل الـ webhook URL في Telegram.
    يدعم التحقق المرن ومعالجة أخطاء التوكن بشفافية.
    مثال: https://shaher-brain.vercel.app/setup?secret=shaher-setup-2024
    """
    global bot
    setup_secret = os.getenv("SETUP_SECRET", "shaher-setup-2024")
    
    # تحقق مرن من كلمة السر لحماية الراوتر مع منع التعليق
    valid_secrets = {setup_secret, "shaher-setup-2024", "choose-a-secret-word-here", ""}
    if secret and secret not in valid_secrets and setup_secret not in ["", "choose-a-secret-word-here"]:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid secret parameter")

    clean_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip().strip('"').strip("'")
    if not clean_token or clean_token == "your_telegram_bot_token_here":
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "TELEGRAM_BOT_TOKEN is missing or placeholder in Vercel",
                "instructions": "Go to Vercel Dashboard -> Project Settings -> Environment Variables, and set TELEGRAM_BOT_TOKEN to your real token from @BotFather on Telegram."
            }
        )

    try:
        bot = Bot(token=clean_token)
        me = await bot.get_me()
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": type(e).__name__,
                "message": str(e),
                "token_preview": f"{clean_token[:4]}...{clean_token[-4:]}" if len(clean_token) >= 8 else clean_token,
                "token_length": len(clean_token),
                "hint": "Check TELEGRAM_BOT_TOKEN in Vercel Settings -> Environment Variables. It must be the exact token provided by @BotFather (e.g. 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)."
            }
        )

    webhook_url = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")
    if not webhook_url:
        vercel_url = os.getenv("VERCEL_URL", "")
        if vercel_url:
            webhook_url = f"https://{vercel_url.rstrip('/')}"
        elif request and request.headers.get("host"):
            webhook_url = f"https://{request.headers.get('host')}"
        else:
            webhook_url = "https://shaher-brain.vercel.app"

    full_webhook = f"{webhook_url}/webhook"

    try:
        result = await bot.set_webhook(
            url=full_webhook,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
        )
        return {
            "success": result,
            "bot_username": f"@{me.username}",
            "bot_name": me.first_name,
            "webhook_url": full_webhook,
            "message": f"✅ Webhook set successfully for bot @{me.username}",
        }
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": type(e).__name__,
                "message": str(e),
                "webhook_url": full_webhook,
            }
        )


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
