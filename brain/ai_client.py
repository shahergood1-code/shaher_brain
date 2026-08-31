"""
brain/ai_client.py
──────────────────
Fallback AI Chain لشاهر الثاني.

ترتيب المحاولة:
  1. Gemini Official API (google-generativeai) — المصدر الرسمي الموثوق
  2. SeekAI Aggregator (OpenAI-compatible) — fallback أول
  3. Duck.ai via duckduckgo-search — fallback تاني (مجاني، بدون key)

الفرق عن ChatGPT/Claude:
  شاهر بيبني System Prompt ديناميكي قبل كل رسالة —
  بيشوف مشاريعك النشطة + تفضيلاتك + قراراتك الأخيرة
  من Supabase ويحقنها كـ context. يعني مش بس محادثة —
  شاهر شايف "عالمك" كامل في كل رسالة.
"""

import os
import time
import asyncio
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


# ─── SeekAI Available Models ────────────────────────────────────────
# كل الموديلات دي بتشتغل بنفس SeekAI API key — مفتاح واحد، خيارات كتيرة
SEEKAI_MODELS: dict[str, str] = {
    # الموديل الافتراضي — بيتقرأه من .env
    "default":          os.getenv("SEEKAI_MODEL", "gemini-1.5-flash"),

    # ── أسماء مختصرة (shortcuts) ──
    "claude":           "claude-sonnet-5",
    "claude-opus":      "claude-opus-5",
    "claude-fable":     "claude-fable-5",
    "gpt":              "gpt-5.6-sol",
    "gemini":           "gemini-3-6-flash",
    "deepseek":         "deepseek-v4-pro",
    "grok":             "grok-4-6",
    "kimi":             "kimi-k3",
    "glm":              "glm-5-2",
    "mimo":             "mimo-v2.5",

    # ── أسماء كاملة (exact model names) ──
    "claude-sonnet-5":  "claude-sonnet-5",
    "claude-opus-5":    "claude-opus-5",
    "claude-fable-5":   "claude-fable-5",
    "gpt-5.6-sol":      "gpt-5.6-sol",
    "gemini-3-6-flash": "gemini-3-6-flash",
    "deepseek-v4-pro":  "deepseek-v4-pro",
    "grok-4-6":         "grok-4-6",
    "kimi-k3":          "kimi-k3",
    "glm-5-2":          "glm-5-2",
    "mimo-v2.5":        "mimo-v2.5",
}



# ─── بناء System Prompt ديناميكي ─────────────────────────

def _build_system_prompt(ctx: dict) -> str:
    """
    بيبني System Prompt مخصص من السياق الكامل.
    ctx: النتيجة من get_full_context() في memory/logger.py
    """
    prefs = ctx.get("preferences", {})
    projects = ctx.get("active_projects", [])
    decisions = ctx.get("recent_decisions", [])

    owner = prefs.get("owner_name", "شاهر")
    personality = prefs.get("ai_personality", "مساعد شخصي ذكي، مباشر")
    tz = prefs.get("timezone", "Africa/Cairo")

    # ── الشخصية الأساسية ──
    prompt = f"""أنت شاهر — المساعد الشخصي الذكي لـ {owner}.

طبيعتك:
- تتكلم في أي موضوع بحرية تامة: برمجة، قرارات، أسئلة، أفكار، أي حاجة — زي Claude أو ChatGPT بالظبط
- شخصيتك: {personality}
- بتتكلم بالعربي بشكل طبيعي (مصري أو فصيح حسب السياق)
- مش "بوت مهام" — أنت مساعد حقيقي يفهم السياق ويكمّل الأفكار
- مباشر وواضح: بتقول الحقيقة حتى لو مش اللي {owner} عايز يسمعه
- منطقة الوقت: {tz}

"""

    # ── المشاريع النشطة ──
    if projects:
        prompt += "## مشاريعك النشطة دلوقتي:\n"
        for p in projects:
            line = f"- **{p['name']}**"
            if p.get("description"):
                line += f": {p['description']}"
            if p.get("channel"):
                line += f" (قناة: {p['channel']})"
            if p.get("github_repo"):
                line += f" — GitHub: {p['github_repo']}"
            prompt += line + "\n"
        prompt += "\n"

    # ── القرارات الأخيرة ──
    if decisions:
        prompt += "## قرارات مهمة اتخذت مؤخرًا:\n"
        for d in decisions:
            prompt += f"- **{d['title']}**: {d['decision']}\n"
        prompt += "\n"

    # ── تعليمات التفاعل ──
    prompt += f"""## كيف تتفاعل:
- لو السؤال عام (علم، تكنولوجيا، رأي، أي حاجة): جاوب مباشرة بعمق واهتمام
- لو السؤال يتعلق بمشاريع أو شغل: استخدم المعلومات اللي عندك من السياق
- لو محتاج توضيح: اسأل سؤال واحد بس، مش عشرة
- متحولش كل رسالة لـ "مهمة" أو "خطة عمل" — الكلام الطبيعي مقبول ومطلوب
- لو {owner} بيفكر بصوت عالي، شاركه في التفكير مش بس اسجّل
"""

    return prompt


# ─── Static fallback (لو Supabase مش متاح) ──────────────

_STATIC_SYSTEM_PROMPT = """أنت شاهر — مساعد شخصي ذكي.
تتكلم في أي موضوع بحرية تامة زي Claude أو ChatGPT.
مباشر، واضح، بالعربي. مش بوت مهام — مساعد حقيقي."""


@dataclass
class AIResponse:
    content: str
    source: str        # 'gemini' | 'seekai' | 'duckai' | 'error'
    model: str
    response_time_ms: int
    tokens_used: Optional[int] = None
    error: Optional[str] = None


def _build_messages(user_message: str, history: list[dict], system: str) -> list[dict]:
    """بيبني قائمة رسائل للـ chat API مع history."""
    messages = [{"role": "system", "content": system}]
    for item in history[-8:]:
        if item.get("user_message"):
            messages.append({"role": "user", "content": item["user_message"]})
        if item.get("ai_response"):
            messages.append({"role": "assistant", "content": item["ai_response"]})
    messages.append({"role": "user", "content": user_message})
    return messages


# ─── Timeouts & Performance Settings ──────────────────────────────
GEMINI_TIMEOUT_SECONDS = float(os.getenv("GEMINI_TIMEOUT", "7.0"))
SEEKAI_TIMEOUT_SECONDS = float(os.getenv("SEEKAI_TIMEOUT", "8.0"))
DUCKAI_TIMEOUT_SECONDS = float(os.getenv("DUCKAI_TIMEOUT", "9.0"))


# ─── Source 1: Gemini Official ────────────────────────────

async def _try_gemini(
    user_message: str,
    history: list[dict],
    system_prompt: str,
    api_key: str,
) -> AIResponse:
    """Gemini Official API — المصدر الأساسي مع مهلة سريعة."""
    import google.generativeai as genai

    start = time.time()
    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    if "3.6" in model_name:
        model_name = "gemini-1.5-flash"
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_prompt,
    )

    chat_history = []
    for item in history[-8:]:
        if item.get("user_message"):
            chat_history.append({"role": "user", "parts": [item["user_message"]]})
        if item.get("ai_response"):
            chat_history.append({"role": "model", "parts": [item["ai_response"]]})

    chat = model.start_chat(history=chat_history)
    
    # حماية بـ timeout صريح لمنع التعليق
    response = await asyncio.wait_for(
        asyncio.to_thread(chat.send_message, user_message),
        timeout=GEMINI_TIMEOUT_SECONDS
    )

    elapsed = int((time.time() - start) * 1000)
    return AIResponse(
        content=response.text,
        source="gemini",
        model=model_name,
        response_time_ms=elapsed,
        tokens_used=(
            response.usage_metadata.total_token_count
            if hasattr(response, "usage_metadata") and response.usage_metadata
            else None
        ),
    )


# ─── Source 2: SeekAI ──────────────────────────────────────────────

async def _try_seekai(
    user_message: str,
    history: list[dict],
    system_prompt: str,
    api_key: str,
    model: str | None = None,
) -> AIResponse:
    """SeekAI Aggregator — fallback أول (OpenAI-compatible endpoint)."""
    from openai import AsyncOpenAI

    start = time.time()
    base_url = os.getenv("SEEKAI_BASE_URL", "https://api.seekai.tools/v1")
    # لو محددش موديل: بيختار من SEEKAI_MODELS، لو مش موجود يرجع للافتراضي
    model_name = SEEKAI_MODELS.get(model or "default", model or SEEKAI_MODELS["default"])

    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=SEEKAI_TIMEOUT_SECONDS)
    messages = _build_messages(user_message, history, system_prompt)

    response = await asyncio.wait_for(
        client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=2048,
        ),
        timeout=SEEKAI_TIMEOUT_SECONDS
    )

    elapsed = int((time.time() - start) * 1000)
    return AIResponse(
        content=response.choices[0].message.content or "",
        source="seekai",
        model=model_name,
        response_time_ms=elapsed,
        tokens_used=response.usage.total_tokens if response.usage else None,
    )


# ─── Source 3: Duck.ai ────────────────────────────────────

async def _try_duckai(
    user_message: str,
    history: list[dict],
    system_prompt: str,
) -> AIResponse:
    """Duck.ai — fallback تاني، مجاني بدون API key."""
    from duckduckgo_search import DDGS

    start = time.time()

    context_text = ""
    for item in history[-4:]:
        if item.get("user_message"):
            context_text += f"User: {item['user_message']}\n"
        if item.get("ai_response"):
            context_text += f"Assistant: {item['ai_response']}\n"

    full_prompt = f"{system_prompt}\n\n{context_text}User: {user_message}"

    response_text = await asyncio.wait_for(
        asyncio.to_thread(
            lambda: next(DDGS().chat(full_prompt, model="gpt-4o-mini"), "")
        ),
        timeout=DUCKAI_TIMEOUT_SECONDS
    )

    elapsed = int((time.time() - start) * 1000)
    return AIResponse(
        content=response_text,
        source="duckai",
        model="gpt-4o-mini (duck.ai)",
        response_time_ms=elapsed,
    )


# --- Main: Fallback Chain ---

async def get_ai_response(
    user_message: str,
    context: dict | None = None,
    component: str = "brain",
    seekai_model: str | None = None,
) -> AIResponse:
    """
    الدالة الرئيسية — بتجرب المصادر بالترتيب وتنتقل تلقائيًا وسريعاً عند التأخر أو الفشل.

    Args:
        user_message:  رسالة المستخدم
        context:       النتيجة من get_full_context()
        component:     اسم المكون (عشان API key منفصل لكل مكون)
        seekai_model:  موديل SeekAI محدد لو Gemini فشل
    """
    if context is None:
        context = {}

    system_prompt = _build_system_prompt(context) if context else _STATIC_SYSTEM_PROMPT
    history = context.get("recent_messages", [])
    errors = []

    # -- المصدر 1: Gemini Official (افتراضي دايمًا مع مهلة سريعة) --
    gemini_key = (
        os.getenv(f"GEMINI_API_KEY_{component.upper()}")
        or os.getenv("GEMINI_API_KEY_BRAIN")
    )
    if gemini_key:
        try:
            return await _try_gemini(user_message, history, system_prompt, gemini_key)
        except asyncio.TimeoutError:
            error_msg = f"Gemini: Timeout exceeded ({GEMINI_TIMEOUT_SECONDS}s)"
            errors.append(error_msg)
            label = seekai_model or "default"
            print(f"[WARN] {error_msg} -- Fast switching to SeekAI ({label})...")
        except Exception as e:
            error_msg = f"Gemini: {type(e).__name__}: {e}"
            errors.append(error_msg)
            label = seekai_model or "default"
            print(f"[WARN] {error_msg} -- trying SeekAI ({label})...")

    # -- المصدر 2: SeekAI (بالموديل المحدد أو الافتراضي) --
    seekai_key = os.getenv("SEEKAI_API_KEY")
    if seekai_key:
        try:
            return await _try_seekai(
                user_message, history, system_prompt,
                seekai_key, model=seekai_model,
            )
        except asyncio.TimeoutError:
            label = seekai_model or "default"
            error_msg = f"SeekAI ({label}): Timeout exceeded ({SEEKAI_TIMEOUT_SECONDS}s)"
            errors.append(error_msg)
            print(f"[WARN] {error_msg} -- Fast switching to Duck.ai...")
        except Exception as e:
            label = seekai_model or "default"
            error_msg = f"SeekAI ({label}): {type(e).__name__}: {e}"
            errors.append(error_msg)
            print(f"[WARN] {error_msg} -- trying Duck.ai...")

    # -- المصدر 3: Duck.ai --
    try:
        return await _try_duckai(user_message, history, system_prompt)
    except asyncio.TimeoutError:
        errors.append(f"Duck.ai: Timeout exceeded ({DUCKAI_TIMEOUT_SECONDS}s)")
    except Exception as e:
        errors.append(f"Duck.ai: {type(e).__name__}: {e}")

    # -- كل المصادر فشلت --
    return AIResponse(
        content="عذرًا، مفيش مصدر AI متاح دلوقتي. حاول تاني بعد شوية.",
        source="error",
        model="none",
        response_time_ms=0,
        error=" | ".join(errors),
    )


# --- Standalone: SeekAI Direct (لمهام محددة) ---

async def get_seekai_response(
    user_message: str,
    model: str,
    context: dict | None = None,
) -> AIResponse:
    """
    استدعاء SeekAI بموديل محدد مباشرة — بدون تجربة Gemini أولًا.

    استخدمها لما Shaher Brain يريد رد من Claude أو GPT تحديدًا
    لمهمة معينة (مراجعة كود، رأي ثاني، مقارنة).

    الموديلات المتاحة (SEEKAI_MODELS):
        'gpt'             -> gpt-5.6-sol
        'claude'          -> claude-sonnet-5
        'gpt-5.6-sol'     -> gpt-5.6-sol
        'claude-sonnet-5' -> claude-sonnet-5
        'default'         -> الافتراضي من .env

    مثال:
        result = await get_seekai_response(
            "راجع الكود ده وقترحلي تحسينات",
            model="claude",
            context=ctx,
        )
    """
    if context is None:
        context = {}

    api_key = os.getenv("SEEKAI_API_KEY")
    if not api_key:
        return AIResponse(
            content="SEEKAI_API_KEY غير موجود في .env",
            source="error",
            model=model,
            response_time_ms=0,
            error="missing SEEKAI_API_KEY",
        )

    system_prompt = _build_system_prompt(context) if context else _STATIC_SYSTEM_PROMPT
    history = context.get("recent_messages", [])

    try:
        return await _try_seekai(
            user_message, history, system_prompt,
            api_key, model=model,
        )
    except Exception as e:
        resolved = SEEKAI_MODELS.get(model, model)
        return AIResponse(
            content=f"فشل SeekAI ({resolved}): {e}",
            source="error",
            model=resolved,
            response_time_ms=0,
            error=str(e),
        )
