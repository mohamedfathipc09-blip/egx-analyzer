# -*- coding: utf-8 -*-
"""اختبارات وحدة لفحص جودة البيانات (app/data/quality.py)."""

import numpy as np
import pandas as pd

from app.data.quality import validate_data_quality


def _clean_df(n=100, seed=1):
    np.random.seed(seed)
    close = pd.Series(100 + np.random.normal(0, 1, n).cumsum())
    open_ = close.shift(1).fillna(close.iloc[0])
    high = pd.concat([open_, close], axis=1).max(axis=1) + abs(np.random.normal(0.3, 0.1, n))
    low = pd.concat([open_, close], axis=1).min(axis=1) - abs(np.random.normal(0.3, 0.1, n))
    vol = pd.Series(np.random.randint(1000, 5000, n))
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    return pd.DataFrame({"Open": open_.values, "High": high.values, "Low": low.values,
                          "Close": close.values, "Volume": vol.values}, index=idx)


def test_clean_data_is_valid_with_no_warnings():
    result = validate_data_quality(_clean_df())
    assert result["is_valid"] is True
    assert result["warnings"] == []


def test_empty_dataframe_is_invalid():
    result = validate_data_quality(pd.DataFrame())
    assert result["is_valid"] is False


def test_duplicate_candles_detected_as_critical():
    df = _clean_df()
    df = pd.concat([df, df.iloc[[5]]])
    result = validate_data_quality(df)
    assert result["is_valid"] is False
    assert "duplicate_candles" in result["critical_issues"]


def test_invalid_ohlc_detected_as_critical():
    df = _clean_df()
    df.loc[df.index[10], "High"] = df.loc[df.index[10], "Low"] - 5
    result = validate_data_quality(df)
    assert result["is_valid"] is False
    assert "invalid_ohlc" in result["critical_issues"]


def test_negative_volume_detected_as_critical():
    df = _clean_df()
    df.loc[df.index[3], "Volume"] = -100
    result = validate_data_quality(df)
    assert result["is_valid"] is False
    assert "negative_volume" in result["critical_issues"]


def test_suspicious_price_jump_is_warning_not_critical():
    """تحرك سعري كبير (احتمال انقسام سهم) تحذير خفيف، مش رفض للبيانات."""
    df = _clean_df()
    cols = ["Close", "High", "Low", "Open"]
    df.loc[df.index[50]:, cols] = df.loc[df.index[50]:, cols] / 2
    result = validate_data_quality(df)
    assert result["is_valid"] is True
    assert any("انقسام" in w for w in result["warnings"])


def test_missing_columns_reported_as_critical():
    df = pd.DataFrame({"Close": [1, 2, 3]})
    result = validate_data_quality(df)
    assert result["is_valid"] is False
    assert "missing_columns" in result["critical_issues"]
