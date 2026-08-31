"""
memory/supabase_client.py
─────────────────────────
Singleton client للتعامل مع Supabase.
بيتستخدم من كل مكونات النظام.
"""

import os
from functools import lru_cache
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """
    بيرجع Supabase client واحد (singleton) للنظام كله.
    بيستخدم service role key عشان يقدر يكتب ويقرأ بدون RLS.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        raise EnvironmentError(
            "❌ SUPABASE_URL و SUPABASE_SERVICE_ROLE_KEY (أو SUPABASE_ANON_KEY) "
            "لازم يكونوا موجودين في ملف .env"
        )

    return create_client(url, key)
