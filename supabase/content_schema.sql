-- ═══════════════════════════════════════════════════════════════════
-- شاهر الثاني — Supabase Schema: موديول إنتاج المحتوى (Content Engine)
-- شغّل الـ SQL ده في Supabase SQL Editor لإضافة جداول المرحلة الجديدة
-- ═══════════════════════════════════════════════════════════════════

-- تفعيل إضافات الـ UUID لو لم تكن مفعّلة مسبقاً
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── 1. جدول دورات ومهام الأوركستريتور (Content Tasks) ─────────────
-- يسجل كل تشغيل للمنظومة (التاريخ، الهدف، الخطوات المنفذة، الحالة)
CREATE TABLE IF NOT EXISTS content_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    task_type       TEXT NOT NULL DEFAULT 'daily_pipeline',  -- 'daily_pipeline' | 'manual_shorts' | 'social_post'
    status          TEXT NOT NULL DEFAULT 'running',         -- 'running' | 'completed' | 'failed'
    user_goal       TEXT NOT NULL,                           -- الهدف أو الطلب اللي بدأ التشغيل
    steps           JSONB NOT NULL DEFAULT '[]',             -- سجل استدعاء الأدوات والنتائج
    summary         TEXT,                                    -- ملخص ما تم إنجازه
    error_details   TEXT,                                    -- تفاصيل الخطأ لو حصل فشل
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_content_tasks_created_at ON content_tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_content_tasks_status ON content_tasks(status);

-- ─── 2. جدول المنشورات والمحتوى المُنتج (Content Posts) ──────────────
-- يسجل كل فيديو أو صورة أو بوست تم إنتاجه ومساراته وحالة نشره
CREATE TABLE IF NOT EXISTS content_posts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID REFERENCES content_tasks(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    content_type    TEXT NOT NULL,                           -- 'youtube_shorts' | 'social_image_post'
    title           TEXT,                                    -- عنوان المنشور / الفيديو
    script          TEXT,                                    -- السكريبت أو الفويس أوفر
    prompt_used     TEXT,                                    -- البرومبت المستخدم في التوليد
    caption         TEXT,                                    -- الكابشن والهاشتاجات
    media_path      TEXT,                                    -- مسار الملف محلياً في workspace
    platforms       TEXT[] DEFAULT '{}',                     -- المنصات المستهدفة ['youtube_shorts', 'instagram', ...]
    published_urls  JSONB DEFAULT '{}',                      -- روابط المنشور على المنصات بعد النشر
    status          TEXT NOT NULL DEFAULT 'draft',           -- 'draft' | 'rendered' | 'published' | 'failed'
    published_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_content_posts_created_at ON content_posts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_content_posts_type ON content_posts(content_type);
CREATE INDEX IF NOT EXISTS idx_content_posts_status ON content_posts(status);

-- ─── 3. جدول التحليلات ومقاييس الأداء (Content Analytics) ─────────────
-- يسجل قراءات الأداء بعد 24 ساعة لتغذية حلقة التحسين المستمر
CREATE TABLE IF NOT EXISTS content_analytics (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id               UUID REFERENCES content_posts(id) ON DELETE CASCADE,
    recorded_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    platform              TEXT NOT NULL,                     -- 'youtube_shorts' | 'tiktok' | 'instagram' | 'facebook'
    views                 INTEGER DEFAULT 0,
    likes                 INTEGER DEFAULT 0,
    comments              INTEGER DEFAULT 0,
    shares                INTEGER DEFAULT 0,
    avg_percentage_viewed NUMERIC(5, 2),                     -- نسبة الإكمال ومتوسط المشاهدة
    watch_time_seconds    NUMERIC(10, 2),
    retention_notes       TEXT,                              -- ملاحظات حول نقاط انخفاض المشاهدة
    raw_stats             JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_content_analytics_post_id ON content_analytics(post_id);
CREATE INDEX IF NOT EXISTS idx_content_analytics_recorded_at ON content_analytics(recorded_at DESC);
