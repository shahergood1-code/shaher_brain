"""
workers/media/subtitle_worker.py
────────────────────────────────
تفريغ الصوت وتوليد ملفات ترجمة مغناطيسية فيروسية (Viral ASS Subtitles)
باستخدام faster-whisper على CPU int8 (لتوفير 8GB VRAM بالكامل لـ RTX 4070 و Ollama).

مواصفات الترجمة المغناطيسية:
- خط عريض مشدود (Bold)
- لون أصفر نيون متوهج (&H0000FFFF) مع أبيض ناصع
- إطار وحدود سوداء سميكة (Outline=5, Shadow=2)
- تموضع رأسي آمن (MarginV=420) لتفادي أزرار واجهة تيك توك، ريلز، وشورتس
- تقسيم سريع للكلمات لضمان القراءة السلسة والمتابعة المستمرة
"""

import logging
from pathlib import Path
from typing import Any

from config.settings import WHISPER_DEVICE, WHISPER_MODEL

logger = logging.getLogger("SubtitleWorker")


def _format_timestamp_ass(seconds: float) -> str:
    """تحويل الثواني إلى تنسيق ASS: H:MM:SS.CC"""
    centis = int((seconds % 1) * 100)
    total_seconds = int(seconds)
    secs = total_seconds % 60
    mins = (total_seconds // 60) % 60
    hours = total_seconds // 3600
    return f"{hours:d}:{mins:02d}:{secs:02d}.{centis:02d}"


_cached_whisper_models: dict = {}

def _get_whisper_model(model_size: str, device: str, compute_type: str):
    """كاش ذكي لموديل Whisper لتفادي إعادة القراءة من القرص في كل استدعاء."""
    key = (model_size, device, compute_type)
    if key not in _cached_whisper_models:
        from faster_whisper import WhisperModel
        logger.info(f"تحميل Whisper ({model_size}) على {device} ({compute_type})...")
        cpu_threads = 4 if device == "cpu" else 0
        _cached_whisper_models[key] = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_threads,
        )
    return _cached_whisper_models[key]


def _chunk_text_to_punchy_lines(text: str, max_words: int = 4) -> list[str]:
    """تقسيم النص الطويل إلى عبارات قصيرة جداً ومغناطيسية للقراءة السريعة."""
    words = text.strip().split()
    if len(words) <= max_words:
        return [text.strip()]
    chunks = []
    for i in range(0, len(words), max_words):
        chunks.append(" ".join(words[i:i + max_words]))
    return chunks


def generate_subtitles(
    audio_path: str,
    output_ass_name: str | None = None,
    language: str = "ar",
    device: str = WHISPER_DEVICE,
    model_size: str = WHISPER_MODEL,
) -> dict[str, Any]:
    """
    تفريغ ملف الصوت وتوليد ملف ترجمة مغناطيسية مصمم خصيصاً للفيديوهات الرأسية (Shorts/Reels/TikTok).
    """
    audio_file = Path(audio_path)
    if not audio_file.exists():
        return {"status": "error", "error": f"ملف الصوت غير موجود: {audio_path}"}

    if output_ass_name:
        ass_path = audio_file.parent / output_ass_name
    else:
        ass_path = audio_file.with_suffix(".ass")

    try:
        compute_type = "float16" if device == "cuda" else "int8"
        model = _get_whisper_model(model_size, device, compute_type)
        segments, info = model.transcribe(
            str(audio_file),
            language=language,
            vad_filter=True,
            word_timestamps=True,
        )

        # رأس ملف ASS بتنسيق مغناطيسي فائق التباين (أصفر ذهبي وأبيض مع حدود سوداء سميكة وموقع رأسي آمن)
        # PrimaryColour: &H0000FFFF (أصفر ناصع في نظام BGR)
        # OutlineColour: &H00000000 (أسود)
        # Alignment: 2 (منتصف أسفل الشاشة لكن بهامش رأسي مرتفع 420px لتجنب أزرار المنصة)
        ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ViralYellow,Segoe UI Black,62,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,5,2.5,2,50,50,380,1
Style: ViralWhite,Segoe UI Black,62,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,5,2.5,2,50,50,380,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []
        seg_counter = 0

        for seg in segments:
            # إذا توفرت الكلمات بدقة، نقسم المقطع لكلمات سريعة ومثيرة
            if hasattr(seg, "words") and seg.words:
                sub_words = [w for w in seg.words if w.word.strip()]
                # تجميع كل 3 كلمات معاً
                chunk_size = 3
                for i in range(0, len(sub_words), chunk_size):
                    chunk = sub_words[i:i + chunk_size]
                    w_start = chunk[0].start
                    w_end = chunk[-1].end
                    w_text = " ".join(w.word.strip() for w in chunk)
                    style = "ViralYellow" if seg_counter % 2 == 0 else "ViralWhite"
                    seg_counter += 1
                    events.append(
                        f"Dialogue: 0,{_format_timestamp_ass(w_start)},{_format_timestamp_ass(w_end)},{style},,0,0,0,,{w_text}"
                    )
            else:
                # تقسيم عادي بالجمل
                start_str = _format_timestamp_ass(seg.start)
                end_str = _format_timestamp_ass(seg.end)
                text = seg.text.strip().replace("\n", " ")
                if text:
                    style = "ViralYellow" if seg_counter % 2 == 0 else "ViralWhite"
                    seg_counter += 1
                    events.append(
                        f"Dialogue: 0,{start_str},{end_str},{style},,0,0,0,,{text}"
                    )

        ass_content = ass_header + "\n".join(events) + "\n"
        ass_path.write_text(ass_content, encoding="utf-8")

        logger.info(f"✨ تم توليد الترجمة المغناطيسية الفيروسية: {ass_path}")
        return {
            "status": "ok",
            "path": str(ass_path),
            "language": info.language,
            "duration": info.duration,
        }
    except Exception as exc:
        logger.error(f"فشل توليد الترجمة بـ Whisper: {exc}")
        return {
            "status": "error",
            "error": str(exc),
        }
