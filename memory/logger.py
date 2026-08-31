"""
memory/logger.py
────────────────
تسجيل كل تفاعل تلقائيًا في Supabase.
كل رسالة جاية + كل رد بيتسجل هنا بدون استثناء.
"""

import time
from typing import Optional
from memory.supabase_client import get_supabase

# ── In-Memory TTL Cache ──────────────────────────────
# تخزين مؤقت للبيانات شبه الثابتة لتقليل زمن الاستعلام (Latency) من ~600ms إلى ~0ms
_CACHE_TTL_SECONDS = 300  # 5 دقائق

_cached_preferences: Optional[dict] = None
_cached_preferences_ts: float = 0.0

_cached_projects: Optional[list] = None
_cached_projects_ts: float = 0.0

_cached_decisions: Optional[list] = None
_cached_decisions_ts: float = 0.0


def invalidate_context_cache() -> None:
    """تفريغ الكاش يدوياً عند حدوث تغيير."""
    global _cached_preferences, _cached_projects, _cached_decisions
    _cached_preferences = None
    _cached_projects = None
    _cached_decisions = None


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
    """بيجيب تفضيل معين من الذاكرة الدائمة (أو الكاش إن وجد)."""
    global _cached_preferences
    if _cached_preferences is not None and key in _cached_preferences:
        return {"value": _cached_preferences[key], "description": None}
        
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
    """بيحفظ أو يحدث تفضيل في الذاكرة الدائمة ويحدث الكاش."""
    global _cached_preferences
    try:
        db = get_supabase()
        db.table("preferences").upsert({
            "key": key,
            "value": value,
            "description": description,
        }, on_conflict="key").execute()
        
        # تحديث الكاش المحلي فوراً
        if _cached_preferences is not None:
            _cached_preferences[key] = value
    except Exception as e:
        print(f"⚠️ فشل حفظ التفضيل: {e}")


async def get_full_context() -> dict:
    """
    بيجيب كل السياق المتاح لشاهر دفعة واحدة مع كاش ذكي:
      - آخر 8 رسائل من المحادثات (استعلام مباشر وخفيف)
      - المشاريع النشطة (من الكاش بمدة 5 دقائق)
      - التفضيلات الشخصية (من الكاش بمدة 5 دقائق)
      - آخر قرارات مهمة (من الكاش بمدة 5 دقائق)

    النتيجة دي بتتحقن في الـ System Prompt عشان شاهر
    يشوف الصورة كاملة بأقل زمن استجابة ممكن.
    """
    global _cached_preferences, _cached_preferences_ts
    global _cached_projects, _cached_projects_ts
    global _cached_decisions, _cached_decisions_ts

    now = time.time()
    db = get_supabase()
    
    ctx: dict = {
        "recent_messages": [],
        "active_projects": [],
        "preferences": {},
        "recent_decisions": [],
    }

    # ── 1. آخر المحادثات (دائماً مباشرة من قاعدة البيانات) ──
    try:
        result = (
            db.table("interactions")
            .select("user_message, ai_response, created_at")
            .order("created_at", desc=True)
            .limit(8)
            .execute()
        )
        ctx["recent_messages"] = list(reversed(result.data or []))
    except Exception as e:
        print(f"⚠️ context/messages: {e}")

    # ── 2. المشاريع النشطة (مخزنة مؤقتاً) ──
    if _cached_projects is not None and (now - _cached_projects_ts) < _CACHE_TTL_SECONDS:
        ctx["active_projects"] = _cached_projects
    else:
        try:
            result = (
                db.table("projects")
                .select("name, description, status, channel, github_repo")
                .eq("status", "active")
                .limit(10)
                .execute()
            )
            _cached_projects = result.data or []
            _cached_projects_ts = now
            ctx["active_projects"] = _cached_projects
        except Exception as e:
            print(f"⚠️ context/projects: {e}")
            ctx["active_projects"] = _cached_projects or []

    # ── 3. التفضيلات كلها (مخزنة مؤقتاً) ──
    if _cached_preferences is not None and (now - _cached_preferences_ts) < _CACHE_TTL_SECONDS:
        ctx["preferences"] = _cached_preferences
    else:
        try:
            result = (
                db.table("preferences")
                .select("key, value")
                .execute()
            )
            prefs = {}
            for row in (result.data or []):
                prefs[row["key"]] = row["value"]
            _cached_preferences = prefs
            _cached_preferences_ts = now
            ctx["preferences"] = _cached_preferences
        except Exception as e:
            print(f"⚠️ context/preferences: {e}")
            ctx["preferences"] = _cached_preferences or {}

    # ── 4. آخر القرارات (مخزنة مؤقتاً) ──
    if _cached_decisions is not None and (now - _cached_decisions_ts) < _CACHE_TTL_SECONDS:
        ctx["recent_decisions"] = _cached_decisions
    else:
        try:
            result = (
                db.table("decisions")
                .select("title, decision, created_at")
                .order("created_at", desc=True)
                .limit(5)
                .execute()
            )
            _cached_decisions = result.data or []
            _cached_decisions_ts = now
            ctx["recent_decisions"] = _cached_decisions
        except Exception as e:
            print(f"⚠️ context/decisions: {e}")
            ctx["recent_decisions"] = _cached_decisions or []

    return ctx
