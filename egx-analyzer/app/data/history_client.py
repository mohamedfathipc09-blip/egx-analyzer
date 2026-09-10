# -*- coding: utf-8 -*-
"""
جلب بيانات الأسعار التاريخية (OHLCV) لأسهم البورصة المصرية عبر Yahoo Finance.

Yahoo Finance يتتبع أسهم البورصة المصرية برمز السهم + لاحقة ".CA"
(مثال: COMI.CA)، وهو مصدر مجاني وموثوق لا يعتمد على جافاسكريبت، بعكس
صفحة الرسم البياني على مباشر.
"""

import logging

import pandas as pd
import yfinance as yf

from app.config import YAHOO_SUFFIX, DEFAULT_HISTORY_PERIOD
from app.data.retry_utils import retry_with_backoff

log = logging.getLogger("history_client")

_CACHE = {}  # cache بسيط في الذاكرة: {(symbol, period, interval): DataFrame}


class HistoryNotFoundError(Exception):
    """يُرفع عندما لا توجد بيانات تاريخية لرمز السهم المطلوب."""


def to_yahoo_symbol(symbol: str) -> str:
    symbol = symbol.upper().strip()
    return symbol if symbol.endswith(YAHOO_SUFFIX) else f"{symbol}{YAHOO_SUFFIX}"


@retry_with_backoff(max_attempts=3, base_delay=1.5, exceptions=(Exception,))
def _fetch_yahoo_history(ysym: str, period: str, interval: str):
    """
    نداء yfinance نفسه، بمحاولة إعادة تلقائية. ملحوظة: yfinance مالوش نوع
    استثناء موحّد عبر الإصدارات المختلفة عند فشل الشبكة، فبنعيد المحاولة
    على أي Exception هنا تحديدًا (على عكس باقي المصادر اللي بنحدد نوع
    الخطأ بدقة) - القرار ده مقصود ومش إهمال.
    """
    return yf.Ticker(ysym).history(period=period, interval=interval)


def fetch_history(
    symbol: str,
    period: str = DEFAULT_HISTORY_PERIOD,
    interval: str = "1d",
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    يرجع DataFrame بأعمدة Open/High/Low/Close/Volume مفهرس بالتاريخ.
    يرفع HistoryNotFoundError لو الرمز غير موجود أو مفيش بيانات كافية.
    """
    cache_key = (symbol.upper(), period, interval)
    if use_cache and cache_key in _CACHE:
        return _CACHE[cache_key]

    ysym = to_yahoo_symbol(symbol)
    try:
        df = _fetch_yahoo_history(ysym, period, interval)
    except Exception as e:  # yfinance قد يرمي أنواع أخطاء متعددة حسب الإصدار
        raise HistoryNotFoundError(f"تعذر جلب بيانات {ysym}: {e}") from e

    if df is None or df.empty:
        raise HistoryNotFoundError(f"لا توجد بيانات تاريخية لهذا الرمز على Yahoo Finance: {ysym}")

    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    if use_cache:
        _CACHE[cache_key] = df
    return df


def clear_cache():
    _CACHE.clear()
