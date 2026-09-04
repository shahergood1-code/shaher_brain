"""
config/selectors.py
───────────────────
مستودع محددات الـ DOM (Selectors) الموحد لأتمتة المتصفح عبر Playwright.
كل صفحة لها قسم مخصص لتسهيل الضبط والتحديث عند تغير واجهات المواقع.
"""

# ─── 1. Google Gemini Web ──────────────────────────────────────────
GEMINI_SELECTORS = {
    # مربع كتابة البرومبت في جيمناي (rich-textarea أو contenteditable)
    "input_box": [
        "div[contenteditable='true']",
        "rich-textarea [contenteditable='true']",
        "div.ql-editor",
        "textarea[placeholder*='Ask']",
    ],
    # زر الإرسال
    "send_button": [
        "button[aria-label*='Send']",
        "button[aria-label*='إرسال']",
        "button.send-button",
    ],
    # فقاعة الرد (نص إجابة الموديل)
    "response_container": [
        ".model-response-text",
        "message-content",
        ".response-container",
        "div[data-test-id='response-content']",
    ],
    # مؤشر انتهاء التوليد (ظهور أزرار النسخ أو اختفاء زر الإيقاف)
    "stop_generating_button": [
        "button[aria-label*='Stop']",
        "button[aria-label*='إيقاف']",
    ],
}

# ─── 2. Google Flow (Nano Banana 2 / Veo Lite) ─────────────────────
FLOW_SELECTORS = {
    # مربع البرومبت للصور
    "image_prompt_input": [
        "textarea[placeholder*='prompt']",
        "textarea[placeholder*='برومبت']",
        "input[placeholder*='Describe']",
        "textarea",
    ],
    # زر اختيار الموديل (Nano Banana 2)
    "model_dropdown": [
        "button:has-text('Model')",
        "[aria-label*='Model']",
        "button:has-text('Nano Banana')",
    ],
    "nano_banana_option": [
        "div[role='option']:has-text('Nano Banana 2')",
        "button:has-text('Nano Banana 2')",
    ],
    # زر التوليد
    "generate_button": [
        "button:has-text('Generate')",
        "button:has-text('توليد')",
        "button[type='submit']",
    ],
    # رفع الصورة لتحريكها بـ Veo Lite
    "video_source_file_input": [
        "input[type='file'][accept*='image']",
        "input[type='file']",
    ],
    # برومبت الحركة
    "motion_prompt_input": [
        "textarea[placeholder*='motion']",
        "textarea[placeholder*='حركة']",
        "textarea[placeholder*='animate']",
    ],
    "veo_lite_option": [
        "div[role='option']:has-text('Veo Lite')",
        "button:has-text('Veo Lite')",
    ],
    # زر تحميل النتيجة
    "download_button": [
        "button:has-text('Download')",
        "button[aria-label*='Download']",
        "a[download]",
    ],
}

# ─── 3. يوتيوب ستوديو (YouTube Studio Shorts) ──────────────────────
YOUTUBE_STUDIO_SELECTORS = {
    "url": "https://studio.youtube.com",
    # زر الإنشاء / Create
    "create_button": [
        "#create-icon",
        "button:has-text('Create')",
        "button:has-text('إنشاء')",
    ],
    # خيار رفع فيديو
    "upload_video_item": [
        "tp-yt-paper-item:has-text('Upload videos')",
        "tp-yt-paper-item:has-text('تحميل فيديوهات')",
    ],
    # رفع الملف
    "file_input": "input[type='file']",
    # عنوان الشورتس
    "title_box": [
        "#title-textarea [contenteditable='true']",
        "#textbox[aria-label*='Title']",
        "#textbox[aria-label*='العنوان']",
    ],
    # مربع الوصف
    "description_box": [
        "#description-textarea [contenteditable='true']",
        "#description[aria-label*='Description']",
    ],
    # اختيار "ليس مخصصاً للأطفال"
    "not_for_kids_radio": [
        "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']",
    ],
    # زر التالي Next
    "next_button": [
        "#next-button",
        "button:has-text('Next')",
        "button:has-text('التالي')",
    ],
    # زر علني Public
    "public_radio": [
        "tp-yt-paper-radio-button[name='PUBLIC']",
    ],
    # زر النشر النهائي Done / Publish
    "done_button": [
        "#done-button",
        "button:has-text('Publish')",
        "button:has-text('نشر')",
    ],
}

# ─── 4. تيك توك (TikTok Upload) ────────────────────────────────────
TIKTOK_SELECTORS = {
    "url": "https://www.tiktok.com/upload",
    "file_input": "input[type='file']",
    "caption_box": [
        "div[contenteditable='true']",
        ".public-DraftEditor-content",
    ],
    "post_button": [
        "button:has-text('Post')",
        "button:has-text('نشر')",
    ],
}

# ─── 5. إنستغرام (Instagram Web) ───────────────────────────────────
INSTAGRAM_SELECTORS = {
    "url": "https://www.instagram.com",
    "new_post_button": [
        "svg[aria-label='New post']",
        "svg[aria-label='منشور جديد']",
        "a[href='#']:has-text('Create')",
    ],
    "file_input": "input[type='file']",
    "caption_box": [
        "div[aria-label*='Write a caption']",
        "div[aria-label*='اكتب شرحاً توضيحياً']",
    ],
    "share_button": [
        "button:has-text('Share')",
        "button:has-text('مشاركة')",
    ],
}
