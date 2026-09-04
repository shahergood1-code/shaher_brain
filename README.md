# 🧠 شاهر الثاني — نظام التشغيل الشخصي بالذكاء الاصطناعي (Shaher II OS)

> **نظام تشغيل شخصي متكامل بالذكاء الاصطناعي يجمع بين: التفاعل الفوري عبر تليجرام (نص وصوت)، الذاكرة الدائمة في Supabase، وخط إنتاج ونشر المحتوى الرقمي المؤتمت بالكامل (Content Orchestrator).**

---

## 🏛️ المعمارية العامة للنظام (Architecture)

```
                       ┌─────────────────────────────────────────┐
                       │       Telegram Bot (نص & فويس نوت)      │
                       └────────────────────┬────────────────────┘
                                            │
                                            ▼
                       ┌─────────────────────────────────────────┐
                       │          Shaher Brain (Router)          │
                       │   توجيه الرسائل / الأوامر / الذاكرة     │
                       └───────────┬─────────────────┬───────────┘
                                   │                 │
            ┌──────────────────────┴──────┐          │
            ▼                             ▼          ▼
┌───────────────────────┐   ┌─────────────────┐  ┌─────────────────────────────────┐
│     Cloud AI Chain    │   │  SeekAI Images  │  │  Supabase Memory (9 جداول)      │
│ Gemini ➔ SeekAI ➔ DDG │   │  Flux / Banana  │  │  interactions, preferences,     │
└───────────────────────┘   └─────────────────┘  │  projects, decisions, knowledge,│
                                                 │  content_tasks, content_posts,  │
                                                 │  content_analytics, images      │
                                                 └───────────────▲─────────────────┘
                                                                 │ (Sync & Feedback)
═════════════════════════════════════════════════════════════════╪══════════════════════
المرحلة الثانية: خط إنتاج المحتوى المستقل (Content Orchestrator) │ (Local RTX 4070 8GB)
═════════════════════════════════════════════════════════════════╪══════════════════════
                                                                 │
                       ┌─────────────────────────────────────────┴───────────────┐
                       │     Master Orchestrator (Ollama: qwen2.5:7b)            │
                       │      إدارة الخطة والأدوات عبر Function Calling           │
                       └────────────────────────────┬────────────────────────────┘
                                                    │
         ┌──────────────────────────────────────────┼──────────────────────────────────────┐
         ▼                                          ▼                                      ▼
┌───────────────────────────────┐   ┌──────────────────────────────┐   ┌───────────────────────────────┐
│     Browser Worker (CDP 9222) │   │     Local Media Engine       │   │    Automation & Analytics     │
│ 1. Gemini Pinned Chats (أفكار)│   │ 1. edge-tts (صوت عربي شاكر)  │   │ 1. رفع Shorts (YouTube/TikTok)│
│ 2. Google Flow (Nano Banana 2)│   │ 2. faster-whisper (ترجمة ASS)│   │ 2. قراءة إحصائيات 24h         │
│ 3. Veo Lite (تحريك المشاهد)   │   │ 3. FFmpeg NVENC 9:16 (مونتاج)│   │ 3. Windows Task Scheduler     │
└───────────────────────────────┘   └──────────────────────────────┘   └───────────────────────────────┘
```

---

## 💻 التوافق مع مواصفات العتاد المحلي (Hardware Optimization)

تم ضبط كافة العمليات المحلية لتعمل بأعلى كفاءة على:
- **الجهاز**: ASUS TUF Gaming F15 (i7-13620H - 16GB RAM - 1TB SSD).
- **كرت الشاشة**: NVIDIA GeForce RTX 4070 Laptop **8GB VRAM**.
- **إدارة الذاكرة (VRAM Guard)**:
  - موديل **Ollama `qwen2.5:7b`** يستهلك قرابة **4.7 - 5.3 GB VRAM** ويظل شغالاً باستقرار.
  - محرك الترجمة **`faster-whisper`** يعمل على المعالج i7-13620H (10 أنوية) بنمط `int8` ويفرّغ الصوت في **1.5 ثانية باستهلاك 0 VRAM** تماماً، أو على CUDA بحجم `base`.
  - محرك المونتاج **FFmpeg NVENC** (`h264_nvenc -preset p4 -cq 20`) يستخدم شريحة التشفير العتادية المخصصة بالكرت مع استهلاك VRAM ضئيل جداً (<100MB)، وينتج ريلز 9:16 كامل مع حرق الترجمة في **ثانيتين فقط**.

---

## 📁 هيكل المشروع المنظم (Directory Tree)

```
shaher_brain/
├── config/
│   ├── settings.py             # المسارات، إعدادات العتاد وNVENC، كشف FFmpeg التلقائي
│   └── selectors.py            # مركز محددات الـ DOM (Gemini, Flow, YouTube Studio, TikTok, IG)
├── core/
│   ├── orchestrator.py         # العقل المدير (Ollama Qwen2.5 Tool Calling Loop)
│   ├── prompts.py              # موجهات النظام (Prompts) واستراتيجيات زيادة الـ Retention
│   └── state_manager.py        # مزامنة المهام والمنشورات والإحصائيات الحية مع Supabase
├── workers/
│   ├── browser/
│   │   ├── cdp_client.py       # مدير اتصال متصفح Chrome Remote Debugging (Singleton آمن)
│   │   ├── gemini_worker.py    # أتمتة استخراج الأفكار والسكريبت مع Fallback لـ Phase 1
│   │   ├── flow_worker.py      # أتمتة Flow (Nano Banana 2 و Veo Lite) مع Fallback لـ SeekAI
│   │   └── social_worker.py    # أتمتة النشر واستخراج إحصائيات الأداء بعد 24 ساعة
│   └── media/
│       ├── tts_worker.py       # توليد الفويس أوفر العربي (ar-EG-ShakirNeural)
│       ├── subtitle_worker.py  # تفريغ الصوت وتوليد ملف ترجمة ASS بتنسيق مميز للشورتس
│       └── video_renderer.py   # مونتاج FFmpeg بـ NVENC، تحويل 9:16، وحرق الترجمة
├── utils/
│   ├── gpu_guard.py            # فحص الـ VRAM المتاحة ودرجة حرارة الكرت
│   └── scheduler_setup.py      # تسجيل المهمة في Windows Task Scheduler لتعمل يومياً
├── bot/
│   ├── telegram_handler.py     # معالج رسائل تليجرام
│   ├── voice_handler.py        # تفريغ الصوت القادم من تليجرام
│   └── main.py                 # FastAPI webhook للـ Bot على Railway
├── brain/
│   ├── router.py               # عقل التصنيف (يدعم أوامر /content, /content_status, /content_run)
│   ├── ai_client.py            # سلسلة الـ Fallback السحابية (Gemini, SeekAI, Duck.ai)
│   └── image_client.py         # توليد الصور السحابية عبر SeekAI
├── memory/
│   ├── supabase_client.py      # كائن اتصال Supabase الموحد للنظام
│   ├── logger.py               # تسجيل المحادثات والتفاعلات
│   └── learning_engine.py      # تحليل واستخراج تفضيلات شاهر
├── supabase/
│   ├── schema.sql              # جداول المرحلة الأولى (6 جداول)
│   ├── content_schema.sql      # جداول موديول المحتوى (3 جداول)
│   └── full_schema.sql         # السكيما الموحدة الكاملة لكافة جداول النظام
├── workspace/                  # مجلد العمل المحلي (مستثنى من Git)
│   ├── downloads/              # ملفات المشاهد والصوتيات المؤقتة
│   └── exports/                # الفيديوهات والصور النهائية الجاهزة للنشر
├── main.py                     # واجهة التحكم والتشغيل الموحدة (CLI)
├── requirements.txt            # المتطلبات البرمجية الموحدة بالكامل
└── .env.example                # نموذج المتغيرات البيئية الشامل
```

---

## 🚀 دليل التثبيت والتشغيل السريع

### 1. تثبيت المتطلبات
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. إعداد قاعدة البيانات في Supabase
1. افتح مشروعك في [Supabase](https://supabase.com) واذهب إلى **SQL Editor**.
2. انسخ محتوى الملف `supabase/full_schema.sql` (أو `supabase/content_schema.sql` لو كنت شغلت المرحلة 1 مسبقاً) واضغط **Run**.

### 3. إعداد البيئة (.env)
انسخ `.env.example` إلى `.env` واملأ المفاتيح الخاصة بك:
```bash
cp .env.example .env
```

### 4. تشغيل Ollama
تأكد من تشغيل Ollama محلياً وسحب الموديل:
```bash
ollama serve
ollama pull qwen2.5:7b
```

### 5. تشغيل متصفح Chrome بوضع Remote Debugging
افتح Chrome بالأمر التالي (ليستخدم حساباتك ومحادثات جيمناي المثبتة):
```cmd
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\Users\shaher\AppData\Local\Google\Chrome\User Data"
```

---

## 🎮 أوامر واجهة التحكم (CLI Commands)

| الأمر | الوظيفة |
| :--- | :--- |
| `python main.py status` | فحص حالة كرت الشاشة RTX 4070، اتصال Chrome 9222، Ollama، وSupabase |
| `python main.py run` | تشغيل خطة إنتاج المحتوى اليومي بالكامل (شورتس + بوست سوشيال) |
| `python main.py test-tts` | اختبار توليد الفويس أوفر الصوتي العربي |
| `python main.py test-subtitles --audio <path>` | اختبار تفريغ الصوت بـ Whisper وتوليد ملف الترجمة ASS |
| `python main.py test-render --audio <file> --scenes <file>` | اختبار مونتاج ريلز 9:16 مسرّع بـ NVENC مع حرق الترجمة |
| `python main.py test-gemini` | اختبار استشارة جيمناي واستخراج الأفكار والسيناريو |
| `python main.py schedule --time 10:00` | تثبيت المهمة لتعمل يومياً تلقائياً في Windows Task Scheduler |

---

## 📱 أوامر البوت في تليجرام (Telegram Commands)

- `/status`: فحص حالة النظام العامة وسلسلة الذكاء الاصطناعي.
- `/content`: عرض تفاصيل موديول إنتاج المحتوى.
- `/content_status`: الاستعلام عن حالة آخر دورة إنتاج محتوى مسجلة في Supabase.
- `/content_run`: إطلاق خط الإنتاج والمونتاج فوراً من تليجرام ومتابعة التقدم.
