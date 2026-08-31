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
    "ولّد صور", "ولّدلي", "اعمل صور", "اعمللي صورة",
    "غلاف", "غلاف يوتيوب", "ثمبنايل",
    "بوست", "بوستات", "صورة انستجرام", "صورة محتوى",
    "توليد صورة", "انشئ صورة", "ارسم", "تصميم",
    # إنجليزي
    "generate image", "create image", "make image",
    "thumbnail", "cover art", "image for",
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
            "/status — حالة النظام\n"
            "\nأو ابعتلي أي رسالة عادية وهرد عليك مباشرة! 🧠"
        ),
        "status": "✅ النظام شغال\n🧠 AI: Gemini (مع fallback تلقائي)\n💾 الذاكرة: Supabase",
    }

    return commands.get(cmd, f"❓ أمر مش متعرف عليه: `{text}`\nاكتب /help عشان تشوف الأوامر.")
