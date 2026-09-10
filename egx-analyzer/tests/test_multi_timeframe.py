# -*- coding: utf-8 -*-
"""اختبارات وحدة لـ Multi-Timeframe Confirmation (app/analysis/multi_timeframe.py)."""

from unittest.mock import patch

from app.analysis import multi_timeframe as mtf


def _fake_analysis(recommendation, score, trend_votes, trade_plan_status="valid_long_setup"):
    return {
        "score": score,
        "recommendation": recommendation,
        "categories": {"trend": {f"ind{i}": {"vote": v} for i, v in enumerate(trend_votes)}},
        "trade_plan": {"status": trade_plan_status, "status_label": "حالة تجريبية"},
    }


def test_classify_trend_thresholds():
    assert mtf.classify_trend(60) == "صاعد بقوة"
    assert mtf.classify_trend(20) == "صاعد"
    assert mtf.classify_trend(0) == "عرضي"
    assert mtf.classify_trend(-20) == "هابط"
    assert mtf.classify_trend(-60) == "هابط بقوة"
    # حدود العتبات بالظبط
    assert mtf.classify_trend(40) == "صاعد بقوة"
    assert mtf.classify_trend(-40) == "هابط بقوة"


def test_pure_category_score_empty_category_returns_zero():
    assert mtf._pure_category_score({}, "trend") == 0.0
    assert mtf._pure_category_score({"trend": {}}, "trend") == 0.0


def test_gate_applied_when_strong_buy_conflicts_with_strong_bearish_higher_trend():
    with patch("app.analysis.multi_timeframe.analyze_stock") as m:
        m.side_effect = [
            _fake_analysis("شراء قوي (Strong Buy)", 60, [1, 1, 1]),
            _fake_analysis("بيع قوي (Strong Sell)", -70, [-1, -1, -1, -1]),
        ]
        result = mtf.analyze_multi_timeframe("TEST")

    assert result["gate_applied"] is True
    assert result["higher_trend_classification"] == "هابط بقوة"
    assert "خُفِّفت" in result["final_recommendation"]
    assert result["final_trade_plan_status"] == "gated_by_higher_timeframe"
    assert result["gate_reason"] is not None


def test_no_gate_when_timeframes_agree():
    with patch("app.analysis.multi_timeframe.analyze_stock") as m:
        m.side_effect = [
            _fake_analysis("شراء (Buy)", 30, [1, 1, 1]),
            _fake_analysis("شراء قوي (Strong Buy)", 55, [1, 1, 1, 1]),
        ]
        result = mtf.analyze_multi_timeframe("TEST")

    assert result["gate_applied"] is False
    assert result["final_recommendation"] == "شراء (Buy)"
    assert result["final_trade_plan_status"] == "valid_long_setup"


def test_no_gate_when_primary_is_not_a_buy_signal():
    """لو الإطار الأصغر مش بيقول شراء أصلًا، البوابة متتفعّلش حتى لو الاتجاه الأكبر هابط بقوة."""
    with patch("app.analysis.multi_timeframe.analyze_stock") as m:
        m.side_effect = [
            _fake_analysis("بيع (Sell)", -30, [-1, -1]),
            _fake_analysis("بيع قوي (Strong Sell)", -80, [-1, -1, -1, -1]),
        ]
        result = mtf.analyze_multi_timeframe("TEST")

    assert result["gate_applied"] is False
    assert result["final_recommendation"] == "بيع (Sell)"


def test_regular_buy_downgraded_to_neutral_not_just_softened():
    """شراء عادي (مش قوي) مع اتجاه أكبر هابط بشدة - المفروض ينزل لمحايد، مش يفضل شراء."""
    with patch("app.analysis.multi_timeframe.analyze_stock") as m:
        m.side_effect = [
            _fake_analysis("شراء (Buy)", 25, [1]),
            _fake_analysis("بيع قوي (Strong Sell)", -75, [-1, -1, -1, -1, -1]),
        ]
        result = mtf.analyze_multi_timeframe("TEST")

    assert result["gate_applied"] is True
    assert result["final_recommendation"] == "محايد / انتظار (تعارض مع الاتجاه الأكبر)"


def test_gate_not_applied_when_higher_trend_bearish_but_not_strong():
    """اتجاه أكبر هابط عادي (مش بقوة) - المفروض مفيش تدخل، البوابة بس للحالة الشديدة."""
    with patch("app.analysis.multi_timeframe.analyze_stock") as m:
        m.side_effect = [
            _fake_analysis("شراء قوي (Strong Buy)", 55, [1, 1, 1]),
            _fake_analysis("بيع (Sell)", -20, [-1, 0, 0]),  # متوسط -33.3 - هابط لكن مش بقوة (العتبة -40)
        ]
        result = mtf.analyze_multi_timeframe("TEST")

    assert result["higher_trend_classification"] == "هابط"
    assert result["gate_applied"] is False
    assert result["final_recommendation"] == "شراء قوي (Strong Buy)"


def test_result_includes_both_full_analyses_for_transparency():
    with patch("app.analysis.multi_timeframe.analyze_stock") as m:
        m.side_effect = [
            _fake_analysis("شراء (Buy)", 25, [1]),
            _fake_analysis("محايد / انتظار (Hold)", 5, [0, 1]),
        ]
        result = mtf.analyze_multi_timeframe("TEST")

    assert "primary_analysis" in result
    assert "higher_analysis" in result
