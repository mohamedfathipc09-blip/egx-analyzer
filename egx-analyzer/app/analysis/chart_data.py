# -*- coding: utf-8 -*-
"""
تجهيز بيانات الرسم البياني (Candlestick) لسهم واحد: سلسلة OHLCV زمنية +
مؤشرات فوقها (SMA50, SMA200, Bollinger Bands) - جاهزة للاستهلاك المباشر
في رسم بياني تفاعلي بدون ما الواجهة تحتاج تحسب أي حاجة بنفسها.
"""

from app.data.history_client import fetch_history, HistoryNotFoundError
from app.indicators import trend, volatility, momentum


def get_chart_data(symbol: str, period: str = "1y", timeframe: str = "daily") -> dict:
    """
    يرجع بيانات جاهزة للرسم: تواريخ + OHLCV + SMA50/SMA200 + نطاقات بولينجر
    + RSI (لعرضه في لوحة سفلية منفصلة زي منصات التداول الاحترافية).
    القيم اللي مفيش بيانات كافية لحسابها (بداية السلسلة) بترجع None بدل
    ما تتجاهل، عشان طول كل مصفوفة يفضل متطابق مع طول التواريخ.
    """
    interval = "1d" if timeframe == "daily" else "1wk"
    try:
        df = fetch_history(symbol, period=period, interval=interval)
    except HistoryNotFoundError as e:
        raise ValueError(str(e)) from e

    close = df["Close"]
    sma50 = trend.sma(close, 50)
    sma200 = trend.sma(close, 200)
    upper, mid, lower = volatility.bollinger_bands(close)
    rsi = momentum.rsi(close, 14)

    def _clean(series):
        return [None if v != v else round(float(v), 2) for v in series]  # v != v => NaN

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "dates": [d.strftime("%Y-%m-%d") for d in df.index],
        "open": _clean(df["Open"]),
        "high": _clean(df["High"]),
        "low": _clean(df["Low"]),
        "close": _clean(df["Close"]),
        "volume": [int(v) if v == v else 0 for v in df["Volume"]],
        "sma50": _clean(sma50),
        "sma200": _clean(sma200),
        "bollinger_upper": _clean(upper),
        "bollinger_mid": _clean(mid),
        "bollinger_lower": _clean(lower),
        "rsi": _clean(rsi),
    }
