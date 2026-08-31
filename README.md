# شاهر الثاني — دليل التشغيل الكامل

## البنية التقنية

```
Telegram ←→ Railway (FastAPI) ←→ Supabase (Memory)
                    ↕
            Shaher Brain (Router)
              ↙        ↓        ↘
         Chat AI    Image AI   Commands
        Gemini→     SeekAI      Direct
        SeekAI→     (only)
        Duck.ai
```

---

## متطلبات قبل البدء

قبل ما تبدأ، لازم تجمع الحاجات دي:

| الحاجة | من فين | وقت التجهيز |
|--------|--------|------------|
| Telegram Bot Token | [@BotFather](https://t.me/BotFather) | دقيقة |
| Telegram User ID | [@userinfobot](https://t.me/userinfobot) | ثواني |
| Supabase URL + Keys | [supabase.com](https://supabase.com) | 5 دقايق |
| Gemini API Key | [AI Studio](https://aistudio.google.com) | دقيقتين |
| SeekAI API Key | حسابك على SeekAI | عندك بالفعل |
| GitHub account | لرفع الـ repo | عندك |
| Railway account | [railway.app](https://railway.app) | دقيقة |

---

## الخطوات بالترتيب

### الخطوة 1 — اعمل Telegram Bot

1. افتح [@BotFather](https://t.me/BotFather) على تليجرام
2. ابعت: `/newbot`
3. حدد اسم البوت (مثال: `شاهر`)
4. حدد username (لازم ينتهي بـ `bot`، مثال: `shaher_ii_bot`)
5. احتفظ بالـ **Token** اللي هيظهر — هتحتاجه لاحقًا

**لمعرفة Telegram User ID بتاعك:**
- ابعت أي رسالة لـ [@userinfobot](https://t.me/userinfobot)
- هيرد بالـ ID الرقمي بتاعك (مثال: `123456789`)

---

### الخطوة 2 — اعمل Supabase Project

1. روح [supabase.com](https://supabase.com) → **New Project**
2. اختار اسم (مثال: `shaher-brain`) وكلمة سر قوية
3. استنى لحد ما المشروع يجهز (~2 دقيقة)
4. من القائمة اليسرى → **SQL Editor**
5. انسخ كل محتوى `supabase/schema.sql` والصقه في الـ Editor
6. اضغط **Run** — المفروض يقول "Success"
7. من **Settings → API** احتفظ بـ:
   - `Project URL` (شكله: `https://xyz.supabase.co`)
   - `anon public` key
   - `service_role` key ⚠️ (سري جدًا)

---

### الخطوة 3 — احصل على Gemini API Keys

1. روح [Google AI Studio](https://aistudio.google.com)
2. من القائمة اليسرى → **Get API Key** → **Create API Key**
3. اعمل **مفتاح واحد** للبداية وحطه في `GEMINI_API_KEY_BRAIN`
4. الخطة: مفاتيح منفصلة لكل مكون لاحقًا (Brain, Trend, Browser)

> 💡 المفتاح المجاني = 1,500 طلب/يوم على Gemini 1.5 Flash. كافي جدًا للبداية. لو راح، SeekAI هيتولى تلقائيًا.

---

### الخطوة 4 — اعمل GitHub Repo وارفع الكود

```bash
# من جهازك، داخل مجلد المشروع
cd "C:\Users\Ncic\Desktop\شاهر\brain"

# initialize git
git init
git add .
git commit -m "feat: شاهر الثاني — المرحلة 1"

# اعمل repo جديد على github.com اسمه: shaher-ii (private)
# ثم:
git remote add origin https://github.com/YOUR_USERNAME/shaher-ii.git
git branch -M main
git push -u origin main
```

> ⚠️ **مهم**: تأكد إن `.gitignore` موجود وإن `.env` **مش** في الملفات المرفوعة. لو عملت `git status` المفروض `.env` مش في القائمة.

---

### الخطوة 5 — Railway Setup والـ Deploy ⭐

ده أهم قسم — اتبعه خطوة بخطوة:

#### 5.1 اعمل حساب على Railway
- روح [railway.app](https://railway.app)
- سجل دخول بـ GitHub مباشرة (أسهل)

#### 5.2 اعمل Project جديد
1. من Dashboard → **New Project**
2. اختار → **Deploy from GitHub repo**
3. لو أول مرة: اضغط **Configure GitHub App** وادّي Railway صلاحية الـ repo
4. اختار repo: `shaher-ii`
5. Railway هيبدأ يبني الـ project تلقائيًا (هيشوف `Procfile` و `railway.toml`)

#### 5.3 أضف Environment Variables
1. بعد ما المشروع يتعمل → اضغط على الـ **Service**
2. من القائمة → **Variables**
3. أضف كل متغير من `.env.example` بالقيم الحقيقية:

```
TELEGRAM_BOT_TOKEN       = [Token من BotFather]
SUPABASE_URL             = [URL من Supabase]
SUPABASE_ANON_KEY        = [anon key]
SUPABASE_SERVICE_ROLE_KEY = [service_role key]
GEMINI_API_KEY_BRAIN     = [Gemini key]
SEEKAI_API_KEY           = [SeekAI key]
SEEKAI_BASE_URL          = https://api.seekai.tools/v1
SEEKAI_IMAGE_MODEL       = flux
AUTHORIZED_USER_ID       = [Telegram User ID]
SETUP_SECRET             = [كلمة سر تختارها]
ENVIRONMENT              = production
```

> ⚠️ `WEBHOOK_BASE_URL` هتعرفه في الخطوة الجاية

#### 5.4 احصل على الـ Railway Domain
1. من الـ Service → **Settings** → **Networking**
2. اضغط **Generate Domain**
3. هيديك URL زي: `shaher-ii-production.up.railway.app`
4. ارجع لـ **Variables** وأضف:
   ```
   WEBHOOK_BASE_URL = https://shaher-ii-production.up.railway.app
   ```
5. اضغط **Deploy** (أو هيعمل redeploy تلقائي)

#### 5.5 تحقق إن الـ Deploy نجح
- من الـ **Deployments** tab، شوف آخر deployment
- لازم يكون **Active** (خضر)
- اضغط **View Logs** وتأكد من رسالة:
  ```
  INFO:     Application startup complete.
  ```

---

### الخطوة 6 — سجّل الـ Webhook في Telegram (مرة واحدة بس)

افتح المتصفح وروح على:
```
https://shaher-ii-production.up.railway.app/setup?secret=YOUR_SETUP_SECRET
```
(غيّر الـ URL والـ secret بالقيم الحقيقية)

المفروض يرد بـ:
```json
{
  "success": true,
  "webhook_url": "https://shaher-ii-production.up.railway.app/webhook"
}
```

---

### الخطوة 7 — اختبر شاهر!

افتح البوت على تليجرام وجرب:

| الرسالة | المتوقع |
|---------|---------|
| `/start` | رسالة ترحيب |
| `/status` | حالة النظام |
| `صباح الخير` | رد من Gemini (أو SeekAI كـ fallback) |
| `ولّدلي صورة غلاف يوتيوب عن البرمجة` | صورة من SeekAI |
| `فتكرني باللي قلناه قبل كده` | بيجيب من الذاكرة |
| رسالة صوتية | بيحولها لنص ويرد |

**تحقق من Supabase** → Table Editor:
- `interactions` — كل تفاعل متسجل
- `generated_images` — كل صورة اتولّدت

---

## Auto-Deploy عند كل Push

من الآن، أي `git push` على الـ `main` branch هيعمل deploy تلقائي:

```bash
# مثال: غيّرت حاجة في الكود
git add .
git commit -m "fix: تحسين في router"
git push origin main
# Railway هيشوف الـ push ويعمل deploy تلقائي خلال 1-2 دقيقة
```

---

## هيكل الملفات

```
brain/
├── .env.example           ← template المتغيرات
├── .gitignore             ← .env محمي
├── requirements.txt       ← المكتبات
├── railway.toml           ← Railway config
├── Procfile               ← start command
├── README.md              ← أنت هنا
│
├── bot/
│   ├── main.py            ← FastAPI: /webhook /health /setup
│   ├── telegram_handler.py ← معالجة النص والصوت والصور
│   └── voice_handler.py   ← Gemini multimodal transcription
│
├── brain/
│   ├── router.py          ← Shaher Brain (CHAT/IMAGE/MEMORY/CMD)
│   ├── ai_client.py       ← Gemini → SeekAI → Duck.ai
│   └── image_client.py    ← SeekAI Image API (flux/nano-banana/seedream)
│
├── memory/
│   ├── supabase_client.py ← Singleton client
│   └── logger.py          ← تسجيل تلقائي لكل تفاعل
│
└── supabase/
    └── schema.sql         ← 6 جداول + triggers + seed data
```

---

## استكشاف الأخطاء

| المشكلة | الحل |
|---------|------|
| البوت مش بيرد | روح `/health` وتأكد إنه شغال، ثم تحقق من الـ webhook بـ `/setup` |
| `SUPABASE_URL not found` | تحقق من Variables في Railway dashboard |
| Gemini rate limit | طبيعي — النظام ينتقل لـ SeekAI تلقائيًا |
| الصورة مش بتيجي | تحقق من `SEEKAI_API_KEY` وإن الموديل صح في `SEEKAI_IMAGE_MODEL` |
| Railway deployment فشل | شوف Logs → غالبًا missing dependency في `requirements.txt` |

---

*شاهر الثاني v1.0 — بُني بـ ❤️*
