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
    revised_prompt: str | None = None
    error: str | None = None


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
    model: str | None = None,
    format_type: str | None = None,
    aspect_ratio: str | None = None,
    n: int = 1,
) -> ImageResult:
    """
    يولّد صورة عالية الجودة مع fallback ذكي وتحسين دقيق للبرومبت.
    """
    start = time.time()
    
    # تحديد المقاس
    if aspect_ratio:
        ar = aspect_ratio.strip().lower()
        if ar in ["16:9", "16/9"]:
            fmt = "youtube"
        elif ar in ["9:16", "9/16"]:
            fmt = "story"
        elif ar in ["1:1"]:
            fmt = "instagram"
        else:
            fmt = format_type or detect_format(prompt)
    else:
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
    يدعم النماذج الواقعية والإضاءة السينمائية والتفاصيل الدقيقة بدقة 8k.
    """
    format_hints = {
        "youtube": "High CTR YouTube thumbnail style, vibrant contrasting colors, dramatic lighting, sharp focus on subject, clean background with depth of field, 16:9 aspect ratio",
        "story": "Vertical 9:16 portrait composition, immersive mobile photography, moody dramatic lighting, ultra-high resolution",
        "post": "Crisp social media banner, professional composition, balanced lighting, striking visual appeal",
        "instagram": "Square 1:1 format, studio quality portrait or scene, symmetrical aesthetics, masterful color grading",
        "ad": "Ultra-clean modern commercial advertisement banner, luxury product podium mockup, sleek aesthetic, cinematic softbox studio lighting, 8k render",
        "default": "Photorealistic masterpiece, cinematic lighting, 8k resolution, intricate textures, ray tracing, sharp details",
    }
    
    # كشف نوع الإعلان أو التصميم
    lower_prompt = prompt_text.lower()
    if any(w in lower_prompt for w in ["اعلان", "إعلان", "منتج", "بوستر", "commercial", "ad", "poster"]):
        hint = format_hints["ad"]
    else:
        hint = format_hints.get(format_type, format_hints["default"])

    try:
        gemini_key = os.getenv("GEMINI_API_KEY_BRAIN")
        if gemini_key:
            import asyncio

            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
            m = genai.GenerativeModel(model_name)
            
            prompt_instruction = (
                "You are an elite AI Art Director specializing in Flux-Dev and Midjourney prompt engineering. "
                "Your task: Convert the user's description (which may be in Arabic or English) into an extraordinary, "
                "ultra-detailed English visual prompt.\n\n"
                "Rules:\n"
                "1. Output ONLY the refined English prompt text. No quotes, no markdown labels, no intro/outro.\n"
                "2. Include specific artistic style, lighting (e.g. volumetric lighting, golden hour, neon rim lights), "
                "camera details (e.g. 35mm lens, f/1.8, bokeh, hyper-detailed, photorealistic, 8k resolution, Unreal Engine 5 render).\n"
                f"3. Incorporate these composition guidelines: {hint}\n"
                "4. Keep it focused, evocative, and visually breathtaking."
            )
            
            resp = await asyncio.wait_for(
                asyncio.to_thread(
                    m.generate_content,
                    f"{prompt_instruction}\n\nUser Concept: {prompt_text}"
                ),
                timeout=12.0
            )
            if resp and resp.text:
                cleaned = resp.text.strip().replace('"', '').replace('`', '').replace('\n', ' ')
                if len(cleaned) > 10:
                    return cleaned
    except Exception as e:
        print(f"[WARN] Gemini prompt enhancement failed or timed out: {e} -- trying NVIDIA NIM...")

    # ── Fallback via NVIDIA NIM ──
    try:
        nvidia_key = os.getenv("NVIDIA_API_KEY")
        if nvidia_key:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=nvidia_key, base_url="https://integrate.api.nvidia.com/v1", timeout=10.0)
            prompt_instruction = (
                "You are an elite AI Art Director specializing in Flux-Dev and Midjourney prompt engineering. "
                "Transform the following user concept into an extraordinary, ultra-detailed English prompt. "
                f"Incorporate style: {hint}, 8k resolution, cinematic lighting, photorealistic. "
                "Output ONLY the prompt text without any intro or markdown."
            )
            r = await client.chat.completions.create(
                model=os.getenv("NVIDIA_MODEL", "meta/llama-3.2-11b-vision-instruct"),
                messages=[{"role": "system", "content": prompt_instruction}, {"role": "user", "content": prompt_text}],
                max_tokens=200
            )
            if r.choices and r.choices[0].message.content:
                cleaned = r.choices[0].message.content.strip().replace('"', '').replace('`', '').replace('\n', ' ')
                if len(cleaned) > 10:
                    return cleaned
    except Exception as e:
        print(f"[WARN] NVIDIA prompt enhancement failed: {e}")

    # Fallback keyword enrichment
    return f"{prompt_text}, {hint}, photorealistic, ultra-detailed, 8k resolution, cinematic lighting"


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
