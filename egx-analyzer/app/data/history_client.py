# -*- coding: utf-8 -*-
import logging
import pandas as pd
import yfinance as yf

from app.config import YAHOO_SUFFIX, DEFAULT_HISTORY_PERIOD
from app.data.retry_utils import retry_with_backoff

log = logging.getLogger("history_client")
_CACHE = {}

class HistoryNotFoundError(Exception):
    pass

def to_yahoo_symbol(symbol: str) -> str:
    symbol = symbol.upper().strip()
    return symbol if symbol.endswith(YAHOO_SUFFIX) else f"{symbol}{YAHOO_SUFFIX}"

@retry_with_backoff(max_attempts=3, base_delay=1.5, exceptions=(Exception,))
def _fetch_yahoo_history(ysym: str, period: str, interval: str):
    # هنسيب المكتبة المتحدثة تتعامل مع الكوكيز والحماية بنفسها
    ticker = yf.Ticker(ysym)
    return ticker.history(period=period, interval=interval)

def fetch_history(symbol: str, period: str = DEFAULT_HISTORY_PERIOD, interval: str = "1d", use_cache: bool = True) -> pd.DataFrame:
    cache_key = (symbol.upper(), period, interval)
    if use_cache and cache_key in _CACHE:
        return _CACHE[cache_key]

    ysym = to_yahoo_symbol(symbol)
    try:
        df = _fetch_yahoo_history(ysym, period, interval)
    except Exception as e:
        raise HistoryNotFoundError(f"تعذر جلب بيانات {ysym}: {e}") from e

    if df is None or df.empty:
        raise HistoryNotFoundError(f"لا توجد بيانات تاريخية لهذا الرمز على Yahoo Finance: {ysym}")

    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    if use_cache:
        _CACHE[cache_key] = df
    return df

def clear_cache():
    _CACHE.clear()