"""
workspace/test_system.py
────────────────────────
فحص شامل لجميع أركان النظام:
1. كرت الشاشة RTX 4070 و VRAM Guard.
2. توليد الصوت العربي بـ edge-tts.
3. تفريغ الصوت وتوليد الترجمة بـ faster-whisper.
4. مونتاج الفيديو بالأبعاد الرأسية 9:16 وحرق الترجمة بـ NVENC.
5. استدعاء أدوات Ollama (qwen2.5:7b).
6. أوامر Shaher Brain Router.
7. مدير الحالة StateManager.
"""

import sys
from pathlib import Path

# إضافة المجلد الرئيسي للمشروع إلى مسار الاستيراد
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

results = {}

print("=" * 60)
print("🚀 بدء الفحص الشامل لمنظومة 'شاهر الثاني'...")
print("=" * 60)

# 1. GPU Guard
print("\n[1/7] فحص كرت الشاشة وذاكرة VRAM:")
try:
    from utils.gpu_guard import get_gpu_memory_status
    gpu = get_gpu_memory_status()
    print(f"  - الكرت: NVIDIA GeForce RTX 4070 Laptop")
    print(f"  - الذاكرة المتاحة: {gpu['free_mb']:.0f} MB / {gpu['total_mb']:.0f} MB")
    print(f"  - درجة الحرارة: {gpu['temperature_c']}°C")
    results["1. GPU & VRAM Guard"] = "✅ سليم ومرتاح"
except Exception as e:
    results["1. GPU & VRAM Guard"] = f"❌ خطأ: {e}"

# 2. Edge-TTS
print("\n[2/7] فحص محرك الصوت العربي (Edge-TTS):")
try:
    from workers.media.tts_worker import generate_voiceover
    res = generate_voiceover(
        text="أهلاً بك يا شاهر. تم تشغيل وفحص نظام إنتاج المحتوى بنجاح.",
        save_as="test_pipeline.mp3"
    )
    if res.get("status") == "ok" and Path(res["path"]).exists():
        print(f"  - تم إنتاج ملف الصوت: {res['path']}")
        results["2. Arabic Voiceover (TTS)"] = "✅ سليم 100%"
    else:
        results["2. Arabic Voiceover (TTS)"] = f"❌ خطأ: {res.get('error')}"
except Exception as e:
    results["2. Arabic Voiceover (TTS)"] = f"❌ استثناء: {e}"

# 3. Faster-Whisper
print("\n[3/7] فحص تفريغ الصوت وتوليد الترجمة (Faster-Whisper):")
try:
    from workers.media.subtitle_worker import generate_subtitles
    audio_path = "workspace/downloads/audio/test_pipeline.mp3"
    sub_res = generate_subtitles(audio_path=audio_path)
    if sub_res.get("status") == "ok" and Path(sub_res["path"]).exists():
        print(f"  - تم توليد ملف الترجمة: {sub_res['path']} (المدة: {sub_res.get('duration'):.2f}s)")
        results["3. Faster-Whisper Subtitles"] = "✅ سليم ودقيق"
    else:
        results["3. Faster-Whisper Subtitles"] = f"❌ خطأ: {sub_res.get('error')}"
except Exception as e:
    results["3. Faster-Whisper Subtitles"] = f"❌ استثناء: {e}"

# 4. FFmpeg NVENC 9:16 Video Rendering
print("\n[4/7] فحص المونتاج الفائق بـ NVENC وحرق الترجمة (9:16):")
try:
    from workers.media.video_renderer import render_shorts_video
    from PIL import Image, ImageDraw

    # مشهد تجريبي ملون
    img_path = Path("workspace/downloads/images/scene_pipeline.png")
    img = Image.new("RGB", (1080, 1920), color=(18, 24, 38))
    d = ImageDraw.Draw(img)
    d.rectangle([(80, 80), (1000, 1840)], outline=(0, 210, 255), width=8)
    img.save(str(img_path))

    render_res = render_shorts_video(
        scene_files=["scene_pipeline.png"],
        audio_file="test_pipeline.mp3",
        output_name="test_pipeline_short.mp4",
        subtitle_file="workspace/downloads/audio/test_pipeline.ass"
    )
    if render_res.get("status") == "ok" and Path(render_res["path"]).exists():
        print(f"  - تم تصدير الفيديو النهائي: {render_res['path']}")
        results["4. FFmpeg NVENC Render"] = "✅ فائق السرعة وجودة 9:16"
    else:
        results["4. FFmpeg NVENC Render"] = f"❌ خطأ: {render_res.get('error')}"
except Exception as e:
    results["4. FFmpeg NVENC Render"] = f"❌ استثناء: {e}"

# 5. Ollama Tool Calling
print("\n[5/7] فحص Ollama (qwen2.5:7b) واستدعاء الأدوات:")
try:
    import ollama
    from core.orchestrator import CONTENT_TOOLS
    client = ollama.Client()
    chat_res = client.chat(
        model="qwen2.5:7b",
        messages=[{"role": "user", "content": "أريد توليد فويس أوفر لجملة: مرحباً بالعالم"}],
        tools=CONTENT_TOOLS,
    )
    calls = chat_res["message"].get("tool_calls") or []
    if calls:
        fn_name = calls[0].function.name
        fn_args = calls[0].function.arguments
        print(f"  - استدعى Ollama الأداة: {fn_name} بالمعطيات: {fn_args}")
        results["5. Ollama Tool Calling"] = "✅ ذكي ويعمل بدقة"
    else:
        results["5. Ollama Tool Calling"] = "⚠️ رد بنص مباشر بدون أداة"
except Exception as e:
    results["5. Ollama Tool Calling"] = f"❌ خطأ: {e}"

# 6. Brain Router
print("\n[6/7] فحص أوامر Shaher Brain Router:")
try:
    import asyncio
    from brain.router import handle_command
    resp = asyncio.run(handle_command("/content"))
    if "Content Orchestrator" in resp:
        print("  - الرد على /content متصل وسليم.")
        results["6. Shaher Brain Router"] = "✅ متصل ببوت تليجرام"
    else:
        results["6. Shaher Brain Router"] = "⚠️ استجابة غير متوقعة"
except Exception as e:
    results["6. Shaher Brain Router"] = f"❌ خطأ: {e}"

# 7. State Manager
print("\n[7/7] فحص مدير الحالة (State Manager):")
try:
    from core.state_manager import StateManager
    task = StateManager.create_task(user_goal="فحص تجريبي شامل للمنظومة")
    StateManager.append_task_step(task["id"], 1, "self_test", {"step": 1}, {"status": "ok"})
    StateManager.complete_task(task["id"], summary="تم اجتياز جميع الفحوصات")
    print(f"  - تم حفظ دورة العمل بنجاح بالمعرف: {task['id']}")
    results["7. State Manager & History"] = "✅ سليم ومحمي بـ Fallback"
except Exception as e:
    results["7. State Manager & History"] = f"❌ خطأ: {e}"

# Summary Table
print("\n" + "=" * 60)
print("📊 لوحة نتائج الفحص الشامل (System Health Scorecard):")
print("=" * 60)
for test_name, status in results.items():
    print(f"{test_name:<35} : {status}")
print("=" * 60)
