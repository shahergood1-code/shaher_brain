"""
bot/run_polling.py
──────────────────
تشغيل البوت محلياً بنظام Long Polling.

النظام المزدوج (محلي + Vercel):
  - لما البوت المحلي شغال: بيحذف الـ Webhook ويستقبل الرسائل مباشرة بـ Ollama RTX 4070
  - لما البوت المحلي مش شغال: Vercel يشتغل تلقائياً عبر الـ Webhook (Gemini/NVIDIA)

ملاحظة: Telegram لا يسمح بالـ Polling والـ Webhook في نفس الوقت.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram import Bot
from telegram.error import Conflict, NetworkError, TimedOut

# إضافة مسار المشروع
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("shaher_polling")

# ── إعادة تسجيل الـ Webhook بعد الإيقاف (اختياري) ──────────────
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "").strip().strip('"')
RESTORE_WEBHOOK_ON_EXIT = (
    bool(WEBHOOK_BASE_URL)
    and os.getenv("RESTORE_WEBHOOK_ON_EXIT", "true").lower() == "true"
)


async def start_polling():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip().strip('"')
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found in .env")
        return

    bot = Bot(token=token)
    try:
        me = await bot.get_me()
        logger.info(f"Bot: @{me.username} ({me.first_name}) — connected!")
    except Exception as e:
        logger.error(f"Failed to connect to Telegram: {e}")
        return

    # حذف الـ Webhook ليبدأ الـ Polling
    logger.info("Deleting existing Webhook to enable local Polling...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted. Now listening via Local Polling (Ollama/RTX 4070)...")
    except Exception as e:
        logger.warning(f"Could not delete webhook: {e}")

    from bot.telegram_handler import handle_update

    offset = None
    consecutive_errors = 0

    try:
        while True:
            try:
                updates = await bot.get_updates(
                    offset=offset,
                    timeout=20,
                    allowed_updates=["message", "callback_query"],
                )
                consecutive_errors = 0

                for update in updates:
                    offset = update.update_id + 1
                    asyncio.create_task(handle_update(update, bot))

            except asyncio.CancelledError:
                logger.info("Bot polling cancelled gracefully.")
                break

            except Conflict as e:
                logger.error(f"Conflict: {e}")
                logger.error("Another bot instance is running. Stop it first, then restart.")
                await asyncio.sleep(5)
                break

            except (NetworkError, TimedOut) as e:
                consecutive_errors += 1
                wait = min(consecutive_errors * 2, 30)
                logger.warning(f"Network error ({e}) — retrying in {wait}s...")
                await asyncio.sleep(wait)

            except Exception as e:
                consecutive_errors += 1
                wait = min(consecutive_errors * 2, 30)
                logger.warning(f"Error: {type(e).__name__}: {e} — retrying in {wait}s")
                await asyncio.sleep(wait)

    finally:
        # إعادة تسجيل الـ Webhook لـ Vercel بعد إيقاف البوت المحلي
        if RESTORE_WEBHOOK_ON_EXIT and WEBHOOK_BASE_URL:
            try:
                webhook_url = f"{WEBHOOK_BASE_URL.rstrip('/')}/webhook"
                await bot.set_webhook(
                    url=webhook_url,
                    allowed_updates=["message", "callback_query"],
                )
                logger.info(f"Webhook restored to Vercel: {webhook_url}")
            except Exception as e:
                logger.warning(f"Failed to restore webhook: {e}")
        logger.info("Bot polling stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(start_polling())
    except KeyboardInterrupt:
        print("\nBot stopped by user (Ctrl+C).")
