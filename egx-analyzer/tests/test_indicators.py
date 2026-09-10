# -*- coding: utf-8 -*-
"""اختبارات وحدة للمؤشرات الفنية باستخدام بيانات وهمية (mock data) معروفة النتيجة مسبقًا."""

import numpy as np
import pandas as pd
import pytest

from app.indicators import trend, momentum, volatility, volume, patterns


@pytest.fixture
def uptrend_df():
    """بيانات صاعدة بشكل ثابت لاختبار أن مؤشرات الاتجاه تلتقط الصعود."""
    n = 250
    close = pd.Series(np.linspace(100, 200, n))
    high = close + 1
    low = close - 1
    open_ = close.shift(1).fillna(close.iloc[0])
    volume_series = pd.Series(np.random.randint(1000, 5000, n))
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"Open": open_.values, "High": high.values, "Low": low.values,
         "Close": close.values, "Volume": volume_series.values},
        index=idx,
    )


def test_sma_increases_with_uptrend(uptrend_df):
    sma20 = trend.sma(uptrend_df["Close"], 20)
    assert sma20.iloc[-1] > sma20.iloc[50]


def test_ema_close_to_price_faster_than_sma(uptrend_df):
    ema20 = trend.ema(uptrend_df["Close"], 20)
    sma20 = trend.sma(uptrend_df["Close"], 20)
    # في اتجاه صاعد ثابت، EMA لازم تكون أقرب للسعر الحالي من SMA
    last_price = uptrend_df["Close"].iloc[-1]
    assert abs(ema20.iloc[-1] - last_price) <= abs(sma20.iloc[-1] - last_price)


def test_rsi_is_high_in_strong_uptrend(uptrend_df):
    rsi_series = momentum.rsi(uptrend_df["Close"], 14)
    # في اتجاه صاعد ثابت بدون أي هبوط تقريبًا، RSI المفروض يكون مرتفع جدًا
    assert rsi_series.iloc[-1] > 60


def test_bollinger_bands_upper_above_lower(uptrend_df):
    upper, mid, lower = volatility.bollinger_bands(uptrend_df["Close"])
    valid = upper.dropna().index.intersection(lower.dropna().index)
    assert (upper[valid] >= lower[valid]).all()


def test_adx_returns_expected_columns(uptrend_df):
    result = trend.adx(uptrend_df)
    assert set(["plus_di", "minus_di", "adx"]).issubset(result.columns)


def test_macd_returns_three_series(uptrend_df):
    macd_line, signal_line, hist = momentum.macd(uptrend_df["Close"])
    assert len(macd_line) == len(uptrend_df)
    assert len(signal_line) == len(uptrend_df)
    assert len(hist) == len(uptrend_df)


def test_on_balance_volume_increases_in_uptrend(uptrend_df):
    obv = volume.on_balance_volume(uptrend_df)
    assert obv.iloc[-1] > obv.iloc[0]


def test_pivot_points_returns_expected_keys(uptrend_df):
    result = patterns.pivot_points(uptrend_df)
    for key in ["pivot", "resistance_1", "resistance_2", "support_1", "support_2"]:
        assert key in result


def test_fibonacci_levels_ordered(uptrend_df):
    levels = patterns.fibonacci_levels(uptrend_df)
    assert levels["0.0%"] >= levels["23.6%"] >= levels["50.0%"] >= levels["100.0%"]


def test_indicators_handle_insufficient_data_gracefully():
    """التأكد من عدم انهيار المؤشرات عند بيانات قليلة جدًا (أقل من الفترة المطلوبة)."""
    short_df = pd.DataFrame({
        "Open": [10, 11, 12],
        "High": [11, 12, 13],
        "Low": [9, 10, 11],
        "Close": [10.5, 11.5, 12.5],
        "Volume": [1000, 1200, 1100],
    })
    sma200 = trend.sma(short_df["Close"], 200)
    assert sma200.isna().all()  # مفيش قيمة كافية لحساب SMA200، لازم يرجع NaN مش خطأ
