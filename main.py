"""
main.py
───────
نقطة الدخول والتحكم الرئيسية (CLI) لمنظومة إنتاج المحتوى المستقلة — شاهر الثاني.
"""

import argparse
import logging
import sys
from pathlib import Path

# ضبط ترميز الإخراج لـ UTF-8 على ويندوز لدعم العربية والإيموجي
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# إعداد الـ Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("MainCLI")


def main():
    parser = argparse.ArgumentParser(description="🚀 شاهر الثاني — Autonomous Content Creation Engine")
    subparsers = parser.add_subparsers(dest="command", help="الأمر المراد تنفيذه")

    # 1. أمر التشغيل الكامل
    run_parser = subparsers.add_parser("run", help="تشغيل خطة الإنتاج والنشر اليومية كاملة")
    run_parser.add_argument("--goal", type=str, default=None, help="هدف مخصص بدلاً من الروتين اليومي الافتراضي")

    # 2. فحص حالة النظام
    subparsers.add_parser("status", help="فحص حالة العتاد والمتصفح وOllama وSupabase")

    # 3. اختبار الصوت
    tts_parser = subparsers.add_parser("test-tts", help="اختبار توليد الفويس أوفر الصوتي")
    tts_parser.add_argument("--text", type=str, default="أهلاً بك! هذا اختبار تجريبي لمحرك الفويس أوفر العربي لشاهر الثاني.")
    tts_parser.add_argument("--save-as", type=str, default="test_voice.mp3")

    # 4. اختبار الترجمة التلقائية
    sub_parser = subparsers.add_parser("test-subtitles", help="اختبار تفريغ الصوت وتوليد ملف الترجمة ASS")
    sub_parser.add_argument("--audio", type=str, required=True, help="مسار ملف الصوت")

    # 5. اختبار المونتاج بـ NVENC
    render_parser = subparsers.add_parser("test-render", help="اختبار دمج فيديو مع تسريع NVENC وحرق الترجمة")
    render_parser.add_argument("--audio", type=str, required=True, help="اسم ملف الصوت في مجلد audio")
    render_parser.add_argument("--scenes", nargs="+", required=True, help="قائمة أسماء المشاهد في مجلد raw_scenes أو images")
    render_parser.add_argument("--output", type=str, default="test_reel.mp4", help="اسم الفيديو الناتج")

    # 6. اختبار جيمناي
    gemini_parser = subparsers.add_parser("test-gemini", help="اختبار أتمتة جيمناي واستخراج الأفكار")
    gemini_parser.add_argument("--chat", type=str, default="youtube_channel", choices=["youtube_channel", "shaher"])
    gemini_parser.add_argument("--prompt", type=str, default="اقترح فكرة واحدة لشورتس تقني مثير مدته 30 ثانية مع الهوك والسكريبت.")

    # 7. جدولة المهمة اليومية
    sched_parser = subparsers.add_parser("schedule", help="تسجيل المهمة اليومية في Windows Task Scheduler")
    sched_parser.add_argument("--time", type=str, default="10:00", help="وقت التشغيل اليومي بتنسيق HH:mm (افتراضي 10:00)")
    sched_parser.add_argument("--remove", action="store_true", help="حذف المهمة من مجدول ويندوز")

    args = parser.parse_args()

    if not args.command or args.command == "run":
        from core.prompts import DAILY_ROUTINE_PROMPT
        from core.orchestrator import run_content_orchestrator

        goal = args.goal if (hasattr(args, "goal") and args.goal) else DAILY_ROUTINE_PROMPT
        print("\n" + "=" * 60)
        print("🌟 تشغيل خطة إنتاج المحتوى اليومي...")
        print("=" * 60)
        res = run_content_orchestrator(goal)
        print(f"\nالنتيجة النهائية: {res.get('status')}")
        if res.get("summary"):
            print(f"الملخص:\n{res['summary']}")

    elif args.command == "status":
        from utils.gpu_guard import get_gpu_memory_status
        from workers.browser.cdp_client import is_cdp_port_open
        from config.settings import OLLAMA_MODEL, FFMPEG_EXE

        print("\n🔍 فحص حالة النظام:")
        print("-" * 40)
        gpu = get_gpu_memory_status()
        print(f"🎮 كرت الشاشة RTX 4070:")
        print(f"   - الذاكرة الحرة: {gpu['free_mb']:.0f} MB / {gpu['total_mb']:.0f} MB")
        print(f"   - درجة الحرارة: {gpu['temperature_c']}°C")

        cdp_ok = is_cdp_port_open()
        print(f"🌐 Chrome Remote Debugging (Port 9222): {'✅ متصل وشغال' if cdp_ok else '❌ غير متصل (افتح Chrome مع --remote-debugging-port=9222)'}")

        print(f"🧠 موديل Ollama: {OLLAMA_MODEL}")
        print(f"🎬 مسار FFmpeg المعتمد: {FFMPEG_EXE}")

        try:
            from memory.supabase_client import get_supabase
            client = get_supabase()
            client.table("projects").select("count", count="exact").execute()
            print("💾 اتصال Supabase: ✅ متصل ومفعل بنجاح")
        except Exception as exc:
            print(f"💾 اتصال Supabase: ⚠️ غير متصل ({exc}) — سيعمل النظام محلياً.")

    elif args.command == "test-tts":
        from workers.media.tts_worker import generate_voiceover
        print(f"🎙️ توليد فويس أوفر: '{args.text}'...")
        res = generate_voiceover(text=args.text, save_as=args.save_as)
        print(f"النتيجة: {res}")

    elif args.command == "test-subtitles":
        from workers.media.subtitle_worker import generate_subtitles
        print(f"📝 تفريغ وتوليد ملف الترجمة للملف: {args.audio}...")
        res = generate_subtitles(audio_path=args.audio)
        print(f"النتيجة: {res}")

    elif args.command == "test-render":
        from workers.media.video_renderer import render_shorts_video
        print(f"🎬 بدء الرندر بـ NVENC للمشاهد: {args.scenes} مع الصوت: {args.audio}...")
        res = render_shorts_video(scene_files=args.scenes, audio_file=args.audio, output_name=args.output)
        print(f"النتيجة: {res}")

    elif args.command == "test-gemini":
        from workers.browser.gemini_worker import ask_gemini_browser
        print(f"🤖 استشارة جيمناي ({args.chat}): '{args.prompt}'...")
        res = ask_gemini_browser(pinned_chat_key=args.chat, prompt=args.prompt)
        print(f"\nالرد:\n{res.get('response')}\nالمصدر: {res.get('source')}")

    elif args.command == "schedule":
        from utils.scheduler_setup import register_windows_daily_task, remove_windows_daily_task
        if args.remove:
            remove_windows_daily_task()
        else:
            register_windows_daily_task(run_time=args.time)


if __name__ == "__main__":
    main()
