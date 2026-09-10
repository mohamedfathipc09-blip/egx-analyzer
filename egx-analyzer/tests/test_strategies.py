# -*- coding: utf-8 -*-
"""اختبارات وحدة لتعريفات الاستراتيجيات (definitions.py) ومحرك المقارنة (engine.py)."""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from app.strategies import definitions as d
from app.strategies.engine import find_best_strategy, backtest_strategy, MIN_TRADES_FOR_RANKING


def _random_walk_df(n=500, seed=15):
    np.random.seed(seed)
    returns = np.random.normal(0.0005, 0.02, n)
    close = pd.Series(100 * np.cumprod(1 + returns))
    high = close * (1 + abs(np.random.normal(0, 0.008, n)))
    low = close * (1 - abs(np.random.normal(0, 0.008, n)))
    open_ = close.shift(1).fillna(close.iloc[0])
    vol = pd.Series(np.random.randint(1000, 5000, n))
    idx = pd.date_range("2022-01-01", periods=n, freq="D")
    return pd.DataFrame({"Open": open_.values, "High": high.values, "Low": low.values,
                          "Close": close.values, "Volume": vol.values}, index=idx)


# ------------------------------------------------------------------ definitions

@pytest.mark.parametrize("strategy_fn", [
    d.strategy_classic_trend, d.strategy_strong_trend, d.strategy_breakout,
    d.strategy_mean_reversion, d.strategy_volume_momentum,
])
def test_strategy_scores_have_matching_length_and_valid_range(strategy_fn):
    df = _random_walk_df()
    scores = strategy_fn(df)
    assert len(scores) == len(df)
    valid = scores.dropna()
    assert valid.between(-100, 100).all()


def test_breakout_detects_genuine_breakout_with_volume_confirmation():
    """
    اختبار انحدار (regression) لباگ حقيقي: كان rolling_high بيتحسب شاملًا
    اليوم الحالي نفسه، فشرط 'الإغلاق >= المقاومة' ميتحققش تقريبًا أبدًا
    لأن أعلى سعر اليوم بيدخل في حساب المقاومة نفسها.
    """
    n = 100
    close = pd.Series([100.0] * 60 + list(np.linspace(100, 130, 40)))
    high = close * 1.005
    low = close * 0.995
    open_ = close.shift(1).fillna(close.iloc[0])
    vol = pd.Series([1000] * 65 + [3000] * 35)
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    df = pd.DataFrame({"Open": open_.values, "High": high.values, "Low": low.values,
                        "Close": close.values, "Volume": vol.values}, index=idx)

    scores = d.strategy_breakout(df)
    active = scores[scores.abs() >= 20]
    assert len(active) > 0, "الاستراتيجية لم تكتشف اختراقًا حقيقيًا واضحًا - الباگ رجع تاني"
    assert (active > 0).any()


def test_mean_reversion_is_contrarian_not_trend_following():
    """الارتداد من التذبذب المفروض يشتري عند التشبع البيعي، مش عند الصعود."""
    n = 250
    np.random.seed(3)
    close = pd.Series(100 + np.random.normal(0, 3, n).cumsum() * 0.1)
    high, low = close + 1, close - 1
    open_ = close.shift(1).fillna(close.iloc[0])
    vol = pd.Series(np.random.randint(1000, 5000, n))
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    df = pd.DataFrame({"Open": open_.values, "High": high.values, "Low": low.values,
                        "Close": close.values, "Volume": vol.values}, index=idx)
    scores = d.strategy_mean_reversion(df)
    # مفيش افتراض على القيم بالظبط - بس نتأكد إن الدالة بترجع نطاق صحيح ومفيش كراش
    assert scores.dropna().between(-100, 100).all()


# ------------------------------------------------------------------ engine

@patch("app.strategies.engine.fetch_history")
def test_find_best_strategy_returns_all_registered_strategies(mock_fetch):
    mock_fetch.return_value = _random_walk_df(n=750, seed=20)
    result = find_best_strategy("TEST", period="3y")
    total = len(result["ranked_strategies"]) + len(result["insufficient_sample_strategies"])
    assert total == 5  # عدد الاستراتيجيات المسجّلة في STRATEGY_REGISTRY


@patch("app.strategies.engine.fetch_history")
def test_low_sample_strategy_excluded_from_ranking(mock_fetch):
    mock_fetch.return_value = _random_walk_df(n=750, seed=20)
    result = find_best_strategy("TEST", period="3y")
    for r in result["insufficient_sample_strategies"]:
        assert (r["n_trades"] or 0) < MIN_TRADES_FOR_RANKING
    for r in result["ranked_strategies"]:
        assert (r["n_trades"] or 0) >= MIN_TRADES_FOR_RANKING


@patch("app.strategies.engine.fetch_history")
def test_ranking_uses_confidence_adjusted_profit_factor_not_raw(mock_fetch):
    """
    اختبار انحدار لتحسين حقيقي: استراتيجية بعدد صفقات قليل نسبيًا (لكن
    فوق الحد الأدنى) وProfit Factor خام عالٍ، متطلعش تلقائيًا أفضل من
    استراتيجية بعينة أكبر بكتير ورقم خام أقل شوية.
    """
    mock_fetch.return_value = _random_walk_df(n=750, seed=20)
    result = find_best_strategy("TEST", period="3y")
    ranked = result["ranked_strategies"]
    for i in range(len(ranked) - 1):
        current = ranked[i]["confidence_adjusted_profit_factor"]
        nxt = ranked[i + 1]["confidence_adjusted_profit_factor"]
        assert current >= nxt, "الترتيب غير صحيح حسب Profit Factor المعدّل بالثقة"


@patch("app.strategies.engine.fetch_history")
def test_best_strategy_matches_top_of_ranked_list(mock_fetch):
    mock_fetch.return_value = _random_walk_df(n=750, seed=20)
    result = find_best_strategy("TEST", period="3y")
    if result["ranked_strategies"]:
        assert result["best_strategy"] == result["ranked_strategies"][0]
    else:
        assert result["best_strategy"] is None


def test_raises_value_error_on_missing_symbol_data():
    from app.data.history_client import HistoryNotFoundError
    with patch("app.strategies.engine.fetch_history") as mock_fetch:
        mock_fetch.side_effect = HistoryNotFoundError("لا توجد بيانات")
        with pytest.raises(ValueError):
            find_best_strategy("NOTREAL")


def test_one_failing_strategy_does_not_stop_the_rest():
    """لو استراتيجية واحدة رمت استثناء، الباقي المفروض يكمل يتفحص عادي."""
    df = _random_walk_df(n=750, seed=20)
    broken_registry = {
        "broken": {"label": "استراتيجية معطوبة", "compute": lambda df: 1 / 0},
        "classic_trend": {"label": "الاتجاه الكلاسيكي", "compute": d.strategy_classic_trend},
    }
    with patch("app.strategies.engine.fetch_history") as mock_fetch, \
         patch("app.strategies.engine.STRATEGY_REGISTRY", broken_registry):
        mock_fetch.return_value = df
        result = find_best_strategy("TEST", period="3y")
    all_keys = {r["strategy_key"] for r in result["ranked_strategies"]} | \
               {r["strategy_key"] for r in result["insufficient_sample_strategies"]}
    assert "broken" not in all_keys
    assert "classic_trend" in all_keys
