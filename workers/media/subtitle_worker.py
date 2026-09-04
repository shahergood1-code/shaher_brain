"""
workers/media/subtitle_worker.py
────────────────────────────────
تفريغ الصوت وتوليد ملفات ترجمة متزامنة (SRT / ASS) تلقائياً باستخدام faster-whisper.
تم تصميمه ليعمل بكفاءة على CPU (لتوفير VRAM كرت الشاشة RTX 4070 لـ Ollama) أو على CUDA.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from config.settings import AUDIO_DIR, WHISPER_MODEL, WHISPER_DEVICE

logger = logging.getLogger("SubtitleWorker")


def _format_timestamp_srt(seconds: float) -> str:
    """تحويل الثواني إلى تنسيق SRT: 00:00:00,000"""
    millis = int((seconds % 1) * 1000)
    total_seconds = int(seconds)
    secs = total_seconds % 60
    mins = (total_seconds // 60) % 60
    hours = total_seconds // 3600
    return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def _format_timestamp_ass(seconds: float) -> str:
    """تحويل الثواني إلى تنسيق ASS: 0:00:00.00"""
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
        logger.info(f"تحميل Whisper للمرة الأولى ({model_size}) على {device} ({compute_type})...")
        cpu_threads = 4 if device == "cpu" else 0
        _cached_whisper_models[key] = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_threads,
        )
    return _cached_whisper_models[key]


def generate_subtitles(
    audio_path: str,
    output_ass_name: Optional[str] = None,
    language: str = "ar",
    device: str = WHISPER_DEVICE,
    model_size: str = WHISPER_MODEL,
) -> Dict[str, Any]:
    """
    تفريغ ملف الصوت وتوليد ملف ترجمة مصمم خصيصاً للفيديوهات الرأسية (Shorts/Reels).
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
        segments, info = model.transcribe(str(audio_file), language=language, vad_filter=True)

        # رأس ملف ASS بتنسيق أنيق ومحاذاة مناسبة للشورتس (فوق أزرار الواجهة)
        ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ShortsStyle,Segoe UI,54,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,40,40,320,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []
        for seg in segments:
            start_str = _format_timestamp_ass(seg.start)
            end_str = _format_timestamp_ass(seg.end)
            text = seg.text.strip().replace("\n", " ")
            if text:
                events.append(f"Dialogue: 0,{start_str},{end_str},ShortsStyle,,0,0,0,,{text}")

        ass_content = ass_header + "\n".join(events) + "\n"
        ass_path.write_text(ass_content, encoding="utf-8")

        logger.info(f"تم توليد الترجمة بنجاح: {ass_path}")
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
