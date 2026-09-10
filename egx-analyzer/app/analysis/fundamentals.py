# -*- coding: utf-8 -*-
"""
طبقة تحليل أساسي تكميلية: تستخدم بيانات مالية (P/E, EPS, القيمة السوقية)
كطبقة تصفية إضافية فوق التحليل الفني، وليست بديلاً عنه.
"""

import logging

from app.data.mubasher_client import get_stock_data

log = logging.getLogger("fundamentals")


def get_fundamentals(symbol: str) -> dict:
    """يرجع البيانات المالية الأساسية المتاحة لسهم من صفحته على مباشر."""
    data = get_stock_data(symbol)
    return {
        "symbol": symbol.upper(),
        "name": data.get("name"),
        "market_cap": data.get("market_cap"),
        "eps": data.get("eps"),
        "pe_ratio": data.get("pe_ratio"),
        "error": data.get("error"),
    }


def adjust_recommendation_with_fundamentals(
    technical_score: float,
    fundamentals: dict,
    sector_avg_pe: float = None,
) -> dict:
    """
    يعدّل قوة الثقة في التوصية الفنية بناءً على مؤشر أساسي بسيط: هل مضاعف
    الربحية (P/E) للسهم مبالغ فيه مقارنة بمتوسط القطاع؟ هذه طبقة تكميلية
    اختيارية - التوصية الأساسية تظل معتمدة على الـ score الفني.
    """
    pe = fundamentals.get("pe_ratio")
    note = "لا توجد بيانات P/E كافية لتطبيق الفلتر الأساسي."
    adjusted_score = technical_score

    if pe is not None and sector_avg_pe:
        if pe > sector_avg_pe * 1.5 and technical_score > 0:
            # مضاعف ربحية مبالغ فيه يقلل الثقة في إشارة الشراء الفنية
            adjusted_score = technical_score * 0.7
            note = f"P/E ({pe}) أعلى بكثير من متوسط القطاع ({sector_avg_pe}) - تم تخفيف قوة إشارة الشراء."
        elif pe < sector_avg_pe * 0.7 and technical_score < 0:
            # مضاعف ربحية منخفض جدًا قد يخفف قوة إشارة البيع
            adjusted_score = technical_score * 0.7
            note = f"P/E ({pe}) أقل بكثير من متوسط القطاع ({sector_avg_pe}) - تم تخفيف قوة إشارة البيع."
        else:
            note = "P/E ضمن نطاق معقول مقارنة بمتوسط القطاع - لا تعديل."

    return {
        "original_score": technical_score,
        "adjusted_score": round(adjusted_score, 1),
        "note": note,
    }
