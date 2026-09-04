"""
brain/ai_client.py
──────────────────
Fallback AI Chain & Multi-Model Engine لشاهر الثاني.

المصادر المدعومة وترتيب الأولوية الذكي:
  1. Ollama Local (qwen2.5:7b) — تشغيل محلي فائق السرعة عبر كرت RTX 4070 وبدون إنترنت
  2. SeekAI Aggregator (glm-5.3-flash, kimi-k3, deepseek-v4-flash, claude, gpt) — فصاحة وجودة لغوية عالية
  3. Gemini Official API (google-generativeai: gemini-1.5-flash / gemini-2.0-flash)
  4. NVIDIA NIM (meta/llama-3.2-11b-vision-instruct, nemotron)

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


# ─── Ollama Available Models (تشغيل محلي مسرع بـ RTX 4070) ───────────
OLLAMA_MODELS: dict[str, str] = {
    "default":          os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
    "qwen":             "qwen2.5:7b",
    "qwen2.5":          "qwen2.5:7b",
    "qwen-7b":          "qwen2.5:7b",
    "llama":            "llama3.2:latest",
    "llama3":           "llama3.2:latest",
    "mistral":          "mistral:latest",
    "deepseek":         "deepseek-r1:7b",
}


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
DUCKAI_TIMEOUT_SECONDS = float(os.getenv("DUCKAI_TIMEOUT", "4.5"))


# ─── Source 1: Gemini Official ────────────────────────────

async def _try_gemini(
    user_message: str,
    history: list[dict],
    system_prompt: str,
    api_key: str,
) -> AIResponse:
    """Gemini Official API — المصدر الأساسي مع مهلة سريعة وتصحيح الموديلات التلقائي."""
    import google.generativeai as genai

    start = time.time()
    genai.configure(api_key=api_key)

    pref_model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    candidate_models = [pref_model, "gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
    models_to_try = list(dict.fromkeys([m for m in candidate_models if m]))

    chat_history = []
    for item in history[-8:]:
        if item.get("user_message"):
            chat_history.append({"role": "user", "parts": [item["user_message"]]})
        if item.get("ai_response"):
            chat_history.append({"role": "model", "parts": [item["ai_response"]]})

    last_err = None
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_prompt,
            )
            chat = model.start_chat(history=chat_history)
            response = await asyncio.wait_for(
                asyncio.to_thread(chat.send_message, user_message),
                timeout=GEMINI_TIMEOUT_SECONDS,
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
        except Exception as exc:
            last_err = exc
            print(f"[WARN] Gemini model '{model_name}' failed: {exc} -- trying next candidate...")

    raise last_err or Exception("All Gemini candidate models failed")


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


# ─── Source 3: NVIDIA NIM (فائق السرعة والاستقرار) ──────────────────────────

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


# ─── Source 4: Ollama Local (العقل المحلي المسرع بـ RTX 4070) ───────────

def is_ollama_online(host_url: str | None = None) -> bool:
    """فحص سريع بـ socket للتأكد من تشغيل خادم Ollama في أقل من 50 مللي ثانية."""
    import socket
    from urllib.parse import urlparse
    if not host_url:
        host_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        parsed = urlparse(host_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 11434
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.15)
            return sock.connect_ex((host, port)) == 0
    except Exception:
        return False


async def _try_ollama(
    user_message: str,
    history: list[dict],
    system_prompt: str,
    model: str | None = None,
) -> AIResponse:
    """Ollama Local API — تشغيل محلي فائق السرعة عبر كرت RTX 4070 وبدون إنترنت."""
    import ollama

    start = time.time()
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model_name = OLLAMA_MODELS.get(model or "default", model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b"))

    chat_msgs = [{"role": "system", "content": system_prompt}]
    for item in history[-6:]:
        if item.get("user_message"):
            chat_msgs.append({"role": "user", "content": item["user_message"]})
        if item.get("ai_response"):
            chat_msgs.append({"role": "assistant", "content": item["ai_response"]})
    chat_msgs.append({"role": "user", "content": user_message})

    client = ollama.AsyncClient(host=host)
    response = await asyncio.wait_for(
        client.chat(model=model_name, messages=chat_msgs),
        timeout=float(os.getenv("OLLAMA_TIMEOUT", "30.0")),
    )

    elapsed = int((time.time() - start) * 1000)
    return AIResponse(
        content=response["message"]["content"],
        source="ollama",
        model=model_name,
        response_time_ms=elapsed,
    )


# ─── Source 5: Duck.ai (Fallback مجاني وبدون API Key) ───────────

async def _try_duckai(
    user_message: str,
    history: list[dict],
    system_prompt: str,
    model: str = "gpt-4o-mini",
) -> AIResponse:
    """
    Duck.ai — مزود مجاني وبدون أي API keys عبر خدمة DuckDuckGo AI.
    مزود بمهلة سريعة جداً (4.5 ثوانٍ) لمنع أي تعطيل في البوت.
    """
    start = time.time()

    context_text = ""
    for item in history[-4:]:
        if item.get("user_message"):
            context_text += f"User: {item['user_message']}\n"
        if item.get("ai_response"):
            context_text += f"Assistant: {item['ai_response']}\n"

    full_prompt = f"{system_prompt}\n\n{context_text}User: {user_message}"

    def _sync_call():
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # محاولة 1: عبر حزمة duckai
            try:
                from duckai import DuckAI
                client = DuckAI(timeout=int(DUCKAI_TIMEOUT_SECONDS))
                res = client.chat(full_prompt, model=model)
                if res and res.strip():
                    return res.strip()
            except Exception:
                pass

            # محاولة 2: عبر duckduckgo_search لو بها chat
            try:
                from duckduckgo_search import DDGS
                ddgs = DDGS()
                if hasattr(ddgs, "chat"):
                    res = next(ddgs.chat(full_prompt, model=model), "")
                    if res and res.strip():
                        return res.strip()
            except Exception:
                pass

        return ""

    response_text = await asyncio.wait_for(
        asyncio.to_thread(_sync_call),
        timeout=DUCKAI_TIMEOUT_SECONDS,
    )

    if not response_text:
        raise Exception("Duck.ai returned empty response or rate limit/challenge active")

    elapsed = int((time.time() - start) * 1000)
    return AIResponse(
        content=response_text,
        source="duckai",
        model=f"{model} (duck.ai)",
        response_time_ms=elapsed,
    )


# ─── Smart Adaptive AI Router (Health & Latency Ranker) ────────────

class SmartAIRouter:
    """
    نظام ذكي لتقييم جودة وسرعة وصحة المزودين ديناميكياً:
    - يفضل النماذج القوية في اللغة العربية (SeekAI, Gemini, Ollama, NVIDIA)
    - يضع المزود الذي يواجه 429 أو خطأ في فترة Cooldown
    - يحدّث متوسط السرعة بعد كل استجابة ناجحة
    """
    def __init__(self):
        self.stats = {
            "seekai":     {"avg_latency": 1200, "fails": 0, "cooldown_until": 0, "tier": 1},
            "gemini":     {"avg_latency": 1500, "fails": 0, "cooldown_until": 0, "tier": 1},
            "ollama":     {"avg_latency": 800,  "fails": 0, "cooldown_until": 0, "tier": 1},
            "nvidia_nim": {"avg_latency": 1100, "fails": 0, "cooldown_until": 0, "tier": 1},
            "duckai":     {"avg_latency": 4000, "fails": 0, "cooldown_until": 0, "tier": 2},
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
    preferred_source: str | None = None,
) -> AIResponse:
    """
    الدالة الرئيسية — تختار ديناميكياً أسرع وأفضل مزود في الوقت الفعلي:
      - تفحص المزودين المتاحين (SeekAI, Gemini, Ollama, NVIDIA NIM)
      - ترتبهم حسب الجودة والسرعة وصحة الاتصال
      - تنفذ وتحدث الإحصائيات فوراً
    """
    if context is None:
        context = {}

    system_prompt = _build_system_prompt(context) if context else _STATIC_SYSTEM_PROMPT
    history = context.get("recent_messages", [])
    errors = []

    # 1. تحديد المزودين المتاحين
    configured = []
    seekai_key = os.getenv("SEEKAI_API_KEY")
    if seekai_key:
        configured.append("seekai")

    gemini_key = (
        os.getenv(f"GEMINI_API_KEY_{component.upper()}")
        or os.getenv("GEMINI_API_KEY_BRAIN")
        or os.getenv("GEMINI_API_KEY")
    )
    if gemini_key:
        configured.append("gemini")

    nvidia_key = os.getenv("NVIDIA_API_KEY")
    if nvidia_key:
        configured.append("nvidia_nim")

    # فحص خادم Ollama المحلي السريع
    if is_ollama_online():
        configured.append("ollama")

    # Duck.ai مجاني وبدون مفتاح ومتاح دائماً
    configured.append("duckai")

    # 2. ترتيب المزودين (مع مراعاة التفضيل لو محدد)
    if preferred_source:
        pref = preferred_source.lower()
        if pref in ("ollama", "local") and "ollama" in configured:
            optimal_order = ["ollama"] + [p for p in configured if p != "ollama"]
        elif pref in ("duckai", "duck") and "duckai" in configured:
            optimal_order = ["duckai"] + [p for p in configured if p != "duckai"]
        elif pref in configured:
            optimal_order = [pref] + [p for p in configured if p != pref]
        else:
            optimal_order = router.get_optimal_order(configured)
    else:
        optimal_order = router.get_optimal_order(configured)

    # 3. التجربة حسب الترتيب
    for provider in optimal_order:
        if provider == "ollama":
            try:
                res = await _try_ollama(
                    user_message, history, system_prompt,
                    model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
                )
                router.record_success("ollama", res.response_time_ms)
                return res
            except Exception as e:
                errors.append(f"Ollama: {e}")
                router.record_failure("ollama", is_rate_limit=False)
                print(f"[SMART ROUTER] Ollama failed: {e} -> Switching to next provider...")

        elif provider == "seekai" and seekai_key:
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
                print(f"[SMART ROUTER] {msg} -> Switching...")
            except Exception as e:
                label = seekai_model or "default"
                msg = f"SeekAI ({label}): {type(e).__name__}: {e}"
                errors.append(msg)
                is_429 = "429" in str(e) or "limit" in str(e).lower()
                router.record_failure("seekai", is_rate_limit=is_429)
                print(f"[SMART ROUTER] {msg} -> Switching...")

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

        elif provider == "nvidia_nim" and nvidia_key:
            try:
                res = await _try_nvidia(user_message, history, system_prompt, nvidia_key)
                router.record_success("nvidia_nim", res.response_time_ms)
                return res
            except Exception as e:
                msg = f"NVIDIA NIM: {type(e).__name__}: {e}"
                errors.append(msg)
                router.record_failure("nvidia_nim", is_rate_limit=("429" in str(e)))
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
                print(f"[SMART ROUTER] {msg} -> Switching...")
            except Exception as e:
                msg = f"Duck.ai: {type(e).__name__}: {e}"
                errors.append(msg)
                router.record_failure("duckai", is_rate_limit=False)
                print(f"[SMART ROUTER] {msg} -> Switching...")

    # 4. Fallback إضافي: لو Ollama مكنش في الترتيب بس متصل
    if "ollama" not in optimal_order and is_ollama_online():
        try:
            res = await _try_ollama(user_message, history, system_prompt)
            router.record_success("ollama", res.response_time_ms)
            return res
        except Exception as ollama_err:
            errors.append(f"Ollama fallback: {ollama_err}")

    # ── كل المصادر السحابية فشلت أو تجاوزت الـ Rate Limits ──
    # لا نظهر رسالة 'عذرًا مفيش AI' نهائياً — نستدعي محرك الإنقاذ الذاتي فوراً
    return _generate_emergency_response(user_message, errors)


def _generate_emergency_response(user_message: str, errors: list[str]) -> AIResponse:
    """
    محرك الإنقاذ الذكي الذاتي (Autonomous Emergency Engine):
    يضمن عدم ظهور أي رسالة خطأ أو 'عذرًا مفيش AI' نهائياً حتى لو انقطعت كل الـ APIs الخارجية في وقت واحد.
    """
    msg = user_message.strip().lower()

    # 1. التحيات والدردشة العادية
    greetings = ["ازيك", "ازيّك", "عامل ايه", "اخبارك", "أخبارك", "مساء الخير", "صباح الخير", "هاي", "hello", "hi", "السلام عليكم", "يا شاهر", "شاهر"]
    if any(g in msg for g in greetings):
        content = (
            "أهلاً يا صديقي! أنا بخير والحمد لله وكله تمام ومركز معاك 100% 🚀\n"
            "قولي، حابب نشتغل على إيه دلوقتي؟ برمجة، تسويق، أفكار، ولا دردشة عادية؟"
        )
    # 2. الاستفسارات البرمجية والتقنية
    elif any(k in msg for k in ["كود", "برمجة", "python", "javascript", "fastapi", "دالة", "خطأ", "error", "bug", "سكريبت", "api"]):
        content = (
            "أنا معاك في البرمجة فوراً! 💻\n"
            "عشان أساعدك بأعلى دقة، ابعتلي مقتطف الكود أو رسالة الخطأ اللي بتواجهك بالظبط، وهحللهالك سطر بسطر مع التصحيح الجاهز."
        )
    # 3. الاستفسارات الاستراتيجية أو صناعة المحتوى
    elif any(k in msg for k in ["يوتيوب", "فيديو", "ريلز", "قناة", "مشاهدات", "تسويق", "بيزنس", "خطة", "استراتيجية", "shorts"]):
        content = (
            "سؤال استراتيجي ممتاز! 🎯\n"
            "الركيزة الأساسية هنا بتعتمد على 3 عناصر أساسية:\n"
            "1. **الهوك (Hook) في أول 3 ثوانٍ:** لازم يجذب الفضول أو يطرح مشكلة مباشرة بدون مقدمات.\n"
            "2. **القيمة المركزة:** خلي كل ثانية في الفيديو بتقدم معلومة أو إبهار بدون حشو.\n"
            "3. **الدعوة للتفاعل (CTA):** اطلب رأي محدد في التعليقات عشان ترفع معدل الـ Engagement.\n\n"
            "تحب نحدد سكريبت أو فكرة معينة نشتغل عليها دلوقتي؟"
        )
    # 4. الرد الذكي العام
    else:
        content = (
            f"أنا سامعك ومركز معاك جداً بخصوص استفسارك 💡\n\n"
            "وضحلي أكتر التفاصيل أو النتيجة اللي عايز توصلها وهبدأ معاك فوراً خطوة بخطوة بأفضل طريقة ممكنة!"
        )

    return AIResponse(
        content=content,
        source="emergency_brain",
        model="shaher-autonomous-v1",
        response_time_ms=5,
        error=" | ".join(errors) if errors else None,
    )


# --- Standalone: Ollama Direct (المعالج المحلي المباشر) ---

async def get_ollama_response(
    user_message: str,
    model: str | None = None,
    context: dict | None = None,
) -> AIResponse:
    """
    استدعاء Ollama محلياً مباشرة وبدون أي مزودات سحابية.
    مناسب للعمل Offline أو للاستفادة الكاملة من كرت الشاشة RTX 4070.

    الموديلات المتاحة (OLLAMA_MODELS):
        'qwen'     -> qwen2.5:7b (الافتراضي)
        'llama'    -> llama3.2:latest
        'mistral'  -> mistral:latest
        'deepseek' -> deepseek-r1:7b
    """
    if context is None:
        context = {}

    system_prompt = _build_system_prompt(context) if context else _STATIC_SYSTEM_PROMPT
    history = context.get("recent_messages", [])

    if not is_ollama_online():
        return AIResponse(
            content="خادم Ollama المحلي غير متصل (تأكد من تشغيل Ollama على جهازك).",
            source="error",
            model=model or "default",
            response_time_ms=0,
            error="Ollama server is offline",
        )

    try:
        resolved_model = OLLAMA_MODELS.get(model or "default", model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b"))
        return await _try_ollama(
            user_message,
            history,
            system_prompt,
            model=resolved_model,
        )
    except Exception as e:
        return AIResponse(
            content=f"خطأ في استدعاء Ollama المحلي: {e}",
            source="error",
            model=model or "default",
            response_time_ms=0,
            error=str(e),
        )


# --- Standalone: SeekAI Direct (لمهام محددة) ---

async def get_seekai_response(
    user_message: str,
    model: str,
    context: dict | None = None,
) -> AIResponse:
    """
    استدعاء SeekAI بموديل محدد مباشرة — بدون تجربة Gemini أولًا.

    الموديلات المتاحة (SEEKAI_MODELS):
        'gpt'             -> gpt-5.6-sol
        'claude'          -> claude-sonnet-5
        'gpt-5.6-sol'     -> gpt-5.6-sol
        'claude-sonnet-5' -> claude-sonnet-5
        'default'         -> الافتراضي من .env
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


# --- Standalone: NVIDIA NIM Direct (لمهام محددة) ---

async def get_nvidia_response(
    user_message: str,
    model: str | None = None,
    context: dict | None = None,
) -> AIResponse:
    """استدعاء NVIDIA NIM مباشرة لموديل محدد."""
    if context is None:
        context = {}

    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        return AIResponse(
            content="NVIDIA_API_KEY غير موجود في .env",
            source="error",
            model=model or "default",
            response_time_ms=0,
            error="missing NVIDIA_API_KEY",
        )

    system_prompt = _build_system_prompt(context) if context else _STATIC_SYSTEM_PROMPT
    history = context.get("recent_messages", [])

    try:
        return await _try_nvidia(
            user_message, history, system_prompt,
            api_key, model=model,
        )
    except Exception as e:
        resolved = NVIDIA_MODELS.get(model or "default", model or "default")
        return AIResponse(
            content=f"فشل NVIDIA NIM ({resolved}): {e}",
            source="error",
            model=resolved,
            response_time_ms=0,
            error=str(e),
        )


# --- Standalone: Duck.ai Direct (بدون API Key) ---

async def get_duckai_response(
    user_message: str,
    model: str = "gpt-4o-mini",
    context: dict | None = None,
) -> AIResponse:
    """استدعاء Duck.ai مباشرة مجاناً بدون API Key وبمهلة سريعة."""
    if context is None:
        context = {}

    system_prompt = _build_system_prompt(context) if context else _STATIC_SYSTEM_PROMPT
    history = context.get("recent_messages", [])

    try:
        return await _try_duckai(
            user_message, history, system_prompt, model=model
        )
    except Exception as e:
        return AIResponse(
            content=f"فشل Duck.ai ({model}): {e}",
            source="error",
            model=model,
            response_time_ms=0,
            error=str(e),
        )
