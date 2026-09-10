# -*- coding: utf-8 -*-
"""
اختبارات وحدة للفحص التلقائي الكامل (app/analysis/top_opportunities.py).

ملحوظة مهمة: الفحص بقى بالتوازي (ThreadPoolExecutor)، فترتيب استدعاء
analyze_stock مش مضمون يطابق ترتيب قائمة الرموز. الاختبارات هنا بتستخدم
side_effect بدالة تعتمد على الرمز نفسه (symbol keyword) بدل قائمة مواقع
ثابتة، عشان تفضل صحيحة بغض النظر عن ترتيب التنفيذ الفعلي بين الـ threads.
"""

from unittest.mock import patch

from app.analysis import top_opportunities as topop


def _fake(symbol, score, agreement=70, valid_plan=True, conflicted=False):
    return {
        "symbol": symbol,
        "score": score,
        "agreement_percent": agreement,
        "signal_conflict": {"is_conflicted": conflicted},
        "trade_plan": {"status": "valid_long_setup" if valid_plan else "rejected_low_rr"},
    }


def _mock_by_symbol(fakes: dict):
    """يرجع دالة side_effect آمنة للتوازي: بترجع نتيجة السهم المطلوب بالظبط بدل موقع ثابت في قائمة."""
    def side_effect(symbol, **kwargs):
        return fakes[symbol]
    return side_effect


def test_returns_top_n_sorted_by_score_descending():
    fakes = {"A": _fake("A", 40), "B": _fake("B", 60), "C": _fake("C", 30)}
    with patch("app.analysis.top_opportunities.analyze_stock", side_effect=_mock_by_symbol(fakes)):
        result = topop.get_top_opportunities(limit=5, symbols=["A", "B", "C"])
    symbols = [r["symbol"] for r in result["top_opportunities"]]
    assert symbols == ["B", "A", "C"]


def test_respects_limit():
    fakes = {s: _fake(s, 30 + i) for i, s in enumerate(["A", "B", "C", "D", "E"])}
    with patch("app.analysis.top_opportunities.analyze_stock", side_effect=_mock_by_symbol(fakes)):
        result = topop.get_top_opportunities(limit=2, symbols=list(fakes.keys()))
    assert len(result["top_opportunities"]) == 2


def test_excludes_stocks_with_invalid_trade_plan():
    fakes = {"BAD_RR": _fake("BAD_RR", 50, valid_plan=False)}
    with patch("app.analysis.top_opportunities.analyze_stock", side_effect=_mock_by_symbol(fakes)):
        result = topop.get_top_opportunities(symbols=["BAD_RR"])
    assert result["top_opportunities"] == []
    assert result["qualifying_count"] == 0


def test_excludes_conflicted_stocks_even_with_high_score():
    fakes = {"CONFLICTED": _fake("CONFLICTED", 70, conflicted=True)}
    with patch("app.analysis.top_opportunities.analyze_stock", side_effect=_mock_by_symbol(fakes)):
        result = topop.get_top_opportunities(symbols=["CONFLICTED"])
    assert result["top_opportunities"] == []


def test_failed_symbol_does_not_stop_the_scan():
    def side_effect(symbol, **kwargs):
        if symbol == "BROKEN":
            raise ValueError("بيانات غير كافية")
        return _fake(symbol, 40)

    with patch("app.analysis.top_opportunities.analyze_stock", side_effect=side_effect):
        result = topop.get_top_opportunities(symbols=["GOOD", "BROKEN"])

    assert result["scanned_count"] == 2
    assert result["failed_count"] == 1
    assert result["qualifying_count"] == 1
    assert result["top_opportunities"][0]["symbol"] == "GOOD"


def test_uses_full_market_list_by_default():
    """الافتراضي دلوقتي use_full_market=True - يستخدم القائمة الكاملة (~229 سهم) مش الـ39 المنسّقة."""
    with patch("app.analysis.top_opportunities.get_full_symbol_list") as m_full, \
         patch("app.analysis.top_opportunities.analyze_stock") as m_analyze:
        m_full.return_value = {"symbols": [{"symbol": "X"}, {"symbol": "Y"}], "source": "live"}
        m_analyze.return_value = _fake("X", 30)
        result = topop.get_top_opportunities()
    m_full.assert_called_once()
    assert result["scanned_count"] == 2


def test_can_opt_out_of_full_market_scan():
    with patch("app.analysis.top_opportunities.get_symbol_codes") as m_codes, \
         patch("app.analysis.top_opportunities.get_full_symbol_list") as m_full, \
         patch("app.analysis.top_opportunities.analyze_stock") as m_analyze:
        m_codes.return_value = ["A", "B"]
        m_analyze.return_value = _fake("A", 30)
        result = topop.get_top_opportunities(use_full_market=False)
    m_codes.assert_called_once()
    m_full.assert_not_called()
    assert result["scanned_count"] == 2


def test_empty_result_when_nothing_qualifies():
    fakes = {"WEAK": _fake("WEAK", 5, valid_plan=False)}
    with patch("app.analysis.top_opportunities.analyze_stock", side_effect=_mock_by_symbol(fakes)):
        result = topop.get_top_opportunities(symbols=["WEAK"])
    assert result["top_opportunities"] == []
    assert result["qualifying_count"] == 0
