"""
workers/media/tts_worker.py
───────────────────────────
توليد الفويس أوفر الصوتي العربي الطبيعي.
يدعم edge-tts كخيار محلي سريع ومجاني، مع جاهزية التوصيل بـ AI Studio.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any

from config.settings import AUDIO_DIR, DEFAULT_VOICE

logger = logging.getLogger("TTSWorker")


def generate_voiceover(text: str, save_as: str = "voiceover.mp3", voice: str = DEFAULT_VOICE) -> Dict[str, Any]:
    """
    يولد فويس أوفر صوتي عربي من النص ويحفظه في مجلد الصوتيات.
    """
    dest_path = AUDIO_DIR / save_as

    try:
        import edge_tts

        async def _synthesize():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(dest_path))

        asyncio.run(_synthesize())
        logger.info(f"تم توليد الصوت بنجاح: {dest_path}")
        return {
            "status": "ok",
            "path": str(dest_path),
            "engine": "edge-tts",
            "voice": voice,
            "filename": save_as,
        }
    except Exception as exc:
        logger.error(f"فشل توليد الصوت: {exc}")
        return {
            "status": "error",
            "error": str(exc),
        }
