"""
core/orchestrator.py
────────────────────
العقل المدير المركزي (Master Orchestrator):
يدير خطة العمل عبر Ollama (qwen2.5:7b) باستخدام Function Calling،
ويربط كافة الأدوات (المتصفح، المونتاج بـ NVENC، الفويس أوفر، والترجمة)،
مع المزامنة الحية لخطوات التنفيذ في Supabase.
"""

import json
import logging
from typing import Dict, Any, List, Optional
import ollama

from config.settings import OLLAMA_MODEL, OLLAMA_HOST
from core.prompts import get_orchestrator_system_prompt
from core.state_manager import StateManager
from workers.browser.gemini_worker import ask_gemini_browser
from workers.browser.flow_worker import generate_flow_image, generate_flow_video
from workers.browser.social_worker import post_to_social_platform, scrape_24h_stats
from workers.browser.cdp_client import get_cdp_manager
from workers.media.tts_worker import generate_voiceover
from workers.media.subtitle_worker import generate_subtitles
from workers.media.video_renderer import render_shorts_video

logger = logging.getLogger("Orchestrator")

# ─── 1. تعريف الأدوات لـ Ollama ────────────────────────────────────
CONTENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "ask_gemini",
            "description": (
                "استشارة محادثات جيمناي المثبتة في المتصفح لتوليد أفكار المحتوى، "
                "السكريبت، وبرومبتات المشاهد. مع دعم Fallback تلقائي لو تعذر المتصفح."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pinned_chat": {
                        "type": "string",
                        "enum": ["youtube_channel", "shaher"],
                        "description": "قناة اليوتيوب (للشورتس) أو شاهر (للبوستات الإعلانية)",
                    },
                    "prompt": {"type": "string", "description": "نص الطلب أو السؤال"},
                },
                "required": ["pinned_chat", "prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_flow_image",
            "description": "توليد صورة احترافية ثابتة عبر Flow (Nano Banana 2) وحفظها محلياً.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "برومبت توليد الصورة بالإنجليزية"},
                    "save_as": {"type": "string", "description": "اسم الملف، مثلاً scene1.png"},
                },
                "required": ["prompt", "save_as"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_flow_video",
            "description": "تحريك صورة موجودة عبر Flow (Veo Lite) بناءً على برومبت حركة وتنزيل الفيديو.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_image": {"type": "string", "description": "اسم الصورة المصدر"},
                    "motion_prompt": {"type": "string", "description": "برومبت الحركة بالإنجليزية"},
                    "save_as": {"type": "string", "description": "اسم الملف الناتج، مثلاً scene1.mp4"},
                },
                "required": ["source_image", "motion_prompt", "save_as"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_voiceover",
            "description": "توليد الفويس أوفر الصوتي العربي الطبيعي من النص بجودة عالية.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "نص السكريبت العربي"},
                    "save_as": {"type": "string", "description": "اسم ملف الصوت، مثلاً voice.mp3"},
                },
                "required": ["text", "save_as"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "render_video",
            "description": (
                "مونتاج المشاهد والصوت وإضافة الترجمة العربية التلقائية وتصدير شورتس رأسي (9:16) "
                "مسرع بالكامل عبر كرت الشاشة RTX 4070 (NVENC)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "scene_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "قائمة أسماء المشاهد بالترتيب (صور أو فيديوهات)",
                    },
                    "voice_file": {"type": "string", "description": "اسم ملف الصوت"},
                    "output_name": {"type": "string", "description": "اسم الفيديو النهائي، مثلاً final_short.mp4"},
                    "with_subtitles": {"type": "boolean", "description": "توليد وحرق الترجمة تلقائياً (افتراضي true)"},
                },
                "required": ["scene_files", "voice_file", "output_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "post_to_social",
            "description": "رفع ونشر الفيديو أو الصورة على المنصة المختارة مع الكابشن.",
            "parameters": {
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "enum": ["youtube_shorts", "tiktok", "instagram", "facebook"],
                    },
                    "file_path": {"type": "string", "description": "المسار المحلي للملف"},
                    "caption": {"type": "string", "description": "النص والكابشن المصاحب"},
                    "title": {"type": "string", "description": "عنوان الفيديو للشورتس"},
                },
                "required": ["platform", "file_path", "caption"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_platform_stats",
            "description": "قراءة إحصائيات منشور سابق (مشاهدات، نسبة الإكمال) بعد 24 ساعة لتغذية التحسين الذاتي.",
            "parameters": {
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "enum": ["youtube_shorts", "tiktok", "instagram", "facebook"],
                    },
                    "post_id": {"type": "string", "description": "معرف المنشور في Supabase"},
                },
                "required": ["platform"],
            },
        },
    },
]


def _execute_tool(name: str, args: Dict[str, Any], task_id: str) -> Dict[str, Any]:
    """توجيه استدعاء الأداة للدالة التنفيذية المناسبة."""
    logger.info(f"⚙️ تنفيذ الأداة: {name} مع المعطيات: {args}")

    if name == "ask_gemini":
        return ask_gemini_browser(pinned_chat_key=args["pinned_chat"], prompt=args["prompt"])

    elif name == "generate_flow_image":
        return generate_flow_image(prompt=args["prompt"], save_as=args.get("save_as", "image.png"))

    elif name == "generate_flow_video":
        return generate_flow_video(
            source_image=args["source_image"],
            motion_prompt=args["motion_prompt"],
            save_as=args.get("save_as", "scene.mp4"),
        )

    elif name == "create_voiceover":
        return generate_voiceover(text=args["text"], save_as=args.get("save_as", "voice.mp3"))

    elif name == "render_video":
        voice_file = args["voice_file"]
        scene_files = args["scene_files"]
        output_name = args.get("output_name", "final_short.mp4")
        with_subtitles = args.get("with_subtitles", True)

        sub_file = None
        if with_subtitles:
            from config.settings import AUDIO_DIR
            audio_full_path = AUDIO_DIR / voice_file
            if audio_full_path.exists():
                logger.info("توليد ملف الترجمة التلقائية المتزامنة...")
                sub_res = generate_subtitles(str(audio_full_path))
                if sub_res.get("status") == "ok":
                    sub_file = sub_res["path"]

        res = render_shorts_video(
            scene_files=scene_files,
            audio_file=voice_file,
            output_name=output_name,
            subtitle_file=sub_file,
        )

        # تسجيل المنشور في Supabase
        if res.get("status") == "ok":
            StateManager.record_post(
                task_id=task_id,
                content_type="youtube_shorts",
                title=output_name,
                media_path=res.get("path"),
                status="rendered",
            )
        return res

    elif name == "post_to_social":
        return post_to_social_platform(
            platform=args["platform"],
            file_path=args["file_path"],
            caption=args["caption"],
            title=args.get("title"),
            task_id=task_id,
        )

    elif name == "read_platform_stats":
        return scrape_24h_stats(platform=args["platform"], post_id=args.get("post_id"))

    return {"status": "error", "error": f"أداة غير معروفة: {name}"}


def run_content_orchestrator(goal: str, max_steps: int = 25) -> Dict[str, Any]:
    """
    الدورة التنفيذية للـ Content Orchestrator:
    1. تسجيل المهمة في Supabase.
    2. تهيئة Ollama ببرومبت يحوي خبرات الأداء السابقة.
    3. تنفيذ حلقة Tool Calling وتوثيق كل خطوة في قاعدة البيانات.
    """
    logger.info("🚀 بدء تشغيل Content Orchestrator...")
    task_record = StateManager.create_task(user_goal=goal)
    task_id = task_record["id"]

    learnings = StateManager.get_recent_learnings()
    system_prompt = get_orchestrator_system_prompt(learnings)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": goal},
    ]

    client = ollama.Client(host=OLLAMA_HOST)
    final_summary = ""

    try:
        for step in range(1, max_steps + 1):
            logger.info(f"\n--- [الخطوة {step} من {max_steps}] ---")

            response = client.chat(
                model=OLLAMA_MODEL,
                messages=messages,
                tools=CONTENT_TOOLS,
            )

            msg = response["message"]
            messages.append(msg)

            tool_calls = msg.get("tool_calls")
            if not tool_calls:
                content = msg.get("content", "")
                logger.info(f"Ollama: {content}")
                if "تم" in content or "تم بنجاح" in content:
                    final_summary = content
                    break
                continue

            # معالجة استدعاءات الأدوات
            for call in tool_calls:
                fn_name = call["function"]["name"]
                fn_args = call["function"]["arguments"]
                if isinstance(fn_args, str):
                    try:
                        fn_args = json.loads(fn_args)
                    except Exception:
                        pass

                result = _execute_tool(fn_name, fn_args, task_id)
                StateManager.append_task_step(task_id, step, fn_name, fn_args, result)

                messages.append({
                    "role": "tool",
                    "content": json.dumps(result, ensure_ascii=False),
                    "name": fn_name,
                })

        else:
            final_summary = "تم الوصول للحد الأقصى من الخطوات."

        StateManager.complete_task(task_id, summary=final_summary, status="completed")
        logger.info("✅ اكتملت المهمة اليومية بنجاح.")
        return {"status": "completed", "task_id": task_id, "summary": final_summary}

    except Exception as exc:
        logger.error(f"❌ حدث خطأ غير متوقع في الـ Orchestrator: {exc}")
        StateManager.complete_task(task_id, summary="فشل التنفيذ", status="failed", error_details=str(exc))
        return {"status": "failed", "task_id": task_id, "error": str(exc)}

    finally:
        # إغلاق جلسات Playwright برفق دون إغلاق متصفح المستخدم
        get_cdp_manager().close_all()
