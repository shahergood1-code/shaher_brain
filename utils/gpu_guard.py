"""
utils/gpu_guard.py
──────────────────
مراقبة استهلاك كرت الشاشة (NVIDIA GeForce RTX 4070 Laptop - 8GB VRAM).
يفحص الذاكرة المتاحة قبل العمليات الثقيلة لتفادي أخطاء Out-Of-Memory.
"""

import logging
import subprocess
from typing import Dict, Any

logger = logging.getLogger("GPUGuard")


def get_gpu_memory_status() -> Dict[str, Any]:
    """استعلام عن استهلاك VRAM عبر nvidia-smi."""
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=memory.total,memory.used,memory.free,temperature.gpu",
            "--format=csv,nounits,noheader",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        total, used, free, temp = [float(x.strip()) for x in res.stdout.strip().split(",")]

        return {
            "status": "ok",
            "total_mb": total,
            "used_mb": used,
            "free_mb": free,
            "temperature_c": temp,
            "is_safe_for_render": free >= 1000,  # يحتاج 1GB على الأقل لتسريع NVENC بأمان
        }
    except Exception as exc:
        logger.warning(f"تعذر قراءة بيانات كرت الشاشة: {exc}")
        return {
            "status": "unknown",
            "free_mb": 2500,  # قيمة افتراضية آمنة
            "is_safe_for_render": True,
        }
