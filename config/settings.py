"""
config/settings.py
──────────────────
الإعدادات المركزية لنظام تشغيل إنتاج المحتوى (Content Orchestrator)
يدير مسارات الملفات، اكتشاف FFmpeg بـ NVENC، اتصال Ollama، والمتصفح.
"""

import os
import shutil
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── 1. مسارات العمل ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = BASE_DIR / "workspace"

# مجلدات التحميل المؤقت
DOWNLOADS_DIR = WORKDIR_DOWNLOADS = WORKSPACE_DIR / "downloads"
RAW_SCENES_DIR = DOWNLOADS_DIR / "raw_scenes"
IMAGES_DIR = DOWNLOADS_DIR / "images"
AUDIO_DIR = DOWNLOADS_DIR / "audio"

# مجلدات المخرجات الجاهزة للنشر
EXPORTS_DIR = WORKSPACE_DIR / "exports"
READY_SHORTS_DIR = EXPORTS_DIR / "ready_shorts"
READY_POSTS_DIR = EXPORTS_DIR / "ready_posts"

# التأكد من وجود كافة المجلدات المطلوبة
for d in [
    WORKSPACE_DIR,
    DOWNLOADS_DIR,
    RAW_SCENES_DIR,
    IMAGES_DIR,
    AUDIO_DIR,
    EXPORTS_DIR,
    READY_SHORTS_DIR,
    READY_POSTS_DIR,
]:
    d.mkdir(parents=True, exist_ok=True)

# ─── 2. كشف FFmpeg وتسريع NVENC (RTX 4070) ───────────────────────
def get_ffmpeg_path() -> str:
    """
    يكتشف مسار FFmpeg تلقائياً:
    1. يفحص أولاً PATH في النظام.
    2. لو مش موجود، يستخدم FFmpeg 7.1 المدمج في imageio_ffmpeg (يدعم NVENC و libass).
    """
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass

    return "ffmpeg"  # fallback افتراضي

FFMPEG_EXE = get_ffmpeg_path()
NVENC_PRESET = os.getenv("NVENC_PRESET", "p4")
NVENC_CQ = os.getenv("NVENC_CQ", "20")
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
TARGET_FPS = 30

# ─── 3. إعدادات العقل المحلي (Ollama) ──────────────────────────────
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

# ─── 4. إعدادات المتصفح (Remote Debugging CDP) ─────────────────────
CHROME_CDP_PORT = int(os.getenv("CHROME_CDP_PORT", "9222"))
CHROME_CDP_URL = f"http://localhost:{CHROME_CDP_PORT}"

FLOW_URL = os.getenv("FLOW_URL", "https://labs.google/flow")

# روابط المحادثات المثبتة في Gemini (يمكن تخصيصها في .env أو config)
PINNED_CHATS = {
    "youtube_channel": os.getenv("GEMINI_PINNED_YOUTUBE", "https://gemini.google.com"),
    "shaher": os.getenv("GEMINI_PINNED_SHAHER", "https://gemini.google.com"),
}

# ─── 5. إعدادات الصوت (TTS & Subtitles) ───────────────────────────
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "ar-EG-ShakirNeural")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
# لاستخدام المعالج بدلاً من مزاحمة كرت الشاشة على الـ 8GB VRAM
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")  # 'cpu' أو 'cuda'
