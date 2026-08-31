"""
bot/telegram_handler.py
────────────────────────
معالجة الرسائل الجاية من Telegram.

بيستقبل:
  - رسائل نصية
  - رسائل صوتية (voice notes)

ثم يمر على:
  1. Shaher Brain Router → تحديد نوع الطلب
  2. AI Client → الحصول على رد
  3. Memory Logger → تسجيل التفاعل
  4. إرسال الرد لـ Telegram
"""

import os
import time
import asyncio
from telegram import Update, Bot
from telegram.constants import ChatAction

from brain.router import route, MessageIntent, handle_command
from brain.ai_client import get_ai_response
from brain.image_client import generate_image
from memory.logger import log_interaction, get_full_context
from bot.voice_handler import transcribe_voice


# Telegram user IDs المصرح لهم (حماية البوت في البداية)
def _get_authorized_ids() -> set[int]:
    raw = os.getenv("AUTHORIZED_USER_ID", "")
    ids = set()
    for part in raw.split(","):
        try:
            ids.add(int(part.strip()))
        except ValueError:
            pass
    return ids


AUTHORIZED_IDS = _get_authorized_ids()


async def handle_update(update_data: dict, bot: Bot) -> None:
    """
    نقطة الدخول الرئيسية — بتاخد update من Telegram وتعالجه.
    بيتستدعى من webhook في main.py
    """
    update = Update.de_json(update_data, bot)

    if not update.message:
        return  # ignore non-message updates

    message = update.message
    user_id = message.from_user.id if message.from_user else None
    chat_id = message.chat.id

    # ── التحقق من الصلاحية ──
    if AUTHORIZED_IDS and user_id not in AUTHORIZED_IDS:
        await bot.send_message(chat_id=chat_id, text="🔒 غير مصرح بالوصول.")
        return

    # ── تحديد نوع الرسالة وجلب النص ──
    message_type = "text"
    user_text = None

    if message.text:
        user_text = message.text.strip()

    elif message.voice:
        # رسالة صوتية — نحولها لنص أولًا
        message_type = "voice"
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

        gemini_key = os.getenv("GEMINI_API_KEY_BRAIN")
        user_text = await transcribe_voice(bot, message.voice.file_id, gemini_key)

        if not user_text:
            await bot.send_message(
                chat_id=chat_id,
                text="⚠️ مقدرتش أفهم الرسالة الصوتية. جرب ابعت نص."
            )
            return

    else:
        # نوع رسالة مش مدعوم (صورة، مستند، إلخ)
        await bot.send_message(
            chat_id=chat_id,
            text="📝 دلوقتي بدعم النص والصوت بس. باقي أنواع الملفات قريبًا!"
        )
        return

    # إظهار "يكتب..." أثناء المعالجة
    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    # ── Shaher Brain: تصنيف الطلب ──
    decision = route(user_text)

    # ── معالجة الأوامر مباشرة ──
    if decision.intent == MessageIntent.COMMAND:
        response_text = await handle_command(user_text)
        await bot.send_message(
            chat_id=chat_id,
            text=response_text,
            parse_mode="Markdown"
        )
        await log_interaction(
            user_message=user_text,
            ai_response=response_text,
            ai_source="command",
            message_type=message_type,
            telegram_user_id=user_id,
            telegram_chat_id=chat_id,
        )
        return

    # ── توليد صورة ──
    if decision.intent == MessageIntent.IMAGE_GENERATION:
        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
        img_result = await generate_image(
            prompt=user_text,
        )
        if img_result.error or not img_result.image_url:
            await bot.send_message(
                chat_id=chat_id,
                text=f"❌ فشل توليد الصورة:\n`{img_result.error}`",
                parse_mode="Markdown",
            )
        else:
            caption = f"🎨 *{img_result.model_used}* ({img_result.size})\n_{user_text[:100]}_"
            try:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=img_result.image_url,
                    caption=caption,
                    parse_mode="Markdown",
                )
            except Exception:
                # لو الـ URL انتهت صلاحيته، نبعت الرابط كنص
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"🎨 الصورة جاهزة ({img_result.size}):\n{img_result.image_url}",
                )
        await log_interaction(
            user_message=user_text,
            ai_response=img_result.image_url or img_result.error or "",
            ai_source="image_gen",
            ai_model=img_result.model_used,
            message_type=message_type,
            telegram_user_id=user_id,
            telegram_chat_id=chat_id,
            response_time_ms=img_result.response_time_ms,
            error_details=img_result.error,
        )
        return

    # ── جلب السياق الكامل من الذاكرة ──────────────────────────
    # get_full_context() بيجيب: آخر محادثات + مشاريع + تفضيلات + قرارات
    # ده اللي بيخلي شاهر يحس زي ChatGPT/Claude — شايف عالمك كامل
    context = {}
    if decision.needs_history:
        context = await get_full_context()

    # ── الحصول على رد من AI ──
    ai_result = await get_ai_response(
        user_message=user_text,
        context=context,
        component="brain",
    )

    # ── إرسال الرد لـ Telegram ──
    response_to_send = ai_result.content
    # Telegram Markdown parsing — نحاول أولًا بـ Markdown
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=response_to_send,
            parse_mode="Markdown",
        )
    except Exception:
        # لو فيه حاجة في التنسيق غلط، نبعت plain text
        await bot.send_message(chat_id=chat_id, text=response_to_send)

    # ── تسجيل التفاعل في Supabase ──
    await log_interaction(
        user_message=user_text,
        ai_response=ai_result.content,
        ai_source=ai_result.source,
        ai_model=ai_result.model,
        message_type=message_type,
        telegram_user_id=user_id,
        telegram_chat_id=chat_id,
        response_time_ms=ai_result.response_time_ms,
        tokens_used=ai_result.tokens_used,
        error_details=ai_result.error,
    )
