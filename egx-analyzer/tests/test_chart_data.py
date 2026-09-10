# -*- coding: utf-8 -*-
"""اختبارات وحدة لطبقة بيانات الرسم البياني (app/analysis/chart_data.py)."""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from app.analysis.chart_data import get_chart_data


def _make_df(n=300, seed=9):
    np.random.seed(seed)
    close = pd.Series(np.linspace(100, 150, n) + np.random.normal(0, 2, n))
    high, low = close + 1, close - 1
    open_ = close.shift(1).fillna(close.iloc[0])
    vol = pd.Series(np.random.randint(1000, 5000, n))
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    return pd.DataFrame({"Open": open_.values, "High": high.values, "Low": low.values,
                          "Close": close.values, "Volume": vol.values}, index=idx)


@patch("app.analysis.chart_data.fetch_history")
def test_all_arrays_have_matching_length(mock_fetch):
    mock_fetch.return_value = _make_df()
    result = get_chart_data("TEST")
    lengths = {k: len(v) for k, v in result.items() if isinstance(v, list)}
    assert len(set(lengths.values())) == 1, f"أطوال غير متطابقة: {lengths}"


@patch("app.analysis.chart_data.fetch_history")
def test_sma200_starts_with_none_then_has_values(mock_fetch):
    mock_fetch.return_value = _make_df()
    result = get_chart_data("TEST")
    assert result["sma200"][0] is None  # مفيش بيانات كافية لأول 199 يوم
    assert result["sma200"][-1] is not None


@patch("app.analysis.chart_data.fetch_history")
def test_dates_are_iso_formatted_strings(mock_fetch):
    mock_fetch.return_value = _make_df()
    result = get_chart_data("TEST")
    assert result["dates"][0] == "2023-01-01"


@patch("app.analysis.chart_data.fetch_history")
def test_bollinger_upper_never_below_lower_when_both_present(mock_fetch):
    mock_fetch.return_value = _make_df()
    result = get_chart_data("TEST")
    for upper, lower in zip(result["bollinger_upper"], result["bollinger_lower"]):
        if upper is not None and lower is not None:
            assert upper >= lower


@patch("app.analysis.chart_data.fetch_history")
def test_weekly_timeframe_uses_weekly_interval(mock_fetch):
    mock_fetch.return_value = _make_df(n=104)  # سنتين تقريبًا لو كانت بيانات أسبوعية
    result = get_chart_data("TEST", timeframe="weekly")
    mock_fetch.assert_called_once()
    _, kwargs = mock_fetch.call_args
    assert kwargs.get("interval") == "1wk"


@patch("app.analysis.chart_data.fetch_history")
def test_rsi_included_and_within_valid_range(mock_fetch):
    mock_fetch.return_value = _make_df()
    result = get_chart_data("TEST")
    assert "rsi" in result
    assert result["rsi"][0] is None  # مفيش بيانات كافية في بداية السلسلة
    valid_rsi = [v for v in result["rsi"] if v is not None]
    assert all(0 <= v <= 100 for v in valid_rsi)


def test_raises_value_error_when_symbol_not_found():
    from app.data.history_client import HistoryNotFoundError
    with patch("app.analysis.chart_data.fetch_history") as mock_fetch:
        mock_fetch.side_effect = HistoryNotFoundError("لا توجد بيانات")
        with pytest.raises(ValueError):
            get_chart_data("NOTREAL")
