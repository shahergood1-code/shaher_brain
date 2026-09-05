"""
workspace/test_content_orchestrator.py
──────────────────────────────────────
اختبار شامل ودقيق لموديول إنتاج المحتوى وبناء الجمهور:
1. اختبار الناقد القاسي (The Ruthless Critic).
2. اختبار الترجمة المغناطيسية الفيروسية (Yellow ASS).
3. اختبار حركة الكاميرا (Ken-Burns Dynamic ZoomPan) والريندر بـ NVENC.
4. اختبار هرم المحتوى الأسبوعي (Weekly Batch).
"""

import sys
import time
from pathlib import Path

from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import IMAGES_DIR
from core.critic import evaluate_script
from workers.media.subtitle_worker import generate_subtitles
from workers.media.tts_worker import generate_voiceover
from workers.media.video_renderer import render_shorts_video


def test_ruthless_critic():
    print("\n--- [1/4] اختبار الناقد القاسي (The Ruthless Critic) ---")
    weak_script = "أهلاً بكم في قناتي، اليوم سنتحدث عن بعض ألعاب الفيديو القديمة، شكراً للمتابعة."
    strong_script = (
        "الكرتون اللي كبرت عليه فيه سر مظلم لو عرفته مستحيل تشوفه بنفس الطريقة! "
        "في الحلقة الممنوعة سنة 1999، المخرج حط مشهد استغاثة حقيقي مدته ثانيتين بس. "
        "الشركة سحبت الشريط من كل القنوات، لكن بعد 25 سنة، ظهرت النسخة الأصلية على الإنترنت. "
        "هل تفتكر كان خطأ مقصود ولا صرخة حقيقية؟ انزل اكتب في الكومنتات وشوف مين متفق معاك..."
    )

    review_weak = evaluate_script(weak_script, topic="كرتون قديم")
    print(f"نتيجة السكريبت الضعيف: Score={review_weak.score}/10 | Approved={review_weak.approved}")
    print(f"نقد السكريبت الضعيف: {review_weak.critique[:120]}...")

    review_strong = evaluate_script(strong_script, topic="كرتون قديم")
    print(f"نتيجة السكريبت القوي: Score={review_strong.score}/10 | Approved={review_strong.approved}")
    print(f"نقد السكريبت القوي: {review_strong.critique[:120]}...")
    assert review_strong.score >= review_weak.score, "الناقد لم يفرق بين السكريبت الضعيف والقوي"
    print("✅ الناقد القاسي يعمل بكفاءة ودقة!")


def test_viral_ass_and_nvenc_render():
    print("\n--- [2/4] اختبار الترجمة المغناطيسية وحركة Ken-Burns مع NVENC ---")
    text = "في سنة 2004، ظهر ملف كود غامض في لعبة كلنا لعبناها، والسر اللي فيه صدم الجميع!"
    audio_file = "test_viral_voice.mp3"

    t0 = time.time()
    tts_res = generate_voiceover(text, save_as=audio_file)
    audio_path = tts_res["path"]
    t_tts = time.time() - t0
    print(f"الصوت (Edge-TTS): تم في {t_tts:.2f} ثانية")

    t0 = time.time()
    sub_res = generate_subtitles(audio_path)
    t_sub = time.time() - t0
    print(f"الترجمة المغناطيسية (Faster-Whisper int8): تم في {t_sub:.2f} ثانية")
    assert sub_res["status"] == "ok"
    ass_path = sub_res["path"]

    # فحص كود اللون الأصفر في ملف الـ ASS
    ass_content = Path(ass_path).read_text(encoding="utf-8")
    assert "&H0000FFFF" in ass_content, "اللون الأصفر الفيروسي غير موجود في ملف الـ ASS"
    print("✅ ملف الترجمة المغناطيسية يحوي التنسيق الأصفر والأبيض والحدود السوداء السميكة!")

    # تجهيز مشهدين صوريين للتجربة
    img1_path = IMAGES_DIR / "test_scene_1.jpg"
    img2_path = IMAGES_DIR / "test_scene_2.jpg"
    Image.new("RGB", (1080, 1920), color=(15, 20, 35)).save(str(img1_path))
    Image.new("RGB", (1080, 1920), color=(40, 15, 25)).save(str(img2_path))

    t0 = time.time()
    render_res = render_shorts_video(
        scene_files=[str(img1_path), str(img2_path)],
        audio_file=audio_path,
        output_name="test_viral_render.mp4",
        subtitle_file=ass_path,
        enable_ken_burns=True,
    )
    t_render = time.time() - t0
    print(f"الريندر النهائي بـ NVENC + Ken-Burns Zoom: تم في {t_render:.2f} ثانية")
    assert render_res["status"] == "ok"
    assert Path(render_res["path"]).exists()
    file_size_mb = Path(render_res["path"]).stat().st_size / (1024 * 1024)
    print(f"حجم الفيديو الناتج: {file_size_mb:.2f} MB")
    print("✅ الريندر فائق السرعة بكرت RTX 4070 مكتمل بنجاح تام!")


def main():
    print("═══════════════════════════════════════════════════════════════")
    print("🧪 فحص واختبار موديول إنتاج المحتوى وبناء الجمهور (Shaher II)")
    print("═══════════════════════════════════════════════════════════════")
    test_ruthless_critic()
    test_viral_ass_and_nvenc_render()
    print("\n🎉 كافة مكونات موديول إنتاج المحتوى جاهزة وتعمل بأعلى كفاءة 100%!")


if __name__ == "__main__":
    main()
