"""
workers/media/video_renderer.py
───────────────────────────────
محرك المونتاج المسرّع بـ NVENC على NVIDIA RTX 4070 Laptop.
يقوم بـ:
1. توحيد مقاييس المشاهد إلى 9:16 (1080x1920) بمعدل 30fps وقص ذكي (Center Crop).
2. دمج المقاطع بسلاسة بدون أخطاء Concat.
3. دمج تراك الفويس أوفر الصوتي.
4. حرق الترجمة العربية (Burn-in subtitles) عبر libass.
5. التصدير بترميز h264_nvenc عالي الجودة وسريع جداً.
"""

import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

from config.settings import (
    FFMPEG_EXE,
    NVENC_PRESET,
    NVENC_CQ,
    VIDEO_WIDTH,
    VIDEO_HEIGHT,
    TARGET_FPS,
    WORKSPACE_DIR,
    RAW_SCENES_DIR,
    READY_SHORTS_DIR,
)

logger = logging.getLogger("VideoRenderer")


def _get_audio_duration(audio_path: Path) -> float:
    """استخراج مدة الملف الصوتي بالثواني باستخدام ffprobe أو حساب تقديري."""
    try:
        import imageio_ffmpeg
        # نستخدم ffprobe لو متاح أو ffmpeg نفسه لقراءة المدة
        probe_cmd = [
            FFMPEG_EXE,
            "-i", str(audio_path),
            "-f", "null", "-",
        ]
        res = subprocess.run(probe_cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
        # البحث عن Duration: 00:00:15.30
        for line in res.stderr.splitlines():
            if "Duration:" in line:
                part = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = part.split(":")
                return float(h) * 3600 + float(m) * 60 + float(s)
    except Exception as exc:
        logger.warning(f"تعذر حساب مدة الصوت بدقة: {exc}")
    return 15.0  # قيمة افتراضية في حال الفشل


def render_shorts_video(
    scene_files: List[str],
    audio_file: str,
    output_name: str = "final_shorts.mp4",
    subtitle_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    دمج المشاهد مع الصوت والترجمة وتصدير فيديو شورتس رأسي متكامل.
    """
    if not scene_files:
        return {"status": "error", "error": "قائمة المشاهد فارغة"}

    audio_path = Path(audio_file)
    if not audio_path.is_absolute():
        audio_path = WORKSPACE_DIR / "downloads" / "audio" / audio_file
    if not audio_path.exists():
        return {"status": "error", "error": f"ملف الصوت غير موجود: {audio_path}"}

    total_audio_duration = _get_audio_duration(audio_path)
    per_scene_duration = max(2.5, total_audio_duration / len(scene_files))

    normalized_clips = []
    temp_dir = WORKSPACE_DIR / "temp_render"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1) تسوية وتحجيم كل مشهد لـ 1080x1920 @ 30fps
        for idx, scene_name in enumerate(scene_files):
            scene_path = Path(scene_name)
            if not scene_path.is_absolute():
                scene_path = RAW_SCENES_DIR / scene_name
                if not scene_path.exists():
                    scene_path = WORKSPACE_DIR / "downloads" / "images" / scene_name

            if not scene_path.exists():
                logger.warning(f"المشهد {scene_name} غير موجود، تخطي...")
                continue

            norm_clip = temp_dir / f"norm_scene_{idx}.mp4"
            is_image = scene_path.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]

            filter_vf = (
                f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},setsar=1,fps={TARGET_FPS},format=yuv420p"
            )

            if is_image:
                # لو صورة نثبتها لمدة كافية
                cmd = [
                    FFMPEG_EXE, "-y",
                    "-loop", "1",
                    "-i", str(scene_path),
                    "-t", f"{per_scene_duration:.2f}",
                    "-vf", filter_vf,
                    "-c:v", "h264_nvenc", "-preset", NVENC_PRESET, "-cq", NVENC_CQ,
                    str(norm_clip),
                ]
            else:
                # لو فيديو نحجمه ونضبط الـ framerate
                cmd = [
                    FFMPEG_EXE, "-y",
                    "-i", str(scene_path),
                    "-t", f"{per_scene_duration:.2f}",
                    "-vf", filter_vf,
                    "-an",  # حذف الصوت الأصلي للمشهد لتجنب التشويش
                    "-c:v", "h264_nvenc", "-preset", NVENC_PRESET, "-cq", NVENC_CQ,
                    str(norm_clip),
                ]

            subprocess.run(cmd, check=True, capture_output=True, text=True)
            normalized_clips.append(norm_clip)

        if not normalized_clips:
            return {"status": "error", "error": "لم يتم العثور على أي مشاهد صالحة للدمج"}

        # 2) إنشاء قائمة Concat لو أكثر من مشهد
        if len(normalized_clips) == 1:
            merged_video = normalized_clips[0]
        else:
            concat_txt = temp_dir / "concat_list.txt"
            concat_content = "\n".join(f"file '{c.resolve().as_posix()}'" for c in normalized_clips)
            concat_txt.write_text(concat_content, encoding="utf-8")

            merged_video = temp_dir / "merged_video.mp4"
            concat_cmd = [
                FFMPEG_EXE, "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_txt),
                "-c", "copy",
                str(merged_video),
            ]
            subprocess.run(concat_cmd, check=True, capture_output=True, text=True)

        # 3) الدمج النهائي مع الصوت وحرق الترجمة بـ NVENC
        output_path = READY_SHORTS_DIR / output_name

        final_cmd = [
            FFMPEG_EXE, "-y",
            "-i", str(merged_video),
            "-i", str(audio_path),
        ]

        if subtitle_file and Path(subtitle_file).exists():
            # تجهيز مسار الترجمة لـ FFmpeg (تجاوز مشكلة الباك سلاش في ويندوز)
            sub_clean_path = Path(subtitle_file).resolve().as_posix().replace(":", "\\:")
            final_cmd.extend(["-vf", f"subtitles='{sub_clean_path}'"])

        final_cmd.extend([
            "-c:v", "h264_nvenc",
            "-preset", NVENC_PRESET,
            "-cq", NVENC_CQ,
            "-c:a", "aac",
            "-b:a", "192k",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            str(output_path),
        ])

        logger.info("بدء الرندر النهائي مسرع بـ NVENC...")
        subprocess.run(final_cmd, check=True, capture_output=True, text=True)
        logger.info(f"تم تصدير الفيديو النهائي بنجاح: {output_path}")

        # تنظيف الملفات المؤقتة تلقائياً للحفاظ على مساحة القرص
        try:
            for item in temp_dir.glob("norm_scene_*.mp4"):
                item.unlink(missing_ok=True)
            (temp_dir / "concat_list.txt").unlink(missing_ok=True)
            (temp_dir / "merged_video.mp4").unlink(missing_ok=True)
        except Exception:
            pass

        return {
            "status": "ok",
            "path": str(output_path),
            "filename": output_name,
            "duration": total_audio_duration,
        }

    except subprocess.CalledProcessError as exc:
        err_msg = exc.stderr if exc.stderr else str(exc)
        logger.error(f"فشل FFmpeg: {err_msg}")
        return {"status": "error", "error": f"FFmpeg failure: {err_msg}"}
    except Exception as exc:
        logger.error(f"خطأ غير متوقع أثناء الرندر: {exc}")
        return {"status": "error", "error": str(exc)}
