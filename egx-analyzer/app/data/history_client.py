# -*- coding: utf-8 -*-
"""
جلب بيانات الأسعار التاريخية (OHLCV) لأسهم البورصة المصرية عبر مباشر (Mubasher).
"""
import logging
import time
import requests
import pandas as pd

from app.config import DEFAULT_HISTORY_PERIOD, YAHOO_SUFFIX
from app.data.retry_utils import retry_with_backoff

log = logging.getLogger("history_client")
_CACHE = {}

class HistoryNotFoundError(Exception):
    """يُرفع عندما لا توجد بيانات تاريخية لرمز السهم المطلوب."""
    pass

def to_yahoo_symbol(symbol: str) -> str:
    """
    دالة توافقية (Backward Compatibility):
    موجودة هنا بس عشان لو في أي ملف قديم في المشروع بيستدعيها، السيرفر ميقعش.
    """
    symbol = symbol.upper().strip()
    return symbol if symbol.endswith(YAHOO_SUFFIX) else f"{symbol}{YAHOO_SUFFIX}"

@retry_with_backoff(max_attempts=3, base_delay=1.5, exceptions=(Exception,))
def _fetch_mubasher_history(symbol: str, period: str = "2y"):
    symbol = symbol.upper().strip()
    mubasher_symbol = f"EGX:{symbol}"
    
    end_time = int(time.time())
    years = 2 if "2y" in period else 1
    start_time = end_time - (years * 365 * 24 * 60 * 60)
    
    url = "https://www.mubasher.info/api/1/chart/udf/history"
    params = {
        "symbol": mubasher_symbol,
        "resolution": "D",
        "from": start_time,
        "to": end_time
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Origin': 'https://www.mubasher.info',
        'Referer': f'https://www.mubasher.info/markets/EGX/stocks/{symbol}'
    }
    
    res = requests.get(url, params=params, headers=headers, timeout=15)
    
    if res.status_code != 200:
        raise Exception(f"خطأ في الاتصال بسيرفر مباشر: {res.status_code}")
        
    data = res.json()
    
    if data.get('s') != 'ok' or not data.get('t'):
        raise Exception(f"لا توجد بيانات متاحة لهذا الرمز على مباشر: {symbol}")
        
    df = pd.DataFrame({
        'Open': data['o'],
        'High': data['h'],
        'Low': data['l'],
        'Close': data['c'],
        'Volume': data['v']
    }, index=pd.to_datetime(data['t'], unit='s'))
    
    return df

def fetch_history(
    symbol: str,
    period: str = DEFAULT_HISTORY_PERIOD,
    interval: str = "1d",
    use_cache: bool = True,
) -> pd.DataFrame:
    cache_key = (symbol.upper(), period, interval)
    if use_cache and cache_key in _CACHE:
        return _CACHE[cache_key]

    try:
        df = _fetch_mubasher_history(symbol, period)
    except Exception as e:
        raise HistoryNotFoundError(f"تعذر جلب بيانات {symbol}: {e}") from e

    if df is None or df.empty:
        raise HistoryNotFoundError(f"لا توجد بيانات تاريخية لهذا الرمز على مباشر: {symbol}")

    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    
    if use_cache:
        _CACHE[cache_key] = df
        
    return df

def clear_cache():
    _CACHE.clear()