"""
brain/image_client.py
──────────────────────
توليد الصور لشاهر الثاني.

الاستراتيجية:
  1. تحسين وترجمة البرومبت للإنجليزية تلقائياً للحصول على أعلى جودة.
  2. تجربة SeekAI Image API أولاً (لو الموديل متاح في الحساب).
  3. Fallback تلقائي لموديل Flux عالي الجودة (سريع ومجاني بدون أخطاء).
  4. تسجيل كل صورة في جدول generated_images في Supabase.
"""

import os
import time
import urllib.parse
from dataclasses import dataclass
from typing import Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_IMAGE_MODEL = os.getenv("SEEKAI_IMAGE_MODEL", "flux")

# أبعاد الصور
IMAGE_DIMENSIONS = {
    "youtube":    (1280, 720),
    "instagram":  (1080, 1080),
    "story":      (1080, 1920),
    "post":       (1200, 628),
    "default":    (1024, 1024),
}


@dataclass
class ImageResult:
    image_url: str
    model_used: str
    prompt: str
    size: str
    response_time_ms: int
    revised_prompt: Optional[str] = None
    error: Optional[str] = None


async def generate_image(
    prompt: str,
    model: Optional[str] = None,
    format_type: str = "default",
    n: int = 1,
) -> ImageResult:
    """
    يولّد صورة عالية الجودة مع Fallback ذكي.
    """
    start = time.time()
    width, height = IMAGE_DIMENSIONS.get(format_type, IMAGE_DIMENSIONS["default"])
    size_str = f"{width}x{height}"
    model_name = model or DEFAULT_IMAGE_MODEL

    # ── 1. محاولة SeekAI Image API ──
    seekai_key = os.getenv("SEEKAI_API_KEY")
    seekai_base = os.getenv("SEEKAI_BASE_URL", "https://seekai.cc/v1")

    if seekai_key:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=seekai_key, base_url=seekai_base)
            response = await client.images.generate(
                model=model_name,
                prompt=prompt,
                n=1,
                size=size_str if size_str in ["1024x1024", "512x512", "256x256"] else "1024x1024",
                response_format="url",
            )
            elapsed = int((time.time() - start) * 1000)
            img_data = response.data[0]
            result = ImageResult(
                image_url=img_data.url or "",
                model_used=f"seekai-{model_name}",
                prompt=prompt,
                size=size_str,
                response_time_ms=elapsed,
                revised_prompt=getattr(img_data, "revised_prompt", None),
            )
            await _log_generated_image(result)
            return result
        except Exception as e:
            print(f"[WARN] SeekAI image gen failed: {e} -- switching to Flux Engine...")

    # ── 2. Fallback: Flux High Quality Engine ──
    try:
        # ترجمة/تحسين البرومبت للإنجليزية إذا كان عربي
        enhanced_prompt = await _enhance_prompt(prompt)
        encoded_prompt = urllib.parse.quote(enhanced_prompt)
        image_url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?width={width}&height={height}&model=flux&nologo=true&seed={int(time.time())}"
        )

        # التأكد من صحة الرابط وسرعة الاستجابة
        async with httpx.AsyncClient() as http_client:
            res = await http_client.get(image_url, timeout=35.0)
            if res.status_code == 200:
                elapsed = int((time.time() - start) * 1000)
                result = ImageResult(
                    image_url=image_url,
                    model_used="flux-engine",
                    prompt=prompt,
                    size=size_str,
                    response_time_ms=elapsed,
                    revised_prompt=enhanced_prompt,
                )
                await _log_generated_image(result)
                return result

    except Exception as e:
        print(f"[ERROR] Flux engine failed: {e}")

    elapsed = int((time.time() - start) * 1000)
    return ImageResult(
        image_url="",
        model_used="none",
        prompt=prompt,
        size=size_str,
        response_time_ms=elapsed,
        error="تعذر توليد الصورة حالياً، يرجى المحاولة بعد قليل.",
    )


async def _enhance_prompt(arabic_prompt: str) -> str:
    """
    يحوّل ويحسّن البرومبت العربي إلى برومبت دقيق بالإنجليزية لموديل Flux.
    """
    try:
        gemini_key = os.getenv("GEMINI_API_KEY_BRAIN")
        if gemini_key:
            import google.generativeai as genai
            import asyncio
            genai.configure(api_key=gemini_key)
            m = genai.GenerativeModel("gemini-3.6-flash")
            resp = await asyncio.to_thread(
                m.generate_content,
                f"Translate and enhance this image description into a high-quality, detailed English prompt for Flux AI image generator (output only the prompt, no explanation): {arabic_prompt}"
            )
            if resp and resp.text:
                return resp.text.strip()
    except Exception:
        pass
    return arabic_prompt


async def _log_generated_image(result: ImageResult) -> None:
    """يسجل الصورة في Supabase."""
    try:
        from memory.supabase_client import get_supabase
        db = get_supabase()
        db.table("generated_images").insert({
            "prompt": result.prompt,
            "model_used": result.model_used,
            "image_url": result.image_url,
            "size": result.size,
            "response_time_ms": result.response_time_ms,
            "revised_prompt": result.revised_prompt,
            "error_details": result.error,
        }).execute()
    except Exception as e:
        print(f"⚠️ فشل تسجيل الصورة في Supabase: {e}")
