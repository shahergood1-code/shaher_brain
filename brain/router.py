"""
brain/router.py
───────────────
Shaher Brain — عقل التوجيه المركزي (المرحلة 1)

المرحلة دي: منطق تصنيف بسيط بالقواعد (rules-based).
مش نموذج AI معقد — الذكاء الحقيقي بيجي من البيانات اللي هتتراكم.

أنواع الطلبات:
  - GENERAL_CHAT: محادثة عادية، سؤال، تفكير في حاجة → رد مباشر من AI
  - MEMORY_QUERY: "فتكرني"، "إيه آخر حاجة"، سؤال عن الذاكرة → يجيب من Supabase
  - COMMAND: أوامر للنظام ("/help", "/status") → معالجة مباشرة
"""

import re
from dataclasses import dataclass
from enum import Enum


class MessageIntent(Enum):
    GENERAL_CHAT = "general_chat"
    MEMORY_QUERY = "memory_query"
    IMAGE_GENERATION = "image_generation"
    COMMAND = "command"


@dataclass
class RouterDecision:
    intent: MessageIntent
    needs_history: bool
    confidence: str  # 'high' | 'medium' | 'low'
    debug_reason: str


# كلمات تدل على طلب توليد صورة
IMAGE_KEYWORDS = [
    # عربي
    "صورة", "صوره", "صور لي", "صور عن",
    "ولّد صور", "ولّدلي", "ولدلي", "ولدي", "ولد لي", "ولّد لي",
    "اعمل صور", "اعمللي صورة", "اعمل صورة", "اعمل لي صورة",
    "غلاف", "غلاف يوتيوب", "ثمبنايل", "ثيمب", "بانر", "بنر",
    "بوست", "بوستات", "صورة انستجرام", "صورة انستقرام", "صورة محتوى",
    "توليد صورة", "انشئ صورة", "انشئ لي صورة", "ارسم", "ارسم لي", "تصميم صورة", "صمم لي",
    "خلفية", "خلفيه",
    # إنجليزي
    "generate image", "create image", "make image", "draw",
    "thumbnail", "cover art", "image for", "wallpaper",
]

# كلمات تدل على استفسار عن الذاكرة
MEMORY_KEYWORDS = [
    "فتكرني", "فاكر", "تذكر", "ذاكرتك",
    "آخر حاجة", "آخر مرة", "قبل كده",
    "اللي قلته", "اتكلمنا", "اتفقنا",
    "بياناتك", "حفظت", "سجلت",
    "remember", "recall", "last time",
]

# أوامر صريحة
COMMAND_PATTERNS = [
    r"^/\w+",         # /help, /status, /start
    r"^![\w\u0600-\u06FF]+",  # !مساعدة
]


def route(message: str) -> RouterDecision:
    """
    بياخد الرسالة ويقرر إيه النوع وإيه اللي لازم يتعمل.

    المبدأ: الأغلبية العظمى من الرسائل → GENERAL_CHAT
    مش كل رسالة لازم تتصنف كـ "مهمة" أو "مهمة معقدة".
    """
    text = message.strip()

    # ── أوامر صريحة ──
    for pattern in COMMAND_PATTERNS:
        if re.match(pattern, text, re.IGNORECASE):
            return RouterDecision(
                intent=MessageIntent.COMMAND,
                needs_history=False,
                confidence="high",
                debug_reason=f"matches command pattern: {pattern}",
            )

    text_lower = text.lower()

    # ── طلب توليد صورة ──
    for kw in IMAGE_KEYWORDS:
        if kw in text_lower:
            return RouterDecision(
                intent=MessageIntent.IMAGE_GENERATION,
                needs_history=False,
                confidence="high",
                debug_reason=f"contains image keyword: '{kw}'",
            )

    # ── استفسار عن الذاكرة ──
    for kw in MEMORY_KEYWORDS:
        if kw in text_lower:
            return RouterDecision(
                intent=MessageIntent.MEMORY_QUERY,
                needs_history=True,
                confidence="medium",
                debug_reason=f"contains memory keyword: '{kw}'",
            )

    # ── كل حاجة تانية: محادثة عامة ──
    # شاهر بيرد كـ AI assistant عادي مع context من الذاكرة
    return RouterDecision(
        intent=MessageIntent.GENERAL_CHAT,
        needs_history=True,
        confidence="high",
        debug_reason="default: general conversation",
    )


async def handle_command(text: str) -> str:
    """معالجة الأوامر المباشرة."""
    cmd = text.split()[0].lower().lstrip("/!")

    commands = {
        "start": "👋 أنا شاهر — مساعدك الشخصي. ابعتلي أي حاجة وهرد عليك.",
        "help": (
            "📋 *الأوامر المتاحة:*\n"
            "/start — البداية\n"
            "/help — قائمة الأوامر\n"
            "/status — حالة النظام العامة\n"
            "/content — موديول إنتاج المحتوى (الشورتس والسوشيال ميديا)\n"
            "/content_status — حالة آخر دورة إنتاج محتوى\n"
            "/content_run — تشغيل دورة إنتاج ونشر المحتوى اليومي فوراً\n"
            "\nأو ابعتلي أي رسالة عادية وهرد عليك مباشرة! 🧠"
        ),
        "status": "✅ النظام شغال\n🧠 AI: Gemini (مع fallback تلقائي)\n💾 الذاكرة: Supabase",
        "content": (
            "🎬 *موديول إنتاج المحتوى (Content Orchestrator)*\n\n"
            "النظام مجهز بالكامل لإنتاج شورتس يوتيوب وبوستات السوشيال ميديا يومياً بضغطة زر.\n"
            "للتحكم محلياً، يمكنك استخدام CLI عبر:\n"
            "`python main.py run` (تشغيل خطة اليوم)\n"
            "`python main.py status` (فحص كرت الشاشة والمتصفح)\n"
            "أو أرسل `/content_run` لتشغيل المهمة من هنا."
        ),
    }

    if cmd in ["content_run", "run_content"]:
        try:
            from core.state_manager import StateManager
            task = StateManager.create_task(user_goal="تشغيل دورة المحتوى اليومية عبر تليجرام")
            task_id = task.get("id", "unknown")

            # محاولة الإطلاق في ثريد خلفي محلي
            import threading
            def _bg_run():
                try:
                    from core.orchestrator import run_content_orchestrator
                    from core.prompts import DAILY_ROUTINE_PROMPT
                    run_content_orchestrator(DAILY_ROUTINE_PROMPT)
                except Exception as e:
                    print(f"Background run error: {e}")

            threading.Thread(target=_bg_run, daemon=True).start()

            return (
                f"🚀 *تم إطلاق دورة إنتاج المحتوى اليومي بنجاح!*\n\n"
                f"🆔 معرف المهمة: `{task_id}`\n"
                f"⚙️ العقل المدير (Ollama) بدأ تنفيذ الخطوات بكرت RTX 4070.\n\n"
                f"💡 أرسل `/content_status` في أي وقت لمتابعة التقدم والنتيجة."
            )
        except Exception as exc:
            return f"⚠️ حدث خطأ أثناء إطلاق المهمة: {exc}"

    if cmd == "content_status":
        try:
            from memory.supabase_client import get_supabase
            client = get_supabase()
            res = client.table("content_tasks").select("id, status, created_at, summary").order("created_at", desc=True).limit(1).execute()
            if res.data:
                latest = res.data[0]
                return (
                    f"📊 *آخر مهمة إنتاج محتوى:*\n"
                    f"- الحالة: `{latest.get('status')}`\n"
                    f"- التاريخ: `{latest.get('created_at')[:19]}`\n"
                    f"- الملخص: {latest.get('summary') or 'قيد المعالجة'}"
                )
            return "ℹ️ لا توجد مهام إنتاج محتوى مسجلة بعد في Supabase."
        except Exception as exc:
            return f"⚠️ تعذر جلب حالة المحتوى: {exc}"

    return commands.get(cmd, f"❓ أمر مش متعرف عليه: `{text}`\nاكتب /help عشان تشوف الأوامر.")
