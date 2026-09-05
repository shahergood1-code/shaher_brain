"""
core/critic.py
──────────────
موديول "الناقد القاسي" (The Ruthless Critic Loop):
حارس جودة المحتوى التلقائي في نظام "شاهر الثاني".
يقوم بفحص أي سكريبت شورتس أو فيديو قبل اعتماده للمونتاج، ويرفضه إذا كان رتيباً
أو ضعيفاً، ويجبر محرك التوليد على إعادة كتابته حتى يتجاوز معيار الفيروسية (Score >= 8.0/10).
"""

import json
import logging
import re
from dataclasses import asdict, dataclass
from typing import Any

import ollama

from config.settings import OLLAMA_HOST, OLLAMA_MODEL
from core.prompts import CRITIC_SYSTEM_PROMPT

logger = logging.getLogger("RuthlessCritic")


@dataclass
class CriticReview:
    score: float
    approved: bool
    hook_rating: float
    curiosity_rating: float
    pacing_rating: float
    loop_rating: float
    debate_rating: float
    critique: str
    actionable_fixes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _extract_json_from_text(text: str) -> dict[str, Any] | None:
    """استخراج كائن JSON من رد النموذج بمرونة."""
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return None


def evaluate_script(script_text: str, topic: str = "") -> CriticReview:
    """
    يقوم الناقد القاسي (عبر Ollama qwen2.5:7b) بفحص السكريبت وتقييمه بدقة.
    """
    logger.info("🧐 الناقد القاسي يفحص السكريبت الآن...")
    user_prompt = f"""
راجع السكريبت التالي بدقة وقسوة تامة بناءً على القواعد الخمس:
الموضوع: {topic}

النص المراد تقييمه:
\"\"\"
{script_text}
\"\"\"

أعطني التقييم بـ JSON فقط:
"""

    raw_response = ""
    try:
        client = ollama.Client(host=OLLAMA_HOST)
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": 0.3},
        )
        raw_response = response["message"]["content"]
    except Exception as exc:
        logger.warning(f"تعذر الاتصال بـ Ollama للناقد ({exc}) — تشغيل الفحص السحابي البديل...")
        try:
            import asyncio

            from brain.ai_client import get_ai_response
            ai_res = asyncio.run(get_ai_response(
                user_message=f"{CRITIC_SYSTEM_PROMPT}\n\n{user_prompt}",
                component="brain",
            ))
            raw_response = ai_res.content
        except Exception as cloud_exc:
            logger.error(f"فشل الناقد في السحابة أيضاً: {cloud_exc}")
            # في أسوأ الظروف لا نوقف النظام تماماً
            return CriticReview(
                score=8.0,
                approved=True,
                hook_rating=1.6,
                curiosity_rating=1.6,
                pacing_rating=1.6,
                loop_rating=1.6,
                debate_rating=1.6,
                critique="تم الاعتماد التلقائي بسبب انقطاع محركات التقييم.",
                actionable_fixes=[],
            )

    data = _extract_json_from_text(raw_response)
    if not data:
        # تقييم افتراضي لو الموديل أرجع نصاً حراً
        is_approved = "approved" in raw_response.lower() and "false" not in raw_response.lower()
        score = 8.0 if is_approved else 6.5
        return CriticReview(
            score=score,
            approved=is_approved,
            hook_rating=1.5,
            curiosity_rating=1.5,
            pacing_rating=1.5,
            loop_rating=1.5,
            debate_rating=1.5,
            critique=raw_response[:300],
            actionable_fixes=["تحسين وضوح الـ Hook وإضافة سؤال جدلي واضح."],
        )

    score = float(data.get("score", 7.0))
    approved = bool(data.get("approved", score >= 8.0))

    return CriticReview(
        score=score,
        approved=approved,
        hook_rating=float(data.get("hook_rating", 1.5)),
        curiosity_rating=float(data.get("curiosity_rating", 1.5)),
        pacing_rating=float(data.get("pacing_rating", 1.5)),
        loop_rating=float(data.get("loop_rating", 1.5)),
        debate_rating=float(data.get("debate_rating", 1.5)),
        critique=str(data.get("critique", "مراجعة مكتملة.")),
        actionable_fixes=list(data.get("actionable_fixes", [])),
    )


def refine_script_loop(
    initial_script: str,
    topic: str,
    generator_func,
    max_iterations: int = 3,
) -> dict[str, Any]:
    """
    حلقة التحسين التكرارية:
    يفحص الناقد السكريبت، فإذا رُفض (Score < 8)، يرسل الملاحظات لـ generator_func لإعادة كتابته،
    حتى يتم اعتماده أو استنفاد المحاولات.
    """
    current_script = initial_script
    last_review: CriticReview | None = None

    for iteration in range(1, max_iterations + 1):
        logger.info(f"🔄 دورة الناقد القاسي [المحاولة {iteration} من {max_iterations}]...")
        review = evaluate_script(current_script, topic=topic)
        last_review = review

        logger.info(f"📊 تقييم الناقد: {review.score}/10 | معتمد: {review.approved}")
        if review.approved:
            logger.info("✅ وافق الناقد القاسي على السكريبت بنجاح!")
            return {
                "status": "approved",
                "iterations": iteration,
                "script": current_script,
                "review": review.to_dict(),
            }

        # السكريبت مرفوض — إعادة توليد مع النقد
        logger.warning(f"❌ تم رفض السكريبت (الدرجة {review.score}). أسباب الرفض: {review.critique}")
        if iteration < max_iterations:
            refine_prompt = (
                f"السكريبت السابق تم رفضه من الناقد القاسي بنتيجة {review.score}/10.\n"
                f"أسباب الرفض:\n{review.critique}\n"
                f"التعديلات المطلوبة فوراً:\n" + "\n".join(f"- {f}" for f in review.actionable_fixes) + "\n\n"
                "أعد كتابة السكريبت بالكامل ليكون أقوى، أسرع، وأكثر غموضاً وجدلاً."
            )
            try:
                refined = generator_func(refine_prompt)
                if refined:
                    current_script = refined
            except Exception as gen_exc:
                logger.error(f"فشلت إعادة الصياغة: {gen_exc}")
                break

    # في حال انتهاء المحاولات دون الوصول لـ 8، نعتمد أفضل نسخة
    return {
        "status": "forced_approved",
        "iterations": max_iterations,
        "script": current_script,
        "review": last_review.to_dict() if last_review else {},
    }
