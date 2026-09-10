# -*- coding: utf-8 -*-
"""اختبارات وحدة لنظام التصويت والتجميع (scoring.py) باستخدام بيانات وهمية."""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from app.analysis import scoring


def _make_df(n=250, trend_direction="up"):
    if trend_direction == "up":
        close = pd.Series(np.linspace(100, 200, n))
    else:
        close = pd.Series(np.linspace(200, 100, n))
    high = close + 1
    low = close - 1
    open_ = close.shift(1).fillna(close.iloc[0])
    vol = pd.Series(np.random.randint(1000, 5000, n))
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"Open": open_.values, "High": high.values, "Low": low.values,
         "Close": close.values, "Volume": vol.values},
        index=idx,
    )


@patch("app.analysis.scoring.fetch_history")
def test_uptrend_gives_positive_score(mock_fetch):
    mock_fetch.return_value = _make_df(trend_direction="up")
    result = scoring.analyze_stock("TEST")
    assert result["score"] > 0
    assert "شراء" in result["recommendation"] or "Buy" in result["recommendation"]


@patch("app.analysis.scoring.fetch_history")
def test_downtrend_gives_negative_score(mock_fetch):
    mock_fetch.return_value = _make_df(trend_direction="down")
    result = scoring.analyze_stock("TEST")
    assert result["score"] < 0
    assert "بيع" in result["recommendation"] or "Sell" in result["recommendation"]


@patch("app.analysis.scoring.fetch_history")
def test_response_always_includes_disclaimer(mock_fetch):
    mock_fetch.return_value = _make_df(trend_direction="up")
    result = scoring.analyze_stock("TEST")
    assert "disclaimer" in result
    assert len(result["disclaimer"]) > 0


@patch("app.analysis.scoring.fetch_history")
def test_agreement_percent_between_0_and_100(mock_fetch):
    mock_fetch.return_value = _make_df(trend_direction="up")
    result = scoring.analyze_stock("TEST")
    assert 0 <= result["agreement_percent"] <= 100


def test_raises_value_error_on_insufficient_data():
    with patch("app.analysis.scoring.fetch_history") as mock_fetch:
        mock_fetch.return_value = _make_df(n=5)
        with pytest.raises(ValueError):
            scoring.analyze_stock("TEST")


@patch("app.analysis.scoring.fetch_history")
def test_analyze_multiple_handles_errors_without_crashing(mock_fetch):
    def side_effect(symbol, period="1y", interval="1d"):
        if symbol == "BAD":
            raise scoring.HistoryNotFoundError("لا توجد بيانات")
        return _make_df(trend_direction="up")

    mock_fetch.side_effect = side_effect
    results = scoring.analyze_multiple(["GOOD", "BAD"])
    assert len(results) == 2
    assert "error" in results[1]
