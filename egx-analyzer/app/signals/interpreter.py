# -*- coding: utf-8 -*-
"""
Signal Engine: طبقة مستقلة تحوّل تصويت المؤشر الخام (+1/-1/0) لقراءة كاملة
مفهومة للمستخدم: قيمة + حالة (إيموجي) + تفسير نصي + درجة تأثير عددية على
القرار النهائي.

ليه طبقة منفصلة؟ عشان لو حبينا نغيّر شكل العرض أو طريقة حساب "التأثير"
مستقبلًا، نعدّل هنا بس من غير ما نلمس منطق حساب المؤشرات نفسه في
app/indicators/ أو منطق التصويت في app/analysis/scoring.py.

خاصية مهمة (اتفحصت في tests/test_signals.py): مجموع درجات التأثير لكل
المؤشرات النشطة يساوي الـ Score النهائي تقريبًا (فرق لا يتجاوز أجزاء من
النقطة بسبب التقريب المستقل لكل رقم على حدة)، لأن الاتنين مبنيين على نفس
معادلة الوزن (CATEGORY_WEIGHTS) وعدد المؤشرات في كل فئة.
"""

from app.config import CATEGORY_WEIGHTS

STATUS_ICONS = {1: "🟢", -1: "🔴", 0: "⚪"}


def compute_impact(vote: int, category: str, n_indicators_in_category: int) -> float:
    """
    يحوّل التصويت الخام لدرجة تأثير عددية موقّعة على الـ Score النهائي (من
    -100 إلى +100)، بناءً على وزن الفئة (CATEGORY_WEIGHTS) وعدد المؤشرات
    فيها. مثال: MACD في فئة الزخم (وزن 30%) ضمن 5 مؤشرات زخم، وتصويته
    هابط (-1) → التأثير = -1 × (100 × 0.30 / 5) = -6.0
    """
    if n_indicators_in_category <= 0:
        return 0.0
    weight = CATEGORY_WEIGHTS.get(category, 0)
    max_contribution = 100 * weight / n_indicators_in_category
    return round(vote * max_contribution, 2)


def interpret_indicator(
    name: str,
    vote: int,
    category: str,
    n_indicators_in_category: int,
    signal_text: str = "",
    value=None,
) -> dict:
    """
    يبني القراءة الكاملة لمؤشر واحد. لو signal_text فاضي (يعني بيانات غير
    كافية)، بيرجع تفسير صريح بدل ما يخترع قيمة.
    """
    return {
        "name": name,
        "value": value,
        "status_icon": STATUS_ICONS.get(vote, "⚪"),
        "interpretation": signal_text or "بيانات غير كافية",
        "impact": compute_impact(vote, category, n_indicators_in_category),
    }


def enrich_category_votes(category_votes: dict) -> dict:
    """
    يمرّ على مخرجات نظام التصويت (category -> {indicator_name: {vote, signal, ...}})
    ويضيف لكل مؤشر الحقول الجديدة (status_icon, impact) في نفس القاموس من
    غير ما يشيل أي حقل موجود - عشان أي كود قديم بيقرأ "vote" أو "signal"
    يفضل شغال زي ما هو.
    """
    for category, indicators in category_votes.items():
        n = len(indicators)
        for name, info in indicators.items():
            enriched = interpret_indicator(
                name=name,
                vote=info["vote"],
                category=category,
                n_indicators_in_category=n,
                signal_text=info.get("signal", ""),
                value=info.get("value"),
            )
            info["status_icon"] = enriched["status_icon"]
            info["impact"] = enriched["impact"]
    return category_votes
