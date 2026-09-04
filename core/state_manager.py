"""
core/state_manager.py
─────────────────────
يدير مزامنة حالة مهام موديول المحتوى مع Supabase (بديل history.json).
يدعم Fallback محلي في حال غياب الاتصال أو عدم توفر المفاتيح.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

from config.settings import WORKSPACE_DIR

logger = logging.getLogger("StateManager")
LOCAL_HISTORY_FILE = WORKSPACE_DIR / "history.json"


def _get_supabase_client():
    """يحاول جلب كائن Supabase من memory/supabase_client."""
    try:
        from memory.supabase_client import get_supabase
        return get_supabase()
    except Exception as exc:
        logger.warning(f"تعذر الاتصال بـ Supabase: {exc} — سيتم استخدام التخزين المحلي.")
        return None


def _load_local_history() -> List[Dict[str, Any]]:
    if LOCAL_HISTORY_FILE.exists():
        try:
            return json.loads(LOCAL_HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_local_history(data: List[Dict[str, Any]]) -> None:
    LOCAL_HISTORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class StateManager:
    """إدارة حفظ واسترجاع المهام والمنشورات والإحصائيات."""

    @staticmethod
    def create_task(user_goal: str, task_type: str = "daily_pipeline") -> Dict[str, Any]:
        """تسجيل بدء مهمة جديدة في content_tasks."""
        now_iso = datetime.now(timezone.utc).isoformat()
        client = _get_supabase_client()

        if client:
            try:
                res = client.table("content_tasks").insert({
                    "task_type": task_type,
                    "status": "running",
                    "user_goal": user_goal,
                    "steps": [],
                }).execute()
                if res.data:
                    return res.data[0]
            except Exception as exc:
                logger.error(f"خطأ أثناء إنشاء المهمة في Supabase: {exc}")

        # Fallback محلي
        task_id = f"local_{int(datetime.now().timestamp())}"
        local_task = {
            "id": task_id,
            "created_at": now_iso,
            "task_type": task_type,
            "status": "running",
            "user_goal": user_goal,
            "steps": [],
        }
        history = _load_local_history()
        history.append(local_task)
        _save_local_history(history)
        return local_task

    @staticmethod
    def append_task_step(task_id: str, step_num: int, tool_name: str, args: Dict[str, Any], result: Dict[str, Any]) -> None:
        """إضافة خطوة تم تنفيذها إلى سجل خطوات المهمة."""
        step_entry = {
            "step": step_num,
            "tool": tool_name,
            "args": args,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        client = _get_supabase_client()
        if client and not task_id.startswith("local_"):
            try:
                # نجلب الخطوات الحالية ونضيف عليها
                res = client.table("content_tasks").select("steps").eq("id", task_id).execute()
                if res.data:
                    current_steps = res.data[0].get("steps") or []
                    current_steps.append(step_entry)
                    client.table("content_tasks").update({"steps": current_steps}).eq("id", task_id).execute()
                    return
            except Exception as exc:
                logger.error(f"خطأ أثناء تحديث الخطوة في Supabase: {exc}")

        # Fallback محلي
        history = _load_local_history()
        for t in history:
            if t.get("id") == task_id:
                t.setdefault("steps", []).append(step_entry)
                break
        _save_local_history(history)

    @staticmethod
    def complete_task(task_id: str, summary: str, status: str = "completed", error_details: Optional[str] = None) -> None:
        """تحديث حالة انتهاء المهمة (نجاح أو فشل)."""
        now_iso = datetime.now(timezone.utc).isoformat()
        client = _get_supabase_client()

        if client and not task_id.startswith("local_"):
            try:
                update_data = {
                    "status": status,
                    "summary": summary,
                    "completed_at": now_iso,
                }
                if error_details:
                    update_data["error_details"] = error_details
                client.table("content_tasks").update(update_data).eq("id", task_id).execute()
                return
            except Exception as exc:
                logger.error(f"خطأ أثناء إنهاء المهمة في Supabase: {exc}")

        # Fallback محلي
        history = _load_local_history()
        for t in history:
            if t.get("id") == task_id:
                t["status"] = status
                t["summary"] = summary
                t["completed_at"] = now_iso
                if error_details:
                    t["error_details"] = error_details
                break
        _save_local_history(history)

    @staticmethod
    def record_post(
        task_id: str,
        content_type: str,
        title: Optional[str] = None,
        script: Optional[str] = None,
        prompt_used: Optional[str] = None,
        caption: Optional[str] = None,
        media_path: Optional[str] = None,
        platforms: Optional[List[str]] = None,
        status: str = "draft",
    ) -> Optional[str]:
        """تسجيل منشور جديد في content_posts."""
        client = _get_supabase_client()
        platforms = platforms or []

        if client and not task_id.startswith("local_"):
            try:
                res = client.table("content_posts").insert({
                    "task_id": task_id,
                    "content_type": content_type,
                    "title": title,
                    "script": script,
                    "prompt_used": prompt_used,
                    "caption": caption,
                    "media_path": media_path,
                    "platforms": platforms,
                    "status": status,
                }).execute()
                if res.data:
                    return res.data[0]["id"]
            except Exception as exc:
                logger.error(f"خطأ أثناء تسجيل المنشور في Supabase: {exc}")

        return None

    @staticmethod
    def get_recent_learnings(limit: int = 3) -> str:
        """
        يقرأ إحصائيات آخر المنشورات وملاحظات الاحتفاظ لتغذية الـ System Prompt
        بما نجح وفشل في المنشورات السابقة.
        """
        client = _get_supabase_client()
        if client:
            try:
                res = (
                    client.table("content_analytics")
                    .select("platform, views, avg_percentage_viewed, retention_notes, recorded_at")
                    .order("recorded_at", desc=True)
                    .limit(limit)
                    .execute()
                )
                if res.data:
                    lines = ["📊 إحصائيات الأداء السابقة للتعلم والتحسين:"]
                    for row in res.data:
                        lines.append(
                            f"- منصة {row.get('platform')}: مشاهدات {row.get('views')}، "
                            f"نسبة الإكمال: {row.get('avg_percentage_viewed')}%. "
                            f"ملاحظة: {row.get('retention_notes') or 'لا توجد'}"
                        )
                    return "\n".join(lines)
            except Exception as exc:
                logger.warning(f"تعذر جلب تحليلات الأداء السابقة: {exc}")

        return "لا توجد تحليلات سابقة كافية بعد. ركز على هوك قوي في أول ثانيتين وسرعة إيقاع."
