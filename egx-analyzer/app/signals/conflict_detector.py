# -*- coding: utf-8 -*-
"""
كشف "تضارب قوي بين المؤشرات" - حالة مختلفة تمامًا عن مجرد "سوق هادئ
بدون اتجاه واضح". لو عدد كبير من المؤشرات نشط (مش محايد) لكن منقسم
بالتساوي تقريبًا بين صاعد وهابط، ده مؤشر على عدم يقين حقيقي وتذبذب في
قراءة السوق - مش غياب إشارة. الفرق مهم: سوق هادئ = "مفيش حاجة تستاهل"،
سوق متضارب بشدة = "فيه حاجة بس مش واضحة، والمخاطرة أعلى من الظاهر".

النظام في الحالة دي بيرفض يجبر نفسه على توصية "شراء" أو "بيع" حتى لو
الـ Score التجميعي طلع يميل لجهة معينة بالصدفة - ويعرض NO TRADE صراحة.
"""

MIN_ACTIVE_INDICATORS_FOR_CONFLICT = 6  # أقل عدد مؤشرات نشطة (غير محايدة) قبل ما نعتبر أي انقسام "تضارب حقيقي"
CONFLICT_RATIO_THRESHOLD = 0.6  # نسبة الأقل للأكتر - كل ما اقتربت من 1 كل ما الانقسام متساوي أكتر


def detect_conflict(indicators_bullish: int, indicators_bearish: int) -> dict:
    """
    يرجع {is_conflicted, conflict_ratio, reason}. is_conflicted بيبقى True
    بس لو فيه عدد كافٍ من المؤشرات النشطة (مش قليل عشوائي) ومنقسمة بشكل
    متقارب جدًا بين الاتجاهين.
    """
    total_active = indicators_bullish + indicators_bearish
    if total_active < MIN_ACTIVE_INDICATORS_FOR_CONFLICT:
        return {"is_conflicted": False, "conflict_ratio": 0.0, "reason": None}

    larger = max(indicators_bullish, indicators_bearish)
    smaller = min(indicators_bullish, indicators_bearish)
    conflict_ratio = round(smaller / larger, 2) if larger > 0 else 0.0

    if conflict_ratio >= CONFLICT_RATIO_THRESHOLD:
        return {
            "is_conflicted": True,
            "conflict_ratio": conflict_ratio,
            "reason": (
                f"{indicators_bullish} مؤشر صاعد مقابل {indicators_bearish} مؤشر هابط "
                f"(تقارب {conflict_ratio:.0%} بين الجهتين) - المؤشرات بتتعارك مع بعض فعليًا، "
                f"مش مجرد غياب اتجاه واضح."
            ),
        }
    return {"is_conflicted": False, "conflict_ratio": conflict_ratio, "reason": None}
