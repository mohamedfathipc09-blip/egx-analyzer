# -*- coding: utf-8 -*-
"""
جلب القائمة الكاملة لأسهم البورصة المصرية المُدرجة (~229 سهم) من
stockanalysis.com - بديل عن القائمة المنسّقة يدويًا (39 سهم بس) في
egx_symbols.json، وبديل عن صفحة مباشر/موقع البورصة الرسمي اللي مش
قابلين للاستخراج الآلي (Angular / WAF).

هذه القائمة بأسماء إنجليزية (المصدر إنجليزي)، وبتُخزَّن محليًا في ملف
JSON بعد أول جلب ناجح، عشان منضغطش على السيرفر كل مرة ومنعتمدش على
اتصال حي في كل تحليل.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from app.config import REQUEST_HEADERS, REQUEST_TIMEOUT_SECONDS
from app.data.retry_utils import retry_with_backoff

log = logging.getLogger("stockanalysis_client")

FULL_LIST_URL = "https://stockanalysis.com/list/egyptian-stock-exchange/"
CACHE_PATH = str(Path(__file__).resolve().parent / "egx_symbols_full_cache.json")

SESSION = requests.Session()
SESSION.headers.update(REQUEST_HEADERS)


@retry_with_backoff(
    max_attempts=3, base_delay=1.0,
    exceptions=(requests.exceptions.ConnectionError, requests.exceptions.Timeout),
)
def _fetch_page():
    resp = SESSION.get(FULL_LIST_URL, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp


def fetch_full_symbol_list_live() -> list:
    """
    يجيب القائمة الكاملة مباشرة من stockanalysis.com. يرجع [{symbol,
    name_en}, ...]. بيرمي استثناء لو فشل الاتصال - الاستخدام العادي
    لازم يكون عبر get_full_symbol_list() اللي بيرجع للكاش أو القائمة
    المنسّقة عند الفشل.
    """
    resp = _fetch_page()
    soup = BeautifulSoup(resp.text, "html.parser")

    symbols = []
    seen = set()
    # كل سطر في الجدول فيه رابط لصفحة السهم بالشكل /quote/egx/{SYMBOL}/
    for a in soup.find_all("a", href=True):
        m = re.search(r"/quote/egx/([A-Z0-9]+)/?$", a["href"])
        if not m:
            continue
        symbol = m.group(1)
        if symbol in seen:
            continue
        # اسم الشركة بيكون في نفس صف الجدول - أقرب <td> بعد رابط الرمز
        row = a.find_parent("tr")
        name_en = None
        if row:
            cells = row.find_all("td")
            if len(cells) >= 3:
                name_en = cells[2].get_text(strip=True)
        seen.add(symbol)
        symbols.append({"symbol": symbol, "name_en": name_en or symbol})

    return symbols


def get_full_symbol_list(force_refresh: bool = False) -> dict:
    """
    يرجع {"symbols": [...], "source": "live"|"cache"|"fallback",
    "count": N, "fetched_at": iso}. بيحاول المصدر الحي أولًا (أو الكاش لو
    موجود ومش force_refresh)، ولو فشل الاتنين بيرجع القائمة المنسّقة
    الأساسية (39 سهم) كخيار أخير مضمون الاشتغال.
    """
    cache_file = Path(CACHE_PATH)

    if not force_refresh and cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            cached["source"] = "cache"
            return cached
        except (json.JSONDecodeError, OSError) as e:
            log.warning("تعذرت قراءة كاش القائمة الكاملة: %s", e)

    try:
        symbols = fetch_full_symbol_list_live()
        if not symbols:
            raise ValueError("الصفحة استجابت لكن مفيش رموز اتستخرجت - احتمال تغيّر تصميم الصفحة")
        result = {
            "symbols": symbols,
            "source": "live",
            "count": len(symbols),
            "fetched_at": datetime.now().isoformat(),
        }
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except OSError as e:
            log.warning("تعذر حفظ كاش القائمة الكاملة: %s", e)
        return result
    except Exception as e:
        log.warning("فشل جلب القائمة الكاملة من stockanalysis.com: %s", e)
        from app.data.symbols_repository import get_all_symbols
        fallback = [{"symbol": s["symbol"], "name_en": s["name_ar"]} for s in get_all_symbols()]
        return {
            "symbols": fallback,
            "source": "fallback_curated_list",
            "count": len(fallback),
            "fetched_at": datetime.now().isoformat(),
            "error": str(e),
        }


def get_full_symbol_codes(force_refresh: bool = False) -> list:
    """اختصار: رموز الأسهم بس، بدون أسماء - للاستخدام المباشر في الفحص الشامل."""
    return [s["symbol"] for s in get_full_symbol_list(force_refresh=force_refresh)["symbols"]]
