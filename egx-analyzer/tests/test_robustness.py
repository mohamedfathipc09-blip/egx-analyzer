# -*- coding: utf-8 -*-
"""اختبارات وحدة لطبقة متانة الباك-تيستنج (app/backtesting/robustness.py)."""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from app.backtesting import robustness
from app.backtesting.engine import _summarize_trades


def _make_realistic_df(n=1250, seed=50, drift=0.0003, vol=0.018):
    np.random.seed(seed)
    returns = np.random.normal(drift, vol, n)
    close = pd.Series(100 * np.cumprod(1 + returns))
    high = close * (1 + abs(np.random.normal(0, 0.008, n)))
    low = close * (1 - abs(np.random.normal(0, 0.008, n)))
    open_ = close.shift(1).fillna(close.iloc[0])
    vol_series = pd.Series(np.random.randint(1000, 5000, n))
    idx = pd.date_range("2021-01-01", periods=n, freq="D")
    return pd.DataFrame({"Open": open_.values, "High": high.values, "Low": low.values,
                          "Close": close.values, "Volume": vol_series.values}, index=idx)


# ------------------------------------------------ اختبارات المقاييس الجديدة

def test_summarize_trades_includes_profit_factor_and_expected_value():
    returns = pd.Series([5.0, -2.0, 3.0, -1.0, 4.0])
    stats = _summarize_trades(returns)
    assert "profit_factor" in stats
    assert "expected_value_percent" in stats
    assert "avg_profit_percent" in stats
    assert "avg_loss_percent" in stats
    # gross_profit = 12, gross_loss = 3 -> profit_factor = 4.0
    assert stats["profit_factor"] == 4.0
    assert stats["expected_value_percent"] == round(returns.mean(), 2)


def test_summarize_trades_profit_factor_none_without_losses():
    returns = pd.Series([1.0, 2.0, 3.0])
    stats = _summarize_trades(returns)
    assert stats["profit_factor"] is None  # مفيش خسائر نقارن بيها


def test_summarize_trades_empty_returns_all_none_fields():
    stats = _summarize_trades(pd.Series([], dtype=float))
    assert stats["n_trades"] == 0
    assert stats["profit_factor"] is None


# ------------------------------------------------ اختبارات Train/Test Split

@patch("app.backtesting.robustness.fetch_history")
def test_train_test_split_returns_both_segments(mock_fetch):
    mock_fetch.return_value = _make_realistic_df()
    result = robustness.train_test_split_backtest("TEST", period="5y", split_ratio=0.7)
    assert "in_sample" in result and "out_of_sample" in result
    assert result["in_sample"]["n_days"] > result["out_of_sample"]["n_days"]  # 70% vs 30%
    assert "stability_note" in result


@patch("app.backtesting.robustness.fetch_history")
def test_train_test_split_segments_are_chronologically_separate(mock_fetch):
    mock_fetch.return_value = _make_realistic_df()
    result = robustness.train_test_split_backtest("TEST", period="5y", split_ratio=0.7)
    in_end = result["in_sample"]["end_date"]
    out_start = result["out_of_sample"]["start_date"]
    assert in_end < out_start  # الجزء الأول لازم ينتهي قبل ما يبدأ التاني


# ------------------------------------------------ اختبارات Walk-Forward

@patch("app.backtesting.robustness.fetch_history")
def test_walk_forward_returns_requested_number_of_folds(mock_fetch):
    mock_fetch.return_value = _make_realistic_df()
    result = robustness.walk_forward_backtest("TEST", period="5y", n_folds=4)
    assert len(result["folds"]) == 4
    assert "win_rate_std_across_folds" in result


@patch("app.backtesting.robustness.fetch_history")
def test_walk_forward_folds_are_sequential_non_overlapping(mock_fetch):
    mock_fetch.return_value = _make_realistic_df()
    result = robustness.walk_forward_backtest("TEST", period="5y", n_folds=3)
    end_dates = [f["end_date"] for f in result["folds"]]
    start_dates = [f["start_date"] for f in result["folds"]]
    for i in range(len(result["folds"]) - 1):
        assert end_dates[i] < start_dates[i + 1]  # مفيش تداخل بين الفترات


def test_walk_forward_raises_on_insufficient_data():
    with patch("app.backtesting.robustness.fetch_history") as mock_fetch:
        mock_fetch.return_value = _make_realistic_df(n=100)  # قليل جدًا لـ 4 فترات
        with pytest.raises(ValueError):
            robustness.walk_forward_backtest("TEST", n_folds=4)


# ------------------------------------------------ اختبارات تصنيف حالة السوق

def test_classify_market_regime_detects_strong_uptrend():
    n = 200
    close = pd.Series(np.linspace(100, 200, n))  # صعود 100% - لازم يتصنف bull
    regime = robustness._classify_market_regime(close, lookback=90, threshold_pct=10.0)
    assert regime.iloc[-1] == "bull"


def test_classify_market_regime_detects_strong_downtrend():
    n = 200
    close = pd.Series(np.linspace(200, 100, n))  # هبوط 50% - لازم يتصنف bear
    regime = robustness._classify_market_regime(close, lookback=90, threshold_pct=10.0)
    assert regime.iloc[-1] == "bear"


def test_classify_market_regime_detects_sideways():
    n = 200
    close = pd.Series(100 + np.sin(np.linspace(0, 10, n)) * 2)  # تذبذب بسيط حوالين 100
    regime = robustness._classify_market_regime(close, lookback=90, threshold_pct=10.0)
    assert regime.iloc[-1] == "sideways"


@patch("app.backtesting.robustness.fetch_history")
def test_backtest_by_market_regime_returns_all_three_regimes(mock_fetch):
    mock_fetch.return_value = _make_realistic_df()
    result = robustness.backtest_by_market_regime("TEST", period="5y")
    assert set(result["by_regime"].keys()) == {"سوق صاعد", "سوق هابط", "سوق عرضي"}
    for stats in result["by_regime"].values():
        assert "win_rate_percent" in stats
