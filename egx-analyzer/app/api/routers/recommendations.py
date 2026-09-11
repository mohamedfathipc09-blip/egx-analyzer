# -*- coding: utf-8 -*-
import logging
import pandas as pd
import requests
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

@retry_with_backoff(max_attempts=3, base_delay=2.0, exceptions=(Exception,))
def _fetch_yahoo_direct(ysym: str, period: str, interval: str):
    """
    الضربة القاضية لياهو: جلب البيانات من الـ Raw API مباشرة لتخطي حظر السيرفرات السحابية
    """
    # تحويل الفترات لصيغة يفهمها الـ API المباشر
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ysym}?range={period}&interval={interval}"
    
    # بصمة متصفح حقيقي بالكامل
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Origin': 'https://finance.yahoo.com',
        'Referer': f'https://finance.yahoo.com/quote/{ysym}'
    }
    
    res = requests.get(url, headers=headers, timeout=15)
    
    # لو حصل أي مشكلة في المباشر، نجرب مكتبة yf كاحتياطي
    if res.status_code != 200:
        return yf.Ticker(ysym).history(period=period, interval=interval)
        
    data = res.json()
    if not data.get('chart', {}).get('result'):
        return pd.DataFrame()
        
    result = data['chart']['result'][0]
    if 'timestamp' not in result:
        return pd.DataFrame()
        
    # بناء الداتا فريم من الـ JSON مباشرة (أسرع وأخف من المكتبة)
    timestamps = result['timestamp']
    quote = result['indicators']['quote'][0]
    
    df = pd.DataFrame({
        'Open': quote['open'],
        'High': quote['high'],
        'Low': quote['low'],
        'Close': quote['close'],
        'Volume': quote['volume']
    }, index=pd.to_datetime(timestamps, unit='s'))
    
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

    ysym = to_yahoo_symbol(symbol)
    try:
        df = _fetch_yahoo_direct(ysym, period, interval)
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