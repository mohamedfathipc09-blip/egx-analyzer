# -*- coding: utf-8 -*-
"""مؤشرات الاتجاه: SMA, EMA, ADX, Parabolic SAR, Ichimoku Cloud."""

import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def average_true_range_raw(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """ATR أساسي مستخدم داخليًا في ADX وParabolic SAR (نسخة مطابقة في volatility.py للاستخدام العام)."""
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    مؤشر ADX لقياس قوة الاتجاه (بغض النظر عن اتجاهه).
    يرجع DataFrame فيه الأعمدة: plus_di, minus_di, adx
    """
    high, low = df["High"], df["Low"]
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    atr = average_true_range_raw(df, period)
    plus_dm_smooth = pd.Series(plus_dm, index=df.index).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    minus_dm_smooth = pd.Series(minus_dm, index=df.index).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    plus_di = 100 * (plus_dm_smooth / atr.replace(0, np.nan))
    minus_di = 100 * (minus_dm_smooth / atr.replace(0, np.nan))
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_line = dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    return pd.DataFrame({"plus_di": plus_di, "minus_di": minus_di, "adx": adx_line})


def parabolic_sar(df: pd.DataFrame, af_start: float = 0.02, af_step: float = 0.02, af_max: float = 0.2) -> pd.Series:
    """
    Parabolic SAR لتحديد نقاط انعكاس الاتجاه المحتملة.
    يرجع Series بقيمة SAR لكل يوم.
    """
    high, low, close = df["High"].values, df["Low"].values, df["Close"].values
    n = len(df)
    sar = np.zeros(n)
    if n == 0:
        return pd.Series(sar, index=df.index)

    trend_up = True
    af = af_start
    ep = high[0]
    sar[0] = low[0]

    for i in range(1, n):
        prev_sar = sar[i - 1]
        if trend_up:
            sar[i] = prev_sar + af * (ep - prev_sar)
            sar[i] = min(sar[i], low[i - 1], low[i - 2] if i >= 2 else low[i - 1])
            if low[i] < sar[i]:
                trend_up = False
                sar[i] = ep
                ep = low[i]
                af = af_start
            else:
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + af_step, af_max)
        else:
            sar[i] = prev_sar + af * (ep - prev_sar)
            sar[i] = max(sar[i], high[i - 1], high[i - 2] if i >= 2 else high[i - 1])
            if high[i] > sar[i]:
                trend_up = True
                sar[i] = ep
                ep = high[i]
                af = af_start
            else:
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + af_step, af_max)

    return pd.Series(sar, index=df.index)


def ichimoku(df: pd.DataFrame) -> pd.DataFrame:
    """
    سحابة إيشيموكو. يرجع DataFrame فيه: tenkan_sen, kijun_sen,
    senkou_span_a, senkou_span_b, chikou_span
    """
    high, low, close = df["High"], df["Low"], df["Close"]

    def _mid(period):
        return (high.rolling(period).max() + low.rolling(period).min()) / 2

    tenkan_sen = _mid(9)
    kijun_sen = _mid(26)
    senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(26)
    senkou_span_b = _mid(52).shift(26)
    chikou_span = close.shift(-26)

    return pd.DataFrame({
        "tenkan_sen": tenkan_sen,
        "kijun_sen": kijun_sen,
        "senkou_span_a": senkou_span_a,
        "senkou_span_b": senkou_span_b,
        "chikou_span": chikou_span,
    })
