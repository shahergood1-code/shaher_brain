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

import asyncio
import logging
import os

logger = logging.getLogger("telegram_handler")

from telegram import Bot, Update
from telegram.constants import ChatAction

from bot.voice_handler import transcribe_voice
from brain.ai_client import get_ai_response
from brain.image_client import generate_image
from brain.router import MessageIntent, handle_command, route
from memory.logger import get_full_context, log_interaction


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


async def handle_update(update_data: dict | Update, bot: Bot) -> None:
    """
    نقطة الدخول الرئيسية — بتاخد update من Telegram وتعالجه.
    بيتستدعى من webhook في main.py أو من polling في run_polling.py
    """
    if isinstance(update_data, Update):
        update = update_data
    else:
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
        cmd_clean = user_text.strip().split()[0].lower().lstrip("/!")

        # 1. أمر تشغيل وإنتاج فيديو شورتس فيروزي فوري
        if cmd_clean in ["content_run", "run_content"]:
            # استخراج الموضوع المخصص لو كتبه المستخدم بعد الأمر
            parts = user_text.strip().split(maxsplit=1)
            custom_topic = parts[1] if len(parts) > 1 else "لغز اختفاء لعبة شهيرة في عام 2004"

            await bot.send_message(
                chat_id=chat_id,
                text=(
                    f"🎬 *بدء دورة إنتاج ومونتاج الشورتس الفيروسي فوراً...*\n"
                    f"🎯 *الموضوع:* {custom_topic}\n\n"
                    f"⏳ *مراحل التنفيذ الآلية:*\n"
                    f"1️⃣ صياغة السكريبت وفق قواعد الفضول وسيكولوجية النوستالجيا\n"
                    f"2️⃣ مراجعة وفلترة السكريبت عبر الناقد القاسي (The Ruthless Critic)\n"
                    f"3️⃣ توليد الفويس أوفر والترجمة المغناطيسية الفيروسية (Yellow ASS)\n"
                    f"4️⃣ المونتاج وحركة الكاميرا (Ken-Burns) والتصدير بـ NVENC على كارت RTX 4070..."
                ),
                parse_mode="Markdown"
            )

            try:
                from core.orchestrator import produce_viral_short_pipeline
                res = await produce_viral_short_pipeline(topic=custom_topic)

                if res.get("status") == "ok" and res.get("video_path") and os.path.exists(res["video_path"]):
                    video_file_path = res["video_path"]
                    caption_text = (
                        f"🎥 *{res.get('title', 'فيديو شورتس فيروزي')}*\n\n"
                        f"🧐 *تقييم الناقد القاسي:* `{res.get('critic_score')}/10`\n"
                        f"⚡ *زمن الإنتاج الكامل:* `{res.get('production_time_sec')} ثانية`\n\n"
                        f"📝 *السكريبت:*\n_{res.get('script', '')[:280]}..._\n\n"
                        f"🏷️ {res.get('caption', '')}"
                    )

                    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)
                    with open(video_file_path, "rb") as vf:
                        try:
                            await bot.send_video(
                                chat_id=chat_id,
                                video=vf,
                                caption=caption_text,
                                parse_mode="Markdown",
                                supports_streaming=True,
                            )
                        except Exception:
                            # في حال تعذر إرسال الفيديو كـ stream نرسله كملف document
                            vf.seek(0)
                            await bot.send_document(
                                chat_id=chat_id,
                                document=vf,
                                caption=caption_text,
                                parse_mode="Markdown",
                            )
                    return
                else:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"⚠️ تعذر إكمال الريندر: {res.get('error', 'خطأ غير معروف')}"
                    )
                    return
            except Exception as pipe_err:
                logger.error(f"خطأ أثناء تشغيل خط إنتاج الشورتس: {pipe_err}", exc_info=True)
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ حدث خطأ أثناء إنتاج الفيديو: `{pipe_err}`",
                    parse_mode="Markdown"
                )
                return

        # 2. أمر تجهيز هرم المحتوى الأسبوعي بالكامل
        if cmd_clean in ["content_batch", "batch_content"]:
            parts = user_text.strip().split(maxsplit=1)
            custom_niche = parts[1] if len(parts) > 1 else "أسرار الألعاب والنوستالجيا المظلمة وألغاز الإنترنت"

            await bot.send_message(
                chat_id=chat_id,
                text=(
                    f"📅 *جاري إعداد هرم المحتوى الأسبوعي الكامل (Weekly Batch)...*\n"
                    f"🎯 *النيتش:* {custom_niche}\n"
                    f"⏳ يتم الآن تخطيط 2 فيديو طويل (8-12 دقيقة) بـ 4 فصول + 7 شورتس يومية + تصميم الأغلفة الصادمة..."
                ),
                parse_mode="Markdown"
            )

            try:
                from core.weekly_batch import run_weekly_batch_pipeline
                batch_res = await run_weekly_batch_pipeline(niche=custom_niche)

                await bot.send_message(
                    chat_id=chat_id,
                    text=batch_res.get("summary", "تم تجهيز الحزمة الأسبوعية بنجاح!"),
                )

                # إرسال معاينات الأغلفة الصادمة
                for thumb in batch_res.get("thumbnails", []):
                    t_url = thumb.get("thumbnail_url")
                    if t_url:
                        try:
                            await bot.send_photo(
                                chat_id=chat_id,
                                photo=t_url,
                                caption=f"🎨 *غلاف Split-Screen صادم:*\n{thumb.get('video_title')}",
                                parse_mode="Markdown"
                            )
                        except Exception:
                            pass
                return
            except Exception as batch_err:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ تعذر إنهاء حزمة الأسبوع: {batch_err}"
                )
                return

        # 3. أمر توليد فيلم وثائقي طويل بنظام 3D Mannequin
        if cmd_clean in ["documentary", "doc", "mannequin", "وثائقي"]:
            parts = user_text.strip().split(maxsplit=1)
            custom_topic = parts[1] if len(parts) > 1 else ""

            await bot.send_message(
                chat_id=chat_id,
                text=(
                    f"🎬 *بدء تشغيل محرك الوثائقيات الطويلة (3D Mannequin System)...*\n"
                    f"🎯 *الموضوع:* {custom_topic or 'اختيار وتوليد فكرة استقصائية كبرى تلقائياً'}\n\n"
                    f"🛡️ *المعايير المعمارية المفعلة:*\n"
                    f"• ثبات الهوية البصرية 100% رياضياً عبر المشاهد بنظام المانيكان المفرغ\n"
                    f"• درع الحماية الإعلاني (Zero Gore / 100% YouTube Monetization)\n"
                    f"• نظام الألوان الثلاثي: ⚪ محايد/شهود | 🔴 خطر وتهديد | 🔵 ضحايا وفلاش باك\n"
                    f"• إعداد الـ Character Sheet والسكريبت وبرومبتات المشاهد والغلاف 16:9..."
                ),
                parse_mode="Markdown"
            )

            try:
                from core.mannequin_engine import MannequinDocumentaryEngine
                engine = MannequinDocumentaryEngine()
                package = await engine.generate_full_documentary_package(
                    topic=custom_topic,
                    duration="5m",
                )

                exported_files = package.get("exported_files", {})
                md_file_path = exported_files.get("markdown")

                summary_msg = (
                    f"✅ *تم بنجاح إعداد حزمة الوثائقي الكاملة!*\n\n"
                    f"📌 *العنوان:* {package.get('title')}\n"
                    f"⏱️ *المدة:* {package.get('duration')} | *إجمالي المشاهد:* {package.get('total_scenes')} مشهداً\n\n"
                    f"🎭 *ورقة تثبيت الهوية (Character Sheet):*\n"
                    f"_{package.get('character_sheet', {}).get('character_sheet_prompt', '')[:220]}..._\n\n"
                    f"📝 *مقتطف من السكريبت:*\n"
                    f"_{package.get('full_voiceover_arabic', '')[:250]}..._\n\n"
                    f"🏷️ *أفضل عنوان مقترح:* {package.get('metadata', {}).get('titles', [''])[0]}\n\n"
                    f"📁 *تم تصدير ملف الحزمة السينمائية الكاملة أدناه:*"
                )

                await bot.send_message(
                    chat_id=chat_id,
                    text=summary_msg,
                    parse_mode="Markdown"
                )

                # إرسال ملف الـ Markdown الكامل كـ Document
                if md_file_path and os.path.exists(md_file_path):
                    with open(md_file_path, "rb") as mf:
                        await bot.send_document(
                            chat_id=chat_id,
                            document=mf,
                            filename=os.path.basename(md_file_path),
                            caption=f"🎬 حزمة برومبتات وسيناريو: {package.get('title')}",
                        )
                return
            except Exception as doc_err:
                logger.error(f"خطأ أثناء توليد الوثائقي: {doc_err}", exc_info=True)
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ تعذر إنهاء حزمة الوثائقي: `{doc_err}`",
                    parse_mode="Markdown"
                )
                return

        # باقي الأوامر العادية
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
        # تسجيل التفاعل في الخلفية بدون تأخير استجابة الـ Webhook
        asyncio.create_task(
            log_interaction(
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

    # ── إرسال الرد لـ Telegram (مع دعم الرسائل الطويلة وملفات الأكواد) ──
    response_to_send = ai_result.content
    
    # 1. إرسال النص مع دعم التقسيم التلقائي لو تجاوز 4000 حرف
    max_chunk = 3900
    if len(response_to_send) <= max_chunk:
        try:
            await bot.send_message(chat_id=chat_id, text=response_to_send, parse_mode="Markdown")
        except Exception:
            await bot.send_message(chat_id=chat_id, text=response_to_send)
    else:
        # تقسيم الرد لأجزاء
        chunks = [response_to_send[i:i + max_chunk] for i in range(0, len(response_to_send), max_chunk)]
        for chunk in chunks:
            try:
                await bot.send_message(chat_id=chat_id, text=chunk, parse_mode="Markdown")
            except Exception:
                await bot.send_message(chat_id=chat_id, text=chunk)

    # 2. ميزة المطورين: إذا كان الرد يحتوي على كود برمجي كامل لموقع أو سكريبت، نرسله كملف جاهز للتشغيل
    if "```html" in response_to_send.lower() or "```python" in response_to_send.lower() or "<!doctype html>" in response_to_send.lower():
        try:
            import io

            
            if "```html" in response_to_send.lower():
                ext = "html"
                fname = "website_preview.html"
            elif "```python" in response_to_send.lower():
                ext = "py"
                fname = "script.py"
            else:
                ext = "html"
                fname = "index.html"

            # استخراج الكود النقي
            start_code = response_to_send.find(f"```{ext}")
            if start_code != -1:
                start_code += len(f"```{ext}")
                end_code = response_to_send.find("```", start_code)
                code_content = response_to_send[start_code:end_code].strip() if end_code != -1 else response_to_send[start_code:].strip()
            else:
                code_content = response_to_send

            file_bytes = io.BytesIO(code_content.encode("utf-8"))
            file_bytes.name = fname
            await bot.send_document(
                chat_id=chat_id,
                document=file_bytes,
                caption=f"📁 *ملف الكود جاهز للتشغيل والتحميل:* `{fname}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"[WARN] Failed to send code file: {e}")

    # ── تسجيل التفاعل في Supabase والتعلم الذاتي في الخلفية ──
    asyncio.create_task(
        log_interaction(
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
    )
    
    # ── محرك التعلّم الذاتي والتطور المستمر ──
    try:
        from memory.learning_engine import auto_learn_from_interaction
        asyncio.create_task(auto_learn_from_interaction(user_text, ai_result.content))
    except Exception:
        pass
