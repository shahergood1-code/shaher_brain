# ═══════════════════════════════════════════════════════════════════
# Dockerfile — Universal Free Cloud Hosting (Koyeb, Render, Fly.io)
# ═══════════════════════════════════════════════════════════════════
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# تثبيت الاعتماديات الخفيفة للتشغيل السحابي فائق السرعة
COPY api/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# نسخ كود المشروع
COPY . .

EXPOSE 7860
EXPOSE 8000

# تشغيل السيرفر على البورت المعين تلقائياً (7860 لـ HuggingFace أو PORT لأي منصة أخرى)
CMD ["sh", "-c", "uvicorn bot.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
