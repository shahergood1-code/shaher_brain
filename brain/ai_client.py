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


# ─── NVIDIA NIM Available Models ────────────────────────────────────
NVIDIA_MODELS: dict[str, str] = {
    "default":          os.getenv("NVIDIA_MODEL", "meta/llama-3.2-11b-vision-instruct"),
    "llama":            "meta/llama-3.2-11b-vision-instruct",
    "nemotron":         "nvidia/nemotron-3.5-lightning-30b-a3b",
    "llama-3.2-11b":    "meta/llama-3.2-11b-vision-instruct",
    "nemotron-3.5":     "nvidia/nemotron-3.5-lightning-30b-a3b",
}


# ─── SeekAI Available Models ────────────────────────────────────────
# كل الموديلات دي بتشتغل بنفس SeekAI API key — مفتاح واحد، خيارات كتيرة
SEEKAI_MODELS: dict[str, str] = {
    # الموديل الافتراضي — بيتقرأه من .env
    "default":          os.getenv("SEEKAI_MODEL", "glm-5.3-flash"),

    # ── أسماء مختصرة (shortcuts) ──
    "glm":              "glm-5.3-flash",
    "deepseek":         "deepseek-v4-flash",
    "kimi":             "kimi-k3",
    "mimo":             "mimo-v2.5",
    "gemini":           "gemini-3-6-flash",
    "gpt":              "gpt-5.6-sol",
    "claude":           "claude-sonnet-5",

    # ── أسماء كاملة (exact model names) ──
    "glm-5.3-flash":    "glm-5.3-flash",
    "deepseek-v4-flash":"deepseek-v4-flash",
    "kimi-k3":          "kimi-k3",
    "mimo-v2.5":        "mimo-v2.5",
    "gemini-3-6-flash": "gemini-3-6-flash",
    "gpt-5.6-sol":      "gpt-5.6-sol",
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

أسلوبك وطبيعتك:
- تتكلم بلهجة مصرية ذكية وطبيعية ولطيفة جداً، زي أي صديق مصري ذكي ومحترف.
- تتكلم في أي موضوع بحرية وعمق: برمجة، شغل، نصائح، تصاميم، أفكار، أو دردشة عادية.
- مباشر وسريع: إجاباتك واضحة ومركزة بدون لف ودوران ولا تكرار جمل سخيفة.
- لو المستخدم طلب صورة: افهم منه الفكرة أو ولّدهاله باحترافية.
- مش روبوت تقليدي — أنت مساعد ذكي بيفهم المعنى الحقيقي وراء الكلام.
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

    # ── ما تم تعلمه ذاتياً عن شاهر وتفضيلاته وتوجيهاته ──
    learned_items = [v for k, v in prefs.items() if k.startswith("learned_") and v]
    if learned_items:
        prompt += "## دروس ومعارف تعلمتها عن شاهر وتفضيلاته السابقة (تطبيق إلزامي دائم):\n"
        for item in learned_items:
            prompt += f"- {item}\n"
        prompt += "\n"

    # ── قدراتك الشاملة في كل المجالات (Omni-Domain Polymath & Strategic Partner) ──
    prompt += """## قدراتك الشاملة في كل مجالات العمل والحياة:
1. **البيزنس، التجارة، والتسويق (Business & Growth Strategy):**
   - تفهم بعمق في ريادة الأعمال، التجارة الإلكترونية، دراسات الجدوى، استراتيجيات التسعير، وإدارة الحملات الإعلانية (Facebook, Google, TikTok Ads).
   - كتابة نصوص إعلانية مبهرة (High-Converting Copywriting)، وسكربتات قوية لفيديوهات اليوتيوب والريلز، وخطط تسويقية مبنية على الأرقام.

2. **البرمجة وهندسة البرمجيات (Senior Full-Stack Architect):**
   - كتابة أكواد مواقع كاملة (HTML/CSS/JS/React)، وتطبيقات، وسكريبتات بايثون، وAPIs، وقواعد بيانات بأعلى جودة وجاهزة للتشغيل 100% بدون أي نواقص أو تعليقات فارغة.

3. **التحليل المنطقي واتخاذ القرارات (Strategic Decision Making):**
   - تفكير عميق وتحليلي مبني على المبادئ الأولى (First Principles Thinking).
   - مساعدة {owner} في حل المشاكل المعقدة، مقارنة الخيارات، وحساب المخاطر والفرص بموضوعية وحكمة.

4. **الكتابة، المحتوى، والتواصل الإبداعي:**
   - صياغة إيميلات احترافية، عقود عمل، مقالات متخصصة، وتقارير شاملة ومقنعة.

5. **الأسلوب وطريقة التعامل:**
   - لهجتك مصرية ذكية وطبيعية جداً، لبقة، محترمة، وواضحة بدون أي عبارات روبوتية أو مصطنعة.
   - لا تتصرف كـ "بوت مهام صامت"، بل كـ **شريك فكري استراتيجي (Strategic Co-Pilot)** يفهم ما وراء الكلمات ويفكر معك ويقترح الأفضل دائماً.
"""

    # ── تعليمات التفاعل ──
    prompt += f"""## كيف تتفاعل:
- في أي موضوع (بيزنس، برمجة، قرارات، نصائح، تصاميم، أفكار، محادثة عامة): جاوب بأعلى درجات العمق والذكاء والوضوح.
- لو السؤال برمجي: اشرح باختصار ثم اكتب الكود الكامل المنظم الجاهز فوراً.
- لو السؤال بيزنس أو تسويق: قدّم أفكاراً عملية قابلة للتطبيق مباشرة وليست مجرد نظريات.
- لو {owner} بيفكر بصوت عالي أو محتار في قرار: شاركه التفكير وحلل معه الإيجابيات والسلبيات واقترح الخيار الأفضل.
- استخدم كل ما تعلمته عن {owner} وماريعه وتفضيلاته المخزنة في الذاكرة لتخصيص كل إجابة.
"""

    return prompt


# ─── Static fallback (لو Supabase مش متاح) ──────────────

_STATIC_SYSTEM_PROMPT = """أنت شاهر — المساعد الشخصي والشريك الذكي الشامل (Omni-Domain Strategic Partner).
تتحدث بلهجة مصرية طبيعية، ذكية، ولبقة.
خبير في كافة المجالات: البيزنس والتسويق، البرمجة وهندسة البرمجيات، التحليل الاستراتيجي واتخاذ القرارات، وصناعة المحتوى الإبداعي.
تكتب إجابات كاملة وعميقة ومبهرة بدون نواقص، وتفكر مع المستخدم كأفضل مستشار وصديق ذكي."""


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
SEEKAI_TIMEOUT_SECONDS = float(os.getenv("SEEKAI_TIMEOUT", "30.0"))
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
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
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


# ─── Source 2: NVIDIA NIM (فائق السرعة والاستقرار) ──────────────────────────

async def _try_nvidia(
    user_message: str,
    history: list[dict],
    system_prompt: str,
    api_key: str,
    model: str | None = None,
) -> AIResponse:
    """NVIDIA NIM — مصدر فائق السرعة والاستقرار عبر نماذج Llama الحديثة."""
    from openai import AsyncOpenAI

    start = time.time()
    base_url = "https://integrate.api.nvidia.com/v1"
    model_name = NVIDIA_MODELS.get(model or "default", model or NVIDIA_MODELS["default"])

    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=12.0)
    messages = _build_messages(user_message, history, system_prompt)

    response = await asyncio.wait_for(
        client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=2048,
        ),
        timeout=12.0
    )

    elapsed = int((time.time() - start) * 1000)
    return AIResponse(
        content=response.choices[0].message.content or "",
        source="nvidia_nim",
        model=model_name,
        response_time_ms=elapsed,
        tokens_used=response.usage.total_tokens if response.usage else None,
    )


# ─── Source 2: SeekAI (المحرك الأساسي للذكاء العربي الفصيح) ────────────

async def _try_seekai(
    user_message: str,
    history: list[dict],
    system_prompt: str,
    api_key: str,
    model: str | None = None,
) -> AIResponse:
    """SeekAI — المحرك الأساسي الذكي للمحادثات بطلاقة عربية عالية وجودة Claude/ChatGPT."""
    from openai import AsyncOpenAI

    start = time.time()
    base_url = os.getenv("SEEKAI_BASE_URL", "https://seekai.cc/v1")
    
    # قائمة الموديلات المتاحة والمضمونة في SeekAI بالترتيب
    candidate_models = ["glm-5.3-flash", "kimi-k3", "deepseek-v4-flash"]
    if model:
        requested = SEEKAI_MODELS.get(model, model)
        if requested not in candidate_models:
            candidate_models.insert(0, requested)

    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=SEEKAI_TIMEOUT_SECONDS)
    messages = _build_messages(user_message, history, system_prompt)

    last_err = None
    for model_name in candidate_models:
        try:
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
        except Exception as e:
            last_err = e
            print(f"[WARN] SeekAI candidate {model_name} failed: {e} -- trying next...")

    raise last_err or Exception("All SeekAI models failed")


# ─── Source 3: Duck.ai (Fallback إضافي مجاني) ───────────────────────────

async def _try_duckai(
    user_message: str,
    history: list[dict],
    system_prompt: str,
) -> AIResponse:
    """Duck.ai — fallback إضافي، مجاني بدون API key."""
    from duckduckgo_search import DDGS

    start = time.time()

    context_text = ""
    for item in history[-4:]:
        if item.get("user_message"):
            context_text += f"User: {item['user_message']}\n"
        if item.get("ai_response"):
            context_text += f"Assistant: {item['ai_response']}\n"

    full_prompt = f"{system_prompt}\n\n{context_text}User: {user_message}"

    def _sync_chat():
        try:
            return next(DDGS().chat(full_prompt, model="gpt-4o-mini"), "")
        except Exception:
            return ""

    response_text = await asyncio.wait_for(
        asyncio.to_thread(_sync_chat),
        timeout=DUCKAI_TIMEOUT_SECONDS
    )

    if not response_text:
        raise Exception("Duck.ai returned empty response")

    elapsed = int((time.time() - start) * 1000)
    return AIResponse(
        content=response_text,
        source="duckai",
        model="gpt-4o-mini (duck.ai)",
        response_time_ms=elapsed,
    )


# ─── Smart Adaptive AI Router (Health & Latency Ranker) ────────────

class SmartAIRouter:
    """
    نظام ذكي لتقييم جودة وسرعة وصحة المزودين ديناميكياً:
    - يفضل النماذج القوية في اللغة العربية (SeekAI GLM/Kimi & Gemini)
    - يضع المزود الذي يواجه 429 أو خطأ في فترة Cooldown
    - يحدّث متوسط السرعة بعد كل استجابة ناجحة
    """
    def __init__(self):
        self.stats = {
            "seekai":  {"avg_latency": 1200, "fails": 0, "cooldown_until": 0, "tier": 1},
            "gemini":  {"avg_latency": 1500, "fails": 0, "cooldown_until": 0, "tier": 1},
            "duckai":  {"avg_latency": 4000, "fails": 0, "cooldown_until": 0, "tier": 2},
        }

    def record_success(self, provider: str, latency_ms: int):
        if provider in self.stats:
            p = self.stats[provider]
            p["avg_latency"] = int(p["avg_latency"] * 0.6 + latency_ms * 0.4)
            p["fails"] = 0
            p["cooldown_until"] = 0

    def record_failure(self, provider: str, is_rate_limit: bool = False):
        if provider in self.stats:
            p = self.stats[provider]
            p["fails"] += 1
            cooldown_secs = 60 if is_rate_limit else 25
            p["cooldown_until"] = time.time() + cooldown_secs

    def get_optimal_order(self, available_providers: list[str]) -> list[str]:
        now = time.time()
        scored = []
        for prov in available_providers:
            info = self.stats.get(prov, {"avg_latency": 5000, "cooldown_until": 0, "tier": 3})
            in_cooldown = now < info["cooldown_until"]
            score = info["avg_latency"] + (100000 if in_cooldown else 0)
            scored.append((prov, score))
        scored.sort(key=lambda x: x[1])
        return [x[0] for x in scored]


# كائن الراوتر العام
router = SmartAIRouter()


# --- Main: Fallback Chain (Dynamic Smart Router) ---

async def get_ai_response(
    user_message: str,
    context: dict | None = None,
    component: str = "brain",
    seekai_model: str | None = None,
) -> AIResponse:
    """
    الدالة الرئيسية — تختار ديناميكياً أسرع وأفضل مزود في الوقت الفعلي:
      - تفحص المزودين المتاحين (SeekAI و Gemini)
      - ترتبهم حسب الجودة والسرعة
      - تنفذ وتحدث الإحصائيات فوراً
    """
    if context is None:
        context = {}

    system_prompt = _build_system_prompt(context) if context else _STATIC_SYSTEM_PROMPT
    history = context.get("recent_messages", [])
    errors = []

    # 1. تحديد المزودين المهيئين بـ API Keys
    configured = []
    seekai_key = os.getenv("SEEKAI_API_KEY")
    if seekai_key:
        configured.append("seekai")

    gemini_key = (
        os.getenv(f"GEMINI_API_KEY_{component.upper()}")
        or os.getenv("GEMINI_API_KEY_BRAIN")
    )
    if gemini_key:
        configured.append("gemini")

    # Duck.ai متاح دائماً كـ Fallback
    configured.append("duckai")

    # 2. الحصول على الترتيب الأمثل
    optimal_order = router.get_optimal_order(configured)

    # 3. التجربة حسب الترتيب
    for provider in optimal_order:
        if provider == "seekai" and seekai_key:
            try:
                res = await _try_seekai(
                    user_message, history, system_prompt,
                    seekai_key, model=seekai_model,
                )
                router.record_success("seekai", res.response_time_ms)
                return res
            except asyncio.TimeoutError:
                label = seekai_model or "default"
                msg = f"SeekAI ({label}): Timeout ({SEEKAI_TIMEOUT_SECONDS}s)"
                errors.append(msg)
                router.record_failure("seekai", is_rate_limit=False)
                print(f"[SMART ROUTER] {msg} -> Switching to Gemini...")
            except Exception as e:
                label = seekai_model or "default"
                msg = f"SeekAI ({label}): {type(e).__name__}: {e}"
                errors.append(msg)
                is_429 = "429" in str(e) or "limit" in str(e).lower()
                router.record_failure("seekai", is_rate_limit=is_429)
                print(f"[SMART ROUTER] {msg} -> Switching to Gemini...")

        elif provider == "gemini" and gemini_key:
            try:
                res = await _try_gemini(user_message, history, system_prompt, gemini_key)
                router.record_success("gemini", res.response_time_ms)
                return res
            except asyncio.TimeoutError:
                msg = f"Gemini: Timeout ({GEMINI_TIMEOUT_SECONDS}s)"
                errors.append(msg)
                router.record_failure("gemini", is_rate_limit=False)
                print(f"[SMART ROUTER] {msg} -> Switching...")
            except Exception as e:
                msg = f"Gemini: {type(e).__name__}: {e}"
                errors.append(msg)
                is_429 = "429" in str(e) or "ResourceExhausted" in str(e)
                router.record_failure("gemini", is_rate_limit=is_429)
                print(f"[SMART ROUTER] {msg} -> Switching...")

        elif provider == "duckai":
            try:
                res = await _try_duckai(user_message, history, system_prompt)
                router.record_success("duckai", res.response_time_ms)
                return res
            except asyncio.TimeoutError:
                msg = f"Duck.ai: Timeout ({DUCKAI_TIMEOUT_SECONDS}s)"
                errors.append(msg)
                router.record_failure("duckai", is_rate_limit=False)
            except Exception as e:
                msg = f"Duck.ai: {type(e).__name__}: {e}"
                errors.append(msg)
                router.record_failure("duckai", is_rate_limit=False)

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
