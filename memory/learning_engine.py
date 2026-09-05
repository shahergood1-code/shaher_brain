"""
memory/learning_engine.py
─────────────────────────
محرك التعلّم الذاتي والذاكرة التطورية لشاهر الثاني (Self-Evolving Learning Engine).

المهام:
  1. تحليل كل محادثة في الخلفية (Background Learning) لاستخراج:
     - التفضيلات الشخصية للمستخدم (Preferences).
     - القرارات والمشاريع الجديدة (Projects & Decisions).
     - التصحيحات والتوجيهات (Corrections & Feedback).
  2. حفظ المعرفة المستفادة وتحديث الكاش الدائم في Supabase.
  3. حقن ما تم تعلمه تلقائياً في System Prompt لكل محادثة قادمة.
"""

import asyncio
import json

from memory.logger import invalidate_context_cache, set_preference
from memory.supabase_client import get_supabase

# ─── الفحص والاستخراج الذكي للمعرفة ────────────────────────

async def auto_learn_from_interaction(user_message: str, ai_response: str) -> None:
    """
    بيحلل المحادثة في الخلفية بدون تأخير الرد على المستخدم،
    ويستخرج أي معلومات جديدة أو تفضيلات أو تصحيحات ليحفظها في الذاكرة الدائمة.
    """
    if len(user_message.strip()) < 5:
        return

    # كلمات دلالية توحي بوجود تعلّم أو توجيه أو قرار
    learning_triggers = [
        "أنا", "انا", "بحب", "بفضل", "مش عاوز", "مش عايز", "لا غلط",
        "الصح", "قررت", "المشروع", "اسمي", "شغلي", "افتكر", "تذكر",
        "النتيجة", "وحشة", "زفت", "ممتاز", "عاش", "عدل", "قناتي", "تليجرام"
    ]

    has_trigger = any(t in user_message.lower() for t in learning_triggers)
    if not has_trigger and len(user_message) < 40:
        return

    # استخراج الدرس أو التفضيل باستخدام استدعاء سريع
    try:
        import os

        from brain.ai_client import _try_nvidia, _try_seekai

        prompt = f"""أنت محلل ذاكرة ذكية. مهمتك تحليل رسالة المستخدم واستخراج أي معلومة جديدة تخص تفضيلاته، شخصيته، مشاريعه، أو تصحيح لأسلوبك.

رسالة المستخدم: "{user_message}"
رد المساعد: "{ai_response}"

إذا كانت الرسالة تحتوي على:
1. تفضيل شخصي (مثال: أسلوب كلام معين، طريقة تصميم، نوع خط، إلخ)
2. تصحيح أو نقد (مثال: تجنب كذا، اتكلم بطريقة كذا)
3. معلومة عن مشروع أو عمل (مثال: شغال على كذا، رابط كذا)
4. قرار أو توجيه دائم

استخرجها بتنسيق JSON فقط بهذا الشكل:
{{
  "has_learning": true,
  "key": "اسم_المفتاح_المختصر",
  "category": "preference" أو "correction" أو "project" أو "decision",
  "insight": "الوصف الواضح والمختصر لما تعلمته عن المستخدم لتطبيقه مستقبلاً"
}}

إذا لم تكن هناك معلومة دائمة تستحق الحفظ، أرجع:
{{"has_learning": false}}

أخرج JSON فقط بدون أي نص إضافي أو علامات markdown."""

        # محاولة التحليل بـ SeekAI أولاً ثم NVIDIA
        seekai_key = os.getenv("SEEKAI_API_KEY")
        nvidia_key = os.getenv("NVIDIA_API_KEY")
        raw_res = None

        if seekai_key:
            try:
                res = await asyncio.wait_for(
                    _try_seekai(prompt, [], "Output JSON only", seekai_key, model="glm-5.3-flash"),
                    timeout=8.0
                )
                raw_res = res.content
            except Exception:
                pass

        if not raw_res and nvidia_key:
            try:
                res = await asyncio.wait_for(
                    _try_nvidia(prompt, [], "Output JSON only", nvidia_key),
                    timeout=6.0
                )
                raw_res = res.content
            except Exception:
                pass

        if not raw_res:
            return

        # تنظيف وقراءة الـ JSON
        cleaned = raw_res.strip().replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned)

        if data.get("has_learning") and data.get("key") and data.get("insight"):
            key = f"learned_{data['category']}_{data['key']}"
            insight = data["insight"]
            
            # حفظ التفضيل المستفاد في الذاكرة الدائمة
            await set_preference(key, insight, description=f"Auto-learned from: {user_message[:50]}")
            print(f"🧠 [AUTO-LEARNING SUCCESS] شاهر تعلّم معلومة جديدة: [{key}] -> {insight}")
            invalidate_context_cache()

    except Exception:
        # فشل صامت في الخلفية دون التأثير على المستخدم
        pass


# ─── جلب كل الدروس والمعارف المستفادة للحقن في الـ Prompt ───

async def get_learned_insights() -> list[str]:
    """يجلب كافة الدروس والمعارف والتفضيلات التي تعلمها شاهر مع الوقت."""
    try:
        db = get_supabase()
        res = db.table("preferences").select("key, value").like("key", "learned_%").execute()
        insights = []
        for row in res.data or []:
            val = row.get("value")
            if val:
                insights.append(str(val))
        return insights
    except Exception:
        return []
