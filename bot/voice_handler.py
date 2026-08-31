"""
bot/voice_handler.py
─────────────────────
تحويل Telegram voice notes لنص.

الطريقة:
  - Telegram بيديك file_id للـ voice note
  - بنحمله بـ Telegram Bot API
  - بنستخدم Gemini لتحويله لنص (لو متاح)
  - أو بنستخدم ffmpeg + whisper (مكتبة openai-whisper) كـ fallback

المرحلة 1: بنستخدم Gemini multimodal لتحويل الصوت لنص مباشرة.
"""

import os
import tempfile
import asyncio
from pathlib import Path
from telegram import Bot


async def transcribe_voice(
    bot: Bot,
    file_id: str,
    gemini_api_key: str | None = None,
) -> str | None:
    """
    بياخد file_id من Telegram ويرجع النص المحوَّل.
    بيرجع None لو فشل التحويل.
    """
    try:
        # ── تحميل الملف من Telegram ──
        tg_file = await bot.get_file(file_id)

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name

        await tg_file.download_to_drive(tmp_path)

        # ── محاولة التحويل بـ Gemini Multimodal ──
        if gemini_api_key:
            result = await _transcribe_with_gemini(tmp_path, gemini_api_key)
            if result:
                return result

        # ── Fallback: إرجاع رسالة توضيحية ──
        return "[رسالة صوتية — التحويل لنص غير متاح حاليًا]"

    except Exception as e:
        print(f"⚠️ فشل تحويل الصوت: {e}")
        return None
    finally:
        # تنظيف الملف المؤقت
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


async def _transcribe_with_gemini(audio_path: str, api_key: str) -> str | None:
    """
    بيستخدم Gemini multimodal API لتحويل الصوت لنص.
    Gemini 1.5 Flash/Pro بيدعم audio input مباشرة.
    """
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)

        # رفع الملف لـ Gemini Files API
        audio_file = await asyncio.to_thread(
            genai.upload_file,
            path=audio_path,
            mime_type="audio/ogg",
        )

        model = genai.GenerativeModel("gemini-3.6-flash")

        response = await asyncio.to_thread(
            model.generate_content,
            [
                audio_file,
                "حوّل الكلام الموجود في الملف الصوتي ده لنص مكتوب بدقة. "
                "مش محتاج تضيف أي تعليق، بس النص الحرفي.",
            ],
        )

        # حذف الملف من Gemini بعد الاستخدام
        try:
            await asyncio.to_thread(genai.delete_file, audio_file.name)
        except Exception:
            pass

        return response.text.strip() if response.text else None

    except Exception as e:
        print(f"⚠️ فشل Gemini transcription: {e}")
        return None
