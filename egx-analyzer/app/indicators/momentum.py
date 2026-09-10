# -*- coding: utf-8 -*-
"""مؤشرات الزخم: RSI, MACD, Stochastic, ROC, Momentum, Williams %R, CCI."""

import pandas as pd


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    result = 100 - (100 / (1 + rs))

    # حالة حدّية: لو مفيش أي هبوط إطلاقًا خلال الفترة (avg_loss == 0)، القسمة
    # العادية بترجع NaN بسبب استبدال الصفر - لكن الصح رياضيًا إن RSI = 100
    # (طالما فيه صعود فعلي)، أو 50 (محايد) لو مفيش أي حركة سعر إطلاقًا.
    no_loss_mask = avg_loss == 0
    result = result.where(~no_loss_mask, 100.0)
    no_movement_mask = no_loss_mask & (avg_gain == 0)
    result = result.where(~no_movement_mask, 50.0)

    return result


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """يرجع (macd_line, signal_line, histogram)."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3):
    """يرجع (%K, %D)."""
    low_min = df["Low"].rolling(k_period).min()
    high_max = df["High"].rolling(k_period).max()
    k = 100 * (df["Close"] - low_min) / (high_max - low_min)
    d = k.rolling(d_period).mean()
    return k, d


def rate_of_change(series: pd.Series, period: int = 12) -> pd.Series:
    """Rate of Change (ROC) بالنسبة المئوية."""
    return (series - series.shift(period)) / series.shift(period) * 100


def momentum(series: pd.Series, period: int = 10) -> pd.Series:
    return series - series.shift(period)


def williams_r(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_max = df["High"].rolling(period).max()
    low_min = df["Low"].rolling(period).min()
    return -100 * (high_max - df["Close"]) / (high_max - low_min)


def cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Commodity Channel Index."""
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
    sma_tp = typical_price.rolling(period).mean()
    mean_dev = typical_price.rolling(period).apply(lambda x: (x - x.mean()).abs().mean(), raw=False)
    return (typical_price - sma_tp) / (0.015 * mean_dev)
