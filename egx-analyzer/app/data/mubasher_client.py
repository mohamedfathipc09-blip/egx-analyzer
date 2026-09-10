# -*- coding: utf-8 -*-
"""
جلب بيانات السهم اللحظية والبيانات الأساسية من صفحة السهم الفردية على مباشر.

ملحوظة مهمة: صفحة "أسعار الأسهم" الشاملة على مباشر تُحمَّل عبر جافاسكريبت
(Angular) ولا ترجع بيانات حقيقية عبر طلب HTTP عادي. لذلك نعتمد على صفحة كل
سهم على حدة (مثال: mubasher.info/markets/EGX/stocks/ETEL) التي تُعرض بالكامل
من السيرفر وتحتوي على بيانات حقيقية.
"""

import re
import time
import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from app.config import (
    MUBASHER_STOCK_URL_TMPL,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
    REQUEST_DELAY_SECONDS,
)
from app.data.retry_utils import retry_with_backoff

log = logging.getLogger("mubasher_client")

SESSION = requests.Session()
SESSION.headers.update(REQUEST_HEADERS)


class MubasherFetchError(Exception):
    """يُرفع عند فشل جلب أو تحليل صفحة سهم من مباشر."""


def _to_float(text):
    if text is None:
        return None
    cleaned = text.replace(",", "").replace("٬", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _find_number_after(label: str, text: str):
    m = re.search(re.escape(label) + r"\s*([\-\d,.]+)", text)
    return _to_float(m.group(1)) if m else None


@retry_with_backoff(
    max_attempts=3, base_delay=1.0,
    exceptions=(requests.exceptions.ConnectionError, requests.exceptions.Timeout),
)
def _fetch_page(url: str):
    """طلب HTTP بمحاولة إعادة تلقائية عند انقطاع الاتصال أو انتهاء المهلة فقط (مش على أخطاء 404 مثلًا)."""
    resp = SESSION.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp


def get_stock_data(symbol: str, delay: float = REQUEST_DELAY_SECONDS) -> dict:
    """
    يجيب بيانات سهم واحد من صفحته على مباشر: السعر، التغيير، الفتح، الإغلاق
    السابق، أعلى، أدنى، الكمية، القيمة. يرجع قاموس فيه "error" لو فشل الجلب
    بدلًا من رمي استثناء، عشان الاستدعاءات المجمّعة (loop) متتوقفش عند أول خطأ.
    """
    symbol = symbol.upper().strip()
    url = MUBASHER_STOCK_URL_TMPL.format(symbol=symbol)
    result = {"symbol": symbol, "url": url, "fetched_at": datetime.now().isoformat()}

    try:
        resp = _fetch_page(url)
    except requests.RequestException as e:
        log.warning("فشل تحميل صفحة %s بعد إعادة المحاولة: %s", symbol, e)
        result["error"] = str(e)
        return result

    soup = BeautifulSoup(resp.text, "html.parser")

    h1 = soup.find("h1")
    result["name"] = h1.get_text(strip=True) if h1 else None

    full_text = " ".join(soup.get_text(separator=" ", strip=True).split())

    m = re.search(
        r"بتوقيت السوق\s*([\-\d,.]+)\s*([\-\d,.]+)\s*([\-\d,.]+)\s*%",
        full_text,
    )
    if m:
        result["last_price"] = _to_float(m.group(1))
        result["change"] = _to_float(m.group(2))
        result["change_percent"] = _to_float(m.group(3))
    else:
        result["last_price"] = result["change"] = result["change_percent"] = None

    result["open"] = _find_number_after("فتح", full_text)
    result["prev_close"] = _find_number_after("إغلاق سابق", full_text)
    result["high"] = _find_number_after("أعلى", full_text)
    result["low"] = _find_number_after("أدنى", full_text)
    result["volume"] = _find_number_after("حجم التداول", full_text)
    result["turnover"] = _find_number_after("قيمة التداول", full_text)

    # بيانات أساسية إن وُجدت في الصفحة (قد تكون غير متاحة لكل الأسهم)
    result["market_cap"] = _find_number_after("القيمة السوقية", full_text)
    result["eps"] = _find_number_after("ربحية السهم", full_text)
    result["pe_ratio"] = _find_number_after("مكرر الربحية", full_text) or _find_number_after("م/ر", full_text)

    if delay:
        time.sleep(delay)

    return result


def get_multiple_stocks(symbols, delay: float = REQUEST_DELAY_SECONDS) -> list:
    """يجيب بيانات عدة أسهم بالتتابع (استخدم ThreadPoolExecutor في طبقة الـ API للتوازي)."""
    return [get_stock_data(s, delay=delay) for s in symbols]
