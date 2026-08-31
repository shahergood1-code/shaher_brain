"""
brain/image_client.py
──────────────────────
توليد الصور لشاهر الثاني.

الاستراتيجية:
  1. كشف الأبعاد المطلوبة تلقائياً (غلاف يوتيوب، ستوري، بوست، إنستجرام...).
  2. تنظيف البرومبت وترجمته وتحسينه للإنجليزية عبر Gemini لإنتاج جودة سينمائية فائقة لموديل Flux.
  3. محاولة SeekAI Image API إذا تم تحديد موديل مدعوم (مثل dall-e-3).
  4. Fallback تلقائي ومباشر لمحرك Flux Engine فائق الجودة والسرعة (Pollinations AI).
  5. تسجيل كل صورة في جدول generated_images في Supabase.
"""

import os
import re
import time
import urllib.parse
from dataclasses import dataclass
from typing import Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_IMAGE_MODEL = os.getenv("SEEKAI_IMAGE_MODEL", "flux")

# أبعاد الصور المدعومة
IMAGE_DIMENSIONS = {
    "youtube":    (1280, 720),   # 16:9 غلاف يوتيوب / ثمبنايل
    "post":       (1200, 630),   # 1.91:1 بوست أفقي للسوشيال ميديا
    "story":      (720, 1280),   # 9:16 ستوري / ريلز / تيك توك / شورتس
    "instagram":  (1024, 1024),  # 1:1 إنستجرام مربع
    "default":    (1024, 1024),  # 1:1 افتراضي
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


def detect_format(text: str) -> str:
    """
    يكتشف نوع الحجم المطلوب من نص المستخدم تلقائياً.
    """
    t = text.lower()
    
    # YouTube / 16:9 / غلاف / ثمبنايل
    if any(k in t for k in ["youtube", "يوتيوب", "غلاف", "ثمبنايل", "thumbnail", "ثيمب", "بانر", "بنر", "16:9", "16/9", "أفقي", "افقي", "عرضي"]):
        return "youtube"
    
    # Story / Reels / Shorts / TikTok / 9:16
    if any(k in t for k in ["story", "ستوري", "ريلز", "reels", "shorts", "شورتس", "tiktok", "تيك توك", "9:16", "9/16", "طولي", "رأسي", "راسي"]):
        return "story"
    
    # Social Media Post (Facebook, Twitter/X)
    if any(k in t for k in ["بوست", "post", "فيسبوك", "facebook", "تويتر", "twitter"]):
        return "post"
        
    # Instagram / Square
    if any(k in t for k in ["انستقرام", "انستجرام", "instagram", "مربع", "square", "1:1"]):
        return "instagram"

    return "default"


def clean_prompt(raw_prompt: str) -> str:
    """
    ينظف نص الرسالة من عبارات الأمر (مثل: ولد لي صورة، ارسم لي...) لاستخراج الوصف البصري النقي.
    """
    cleaned = raw_prompt.strip()
    patterns = [
        r"^(?:ولد(?:لي| لي|لي |ي)?|ولّد(?:لي| لي|لي |ي)?|اعمل(?:لي| لي)?|ارسم(?:لي| لي)?|صمم(?:لي| لي)?|انشئ(?:لي| لي)?|توليد|إنشاء|تصميم|هاتلي|هات لي)\s+(?:صورة|صوره|تصميم|غلاف|ثمبنايل|بوست|خلفية)?\s*(?:يوتيوب|انستقرام|انستجرام|ستوري|ريلز|فيسبوك|تويتر)?\s*(?:لـ|عن|بخصوص|حول|ل)?\s*",
        r"^(?:generate|create|draw|make|design)\s+(?:an?\s+)?(?:image|picture|photo|thumbnail|cover|art|wallpaper)?\s*(?:of|about|for)?\s*",
    ]
    for p in patterns:
        cleaned = re.sub(p, "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned if len(cleaned) > 2 else raw_prompt.strip()


async def generate_image(
    prompt: str,
    model: Optional[str] = None,
    format_type: Optional[str] = None,
    n: int = 1,
) -> ImageResult:
    """
    يولّد صورة عالية الجودة مع fallback ذكي وتحسين دقيق للبرومبت.
    """
    start = time.time()
    
    # تحديد المقاس
    fmt = format_type or detect_format(prompt)
    width, height = IMAGE_DIMENSIONS.get(fmt, IMAGE_DIMENSIONS["default"])
    size_str = f"{width}x{height}"
    model_name = model or DEFAULT_IMAGE_MODEL
    
    cleaned_desc = clean_prompt(prompt)

    # ── 1. تحسين وترجمة البرومبت عبر Gemini ──
    enhanced_prompt = await _enhance_prompt(cleaned_desc, format_type=fmt)

    # ── 2. محاولة SeekAI Image API (لو الموديل دالي أو SeekAI مفعل) ──
    seekai_key = os.getenv("SEEKAI_API_KEY")
    seekai_base = os.getenv("SEEKAI_BASE_URL", "https://seekai.cc/v1")

    # نتخطى SeekAI إذا كان الموديل المطلوب flux ومفيش channel ليه في SeekAI
    if seekai_key and model_name not in ["flux", "default"]:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=seekai_key, base_url=seekai_base)
            response = await client.images.generate(
                model=model_name,
                prompt=enhanced_prompt,
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
                revised_prompt=getattr(img_data, "revised_prompt", enhanced_prompt),
            )
            await _log_generated_image(result)
            return result
        except Exception as e:
            print(f"[WARN] SeekAI image gen failed: {e} -- switching to Flux Engine...")

    # ── 3. Fallback: Flux High Quality Engine (Pollinations AI) ──
    try:
        encoded_prompt = urllib.parse.quote(enhanced_prompt)
        seed = int(time.time())
        image_url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?width={width}&height={height}&model=flux&nologo=true&seed={seed}"
        )

        # التأكد من صحة الرابط وسرعة الاستجابة
        async with httpx.AsyncClient(follow_redirects=True) as http_client:
            res = await http_client.get(image_url, timeout=40.0)
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


async def _enhance_prompt(prompt_text: str, format_type: str = "default") -> str:
    """
    يحوّل ويحسّن البرومبت إلى وصف فوتوغرافي/فني إنجليزي فائق الدقة لموديل Flux.
    """
    try:
        gemini_key = os.getenv("GEMINI_API_KEY_BRAIN")
        if gemini_key:
            import google.generativeai as genai
            import asyncio
            genai.configure(api_key=gemini_key)
            model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
            m = genai.GenerativeModel(model_name)
            
            prompt_instruction = (
                "You are a world-class AI art director and prompt engineer for Flux AI image generation. "
                "Transform the following user request into a highly detailed, breathtaking English prompt. "
                "Specify vivid lighting, artistic style, texture, depth of field, dramatic composition, and ultra-high fidelity (8k resolution, photorealistic or masterpiece digital art). "
                "Do NOT write any introduction or explanation. Output ONLY the raw English prompt."
            )
            
            resp = await asyncio.to_thread(
                m.generate_content,
                f"{prompt_instruction}\n\nSubject: {prompt_text}\nContext/Format: {format_type}"
            )
            if resp and resp.text:
                cleaned = resp.text.strip().replace('"', '').replace('`', '')
                if cleaned:
                    return cleaned
    except Exception as e:
        print(f"[WARN] Prompt enhancement failed: {e}")
    return prompt_text


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
