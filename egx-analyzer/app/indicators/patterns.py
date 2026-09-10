# -*- coding: utf-8 -*-
"""الدعم والمقاومة، مستويات فيبوناتشي، وأنماط الشموع اليابانية الأساسية."""

import pandas as pd


def pivot_points(df: pd.DataFrame) -> dict:
    """
    نقاط بيفوت (Pivot Points) الكلاسيكية، محسوبة من بيانات آخر يوم تداول
    (High, Low, Close)، تُستخدم كمستويات دعم/مقاومة محتملة لليوم التالي.
    """
    last = df.iloc[-1]
    pivot = (last["High"] + last["Low"] + last["Close"]) / 3
    r1 = 2 * pivot - last["Low"]
    s1 = 2 * pivot - last["High"]
    r2 = pivot + (last["High"] - last["Low"])
    s2 = pivot - (last["High"] - last["Low"])
    return {
        "pivot": round(pivot, 2),
        "resistance_1": round(r1, 2),
        "resistance_2": round(r2, 2),
        "support_1": round(s1, 2),
        "support_2": round(s2, 2),
    }


def recent_support_resistance(df: pd.DataFrame, lookback: int = 60) -> dict:
    """أبسط تقدير للدعم/المقاومة: أدنى وأعلى سعر خلال آخر N يوم تداول."""
    window = df.tail(lookback)
    return {
        "support": round(window["Low"].min(), 2),
        "resistance": round(window["High"].max(), 2),
        "lookback_days": lookback,
    }


def fibonacci_levels(df: pd.DataFrame, lookback: int = 120) -> dict:
    """
    مستويات فيبوناتشي للتصحيح، محسوبة بين أعلى وأدنى سعر خلال فترة معينة.
    مفيدة كمناطق دعم/مقاومة محتملة أثناء تصحيح الاتجاه السائد.
    """
    window = df.tail(lookback)
    high = window["High"].max()
    low = window["Low"].min()
    diff = high - low
    return {
        "0.0%": round(high, 2),
        "23.6%": round(high - 0.236 * diff, 2),
        "38.2%": round(high - 0.382 * diff, 2),
        "50.0%": round(high - 0.5 * diff, 2),
        "61.8%": round(high - 0.618 * diff, 2),
        "100.0%": round(low, 2),
    }


def detect_candlestick_patterns(df: pd.DataFrame) -> list:
    """
    يفحص آخر شمعتين/ثلاثة ويرجع قائمة بأسماء الأنماط المكتشفة (إن وُجدت):
    Hammer, Bullish/Bearish Engulfing, Doji, Morning/Evening Star.
    هذا كشف مبسّط (heuristic) وليس بديلاً عن تحليل بصري احترافي.
    """
    patterns = []
    if len(df) < 3:
        return patterns

    c0, c1, c2 = df.iloc[-1], df.iloc[-2], df.iloc[-3]

    def body(c):
        return abs(c["Close"] - c["Open"])

    def range_(c):
        return c["High"] - c["Low"] if c["High"] != c["Low"] else 1e-9

    # Doji: جسم صغير جدًا مقارنة بمدى الشمعة
    if body(c0) / range_(c0) < 0.1:
        patterns.append("Doji - تردد في السوق")

    # Hammer: جسم صغير في أعلى الشمعة وذيل سفلي طويل بعد اتجاه هابط
    lower_wick = min(c0["Open"], c0["Close"]) - c0["Low"]
    if body(c0) / range_(c0) < 0.3 and lower_wick / range_(c0) > 0.5 and c1["Close"] < c1["Open"]:
        patterns.append("Hammer - احتمال ارتداد صاعد")

    # Bullish Engulfing: شمعة صاعدة تبتلع جسم الشمعة الهابطة السابقة بالكامل
    if (c1["Close"] < c1["Open"]) and (c0["Close"] > c0["Open"]) \
            and (c0["Close"] >= c1["Open"]) and (c0["Open"] <= c1["Close"]):
        patterns.append("Bullish Engulfing - إشارة انعكاس صاعد")

    # Bearish Engulfing: شمعة هابطة تبتلع جسم الشمعة الصاعدة السابقة بالكامل
    if (c1["Close"] > c1["Open"]) and (c0["Close"] < c0["Open"]) \
            and (c0["Open"] >= c1["Close"]) and (c0["Close"] <= c1["Open"]):
        patterns.append("Bearish Engulfing - إشارة انعكاس هابط")

    # Morning Star: هبوط قوي، ثم شمعة صغيرة تردد، ثم صعود قوي
    if (c2["Close"] < c2["Open"]) and (body(c1) / range_(c1) < 0.3) and \
            (c0["Close"] > c0["Open"]) and (c0["Close"] > (c2["Open"] + c2["Close"]) / 2):
        patterns.append("Morning Star - إشارة انعكاس صاعد قوية")

    # Evening Star: صعود قوي، ثم شمعة صغيرة تردد، ثم هبوط قوي
    if (c2["Close"] > c2["Open"]) and (body(c1) / range_(c1) < 0.3) and \
            (c0["Close"] < c0["Open"]) and (c0["Close"] < (c2["Open"] + c2["Close"]) / 2):
        patterns.append("Evening Star - إشارة انعكاس هابط قوية")

    return patterns
