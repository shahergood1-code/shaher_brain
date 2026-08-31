-- ═══════════════════════════════════════════════════════
-- شاهر الثاني — Supabase Database Schema (المرحلة 1)
-- شغّل الـ SQL ده في Supabase SQL Editor
-- آخر تحديث: أُضيف جدول generated_images
-- ═══════════════════════════════════════════════════════

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── جدول التفاعلات ──────────────────────────────────────
-- كل رسالة جاية من تليجرام وكل رد بيتسجل هنا تلقائيًا
CREATE TABLE IF NOT EXISTS interactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- بيانات الرسالة الجاية
    telegram_user_id BIGINT,
    telegram_chat_id BIGINT,
    user_message    TEXT NOT NULL,
    message_type    TEXT NOT NULL DEFAULT 'text',  -- 'text' | 'voice'
    
    -- بيانات الرد
    ai_source_used  TEXT,          -- 'gemini' | 'seekai' | 'duckai' | 'error'
    ai_model_used   TEXT,          -- الموديل الفعلي اللي استخدمه
    ai_response     TEXT,
    
    -- أداء
    response_time_ms INTEGER,
    tokens_used      INTEGER,
    error_details    TEXT          -- لو حصل error، بتتسجل هنا
);

-- Index للاستعلام حسب التاريخ
CREATE INDEX IF NOT EXISTS idx_interactions_created_at ON interactions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_user ON interactions(telegram_user_id, created_at DESC);

-- ─── جدول التفضيلات ─────────────────────────────────────
-- ذاكرة دائمة: تفضيلاتي، إعداداتي، معلومات عني
CREATE TABLE IF NOT EXISTS preferences (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key         TEXT UNIQUE NOT NULL,      -- مثال: 'working_hours', 'preferred_tone'
    value       JSONB NOT NULL DEFAULT '{}',
    description TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Trigger لتحديث updated_at تلقائيًا
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_preferences_updated_at
    BEFORE UPDATE ON preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ─── جدول المشاريع ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    description TEXT,
    status      TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'paused' | 'done'
    channel     TEXT,          -- 'shaher_tech' | 'ismail_clinic' | 'aktham_clinic' | null
    github_repo TEXT,          -- رابط الـ repo لو موجود
    metadata    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER update_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ─── جدول القرارات ──────────────────────────────────────
-- قرارات مهمة اتخذتها مع شاهر — عشان يتذكرها ويرجع ليها
CREATE TABLE IF NOT EXISTS decisions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title       TEXT NOT NULL,
    context     TEXT,
    decision    TEXT NOT NULL,
    rationale   TEXT,
    tags        TEXT[] DEFAULT '{}',
    project_id  UUID REFERENCES projects(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── جدول المعرفة (Knowledge Base) ─────────────────────
-- قواعد البرمجة، أسلوب المحتوى، البرومبتات، معلومات متخصصة
CREATE TABLE IF NOT EXISTS knowledge (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category    TEXT NOT NULL,  -- 'programming' | 'content' | 'seo' | 'prompts' | 'general'
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,
    tags        TEXT[] DEFAULT '{}',
    source      TEXT,           -- المصدر لو موجود
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER update_knowledge_updated_at
    BEFORE UPDATE ON knowledge
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge(category);

-- ─── جدول الصور المولّدة ───────────────────────────────────
-- كل صورة بتتولّد عبر SeekAI بتتسجل هنا تلقائيًا
CREATE TABLE IF NOT EXISTS generated_images (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- طلب الصورة
    prompt           TEXT NOT NULL,            -- البرومبت اللي اتبعت للتوليد
    revised_prompt   TEXT,                     -- البرومبت بعد تعديل SeekAI (لو حصل)

    -- نتيجة التوليد
    model_used       TEXT NOT NULL,            -- 'flux' | 'nano-banana' | 'seedream'
    image_url        TEXT,                     -- رابط الصورة من SeekAI
    size             TEXT,                     -- '1024x1024' | '1280x720' | إلخ

    -- أداء
    response_time_ms INTEGER,
    error_details    TEXT                      -- لو حصل خطأ في التوليد
);

CREATE INDEX IF NOT EXISTS idx_generated_images_created_at
    ON generated_images(created_at DESC);

-- ─── بيانات أولية ────────────────────────────────────────
INSERT INTO preferences (key, value, description) VALUES
    ('owner_name', '"شاهر"', 'اسم صاحب النظام'),
    ('language', '"arabic"', 'اللغة الافتراضية'),
    ('ai_personality', '"مساعد شخصي ذكي، مباشر، بدون كلام زيادة"', 'شخصية شاهر'),
    ('timezone', '"Africa/Cairo"', 'منطقة الوقت')
ON CONFLICT (key) DO NOTHING;

-- مشروع شاهر نفسه كأول مشروع في النظام
INSERT INTO projects (name, description, status, channel) VALUES
    ('شاهر الثاني', 'نظام التشغيل الشخصي — المشروع الأساسي', 'active', null)
ON CONFLICT DO NOTHING;
