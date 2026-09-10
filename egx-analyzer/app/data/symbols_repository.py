# -*- coding: utf-8 -*-
"""
طبقة الوصول لقائمة أسهم البورصة المصرية المنسّقة (egx_symbols.json).

ملحوظة صريحة: القائمة دي منسّقة يدويًا مش مستخرجة آليًا من مصدر رسمي لحظي -
صفحة الشركات المدرجة على مباشر معتمدة على جافاسكريبت، وموقع البورصة
المصرية الرسمي (egx.com.eg) رافض الوصول الآلي وقت إعداد هذا الملف. القائمة
قابلة للتوسعة بتعديل ملف JSON مباشرة.
"""

import json
import logging
from pathlib import Path

log = logging.getLogger("symbols_repository")

SYMBOLS_FILE_PATH = Path(__file__).resolve().parent / "egx_symbols.json"

_cache = None  # كاش بسيط في الذاكرة - الملف صغير ونادرًا ما يتغير أثناء التشغيل


def _load_raw(path: Path = SYMBOLS_FILE_PATH) -> dict:
    global _cache
    if _cache is not None:
        return _cache
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _cache = data
        return data
    except (FileNotFoundError, json.JSONDecodeError) as e:
        log.warning("تعذرت قراءة ملف الأسهم (%s): %s - سيتم إرجاع قائمة فاضية", path, e)
        return {"symbols": [], "_note": None, "_last_reviewed": None}


def get_all_symbols() -> list:
    """يرجع كل الأسهم في القائمة، كل واحد {symbol, name_ar, sector}."""
    return _load_raw().get("symbols", [])


def get_symbol_codes() -> list:
    """يرجع رموز الأسهم بس (list[str]) - مفيدة للاستخدام المباشر في screener/prices."""
    return [s["symbol"] for s in get_all_symbols()]


def search_symbols(query: str) -> list:
    """بحث بسيط بالرمز أو الاسم العربي (case-insensitive، مطابقة جزئية)."""
    if not query:
        return get_all_symbols()
    q = query.strip().lower()
    return [
        s for s in get_all_symbols()
        if q in s["symbol"].lower() or q in s.get("name_ar", "").lower()
    ]


def get_symbols_by_sector(sector: str) -> list:
    return [s for s in get_all_symbols() if s.get("sector") == sector]


def list_sectors() -> list:
    """يرجع كل القطاعات المتاحة بدون تكرار، بنفس ترتيب ظهورها الأول."""
    seen = []
    for s in get_all_symbols():
        sector = s.get("sector")
        if sector and sector not in seen:
            seen.append(sector)
    return seen


def get_metadata() -> dict:
    """معلومات عن مصدر القائمة نفسها - يُستخدم لتنبيه المستخدم في الواجهة."""
    raw = _load_raw()
    return {
        "note": raw.get("_note"),
        "last_reviewed": raw.get("_last_reviewed"),
        "total_symbols": len(raw.get("symbols", [])),
    }


def clear_cache():
    """لإعادة تحميل الملف بعد أي تعديل يدوي عليه أثناء التشغيل."""
    global _cache
    _cache = None
