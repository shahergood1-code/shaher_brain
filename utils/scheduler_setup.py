"""
utils/scheduler_setup.py
────────────────────────
إعداد وتثبيت المهمة اليومية التلقائية في Windows Task Scheduler.
يتيح تشغيل خط الإنتاج يومياً في ميعاد محدد دون الحاجة لتشغيل الـ Terminal يدوياً.
"""

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("SchedulerSetup")


def register_windows_daily_task(task_name: str = "ShaherContentEngine", run_time: str = "10:00") -> bool:
    """
    تسجيل مهمة يومية في Windows Task Scheduler.
    run_time بتنسيق HH:mm (مثلاً 10:00).
    """
    python_exe = sys.executable
    main_script = Path(__file__).resolve().parent.parent / "main.py"

    # أمر التشغيل الكامل
    action = f'"{python_exe}" "{main_script}" run'

    cmd = [
        "schtasks",
        "/Create",
        "/SC", "DAILY",
        "/TN", task_name,
        "/TR", action,
        "/ST", run_time,
        "/F",  # استبدال المهمة لو كانت موجودة مسبقاً
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(f"✅ تم تسجيل المهمة اليومية بنجاح: {res.stdout.strip()}")
        print(f"✅ تم تسجيل المهمة بنجاح في Windows Task Scheduler لتعمل يومياً الساعة {run_time}.")
        return True
    except subprocess.CalledProcessError as exc:
        err = exc.stderr.strip() if exc.stderr else str(exc)
        logger.error(f"❌ فشل تسجيل المهمة في Windows: {err}")
        print(f"❌ تعذر تسجيل المهمة: {err}\n(ملاحظة: قد يتطلب تشغيل الـ Terminal كمسؤول Run as Administrator).")
        return False


def remove_windows_daily_task(task_name: str = "ShaherContentEngine") -> bool:
    """حذف المهمة من جدول مهام ويندوز."""
    cmd = ["schtasks", "/Delete", "/TN", task_name, "/F"]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✅ تم حذف المهمة '{task_name}' بنجاح.")
        return True
    except Exception as exc:
        print(f"❌ تعذر حذف المهمة: {exc}")
        return False
