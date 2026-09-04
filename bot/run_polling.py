"""
bot/run_polling.py
──────────────────
تشغيل البوت محلياً بنظام Long Polling بدون الحاجة لأي سيرفر سحابي أو Webhook.
مجاني 100% ويعمل مباشرة على جهازك مستفيداً من الـ RTX 4070 و Ollama المحلي!
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv
from telegram import Bot

# إضافة مسار المشروع
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("shaher_polling")


async def start_polling():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("❌ TELEGRAM_BOT_TOKEN غير موجود في ملف .env")
        return

    bot = Bot(token=token)
    me = await bot.get_me()
    logger.info(f"🚀 تم بدء تشغيل شاهر الثاني محلياً (Polling): @{me.username} ({me.first_name})")

    # حذف الـ Webhook القديم للسماح بنظام الـ Polling
    logger.info("🔄 جاري إلغاء أي Webhook قديم لتفعيل الاستقبال المحلي المباشر...")
    await bot.delete_webhook(drop_pending_updates=False)
    logger.info("✅ البوت جاهز ويستمع للرسائل الآن (0$ وبدون أي سيرفر خارجي)...")

    from bot.telegram_handler import handle_update

    offset = None
    while True:
        try:
            updates = await bot.get_updates(offset=offset, timeout=20, allowed_updates=["message", "callback_query"])
            for update in updates:
                offset = update.update_id + 1
                asyncio.create_task(handle_update(update.to_dict(), bot))
        except asyncio.CancelledError:
            logger.info("🛑 تم إيقاف البوت المحلي.")
            break
        except Exception as e:
            logger.warning(f"⚠️ خطأ أثناء جلب التحديثات: {e}")
            await asyncio.sleep(2)


if __name__ == "__main__":
    try:
        asyncio.run(start_polling())
    except KeyboardInterrupt:
        print("\n👋 تم إيقاف التشغيل المحلي بنجاح.")
