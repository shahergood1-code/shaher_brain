"""
workers/browser/flow_worker.py
──────────────────────────────
أتمتة توليد المشاهد البصرية عبر Google Flow:
- توليد صور ثابتة عبر Nano Banana 2.
- تحريك المشاهد عبر Veo Lite.
- Fallback تلقائي لمولد الصور في المرحلة الأولى (brain/image_client.py) عند التعذر.
"""

import logging
from pathlib import Path
from typing import Any

from config.selectors import FLOW_SELECTORS
from config.settings import FLOW_URL, IMAGES_DIR, RAW_SCENES_DIR
from workers.browser.cdp_client import get_cdp_manager

logger = logging.getLogger("FlowWorker")


def generate_flow_image(prompt: str, save_as: str = "image.png") -> dict[str, Any]:
    """
    يفتح Flow، يختار Nano Banana 2، يدخل البرومبت، ويحمل الصورة الناتجة.
    """
    dest_path = IMAGES_DIR / save_as
    cdp_manager = get_cdp_manager()
    page = None

    try:
        logger.info(f"فتح Flow لتوليد صورة: '{prompt[:40]}...'")
        page = cdp_manager.new_page()
        page.goto(FLOW_URL, wait_until="domcontentloaded")

        # 1. إدخال البرومبت
        prompt_box = None
        for sel in FLOW_SELECTORS["image_prompt_input"]:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                prompt_box = loc
                break

        if not prompt_box:
            prompt_box = page.locator("textarea").first

        prompt_box.click()
        prompt_box.fill(prompt)

        # 2. زر التوليد
        gen_btn = None
        for sel in FLOW_SELECTORS["generate_button"]:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                gen_btn = loc
                break

        if gen_btn:
            gen_btn.click()
        else:
            page.keyboard.press("Enter")

        logger.info("انتظار توليد الصورة في Flow...")
        # انتظار التوليد وتحميل الملف
        with page.expect_download(timeout=45000) as download_info:
            # محاولة النقر على زر التحميل بعد ظهوره
            download_btn = page.locator("button[aria-label*='Download'], button:has-text('Download')").first
            download_btn.wait_for(state="visible", timeout=40000)
            download_btn.click()

        download = download_info.value
        download.save_as(str(dest_path))
        logger.info(f"تم حفظ الصورة من Flow: {dest_path}")

        return {
            "status": "ok",
            "path": str(dest_path),
            "filename": save_as,
            "engine": "flow_nano_banana_2",
        }

    except Exception as exc:
        logger.warning(f"تعذر التوليد عبر Flow المتصفح ({exc}) — تجربة Fallback المحلي عبر SeekAI...")
        return _fallback_to_brain_image(prompt, dest_path, str(exc))

    finally:
        if page:
            try:
                page.close()
            except Exception:
                pass


def generate_flow_video(source_image: str, motion_prompt: str, save_as: str = "scene.mp4") -> dict[str, Any]:
    """
    تحريك صورة ثابتة عبر Veo Lite في Flow وحفظ مقطع الفيديو الناتج.
    """
    source_path = Path(source_image)
    if not source_path.is_absolute():
        source_path = IMAGES_DIR / source_image
        if not source_path.exists():
            source_path = RAW_SCENES_DIR / source_image

    dest_path = RAW_SCENES_DIR / save_as
    cdp_manager = get_cdp_manager()
    page = None

    try:
        logger.info(f"فتح Flow لتحريك مشهد بـ Veo Lite: '{motion_prompt[:40]}...'")
        page = cdp_manager.new_page()
        page.goto(FLOW_URL, wait_until="domcontentloaded")

        # 1. رفع الصورة المصدر
        if source_path.exists():
            page.set_input_files("input[type='file']", str(source_path))
            page.wait_for_timeout(2000)

        # 2. كتابة برومبت الحركة
        motion_box = page.locator("textarea").first
        motion_box.click()
        motion_box.fill(motion_prompt)

        # 3. الضغط على Generate
        page.keyboard.press("Enter")

        logger.info("انتظار تحريك الفيديو عبر Veo Lite...")
        with page.expect_download(timeout=90000) as download_info:
            dl_btn = page.locator("button:has-text('Download')").first
            dl_btn.wait_for(state="visible", timeout=85000)
            dl_btn.click()

        download = download_info.value
        download.save_as(str(dest_path))
        logger.info(f"تم تحميل الفيديو من Veo Lite: {dest_path}")

        return {
            "status": "ok",
            "path": str(dest_path),
            "filename": save_as,
            "engine": "flow_veo_lite",
        }

    except Exception as exc:
        logger.error(f"فشل توليد فيديو Veo Lite: {exc}")
        # لو فشل تحريك الفيديو، نعتمد على الصورة الثابتة كمشهد قابل للرندر في FFmpeg
        if source_path.exists():
            logger.info("الاعتماد على الصورة الثابتة كبديل للمشهد في المونتاج...")
            return {
                "status": "ok",
                "path": str(source_path),
                "filename": source_path.name,
                "engine": "fallback_static_image",
                "note": f"تم استخدام الصورة الثابتة بدلاً من الفيديو لسبب: {exc}",
            }
        return {"status": "error", "error": str(exc)}

    finally:
        if page:
            try:
                page.close()
            except Exception:
                pass


def _fallback_to_brain_image(prompt: str, dest_path: Path, reason: str) -> dict[str, Any]:
    """توليد الصورة عبر SeekAI المسجل في المرحلة الأولى."""
    try:
        import asyncio
        import concurrent.futures

        from brain.image_client import generate_image

        coro = generate_image(prompt=prompt, model="nano-banana")
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                res = executor.submit(asyncio.run, coro).result()
        else:
            res = asyncio.run(coro)
        if res.get("status") == "success" and res.get("image_url"):
            # تحميل رابط الصورة من SeekAI
            import urllib.request
            urllib.request.urlretrieve(res["image_url"], str(dest_path))
            return {
                "status": "ok",
                "path": str(dest_path),
                "engine": "seekai_nano_banana",
                "note": f"تم استخدام SeekAI كبديل بسبب: {reason}",
            }
    except Exception as exc:
        logger.error(f"فشل مولد الصور البديل أيضاً: {exc}")

    return {"status": "error", "error": f"فشل Flow ({reason}) وفشل البديل."}
