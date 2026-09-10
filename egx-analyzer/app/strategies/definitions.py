# -*- coding: utf-8 -*-
"""
تعريف استراتيجيات تداول مختلفة، كل واحدة بمنطق مؤشرات مختلف. كل دالة
بتحسب "درجة يومية" (Series) عبر السلسلة الزمنية كلها مرة واحدة (نفس أسلوب
app/backtesting/engine.py) عشان الباك-تيستنج يكون سريع.

القيمة NaN بترجع في الأيام اللي مفيش فيها بيانات كافية لحساب المؤشر
(بداية السلسلة) - بتتجاهل تلقائيًا في الباك-تيستنج بدل ما تتفسّر كإشارة
محايدة.
"""

import numpy as np
import pandas as pd

from app.indicators import trend, momentum, volatility, volume


def strategy_classic_trend(df: pd.DataFrame) -> pd.Series:
    """EMA20 + EMA50 + RSI + الحجم - استراتيجية اتجاه كلاسيكية."""
    close = df["Close"]
    ema20, ema50 = trend.ema(close, 20), trend.ema(close, 50)
    rsi = momentum.rsi(close, 14)
    _, vol_ratio = volume.volume_vs_average(df, 20)

    ema_vote = np.where(ema20 > ema50, 1, -1)
    rsi_vote = np.select([rsi > 50, rsi < 50], [1, -1], default=0)
    volume_vote = np.where(vol_ratio > 1.2, 1, 0)

    score = np.vstack([ema_vote, rsi_vote, volume_vote]).mean(axis=0) * 100
    invalid = ema20.isna() | ema50.isna() | rsi.isna()
    return pd.Series(np.where(invalid, np.nan, score), index=close.index)


def strategy_strong_trend(df: pd.DataFrame) -> pd.Series:
    """EMA20/50 + MACD + ADX - استراتيجية تركّز على قوة الاتجاه مش بس اتجاهه."""
    close = df["Close"]
    ema20, ema50 = trend.ema(close, 20), trend.ema(close, 50)
    _, _, hist = momentum.macd(close)
    adx_df = trend.adx(df, 14)

    ema_vote = np.where(ema20 > ema50, 1, -1)
    macd_vote = np.where(hist > 0, 1, -1)
    adx_vote = np.select(
        [(adx_df["adx"] >= 20) & (adx_df["plus_di"] > adx_df["minus_di"]),
         (adx_df["adx"] >= 20) & (adx_df["plus_di"] < adx_df["minus_di"])],
        [1, -1], default=0,
    )

    score = np.vstack([ema_vote, macd_vote, adx_vote]).mean(axis=0) * 100
    invalid = ema20.isna() | ema50.isna() | hist.isna() | adx_df["adx"].isna()
    return pd.Series(np.where(invalid, np.nan, score), index=close.index)


def strategy_breakout(df: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """اختراق أعلى/أدنى سعر خلال فترة + تأكيد حجم - استراتيجية اختراق."""
    close, high, low = df["Close"], df["High"], df["Low"]
    # مهم: .shift(1) عشان نحسب المقاومة/الدعم من الأيام اللي فاتت بس، مش
    # شاملة اليوم الحالي - لو سبناها من غير shift، أعلى سعر النهاردة نفسه
    # بيدخل في حساب المقاومة، فشرط "الإغلاق >= المقاومة" ميتحققش تقريبًا
    # أبدًا لأن أعلى سعر دايمًا >= الإغلاق في نفس اليوم
    rolling_high = high.rolling(lookback).max().shift(1)
    rolling_low = low.rolling(lookback).min().shift(1)
    _, vol_ratio = volume.volume_vs_average(df, 20)

    breakout_up = (close >= rolling_high) & (vol_ratio > 1.5)
    breakout_down = (close <= rolling_low) & (vol_ratio > 1.5)

    score = np.select([breakout_up, breakout_down], [100, -100], default=0)
    invalid = rolling_high.isna() | rolling_low.isna() | vol_ratio.isna()
    return pd.Series(np.where(invalid, np.nan, score), index=close.index)


def strategy_mean_reversion(df: pd.DataFrame) -> pd.Series:
    """بولينجر + RSI للارتداد من التذبذب - استراتيجية عكسية (contrarian)، عكس باقي الاستراتيجيات اتجاهيًا."""
    close = df["Close"]
    upper, mid, lower = volatility.bollinger_bands(close)
    rsi = momentum.rsi(close, 14)

    oversold = (close <= lower) & (rsi < 35)
    overbought = (close >= upper) & (rsi > 65)

    score = np.select([oversold, overbought], [100, -100], default=0)
    invalid = upper.isna() | lower.isna() | rsi.isna()
    return pd.Series(np.where(invalid, np.nan, score), index=close.index)


def strategy_volume_momentum(df: pd.DataFrame) -> pd.Series:
    """VWAP + الحجم + الزخم (ROC) - استراتيجية زخم مدعومة بالحجم."""
    close = df["Close"]
    vwap_series = volume.vwap(df)
    _, vol_ratio = volume.volume_vs_average(df, 20)
    roc = momentum.rate_of_change(close, 12)

    bullish = (close > vwap_series) & (vol_ratio > 1.2) & (roc > 0)
    bearish = (close < vwap_series) & (vol_ratio > 1.2) & (roc < 0)

    score = np.select([bullish, bearish], [100, -100], default=0)
    invalid = vwap_series.isna() | vol_ratio.isna() | roc.isna()
    return pd.Series(np.where(invalid, np.nan, score), index=close.index)
