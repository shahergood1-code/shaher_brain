"""
brain/image_client.py
──────────────────────
توليد الصور عبر SeekAI Image API (OpenAI-compatible).

الموديلات المدعومة عبر SeekAI:
  - nano-banana    ← سريع، مناسب للتجربة
  - flux           ← جودة عالية، مناسب للمحتوى
  - seedream       ← إبداعي، مناسب للبوستات

الاستخدام:
  result = await generate_image("غلاف يوتيوب عن البرمجة بأسلوب حديث")
  print(result.image_url)

كل صورة تُولّد تُسجّل تلقائيًا في Supabase (جدول generated_images).
"""

import os
import time
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# الموديل الافتراضي — غيّره لو SeekAI حدّث أسماء الموديلات
DEFAULT_IMAGE_MODEL = os.getenv("SEEKAI_IMAGE_MODEL", "flux")

# أبعاد الصور الشائعة لمحتوى شاهر
IMAGE_SIZES = {
    "youtube":    "1280x720",   # غلاف يوتيوب
    "instagram":  "1080x1080",  # بوست انستجرام مربع
    "story":      "1080x1920",  # ستوري
    "post":       "1200x628",   # بوست فيسبوك/لينكدإن
    "default":    "1024x1024",
}


@dataclass
class ImageResult:
    image_url: str
    model_used: str
    prompt: str
    size: str
    response_time_ms: int
    revised_prompt: Optional[str] = None   # لو SeekAI عدّل البرومبت
    error: Optional[str] = None


async def generate_image(
    prompt: str,
    model: Optional[str] = None,
    format_type: str = "default",   # 'youtube' | 'instagram' | 'story' | 'post' | 'default'
    n: int = 1,
) -> ImageResult:
    """
    يولّد صورة عبر SeekAI ويرجع ImageResult.

    Args:
        prompt:      وصف الصورة المطلوبة (عربي أو إنجليزي)
        model:       الموديل المطلوب (None = الافتراضي)
        format_type: نوع الاستخدام المحدد أبعاد الصورة تلقائيًا
        n:           عدد الصور (1 في المرحلة الأولى)
    """
    from openai import AsyncOpenAI

    api_key = os.getenv("SEEKAI_API_KEY")
    if not api_key:
        return ImageResult(
            image_url="",
            model_used="none",
            prompt=prompt,
            size="none",
            response_time_ms=0,
            error="SEEKAI_API_KEY غير موجود في .env",
        )

    base_url = os.getenv("SEEKAI_BASE_URL", "https://api.seekai.tools/v1")
    model_name = model or DEFAULT_IMAGE_MODEL
    size = IMAGE_SIZES.get(format_type, IMAGE_SIZES["default"])

    start = time.time()

    try:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        response = await client.images.generate(
            model=model_name,
            prompt=prompt,
            n=n,
            size=size,
            response_format="url",
        )

        elapsed = int((time.time() - start) * 1000)
        image_data = response.data[0]

        result = ImageResult(
            image_url=image_data.url or "",
            model_used=model_name,
            prompt=prompt,
            size=size,
            response_time_ms=elapsed,
            revised_prompt=getattr(image_data, "revised_prompt", None),
        )

        # تسجيل الصورة في Supabase تلقائيًا
        await _log_generated_image(result)

        return result

    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        error_msg = f"{type(e).__name__}: {e}"
        print(f"❌ فشل توليد الصورة بـ SeekAI: {error_msg}")

        return ImageResult(
            image_url="",
            model_used=model_name,
            prompt=prompt,
            size=size,
            response_time_ms=elapsed,
            error=error_msg,
        )


async def _log_generated_image(result: ImageResult) -> None:
    """يسجل الصورة المولّدة في Supabase."""
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
