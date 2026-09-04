"""
workers/browser/gemini_worker.py
────────────────────────────────
أتمتة التفاعل مع Google Gemini عبر المتصفح (المحادثات المثبتة Pinned Gems).
يتضمن نظام Fallback متكامل مع brain/ai_client التابع لـ "شاهر الثاني" في حال حدوث أي خطأ.
"""

import logging
import time
from typing import Dict, Any, Optional

from config.settings import PINNED_CHATS
from config.selectors import GEMINI_SELECTORS
from workers.browser.cdp_client import get_cdp_manager

logger = logging.getLogger("GeminiWorker")


def ask_gemini_browser(pinned_chat_key: str, prompt: str) -> Dict[str, Any]:
    """
    إرسال برومبت لمحادثة جيمناي المثبتة بالمتصفح واسترجاع الرد.
    """
    target_url = PINNED_CHATS.get(pinned_chat_key, "https://gemini.google.com")
    cdp_manager = get_cdp_manager()
    page = None

    try:
        logger.info(f"فتح جيمناي: {pinned_chat_key} -> {target_url}...")
        page = cdp_manager.new_page()
        page.goto(target_url, wait_until="domcontentloaded")

        # 1. العثور على مربع الكتابة
        input_locator = None
        for sel in GEMINI_SELECTORS["input_box"]:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                input_locator = loc
                break

        if not input_locator:
            # تجربة إيجاد أي مربع قابل للتعديل
            input_locator = page.locator("div[contenteditable='true']").first

        input_locator.click()
        input_locator.fill(prompt)
        page.keyboard.press("Enter")

        # 2. الانتظار الذكي حتى ينتهي التوليد
        logger.info("انتظار رد جيمناي...")
        # انتظار أولي لبدء الرد
        page.wait_for_timeout(3000)

        # انتظار استقرار النص أو اختفاء زر Stop
        last_text = ""
        stable_count = 0
        max_wait = 45  # ثانية كحد أقصى
        start_time = time.time()

        while time.time() - start_time < max_wait:
            resp_locator = None
            for sel in GEMINI_SELECTORS["response_container"]:
                loc = page.locator(sel).last
                if loc.count() > 0 and loc.is_visible():
                    resp_locator = loc
                    break

            if resp_locator:
                current_text = resp_locator.inner_text().strip()
                if current_text and current_text == last_text:
                    stable_count += 1
                    if stable_count >= 3:  # النص لم يتغير لمدة 3 ثوانٍ = انتهى التوليد
                        break
                else:
                    stable_count = 0
                    last_text = current_text

            page.wait_for_timeout(1000)

        if not last_text:
            raise RuntimeError("لم يتم العثور على رد أو انتهت مهلة الانتظار في متصفح جيمناي.")

        return {
            "status": "ok",
            "source": "gemini_browser",
            "pinned_chat": pinned_chat_key,
            "response": last_text,
        }

    except Exception as exc:
        logger.warning(f"تعذر استدعاء جيمناي عبر المتصفح ({exc}) — تشغيل الـ Fallback عبر Shaher Brain...")
        return _fallback_to_brain_ai(prompt, fallback_reason=str(exc))

    finally:
        if page:
            try:
                page.close()
            except Exception:
                pass


def _fallback_to_brain_ai(prompt: str, fallback_reason: str) -> Dict[str, Any]:
    """
    التحول التلقائي لسلسلة الذكاء الاصطناعي في المرحلة الأولى (brain/ai_client).
    """
    try:
        import asyncio
        from brain.ai_client import get_ai_response

        ai_resp = asyncio.run(
            get_ai_response(
                user_message=prompt,
                component="brain",
            )
        )
        return {
            "status": "ok",
            "source": f"fallback_{ai_resp.source}",
            "response": ai_resp.content,
            "fallback_note": f"تم استخدام البديل بسبب: {fallback_reason}",
        }
    except Exception as exc:
        logger.error(f"فشل الـ Fallback أيضاً: {exc}")
        return {
            "status": "error",
            "error": f"فشل المتصفح ({fallback_reason}) وفشل الـ Fallback ({exc})",
        }
