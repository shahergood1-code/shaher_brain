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
    Gemini 1.5 Flash / 2.0 Flash يدعمان إدخال الصوت مباشرة وبسرعة فائقة.
    """
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        
        # التأكد من صحة اسم الموديل الرسمي
        if "3.6" in model_name:
            model_name = "gemini-1.5-flash"

        # قراءة بايتس الملف مباشرة بدون الحاجة لرفع وحذف منفصل
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        model = genai.GenerativeModel(model_name)

        prompt = (
            "You are a speech-to-text transcription engine. "
            "Transcribe the spoken audio verbatim into accurate Arabic or English as spoken. "
            "Do NOT add any explanation, prefix, quotes, or commentary. Output ONLY the exact transcribed text."
        )

        response = await asyncio.wait_for(
            asyncio.to_thread(
                model.generate_content,
                [
                    {"mime_type": "audio/ogg", "data": audio_bytes},
                    prompt,
                ]
            ),
            timeout=10.0
        )

        if response and response.text:
            text = response.text.strip()
            return text if text else None

    except Exception as e:
        print(f"⚠️ فشل Gemini transcription ({type(e).__name__}): {e}")

    # Fallback to SeekAI / Whisper if available
    seekai_key = os.getenv("SEEKAI_API_KEY")
    if seekai_key:
        try:
            from openai import AsyncOpenAI
            base_url = os.getenv("SEEKAI_BASE_URL", "https://api.seekai.tools/v1")
            client = AsyncOpenAI(api_key=seekai_key, base_url=base_url)
            with open(audio_path, "rb") as audio_file:
                transcript = await client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                )
                if transcript and transcript.text:
                    return transcript.text.strip()
        except Exception as e:
            print(f"⚠️ فشل SeekAI whisper fallback: {e}")

    return None
