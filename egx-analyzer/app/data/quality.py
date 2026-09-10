# -*- coding: utf-8 -*-
"""
فحص جودة البيانات (Data Quality Validation) قبل التحليل الفني - عشان
نتأكد إن الإشارة مبنية على بيانات سليمة، مش نتيجة خطأ في المصدر (بيانات
ناقصة، شمعات مكررة، OHLC غير منطقي، انقسام سهم غير معدّل...).

القاعدة: لو البيانات فيها مشاكل جوهرية، النظام ميدّيش "إشارة قوية" حتى
لو المؤشرات نفسها بتقول كده - نعرض تحذير صريح بدل توصية واثقة على أساس
مهزوز.
"""

import logging

import numpy as np
import pandas as pd

log = logging.getLogger("data_quality")

# نسبة تغير يومي أعلى منها بنعتبرها مشبوهة (احتمال انقسام سهم غير معدّل
# أو خطأ بيانات) - 35% تحرك يومي حقيقي نادر جدًا حتى في أسواق متقلبة
SUSPICIOUS_DAILY_CHANGE_PCT = 35.0
# نسبة أيام بحجم تداول صفر أعلى منها تعتبر مشكلة جوهرية في البيانات
ZERO_VOLUME_WARNING_RATIO = 0.15


def validate_data_quality(df: pd.DataFrame) -> dict:
    """
    يفحص DataFrame بأعمدة Open/High/Low/Close/Volume ويرجع تقرير جودة
    شامل. is_valid=False يعني فيه مشكلة جوهرية (OHLC غير منطقي، بيانات
    مكررة) لازم تمنع أي "إشارة قوية". warnings الأخف (زي شك انقسام سهم)
    بتتسجل بس من غير ما تمنع التحليل تمامًا.
    """
    warnings = []
    critical_issues = []

    if df is None or df.empty:
        return {
            "is_valid": False,
            "has_critical_issues": True,
            "warnings": ["لا توجد بيانات إطلاقًا"],
            "critical_issues": ["empty_dataframe"],
        }

    required_cols = {"Open", "High", "Low", "Close", "Volume"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        return {
            "is_valid": False,
            "has_critical_issues": True,
            "warnings": [f"أعمدة مفقودة: {', '.join(missing_cols)}"],
            "critical_issues": ["missing_columns"],
        }

    # 1) بيانات ناقصة (NaN) في أعمدة أساسية
    missing_count = int(df[list(required_cols)].isna().sum().sum())
    if missing_count > 0:
        warnings.append(f"يوجد {missing_count} قيمة ناقصة (NaN) في بيانات OHLCV")

    # 2) شمعات مكررة (نفس التاريخ مرتين)
    duplicate_count = int(df.index.duplicated().sum())
    if duplicate_count > 0:
        critical_issues.append("duplicate_candles")
        warnings.append(f"يوجد {duplicate_count} شمعة مكررة بنفس التاريخ")

    # 3) ترتيب زمني غير صحيح (تواريخ مش تصاعدية)
    if not df.index.is_monotonic_increasing:
        critical_issues.append("timestamp_order_error")
        warnings.append("التواريخ مش مرتبة تصاعديًا - احتمال خطأ في مصدر البيانات")

    # 4) OHLC غير منطقي: أعلى سعر أقل من أدنى سعر، أو الإغلاق/الفتح خارج نطاق اليوم
    clean = df.dropna(subset=["Open", "High", "Low", "Close"])
    wrong_high_low = (clean["High"] < clean["Low"]).sum()
    wrong_close = ((clean["Close"] > clean["High"]) | (clean["Close"] < clean["Low"])).sum()
    wrong_open = ((clean["Open"] > clean["High"]) | (clean["Open"] < clean["Low"])).sum()
    wrong_ohlc_count = int(wrong_high_low + wrong_close + wrong_open)
    if wrong_ohlc_count > 0:
        critical_issues.append("invalid_ohlc")
        warnings.append(f"يوجد {wrong_ohlc_count} شمعة ببيانات OHLC غير منطقية (أعلى<أدنى أو إغلاق/فتح خارج النطاق)")

    # 5) حجم تداول سالب أو صفري بشكل متكرر
    if "Volume" in df.columns:
        negative_volume = int((df["Volume"] < 0).sum())
        if negative_volume > 0:
            critical_issues.append("negative_volume")
            warnings.append(f"يوجد {negative_volume} يوم بحجم تداول سالب")

        zero_volume_ratio = (df["Volume"] == 0).sum() / len(df) if len(df) else 0
        if zero_volume_ratio > ZERO_VOLUME_WARNING_RATIO:
            warnings.append(f"{zero_volume_ratio:.0%} من الأيام بحجم تداول صفري - قد يشير لسيولة ضعيفة جدًا أو مشكلة بيانات")

    # 6) تحرك سعري يومي مشبوه (احتمال انقسام سهم غير معدّل) - تحذير خفيف مش حرج
    pct_change = clean["Close"].pct_change().abs() * 100
    suspicious_days = int((pct_change > SUSPICIOUS_DAILY_CHANGE_PCT).sum())
    if suspicious_days > 0:
        warnings.append(
            f"يوجد {suspicious_days} يوم بتحرك سعري مفاجئ يتجاوز {SUSPICIOUS_DAILY_CHANGE_PCT:.0f}% - "
            "قد يكون انقسام سهم (Stock Split) غير معدّل في البيانات، أو خبر جوهري حقيقي"
        )

    has_critical = len(critical_issues) > 0
    return {
        "is_valid": not has_critical,
        "has_critical_issues": has_critical,
        "warnings": warnings,
        "critical_issues": critical_issues,
    }
