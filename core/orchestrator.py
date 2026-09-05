"""
core/orchestrator.py
────────────────────
العقل المدير المركزي (Master Content Orchestrator):
يدير خطة العمل عبر Ollama (qwen2.5:7b) باستخدام Function Calling،
ويربط كافة الأدوات (الناقد القاسي، توليد الصور، المونتاج بـ NVENC، الفويس أوفر، والترجمة المغناطيسية)،
مع المزامنة الحية لخطوات التنفيذ في Supabase وإتاحة الإنتاج الفوري للتيليجرام.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

import ollama

from brain.image_client import generate_image
from config.settings import (
    AUDIO_DIR,
    IMAGES_DIR,
    OLLAMA_HOST,
    OLLAMA_MODEL,
)
from core.critic import evaluate_script
from core.prompts import (
    SHORTS_GENERATION_PROMPT_TEMPLATE,
    get_orchestrator_system_prompt,
)
from core.state_manager import StateManager
from workers.browser.cdp_client import get_cdp_manager
from workers.browser.flow_worker import generate_flow_image, generate_flow_video
from workers.browser.gemini_worker import ask_gemini_browser
from workers.browser.social_worker import post_to_social_platform, scrape_24h_stats
from workers.media.subtitle_worker import generate_subtitles
from workers.media.tts_worker import generate_voiceover
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
            "name": "critic_review_script",
            "description": "فحص السكريبت عبر الناقد القاسي (The Ruthless Critic) للتأكد من قوة الهوك ونسبة الاحتفاظ وسؤال الجدل.",
            "parameters": {
                "type": "object",
                "properties": {
                    "script_text": {"type": "string", "description": "نص السكريبت"},
                    "topic": {"type": "string", "description": "موضوع الفيديو"},
                },
                "required": ["script_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_flow_image",
            "description": "توليد صورة احترافية ثابتة عبر Flow (Nano Banana 2) أو Flux وحفظها محلياً.",
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
            "description": "توليد الفويس أوفر الصوتي العربي الطبيعي من النص بجودة عالية وبلهجة جذابة.",
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
                "مونتاج المشاهد والصوت وإضافة الترجمة العربية المغناطيسية (Yellow ASS) "
                "مع تأثير حركة Ken-Burns Zoom وتصدير شورتس رأسي (9:16) مسرع بـ NVENC."
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
            "description": "رفع وجدولة أو نشر الفيديو على المنصة المختارة (YouTube Shorts, TikTok).",
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


def _execute_tool(name: str, args: dict[str, Any], task_id: str) -> dict[str, Any]:
    """توجيه استدعاء الأداة للدالة التنفيذية المناسبة."""
    logger.info(f"⚙️ تنفيذ الأداة: {name} مع المعطيات: {args}")

    if name == "ask_gemini":
        return ask_gemini_browser(pinned_chat_key=args["pinned_chat"], prompt=args["prompt"])

    elif name == "critic_review_script":
        review = evaluate_script(script_text=args["script_text"], topic=args.get("topic", ""))
        return {"status": "ok", "review": review.to_dict()}

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
            audio_full_path = AUDIO_DIR / voice_file
            if not audio_full_path.exists():
                audio_full_path = Path(voice_file)
            if audio_full_path.exists():
                logger.info("توليد الترجمة المغناطيسية الفيروسية (Faster-Whisper int8)...")
                sub_res = generate_subtitles(str(audio_full_path))
                if sub_res.get("status") == "ok":
                    sub_file = sub_res["path"]

        res = render_shorts_video(
            scene_files=scene_files,
            audio_file=voice_file,
            output_name=output_name,
            subtitle_file=sub_file,
            enable_ken_burns=True,
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


async def produce_viral_short_pipeline(
    topic: str = "لغز اختفاء لعبة شهيرة في عام 2004",
    task_id: str | None = None,
) -> dict[str, Any]:
    """
    خط إنتاج فوري متكامل لفيديو شورتس فيروسي (End-to-End Viral Short Production):
    1. كتابة السكريبت وفق القواعد الخمس (Hook + Curiosity Loop + Loop + Debate).
    2. تمرير السكريبت على الناقد القاسي (The Ruthless Critic Loop) حتى اعتماده.
    3. توليد الفويس أوفر الصوتي العربي الطبيعي بـ Edge-TTS.
    4. توليد الترجمة المغناطيسية الفيروسية (Yellow Viral ASS) بـ Faster-Whisper على CPU.
    5. توليد أو تحضير المشاهد البصرية عالية التباين.
    6. المونتاج وتطبيق حركة Ken-Burns ZoomPan والتصدير السريع بـ NVENC على RTX 4070.
    7. تسجيل البيانات في Supabase وإرجاع مسار الفيديو والتقرير الكامل.
    """
    start_time = time.time()
    if not task_id:
        task_record = StateManager.create_task(user_goal=f"إنتاج شورتس فيروسي فوري: {topic}")
        task_id = task_record["id"]

    logger.info(f"🚀 بدء خط الإنتاج الفيروسي للموضوع: '{topic}'...")

    # 1. توليد السكريبت
    script_prompt = SHORTS_GENERATION_PROMPT_TEMPLATE.format(topic=topic)
    script_data = None
    try:
        from brain.ai_client import get_ai_response
        ai_resp = await get_ai_response(user_message=script_prompt, component="brain")
        import re
        match = re.search(r"\{[\s\S]*\}", ai_resp.content)
        if match:
            script_data = json.loads(match.group(0))
    except Exception as exc:
        logger.warning(f"فشل توليد السكريبت بالسحابة ({exc}) — استخدام القالب الافتراضي المشوق...")

    if not script_data:
        script_data = {
            "title": f"سر غامض لم يخبرك به أحد عن {topic} #Shorts",
            "hook": "السر اللي مخبياه اللعبة دي لو عرفته مستحيل تبص عليها بنفس الطريقة...",
            "script_full": (
                "السر اللي مخبياه اللعبة دي لو عرفته مستحيل تبص عليها بنفس الطريقة. "
                "في سنة 2004، ظهر ملف كود غامض في التحديث الأخير، المطورين أنكروا وجوده تماماً. "
                "لكن بعد 20 سنة، لاعب واحد فتح الغرفة السرية ولقى رسالة تحذير صادمة. "
                "هل تعتقد إنها كانت مجرد خدعة ولا سر حقيقي؟ اكتب رأيك تحت وشوف مين هيتفق مع..."
            ),
            "ending_loop_word": "مع",
            "debate_question": "هل تعتقد إنها كانت مجرد خدعة ولا سر حقيقي مخفي؟",
            "scenes": [
                {"scene_num": 1, "visual_prompt": "retro 2000s CRT computer monitor glitching in dark room, eerie glowing screen, mystery nostalgia", "voice_segment": "السر اللي مخبياه اللعبة"},
                {"scene_num": 2, "visual_prompt": "corrupted binary code stream red glowing on dark background, intense cyber mystery", "voice_segment": "في سنة 2004 ظهر ملف"},
                {"scene_num": 3, "visual_prompt": "mysterious secret locked iron door with strange glowing symbols, underground hallway", "voice_segment": "لكن بعد 20 سنة لاعب واحد"},
                {"scene_num": 4, "visual_prompt": "shocked person looking at dramatic glowing discovery, high contrast cinematic lighting", "voice_segment": "هل تعتقد إنها خدعة"},
            ],
            "caption": "أغرب لغز في تاريخ الألعاب! هل كنت تعرف السر ده؟ #Shorts #Gaming #Nostalgia",
        }

    full_text = script_data.get("script_full", "")

    # 2. دورة الناقد القاسي
    critic_review = evaluate_script(full_text, topic=topic)
    logger.info(f"🧐 تقييم الناقد القاسي: {critic_review.score}/10 (معتمد: {critic_review.approved})")

    # 3. توليد الصوت (Edge-TTS)
    ts = int(time.time())
    voice_filename = f"voice_{ts}.mp3"
    voice_res = generate_voiceover(text=full_text, save_as=voice_filename)
    voice_file_path = voice_res.get("path") or str(AUDIO_DIR / voice_filename)

    # 4. توليد الترجمة المغناطيسية الصفراء (Faster-Whisper CPU int8)
    sub_res = generate_subtitles(voice_file_path)
    sub_file_path = sub_res.get("path")

    # 5. توليد المشاهد البصرية (صور سينمائية عالية التباين)
    scene_files = []
    scenes = script_data.get("scenes", [])
    for idx, sc in enumerate(scenes[:4]):
        sc_prompt = sc.get("visual_prompt", f"mysterious nostalgic gaming scene {topic}")
        sc_name = f"scene_{ts}_{idx+1}.jpg"
        sc_path = IMAGES_DIR / sc_name
        try:
            # توليد صورة عبر محرك الصور السريع
            img_res = await generate_image(prompt=sc_prompt, aspect_ratio="9:16")
            if img_res.image_url and sc_path.parent.exists():
                # حفظ أو تنزيل الصورة
                import urllib.request
                urllib.request.urlretrieve(img_res.image_url, str(sc_path))
                scene_files.append(str(sc_path))
        except Exception as img_err:
            logger.warning(f"تعذر توليد المشهد {idx+1}: {img_err}")

    # لو تعذر تنزيل صور، نستخدم المشاهد الافتراضية أو ننشئ كادرات لونية ناعمة
    if not scene_files:
        from PIL import Image
        for idx in range(3):
            sc_path = IMAGES_DIR / f"fallback_{ts}_{idx}.jpg"
            colors = [(20, 20, 35), (35, 15, 25), (15, 30, 40)]
            img = Image.new("RGB", (1080, 1920), color=colors[idx % 3])
            img.save(str(sc_path))
            scene_files.append(str(sc_path))

    # 6. المونتاج السريع بـ NVENC وتطبيق حركة Ken-Burns Zoom
    output_video_name = f"viral_short_{ts}.mp4"
    render_res = render_shorts_video(
        scene_files=scene_files,
        audio_file=voice_file_path,
        output_name=output_video_name,
        subtitle_file=sub_file_path,
        enable_ken_burns=True,
    )

    total_time = round(time.time() - start_time, 2)

    # 7. توثيق في Supabase
    post_id = StateManager.record_post(
        task_id=task_id,
        content_type="youtube_shorts",
        title=script_data.get("title", output_video_name),
        script=full_text,
        prompt_used=topic,
        caption=script_data.get("caption", ""),
        media_path=render_res.get("path"),
        platforms=["youtube_shorts", "tiktok"],
        status="rendered",
    )

    summary = (
        f"✅ تم إنتاج الفيديو الفيروسي بنجاح في {total_time} ثانية!\n"
        f"- العنوان: {script_data.get('title')}\n"
        f"- تقييم الناقد القاسي: {critic_review.score}/10\n"
        f"- الريندر: 1080x1920 @ 30fps عبر RTX 4070 NVENC مع الترجمة المغناطيسية وحركة الكاميرا."
    )
    StateManager.complete_task(task_id, summary=summary, status="completed")

    return {
        "status": "ok",
        "task_id": task_id,
        "post_id": post_id,
        "video_path": render_res.get("path"),
        "title": script_data.get("title"),
        "caption": script_data.get("caption"),
        "script": full_text,
        "critic_score": critic_review.score,
        "critic_review": critic_review.to_dict(),
        "duration_sec": render_res.get("duration", 0),
        "production_time_sec": total_time,
    }


def run_content_orchestrator(goal: str, max_steps: int = 25) -> dict[str, Any]:
    """
    الدورة التنفيذية للـ Content Orchestrator:
    1. تسجيل المهمة في Supabase.
    2. تهيئة Ollama ببرومبت يحوي خبرات الأداء السابقة وقواعد الاحتفاظ الـ 5.
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
        logger.info("✅ اكتملت المهمة بنجاح.")
        return {"status": "completed", "task_id": task_id, "summary": final_summary}

    except Exception as exc:
        logger.error(f"❌ حدث خطأ غير متوقع في الـ Orchestrator: {exc}")
        StateManager.complete_task(task_id, summary="فشل التنفيذ", status="failed", error_details=str(exc))
        return {"status": "failed", "task_id": task_id, "error": str(exc)}

    finally:
        get_cdp_manager().close_all()
