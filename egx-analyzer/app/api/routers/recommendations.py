# -*- coding: utf-8 -*-
"""
history_client.py
 
عميل جلب البيانات التاريخية (OHLCV) لأسهم البورصة المصرية عبر Yahoo Finance.
 
التعديلات في هذه النسخة:
- Cache بصلاحية محدودة (TTL) بدل الكاش الدائم اللي مايتحدثش أبدًا.
- توحيد شكل الـ DataFrame الناتج بغض النظر عن المسار (API مباشر أو yfinance).
- دالة async لتفادي حجب الـ event loop في FastAPI.
- تعامل أكثر أمانًا مع استجابة JSON الناقصة (بدل الانفجار بـ KeyError).
- تمييز حالة 429 (Rate Limit) عن باقي الأخطاء، عشان الـ retry decorator
  يعمل backoff حقيقي بدل القفز فورًا لـ yfinance اللي غالبًا هيتحظر بنفس الطريقة.
"""
 
import asyncio
import logging
import time
from typing import Tuple
 
import pandas as pd
import requests
import yfinance as yf
 
from app.config import YAHOO_SUFFIX, DEFAULT_HISTORY_PERIOD
from app.data.retry_utils import retry_with_backoff
 
log = logging.getLogger("history_client")
 
# ---------------------------------------------------------------------------
# الكاش: dict بسيط لكن مع صلاحية (TTL) تختلف حسب الفريم الزمني.
# القيمة المخزنة: (DataFrame, وقت التخزين بالثواني)
# ---------------------------------------------------------------------------
_CACHE: dict = {}
 
# TTL بالثواني لكل نوع interval — الفريمات القصيرة تتحدث بسرعة، اليومية/الأسبوعية أبطأ
_INTRADAY_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}
_TTL_INTRADAY = 60          # دقيقة واحدة للفريمات داخل اليوم
_TTL_DAILY_PLUS = 60 * 30   # نص ساعة لليومي وما فوق
 
 
class HistoryNotFoundError(Exception):
    pass
 
 
class RateLimitedError(Exception):
    """يُرفع خصيصًا عند 429 عشان الـ retry decorator يعمل backoff بدل القفز فورًا للبديل."""
    pass
 
 
def to_yahoo_symbol(symbol: str) -> str:
    symbol = symbol.upper().strip()
    return symbol if symbol.endswith(YAHOO_SUFFIX) else f"{symbol}{YAHOO_SUFFIX}"
 
 
def _ttl_for(interval: str) -> int:
    return _TTL_INTRADAY if interval in _INTRADAY_INTERVALS else _TTL_DAILY_PLUS
 
 
def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    توحيد شكل الـ DataFrame بغض النظر عن المصدر (raw API أو yfinance):
    - نفس الأعمدة بالضبط: Open, High, Low, Close, Volume
    - index من نوع datetime بدون timezone (tz-naive) عشان يتقارن بسهولة مع باقي الكود
    """
    if df is None or df.empty:
        return df
 
    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    df = df[keep].copy()
 
    if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
        df.index = df.index.tz_localize(None)
 
    df.index.name = "Date"
    return df
 
 
@retry_with_backoff(max_attempts=3, base_delay=2.0, exceptions=(Exception,))
def _fetch_yahoo_direct(ysym: str, period: str, interval: str) -> pd.DataFrame:
    """
    جلب البيانات من الـ Raw API مباشرة لتخطي حظر السيرفرات السحابية،
    مع رجوع لمكتبة yfinance كاحتياطي لو المسار المباشر فشل بسبب غير الـ rate limit.
    """
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ysym}?range={period}&interval={interval}"
 
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Origin": "https://finance.yahoo.com",
        "Referer": f"https://finance.yahoo.com/quote/{ysym}",
    }
 
    res = requests.get(url, headers=headers, timeout=15)
 
    # 429 تحديدًا: نرفع استثناء مخصص عشان الـ retry decorator يعمل backoff حقيقي
    # بدل ما نقفز فورًا لـ yfinance اللي غالبًا محظور بنفس السبب
    if res.status_code == 429:
        raise RateLimitedError(f"تم تقييد الطلبات (429) لـ {ysym}")
 
    if res.status_code != 200:
        log.warning("Yahoo direct API رجع %s لـ %s، جاري المحاولة عبر yfinance", res.status_code, ysym)
        df = yf.Ticker(ysym).history(period=period, interval=interval)
        return _normalize_columns(df)
 
    try:
        data = res.json()
    except ValueError as e:
        raise HistoryNotFoundError(f"استجابة غير صالحة (not JSON) من Yahoo لـ {ysym}") from e
 
    result_list = data.get("chart", {}).get("result")
    if not result_list:
        return pd.DataFrame()
 
    result = result_list[0]
    timestamps = result.get("timestamp")
    quote_list = result.get("indicators", {}).get("quote")
 
    if not timestamps or not quote_list:
        return pd.DataFrame()
 
    quote = quote_list[0]
    required = ("open", "high", "low", "close", "volume")
    if not all(k in quote for k in required):
        log.warning("بيانات ناقصة (missing OHLCV keys) لـ %s", ysym)
        return pd.DataFrame()
 
    df = pd.DataFrame(
        {
            "Open": quote["open"],
            "High": quote["high"],
            "Low": quote["low"],
            "Close": quote["close"],
            "Volume": quote["volume"],
        },
        index=pd.to_datetime(timestamps, unit="s"),
    )
 
    return _normalize_columns(df)
 
 
def fetch_history(
    symbol: str,
    period: str = DEFAULT_HISTORY_PERIOD,
    interval: str = "1d",
    use_cache: bool = True,
) -> pd.DataFrame:
    cache_key = (symbol.upper(), period, interval)
 
    if use_cache and cache_key in _CACHE:
        cached_df, cached_at = _CACHE[cache_key]
        if time.time() - cached_at < _ttl_for(interval):
            return cached_df
        # انتهت صلاحية الكاش، نحذفه ونكمل جلب جديد
        del _CACHE[cache_key]
 
    ysym = to_yahoo_symbol(symbol)
    try:
        df = _fetch_yahoo_direct(ysym, period, interval)
    except Exception as e:
        raise HistoryNotFoundError(f"تعذر جلب بيانات {ysym}: {e}") from e
 
    if df is None or df.empty:
        raise HistoryNotFoundError(f"لا توجد بيانات تاريخية لهذا الرمز على Yahoo Finance: {ysym}")
 
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    if df.empty:
        raise HistoryNotFoundError(f"كل الصفوف فيها قيم ناقصة لـ {ysym}")
 
    if use_cache:
        _CACHE[cache_key] = (df, time.time())
 
    return df
 
 
async def fetch_history_async(
    symbol: str,
    period: str = DEFAULT_HISTORY_PERIOD,
    interval: str = "1d",
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    نسخة async لاستخدامها مباشرة جوه routes الـ FastAPI من غير ما تحجب الـ event loop،
    لأن requests و yfinance بيعتمدوا على استدعاءات blocking.
    """
    return await asyncio.to_thread(fetch_history, symbol, period, interval, use_cache)
 
 
def clear_cache():
    _CACHE.clear()
 