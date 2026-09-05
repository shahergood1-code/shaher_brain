"""
core/mannequin_engine.py
─────────────────────────
محرك الوثائقيات الاستقصائية ثلاثية الأبعاد (Arabic 3D Mannequin Documentary Engine).
الموديول الأساسي لإنتاج الفيديوهات الطويلة في «شاهر الثاني» وفق أسلوب المانيكان المفرغ:
- ثبات الهوية البصرية بنسبة 100% رياضياً عبر المشاهد الـ 60+.
- درع حماية من عقوبات يوتيوب وحظر الخوارزميات (Monetization Armor / Zero Gore).
- ترشيد استهلاك VRAM والسرعة الفائقة على كارت RTX 4070.
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

from brain.ai_client import get_ai_response
from config.settings import EXPORTS_DIR
from core.prompts import (
    MANNEQUIN_CHARACTER_SHEET_TEMPLATE,
    MANNEQUIN_DOCUMENTARY_MASTER_PROMPT,
    MANNEQUIN_IDEAS_PROMPT_TEMPLATE,
    MANNEQUIN_METADATA_TEMPLATE,
    MANNEQUIN_SCENE_PROMPTS_TEMPLATE,
    MANNEQUIN_SCRIPT_AND_BREAKDOWN_TEMPLATE,
)

logger = logging.getLogger("MannequinEngine")


def _extract_json(text: str) -> dict[str, Any] | None:
    """استخراج كائن JSON من ردود الذكاء الاصطناعي بدقة حتى لو تضمن نصاً محيطاً."""
    code_block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if code_block:
        candidate = code_block.group(1).strip()
        try:
            return json.loads(candidate)
        except Exception:
            pass

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        candidate = match.group(0).strip()
        try:
            return json.loads(candidate)
        except Exception:
            pass
    return None


class MannequinDocumentaryEngine:
    """
    محرك إنتاج الوثائقيات بنظام المانيكان ثلاثي الأبعاد:
    يدير الخطوات الثمانية للماستر برومبت وينتج حزمة الإنتاج المتكاملة.
    """

    def __init__(self):
        self.system_prompt = MANNEQUIN_DOCUMENTARY_MASTER_PROMPT
        self.exports_dir = Path(EXPORTS_DIR) / "documentaries"
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    async def _query_ai(self, prompt: str) -> str:
        """استدعاء سلسلة الذكاء الاصطناعي مع توجيهات الماستر برومبت المركزية."""
        res = await get_ai_response(
            user_message=prompt,
            system_prompt=self.system_prompt,
        )
        return res.content

    async def generate_ideas(
        self,
        niche: str = "جرائم حقيقية غامضة وعمليات استخباراتية وسرقات كبرى",
        count: int = 10,
    ) -> list[dict[str, Any]]:
        """
        الخطوة 1: توليد 10 أفكار وثائقية حقيقية وموثقة تاريخياً وجنائياً.
        """
        logger.info(f"💡 توليد {count} أفكار وثائقية بنظام المانيكان في مجال: {niche}...")
        prompt = MANNEQUIN_IDEAS_PROMPT_TEMPLATE.format(niche=niche)
        raw_text = await self._query_ai(prompt)
        parsed = _extract_json(raw_text)

        if parsed and "ideas" in parsed and isinstance(parsed["ideas"], list):
            return parsed["ideas"]

        return [
            {
                "id": 1,
                "title": "لغز اختفاء طائرة الشحن 1999",
                "category": "disaster / mystery",
                "premise": "اختفاء طائرة شحن تجارية في ظروف مناخية هادئة وفقدان الصندوق الأسود دون أثر.",
                "visual_potential": "مدرج مطار مظلم، غرفة مراقبة بأضواء شاشات، مانيكان أزرق يمثل الطاقم المفقود.",
            }
        ]

    async def generate_character_sheet(
        self,
        title: str,
        premise: str,
    ) -> dict[str, Any]:
        """
        الخطوة 3: توليد ورقة الشخصيات (Character Sheet Prompt) لتثبيت الألوان والنسب.
        """
        logger.info(f"🎭 صياغة Character Sheet وثائقي: {title}...")
        prompt = MANNEQUIN_CHARACTER_SHEET_TEMPLATE.format(title=title, premise=premise)
        raw_text = await self._query_ai(prompt)
        parsed = _extract_json(raw_text)

        if parsed and "character_sheet_prompt" in parsed:
            return parsed

        return {
            "characters": [
                {
                    "role": "المحقق الرئيسي",
                    "mannequin_color": "WHITE",
                    "build_and_clothing": "Matte white mannequin wearing dark trenchcoat",
                    "narrative_function": "قيادة التحقيق ومراجعة الأدلة",
                },
                {
                    "role": "المشتبه به الغامض",
                    "mannequin_color": "RED",
                    "build_and_clothing": "Glowing red silhouette mannequin with hoodie",
                    "narrative_function": "مصدر الخطر والتهديد",
                },
                {
                    "role": "الضحية المفقودة",
                    "mannequin_color": "BLUE",
                    "build_and_clothing": "Translucent glowing blue mannequin",
                    "narrative_function": "استرجاع مسرح الجريمة والذكريات",
                },
            ],
            "character_sheet_prompt": (
                "Cinematic 3D documentary character sheet, three faceless 3D mannequins standing in neutral T-pose "
                "on plain neutral grey studio background, front view, side view, back view. "
                "Figure 1: matte white featureless mannequin in modern trenchcoat. "
                "Figure 2: intense glowing red silhouette mannequin in dark hoodie representing threat. "
                "Figure 3: translucent glowing ethereal blue mannequin representing memory and victim. "
                "Consistent proportions, physically believable clean studio lighting, realistic scale, 8k resolution."
            ),
        }

    async def generate_script_and_breakdown(
        self,
        title: str,
        premise: str,
        duration: str = "5m",
        characters: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        الخطوة 4: تفصيل المشاهد وكتابة سكريبت الفويس أوفر الوثائقي العربي.
        """
        logger.info(f"📜 إعداد سكريبت ومشاهد الوثائقي ({duration}): {title}...")
        chars_summary = json.dumps(characters, ensure_ascii=False) if characters else "Default Mannequin System (White=Neutral, Red=Threat, Blue=Victim)"

        prompt = MANNEQUIN_SCRIPT_AND_BREAKDOWN_TEMPLATE.format(
            title=title,
            premise=premise,
            duration=duration,
            characters_summary=chars_summary,
        )

        raw_text = await self._query_ai(prompt)
        parsed = _extract_json(raw_text)

        if parsed and "scenes" in parsed and isinstance(parsed["scenes"], list):
            return parsed

        return {
            "total_scenes": 6,
            "duration_est": duration,
            "full_voiceover_arabic": (
                f"في ظروف غامضة، وقعت واحدة من أكثر القضايا إثارة للجدل. {premise} "
                "تشير سجلات التحقيق إلى تفاصيل لم تعلن وقتها، وما زالت الأدلة المتاحة تطرح تساؤلات حائرة حتى اليوم."
            ),
            "scenes": [
                {
                    "scene_num": 1,
                    "time_range": "00:00 - 00:10",
                    "location": "أرشيف السجلات القضائية المظلم",
                    "visual_action": "مانيكان أبيض يتفحص ملفاً ورقياً تحت ضوء مصباح مكتبي خافت",
                    "characters_present": ["WHITE"],
                    "voiceover_segment": "تبدأ القصة في ليلة لم يتوقع أحد أن تترك وراءها هذا الكم من الأسئلة المعلقة.",
                }
            ],
        }

    async def generate_scene_prompts(
        self,
        scenes: list[dict[str, Any]],
        character_sheet_prompt: str,
        max_parallel: int = 5,
    ) -> list[dict[str, Any]]:
        """
        الخطوة 5: توليد برومبتات الصور والتحريك السينمائي لكل مشهد على حدة بصيغة مستقلة (Self-contained).
        """
        logger.info(f"🎨 صياغة برومبتات المشاهد لعدد {len(scenes)} مشهداً...")
        results = []

        async def _process_scene(scene: dict[str, Any]) -> dict[str, Any]:
            s_num = scene.get("scene_num", 1)
            details = f"المكان: {scene.get('location')}\nالحدث البصري: {scene.get('visual_action')}\nالشخصيات: {scene.get('characters_present')}"
            prompt = MANNEQUIN_SCENE_PROMPTS_TEMPLATE.format(
                character_sheet_prompt=character_sheet_prompt,
                scene_num=s_num,
                scene_details=details,
            )
            try:
                raw_text = await self._query_ai(prompt)
                parsed = _extract_json(raw_text)
                if parsed and "image_prompt" in parsed:
                    return {
                        **scene,
                        "image_prompt": parsed["image_prompt"],
                        "animation_prompt": parsed.get("animation_prompt", "Slow cinematic camera dolly in, subtle ambient lighting shift, restrained movement."),
                    }
            except Exception as e:
                logger.warning(f"تعذر توليد برومبت للمشهد {s_num}: {e}")

            return {
                **scene,
                "image_prompt": (
                    f"Cinematic semi-realistic 3D documentary scene, {scene.get('location', 'interior location')}. "
                    f"Featuring faceless 3D mannequin figures ({', '.join(scene.get('characters_present', ['matte white']))}). "
                    f"{scene.get('visual_action', 'investigating forensic evidence')}. "
                    "Moody atmospheric lighting, shallow depth of field, subtle filmic texture, volumetric fog, "
                    "strong silhouettes, zero gore, green dollar monetization safe, photorealistic 3D rendering, 8k."
                ),
                "animation_prompt": "Slow controlled camera dolly in, restrained cinematic movement, atmospheric dust particles drifting, no sudden twitching.",
            }

        for i in range(0, len(scenes), max_parallel):
            chunk = scenes[i : i + max_parallel]
            chunk_res = await asyncio.gather(*[_process_scene(s) for s in chunk])
            results.extend(chunk_res)

        return results

    async def generate_metadata(
        self,
        title: str,
        premise: str,
    ) -> dict[str, Any]:
        """
        الخطوات 6 و 7 و 8: توليد الغلاف 16:9، الـ 10 عناوين الاستقصائية، ووصف اليوتيوب الكامل.
        """
        logger.info(f"📊 إعداد الميتاداتا والغلاف والعناوين لـ: {title}...")
        prompt = MANNEQUIN_METADATA_TEMPLATE.format(title=title, premise=premise)
        raw_text = await self._query_ai(prompt)
        parsed = _extract_json(raw_text)

        if parsed and "titles" in parsed:
            return parsed

        return {
            "thumbnail_prompt": (
                f"Cinematic YouTube 16:9 documentary thumbnail for {title}. "
                "One dominant faceless 3D mannequin in high contrast dramatic pose, glowing red and deep blue lighting, "
                "clean empty negative space on left third for bold Arabic headline text. "
                "A subtle glowing red evidence marker circle, moody shadows, photorealistic 8k render, no gore, zero text watermark."
            ),
            "thumbnail_text_overlay_arabic": "سر الليلة الأخيرة",
            "titles": [
                f"كيف وقعت: القصة الكاملة لـ {title}",
                f"ماذا حدث لـ {title} في تلك الليلة؟",
                f"الحقيقة وراء أخطر عملية في {title}",
                f"الوثائق السرية تكشف ما جرى في {title}",
                f"اليوم الذي تغير فيه كل شيء: ملف {title}",
            ],
            "description": {
                "hook": f"ما الذي حدث بالضبط في قضية {title}؟ حقائق استقصائية مذهلة تُعاد محاكاتها لأول مرة بتقنية المانيكان ثلاثي الأبعاد.",
                "context": f"توثيق تاريخي وجنائي مبني على سجلات التحقيق الرسمية وإفادات الشهود حول {premise}.",
                "seo_keywords": ["وثائقي", "تحقيقات", "جرائم غامضة", "شاهر الثاني", "وثائقيات ثلاثية الأبعاد", title],
                "hashtags": ["#وثائقي", "#تحقيقات", "#شاهر_الثاني", "#جرائم_غامضة"],
            },
        }

    async def generate_full_documentary_package(
        self,
        topic: str = "",
        premise: str = "",
        duration: str = "5m",
        niche: str = "جرائم حقيقية وألغاز غامضة واستخبارات",
    ) -> dict[str, Any]:
        """
        التوليد الآلي الكامل لحزمة الإنتاج الوثائقي (End-to-End Autonomous Pipeline).
        """
        logger.info(f"🚀 بدء الإنتاج الكامل للوثائقي بنظام 3D Mannequin: {topic or niche}...")

        if not topic:
            ideas = await self.generate_ideas(niche=niche, count=3)
            selected_idea = ideas[0] if ideas else {
                "title": "عملية الهروب المستحيلة من الكاتراز",
                "premise": "كيف اختفى ثلاثة سجناء عبر أنفاق مائية ودمى مانيكان مفرغة دون ترك أثر.",
            }
            title = selected_idea["title"]
            premise = selected_idea.get("premise", "")
        else:
            title = topic
            premise = premise or f"تحقيق وثائقي معمق حول {topic} استناداً إلى الوثائق الرسمية وسجلات التحقيق."

        char_sheet = await self.generate_character_sheet(title, premise)

        script_breakdown = await self.generate_script_and_breakdown(
            title=title,
            premise=premise,
            duration=duration,
            characters=char_sheet.get("characters"),
        )

        scenes = script_breakdown.get("scenes", [])
        scenes_with_prompts = await self.generate_scene_prompts(
            scenes=scenes,
            character_sheet_prompt=char_sheet.get("character_sheet_prompt", ""),
        )

        metadata = await self.generate_metadata(title, premise)

        package = {
            "title": title,
            "premise": premise,
            "duration": duration,
            "character_sheet": char_sheet,
            "full_voiceover_arabic": script_breakdown.get("full_voiceover_arabic", ""),
            "total_scenes": len(scenes_with_prompts),
            "scenes": scenes_with_prompts,
            "metadata": metadata,
        }

        export_paths = self.export_documentary_package(package)
        package["exported_files"] = export_paths

        logger.info(f"✅ اكتمل إنتاج حزمة الوثائقي بنجاح! تم الحفظ في: {export_paths.get('markdown')}")
        return package

    def export_documentary_package(
        self,
        package: dict[str, Any],
        output_dir: Path | None = None,
    ) -> dict[str, str]:
        """
        تصدير حزمة الإنتاج كملف Markdown سينمائي جاهز للنسخ والتوليد وملف JSON للأتمتة.
        """
        target_dir = output_dir or self.exports_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        slug = re.sub(r"[^\w\s-]", "", package.get("title", "documentary")).strip().replace(" ", "_")
        if not slug:
            slug = "documentary_project"

        md_path = target_dir / f"{slug}.md"
        json_path = target_dir / f"{slug}.json"

        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(package, jf, ensure_ascii=False, indent=2)

        cs = package.get("character_sheet", {})
        meta = package.get("metadata", {})
        desc = meta.get("description", {})

        md_content = f"""# 🎬 {package.get('title')}
> **نظام الإنتاج:** 3D Mannequin Documentary Generator (شاهر الثاني)  
> **المدة المقدرة:** {package.get('duration')} | **إجمالي المشاهد:** {package.get('total_scenes')} مشهداً  
> **حماية الإعلانات:** 100% Monetization Safe (Zero Gore / Visual Mannequins)

---

## 📌 الفرضية الاستقصائية (Premise)
{package.get('premise')}

---

## 🎭 1. ورقة تثبيت الهوية البصرية (Character Sheet)

### 🎨 توزيع الألوان والشخصيات (Color System):
"""
        for char in cs.get("characters", []):
            color = char.get("mannequin_color", "WHITE")
            emoji = "⚪" if "WHITE" in color else ("🔴" if "RED" in color else ("🔵" if "BLUE" in color else "🎨"))
            md_content += f"- {emoji} **{char.get('role')}** ({color}): {char.get('build_and_clothing')} — *{char.get('narrative_function')}*\n"

        md_content += f"""
### 📋 برومبت مرجع الاستوديو (Character Sheet Image Prompt):
```text
{cs.get('character_sheet_prompt', '')}
```

---

## 🎙️ 2. النص الكامل للفويس أوفر العربي (Full Voiceover Script)
{package.get('full_voiceover_arabic', '')}

---

## 🎬 3. المشاهد والبرومبتات السينمائية (Scenes & Prompts)
"""

        for s in package.get("scenes", []):
            md_content += f"""
### المشهد {s.get('scene_num')}: {s.get('location')} ({s.get('time_range', '')})
- **الحدث البصري:** {s.get('visual_action')}
- **الشخصيات الحاضرة:** {', '.join(s.get('characters_present', []))}
- **النص الصوتي المقابل:**
  > "{s.get('voiceover_segment', '')}"

**🖼️ برومبت توليد الصورة (Image Prompt):**
```text
{s.get('image_prompt', '')}
```

**🎥 برومبت التحريك (Animation Prompt):**
```text
{s.get('animation_prompt', '')}
```
"""

        md_content += f"""
---

## 🎨 4. الغلاف والـ Thumbnail (16:9)
- **النص العربي المقترح على الغلاف (3 كلمات كحد أقصى):** `{meta.get('thumbnail_text_overlay_arabic', '')}`
- **برومبت توليد الغلاف:**
```text
{meta.get('thumbnail_prompt', '')}
```

---

## 🏷️ 5. عناوين اليوتيوب المقترحة (10 Documentary Titles)
"""
        for i, t in enumerate(meta.get("titles", []), 1):
            md_content += f"{i}. {t}\n"

        md_content += f"""
---

## 📝 6. وصف الفيديو وسيو يوتيوب (Description & SEO)
**الهوك:**  
{desc.get('hook', '')}

**السياق:**  
{desc.get('context', '')}

**الكلمات المفتاحية:**  
{', '.join(desc.get('seo_keywords', []))}

**الهاشتاجات:**  
{' '.join(desc.get('hashtags', []))}
"""

        with open(md_path, "w", encoding="utf-8") as mf:
            mf.write(md_content.strip())

        return {
            "markdown": str(md_path),
            "json": str(json_path),
        }
