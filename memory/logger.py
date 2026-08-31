"""
memory/logger.py
────────────────
تسجيل كل تفاعل تلقائيًا في Supabase.
كل رسالة جاية + كل رد بيتسجل هنا بدون استثناء.
"""

from typing import Optional
from memory.supabase_client import get_supabase


async def log_interaction(
    user_message: str,
    ai_response: str,
    ai_source: str,
    ai_model: Optional[str] = None,
    message_type: str = "text",
    telegram_user_id: Optional[int] = None,
    telegram_chat_id: Optional[int] = None,
    response_time_ms: Optional[int] = None,
    tokens_used: Optional[int] = None,
    error_details: Optional[str] = None,
) -> None:
    """
    بيسجل التفاعل في جدول interactions في Supabase.
    بيشتغل async عشان ميأخرش الرد على المستخدم.
    """
    try:
        db = get_supabase()
        db.table("interactions").insert({
            "telegram_user_id": telegram_user_id,
            "telegram_chat_id": telegram_chat_id,
            "user_message": user_message,
            "message_type": message_type,
            "ai_source_used": ai_source,
            "ai_model_used": ai_model,
            "ai_response": ai_response,
            "response_time_ms": response_time_ms,
            "tokens_used": tokens_used,
            "error_details": error_details,
        }).execute()
    except Exception as e:
        print(f"⚠️ فشل تسجيل التفاعل في Supabase: {e}")


async def get_recent_context(limit: int = 10) -> list[dict]:
    """
    بيجيب آخر {limit} تفاعل من الذاكرة.
    بيتستخدم كـ context في طلبات AI عشان شاهر يفتكر المحادثة.
    """
    try:
        db = get_supabase()
        result = (
            db.table("interactions")
            .select("user_message, ai_response, created_at, ai_source_used")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return list(reversed(result.data or []))
    except Exception as e:
        print(f"⚠️ فشل جلب السياق من Supabase: {e}")
        return []


async def get_preference(key: str) -> Optional[dict]:
    """بيجيب تفضيل معين من الذاكرة الدائمة."""
    try:
        db = get_supabase()
        result = (
            db.table("preferences")
            .select("value, description")
            .eq("key", key)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


async def set_preference(key: str, value, description: Optional[str] = None) -> None:
    """بيحفظ أو يحدث تفضيل في الذاكرة الدائمة."""
    try:
        db = get_supabase()
        db.table("preferences").upsert({
            "key": key,
            "value": value,
            "description": description,
        }, on_conflict="key").execute()
    except Exception as e:
        print(f"⚠️ فشل حفظ التفضيل: {e}")


async def get_full_context() -> dict:
    """
    بيجيب كل السياق المتاح لشاهر دفعة واحدة:
      - آخر 12 رسالة من المحادثات
      - المشاريع النشطة
      - التفضيلات الشخصية
      - آخر قرارات مهمة

    النتيجة دي بتتحقن في الـ System Prompt عشان شاهر
    يشوف الصورة كاملة — مش بس الرسالة الحالية.
    """
    db = get_supabase()
    ctx: dict = {
        "recent_messages": [],
        "active_projects": [],
        "preferences": {},
        "recent_decisions": [],
    }

    # ── آخر المحادثات ──────────────────────────────────
    try:
        result = (
            db.table("interactions")
            .select("user_message, ai_response, created_at")
            .order("created_at", desc=True)
            .limit(12)
            .execute()
        )
        ctx["recent_messages"] = list(reversed(result.data or []))
    except Exception as e:
        print(f"⚠️ context/messages: {e}")

    # ── المشاريع النشطة ────────────────────────────────
    try:
        result = (
            db.table("projects")
            .select("name, description, status, channel, github_repo")
            .eq("status", "active")
            .limit(10)
            .execute()
        )
        ctx["active_projects"] = result.data or []
    except Exception as e:
        print(f"⚠️ context/projects: {e}")

    # ── التفضيلات كلها ─────────────────────────────────
    try:
        result = (
            db.table("preferences")
            .select("key, value")
            .execute()
        )
        for row in (result.data or []):
            ctx["preferences"][row["key"]] = row["value"]
    except Exception as e:
        print(f"⚠️ context/preferences: {e}")

    # ── آخر القرارات ───────────────────────────────────
    try:
        result = (
            db.table("decisions")
            .select("title, decision, created_at")
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        ctx["recent_decisions"] = result.data or []
    except Exception as e:
        print(f"⚠️ context/decisions: {e}")

    return ctx
