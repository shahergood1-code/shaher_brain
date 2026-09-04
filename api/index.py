"""
api/index.py
────────────
نقطة الدخول لـ Vercel Serverless Function.
تعمل كـ ASGI handler فوري بدون استهلاك للذاكرة وبدون نوم (Zero Cold Delay).
"""

import sys
from pathlib import Path

# إضافة المجلد الرئيسي للمشروع لتمكين كل الاستيرادات
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from bot.main import app
