# -*- coding: utf-8 -*-
"""مؤشرات الحجم: مقارنة بالمتوسط, OBV, VWAP, Accumulation/Distribution."""

import numpy as np
import pandas as pd


def volume_vs_average(df: pd.DataFrame, period: int = 20):
    """يرجع (المتوسط المتحرك للحجم, نسبة الحجم الحالي إلى المتوسط)."""
    vol_avg = df["Volume"].rolling(period).mean()
    ratio = df["Volume"] / vol_avg.replace(0, np.nan)
    return vol_avg, ratio


def on_balance_volume(df: pd.DataFrame) -> pd.Series:
    """
    On-Balance Volume: يجمع الحجم في أيام الصعود ويطرحه في أيام الهبوط،
    لرصد تدفق الأموال قبل أن ينعكس على السعر أحيانًا.
    """
    direction = np.sign(df["Close"].diff()).fillna(0)
    return (direction * df["Volume"]).cumsum()


def vwap(df: pd.DataFrame) -> pd.Series:
    """
    Volume Weighted Average Price - عادة تُحسب يوميًا (intraday)، وهنا نحسبها
    كمتوسط تراكمي على مستوى السلسلة الزمنية المتاحة كتقريب عملي للبيانات اليومية.
    """
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
    cum_vol = df["Volume"].cumsum()
    cum_vol_price = (typical_price * df["Volume"]).cumsum()
    return cum_vol_price / cum_vol.replace(0, np.nan)


def accumulation_distribution(df: pd.DataFrame) -> pd.Series:
    """Accumulation/Distribution Line."""
    high, low, close, vol = df["High"], df["Low"], df["Close"], df["Volume"]
    clv = ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
    return (clv * vol).cumsum()
