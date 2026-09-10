# -*- coding: utf-8 -*-
"""
Multi-Timeframe Confirmation: يحلل نفس السهم على إطارين زمنيين (أصغر
"أساسي" وأكبر "مرجعي")، ويمنع الإطار الأصغر من إعطاء توصية شراء نشطة لو
الاتجاه على الإطار الأكبر هابط بقوة. الهدف: جودة الإشارة، مش عددها -
سهم ممكن يطلع "شراء قوي" على اليومي رغم إن الاتجاه العام (الأسبوعي)
هابط بشدة، وده بالظبط نوع الإشارات الكاذبة اللي المفروض نقللها.

ملحوظة تصميم: بنحسب "درجة اتجاه نقية" من فئة الاتجاه بس (SMA/ADX/SAR/
Ichimoku) مش الـ Score الكامل، عشان الزخم/الحجم على الإطار الأكبر ميأثرش
على قرار "هل الاتجاه العام صاعد ولا هابط" - ده سؤال عن الاتجاه تحديدًا.
"""

from app.analysis.scoring import analyze_stock

# عتبات تصنيف الاتجاه (من درجة اتجاه نقية بين -100 و+100)
TREND_THRESHOLDS = {
    "strong_bullish": 40,
    "bullish": 15,
    "bearish": -15,
    "strong_bearish": -40,
}


def _pure_category_score(categories: dict, category_name: str) -> float:
    """متوسط أصوات فئة واحدة بس (من غير وزن أو دمج مع فئات تانية) - يعبّر عن اتجاه الفئة دي تحديدًا."""
    indicators = categories.get(category_name, {})
    votes = [info["vote"] for info in indicators.values()]
    if not votes:
        return 0.0
    return round(sum(votes) / len(votes) * 100, 1)


def classify_trend(pure_trend_score: float) -> str:
    t = TREND_THRESHOLDS
    if pure_trend_score >= t["strong_bullish"]:
        return "صاعد بقوة"
    if pure_trend_score >= t["bullish"]:
        return "صاعد"
    if pure_trend_score <= t["strong_bearish"]:
        return "هابط بقوة"
    if pure_trend_score <= t["bearish"]:
        return "هابط"
    return "عرضي"


def analyze_multi_timeframe(
    symbol: str,
    primary_timeframe: str = "daily",
    primary_period: str = "1y",
    higher_timeframe: str = "weekly",
    higher_period: str = "2y",
) -> dict:
    """
    يحلل السهم على إطارين، ويرجع توصية "نهائية" بعد بوابة التأكيد، مع
    توضيح صريح لو تم تخفيف/تجميد الإشارة وليه.
    """
    primary = analyze_stock(symbol, timeframe=primary_timeframe, period=primary_period)
    higher = analyze_stock(symbol, timeframe=higher_timeframe, period=higher_period)

    higher_trend_score = _pure_category_score(higher["categories"], "trend")
    higher_trend_class = classify_trend(higher_trend_score)

    primary_recommendation = primary["recommendation"]
    is_primary_buy = "شراء" in primary_recommendation

    gate_applied = False
    gate_reason = None
    final_recommendation = primary_recommendation
    final_trade_plan_status = primary["trade_plan"]["status"]
    final_trade_plan_label = primary["trade_plan"]["status_label"]

    if higher_trend_class == "هابط بقوة" and is_primary_buy:
        gate_applied = True
        gate_reason = (
            f"الإطار الأكبر ({higher_timeframe}) هابط بقوة (درجة اتجاه {higher_trend_score:+.1f}/100) "
            f"- تم تخفيف قوة إشارة الشراء على الإطار الأصغر ({primary_timeframe}) بدل عرضها كما هي."
        )
        final_recommendation = (
            "شراء (خُفِّفت من قوي - تعارض مع الاتجاه الأكبر)"
            if "قوي" in primary_recommendation
            else "محايد / انتظار (تعارض مع الاتجاه الأكبر)"
        )
        if final_trade_plan_status == "valid_long_setup":
            final_trade_plan_status = "gated_by_higher_timeframe"
            final_trade_plan_label = (
                "⚪ تم تجميد خطة التنفيذ - الاتجاه الأكبر هابط بقوة رغم إشارة الشراء "
                "على الإطار الأصغر. انتظر توافق الإطارين قبل الدخول."
            )

    return {
        "symbol": symbol.upper(),
        "primary_timeframe": primary_timeframe,
        "higher_timeframe": higher_timeframe,
        "primary_score": primary["score"],
        "primary_recommendation": primary_recommendation,
        "higher_trend_score": higher_trend_score,
        "higher_trend_classification": higher_trend_class,
        "gate_applied": gate_applied,
        "gate_reason": gate_reason,
        "final_recommendation": final_recommendation,
        "final_trade_plan_status": final_trade_plan_status,
        "final_trade_plan_label": final_trade_plan_label,
        "primary_analysis": primary,
        "higher_analysis": higher,
    }
