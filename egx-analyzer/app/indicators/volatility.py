# -*- coding: utf-8 -*-
"""مؤشرات التذبذب: Bollinger Bands, ATR, Keltner Channels."""

import pandas as pd


def bollinger_bands(series: pd.Series, period: int = 20, num_std: float = 2.0):
    """يرجع (upper, mid, lower)."""
    mid = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


def average_true_range(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    ATR: مقياس مدى التذبذب، مفيد لتحديد مستويات وقف الخسارة الديناميكية
    (مثال شائع: وقف خسارة = سعر الدخول - 2×ATR).
    """
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def keltner_channels(df: pd.DataFrame, ema_period: int = 20, atr_period: int = 10, multiplier: float = 2.0):
    """
    قنوات كيلتنر: تُستخدم مقارنةً ببولينجر لرصد الاختراقات الحقيقية
    (لو بولينجر اخترقت كيلتنر، ده يرجّح تمدد تذبذب حقيقي وليس ضجيج).
    يرجع (upper, mid, lower).
    """
    mid = df["Close"].ewm(span=ema_period, adjust=False).mean()
    atr = average_true_range(df, atr_period)
    upper = mid + multiplier * atr
    lower = mid - multiplier * atr
    return upper, mid, lower
