# -*- coding: utf-8 -*-
"""اختبارات وحدة لفحص الأسهم الصاعدة (app/analysis/screener.py)."""

from unittest.mock import patch

from app.analysis import screener


def _fake_analysis(symbol, score, is_conflicted=False, agreement=70):
    return {
        "symbol": symbol,
        "score": score,
        "agreement_percent": agreement,
        "signal_conflict": {
            "is_conflicted": is_conflicted,
            "conflict_ratio": 0.8 if is_conflicted else 0.2,
            "reason": "تضارب" if is_conflicted else None,
        },
    }


def test_qualifying_stock_appears_in_results():
    with patch("app.analysis.screener.analyze_stock") as m:
        m.return_value = _fake_analysis("GOOD", 30)
        result = screener.screen_bullish_stocks(["GOOD"], min_score=20, min_agreement=50)
    assert len(result) == 1
    assert result[0]["symbol"] == "GOOD"


def test_low_score_stock_is_excluded():
    with patch("app.analysis.screener.analyze_stock") as m:
        m.return_value = _fake_analysis("WEAK", 10)
        result = screener.screen_bullish_stocks(["WEAK"], min_score=20, min_agreement=50)
    assert result == []


def test_conflicted_stock_excluded_even_with_high_score():
    """
    اختبار انحدار (regression) لباگ حقيقي: كان أي سهم عليه NO_TRADE بسبب
    تضارب المؤشرات لسه بيظهر في قايمة الفرص الصاعدة لو الـ score بالصدفة
    عدّى الحد الأدنى، رغم إن التضارب معناه عدم يقين حقيقي مش فرصة فعلية.
    """
    with patch("app.analysis.screener.analyze_stock") as m:
        m.return_value = _fake_analysis("CONFLICTED", 25, is_conflicted=True)
        result = screener.screen_bullish_stocks(["CONFLICTED"], min_score=20, min_agreement=50)
    assert result == [], "سهم متضارب ظهر في نتائج الفحص رغم NO_TRADE - الباگ رجع تاني"


def test_mixed_batch_only_returns_qualifying_non_conflicted():
    with patch("app.analysis.screener.analyze_stock") as m:
        m.side_effect = [
            _fake_analysis("GOOD", 30, is_conflicted=False),
            _fake_analysis("CONFLICTED", 25, is_conflicted=True),
            _fake_analysis("WEAK", 10, is_conflicted=False),
        ]
        result = screener.screen_bullish_stocks(["GOOD", "CONFLICTED", "WEAK"], min_score=20, min_agreement=50)
    assert [r["symbol"] for r in result] == ["GOOD"]


def test_results_sorted_descending_by_score():
    with patch("app.analysis.screener.analyze_stock") as m:
        m.side_effect = [
            _fake_analysis("LOW", 25),
            _fake_analysis("HIGH", 45),
            _fake_analysis("MID", 35),
        ]
        result = screener.screen_bullish_stocks(["LOW", "HIGH", "MID"], min_score=20, min_agreement=50)
    assert [r["symbol"] for r in result] == ["HIGH", "MID", "LOW"]


def test_analysis_failure_for_one_symbol_does_not_stop_the_rest():
    with patch("app.analysis.screener.analyze_stock") as m:
        def side_effect(symbol, **kwargs):
            if symbol == "BAD":
                raise ValueError("بيانات غير كافية")
            return _fake_analysis(symbol, 30)
        m.side_effect = side_effect
        result = screener.screen_bullish_stocks(["GOOD", "BAD"], min_score=20, min_agreement=50)
    assert [r["symbol"] for r in result] == ["GOOD"]
