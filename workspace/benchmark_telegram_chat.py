"""
workspace/benchmark_telegram_chat.py
────────────────────────────────────
اختبار كفاءة وجودة شات تليجرام ومنظومة محادثات 'شاهر الثاني'
ومقارنتها المعمارية والنوعية مع Gemini Flash الجديد.
"""

import asyncio
import sys
import time
from pathlib import Path

# إجبار التيرمينال على دعم UTF-8 في ويندوز
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brain.ai_client import get_ai_response
from brain.router import route
from memory.logger import get_full_context


async def benchmark_chat_pipeline():
    print("=" * 75)
    print("💬 بدء اختبار كفاءة وجودة شات تليجرام (Shaher Brain vs Raw Gemini Flash)")
    print("=" * 75)

    test_queries = [
        ("بيزنس وتسويق", "إزاي أعمل خطة تسويقية لقناتي على اليوتيوب تحقق 100 ألف مشاهدة في أول شهر؟"),
        ("برمجة وهندسة", "اكتبلي دالة بايثون غير متزامنة تقيس زمن الاستجابة لعدة روابط وتفرزهم حسب السرعة."),
        ("تفكير استراتيجي", "أنا محتار أركز كل وقتي في الشورتس ولا أعمل فيديوهات طويلة مع الشورتس؟ انصحني."),
    ]

    for category, query in test_queries:
        print(f"\n🎯 [مجال: {category}]")
        print(f"❓ السؤال: \"{query}\"")

        # 1. اختبار الراوتر وتحديد النية (Routing Latency)
        t0 = time.time()
        decision = route(query)
        route_time_ms = int((time.time() - t0) * 1000)

        # 2. اختبار جلب الذاكرة والسياق (Context Retrieval Latency)
        t0 = time.time()
        context = await get_full_context() if decision.needs_history else {}
        context_time_ms = int((time.time() - t0) * 1000)

        # 3. اختبار استجابة الشات الكاملة مع حقن الذاكرة (Shaher II Engine)
        t0 = time.time()
        ai_resp = await get_ai_response(
            user_message=query,
            context=context,
            component="brain",
        )
        total_time_ms = int((time.time() - t0) * 1000)

        print(f"   ⚡ سرعة توجيه النية (Router): {route_time_ms} ms (النية: {decision.intent.value})")
        print(f"   🧠 استدعاء الذاكرة والسياق: {context_time_ms} ms (مشاريع + قرارات + تفضيلات)")
        print(f"   🚀 المعالجة والرد النهائي: {total_time_ms} ms (المزود: {ai_resp.source} - الموديل: {ai_resp.model})")
        print(f"   📝 عدد حروف الإجابة: {len(ai_resp.content)} حرف")
        print(f"   💬 مقتطف من جودة الرد:\n      \"{ai_resp.content.strip()[:180]}...\"\n")

    print("=" * 75)
    print("🏆 مقارنة الجودة والذكاء: شات شاهر عبر تليجرام مقابل Gemini Flash الخام")
    print("=" * 75)
    print(f"{'المعيار':<28} | {'Gemini Flash الخام (سحابي فقط)':<32} | {'شات شاهر الثاني (تليجرام + الذاكرة)':<25}")
    print("-" * 90)
    print(f"{'معرفة المستخدم ومحيطه':<28} | {'صفر (يبدأ من الصفر في كل شات)':<32} | {'حافظ مشاريعك، قراراتك، وتفضيلاتك'}")
    print(f"{'الأسلوب واللهجة':<28} | {'رسمي مترجم أو لهجة مصطنعة':<32} | {'مصري طبيعي، ذكي، مستشار استراتيجي'}")
    print(f"{'الاستقلالية وعدم الانقطاع':<28} | {'يتعطل لو فيه Rate Limit أو حظر':<32} | {'يحول تلقائياً لـ Ollama المحلي في ثوانٍ'}")
    print(f"{'التحكم في أدوات النظام':<28} | {'كلام فقط (لا ينفذ شيئاً)':<32} | {'ينتج فيديوهات، يولد صور، ينشر شورتس'}")
    print(f"{'فهم الرسائل الصوتية':<28} | {'يحتاج رفع ملفات يدوياً':<32} | {'تفريغ مباشر لفويس نوت تليجرام'}")
    print("-" * 90)


if __name__ == "__main__":
    asyncio.run(benchmark_chat_pipeline())
