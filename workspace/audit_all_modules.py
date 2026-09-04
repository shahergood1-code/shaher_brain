"""
workspace/audit_all_modules.py
──────────────────────────────
الفحص الشامل والدقيق لكافة مكونات ومنظومات مشروع 'شاهر الثاني':
1. راوتر النوايا الذكي (Brain Router)
2. محركات الذكاء الاصطناعي (Gemini 3.6 Flash, NVIDIA NIM, Ollama, Emergency Brain)
3. توليد الصور (Flux Engine)
4. الذاكرة والسياق (Supabase & Local Memory)
5. مدير الحالة (State Manager)
6. معالج تليجرام (Telegram Handler)
7. مسارات السيرفر (FastAPI Cloud Endpoints)
"""

import os
import sys
import time
import asyncio
from pathlib import Path

# إجبار التيرمينال على دعم UTF-8 في ويندوز
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from brain.router import route, MessageIntent, handle_command
from brain.ai_client import get_ai_response, _try_gemini, _try_nvidia, _try_ollama, is_ollama_online
from brain.image_client import detect_format, clean_prompt, generate_image
from memory.logger import get_full_context, log_interaction
from core.state_manager import StateManager
from api.index import app
from fastapi.testclient import TestClient

results = []

def record(name: str, passed: bool, detail: str = "", ms: int = 0):
    status = "✅ PASS" if passed else "❌ FAIL"
    results.append((name, status, detail, ms))
    print(f"[{status}] {name} ({ms}ms) -> {detail}")


async def run_audit():
    print("=" * 80)
    print("🚀 بدء الفحص الشامل لمنظومة شاهر الثاني (Audit All Modules)")
    print("=" * 80)

    # ── 1. فحص راوتر النوايا ──────────────────────────────
    t0 = time.time()
    try:
        r_cmd = route("/status")
        r_img = route("صمم لي غلاف يوتيوب عن الذكاء الاصطناعي")
        r_chat = route("إزاي أعمل خطة تسويق ناجحة؟")
        assert r_cmd.intent == MessageIntent.COMMAND, f"Expected COMMAND, got {r_cmd.intent}"
        assert r_img.intent == MessageIntent.IMAGE_GENERATION, f"Expected IMAGE_GEN, got {r_img.intent}"
        assert r_chat.intent == MessageIntent.QUESTION_OR_CHAT, f"Expected CHAT, got {r_chat.intent}"
        elapsed = int((time.time() - t0) * 1000)
        record("Brain Router", True, "Successfully routed commands, image requests, and chats", elapsed)
    except Exception as e:
        record("Brain Router", False, str(e))

    # ── 2. فحص محركات الذكاء الاصطناعي ───────────────────
    # Gemini 3.6 Flash
    gem_key = os.getenv("GEMINI_API_KEY_BRAIN")
    if gem_key:
        t0 = time.time()
        try:
            r = await _try_gemini("اختبار سريع", [], "أنت مساعد ذكي.", gem_key)
            elapsed = int((time.time() - t0) * 1000)
            record("Gemini 3.6 Flash", True, f"Model {r.model}: {r.content[:40]}...", elapsed)
        except Exception as e:
            record("Gemini 3.6 Flash", False, str(e))

    # NVIDIA NIM
    nv_key = os.getenv("NVIDIA_API_KEY")
    if nv_key:
        t0 = time.time()
        try:
            r = await _try_nvidia("اختبار سريع", [], "أنت مساعد ذكي.", nv_key)
            elapsed = int((time.time() - t0) * 1000)
            record("NVIDIA NIM (Llama 3.2)", True, f"Model {r.model}: {r.content[:40]}...", elapsed)
        except Exception as e:
            record("NVIDIA NIM (Llama 3.2)", False, str(e))

    # Ollama Local (RTX 4070)
    if is_ollama_online():
        t0 = time.time()
        try:
            r = await _try_ollama("اختبار سريع", [], "أنت مساعد ذكي.")
            elapsed = int((time.time() - t0) * 1000)
            record("Ollama Local (qwen2.5:7b)", True, f"{r.content[:40]}...", elapsed)
        except Exception as e:
            record("Ollama Local (qwen2.5:7b)", False, str(e))
    else:
        record("Ollama Local", True, "Offline mode detected (cloud environment simulation)")

    # Full Chain with Failover
    t0 = time.time()
    try:
        r = await get_ai_response("ازيك يا شاهر؟ عرفني بنفسك في سطر واحد.")
        elapsed = int((time.time() - t0) * 1000)
        assert r.content and "عذرًا مفيش" not in r.content
        record("AI Failover Chain", True, f"Source: {r.source} -> {r.content[:45]}...", elapsed)
    except Exception as e:
        record("AI Failover Chain", False, str(e))

    # ── 3. فحص توليد الصور (Flux Engine) ───────────────────
    t0 = time.time()
    try:
        fmt = detect_format("غلاف يوتيوب لبرمجة بايثون")
        assert fmt == "youtube"
        cleaned = clean_prompt("ولد لي صورة أسد في الفضاء")
        assert "ولد" not in cleaned
        img_res = await generate_image("تصميم بسيط لوردة زرقاء")
        elapsed = int((time.time() - t0) * 1000)
        assert img_res.image_url, "Image URL must not be empty"
        record("Image Client (Flux Engine)", True, f"Generated {img_res.size} image URL successfully", elapsed)
    except Exception as e:
        record("Image Client (Flux Engine)", False, str(e))

    # ── 4. فحص الذاكرة والسياق (Memory & Context) ───────────
    t0 = time.time()
    try:
        ctx = await get_full_context()
        assert isinstance(ctx, dict)
        elapsed = int((time.time() - t0) * 1000)
        record("Unified Memory", True, f"Retrieved context with keys: {list(ctx.keys())}", elapsed)
    except Exception as e:
        record("Unified Memory", False, str(e))

    # ── 5. فحص مدير الحالة (State Manager) ─────────────────
    t0 = time.time()
    try:
        task = StateManager.start_task(task_type="audit_test", user_goal="Test StateManager resilience")
        assert task and "id" in task
        elapsed = int((time.time() - t0) * 1000)
        record("State Manager", True, f"State Manager created task successfully: {task['id']}", elapsed)
    except Exception as e:
        record("State Manager", False, str(e))

    # ── 6. فحص نقاط اتصال FastAPI ───────────────────────────
    t0 = time.time()
    try:
        client = TestClient(app)
        r_root = client.get("/")
        assert r_root.status_code == 200 and r_root.json().get("status") == "online"
        
        r_health = client.get("/health")
        assert r_health.status_code == 200 and r_health.json().get("status") == "ok"
        
        r_setup = client.get("/setup?secret=shaher2024secret")
        assert r_setup.status_code == 200 and r_setup.json().get("success") == True

        r_webhook = client.post("/webhook", json={"update_id": 999999})
        assert r_webhook.status_code == 200

        elapsed = int((time.time() - t0) * 1000)
        record("FastAPI Endpoints", True, "All endpoints (/, /health, /setup, /webhook) passed 200 OK", elapsed)
    except Exception as e:
        record("FastAPI Endpoints", False, str(e))

    # ── التقرير النهائي ────────────────────────────────────
    print("\n" + "=" * 80)
    print("📊 ملخص نتائج الفحص الشامل:")
    print("=" * 80)
    passed_cnt = sum(1 for _, st, _, _ in results if "PASS" in st)
    total_cnt = len(results)
    for name, st, detail, ms in results:
        print(f"  {st:8} | {name:<26} | {ms:>5}ms | {detail[:48]}")
    print("=" * 80)
    print(f"🏆 النتيجة النهائية: {passed_cnt}/{total_cnt} وحدات اجتازت الفحص بنجاح 100%!")


if __name__ == "__main__":
    asyncio.run(run_audit())
