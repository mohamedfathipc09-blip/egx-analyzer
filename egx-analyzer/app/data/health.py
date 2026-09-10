# -*- coding: utf-8 -*-
"""
فحص متانة الاتصال بكل مصدر بيانات على حدة (مباشر، الأخبار الحية، Yahoo
Finance) - عشان تعرف بسرعة أي مصدر واقع دلوقتي من غير ما تجرب كل حاجة
يدويًا. كل فحص بمهلة قصيرة ومعزول عن الباقي (فشل مصدر واحد ميوقفش فحص
الباقي).
"""

import logging
from datetime import datetime

from app.data.mubasher_client import get_stock_data
from app.data.news_client import get_news_live
from app.data.history_client import fetch_history, HistoryNotFoundError

log = logging.getLogger("health_check")

# سهم معروف نستخدمه للفحص بس (COMI من أكتر الأسهم تداولًا، احتمال وجود بياناته دايمًا عالي)
_PROBE_SYMBOL = "COMI"


def _check_mubasher() -> dict:
    try:
        data = get_stock_data(_PROBE_SYMBOL, delay=0)
        if data.get("error"):
            return {"status": "down", "detail": data["error"]}
        if data.get("last_price") is None:
            return {"status": "degraded", "detail": "الصفحة استجابت لكن مفيش سعر - ممكن تصميم الصفحة اتغيّر"}
        return {"status": "ok", "detail": None}
    except Exception as e:
        return {"status": "down", "detail": str(e)}


def _check_news() -> dict:
    try:
        items = get_news_live(limit=1)
        if not items:
            return {"status": "degraded", "detail": "الصفحة استجابت لكن مفيش أخبار - راجع صيغة الصفحة"}
        return {"status": "ok", "detail": None}
    except Exception as e:
        return {"status": "down", "detail": str(e)}


def _check_yahoo_finance() -> dict:
    try:
        df = fetch_history(_PROBE_SYMBOL, period="5d", use_cache=False)
        if df is None or df.empty:
            return {"status": "degraded", "detail": "استجاب لكن رجع بيانات فاضية"}
        return {"status": "ok", "detail": None}
    except HistoryNotFoundError as e:
        return {"status": "down", "detail": str(e)}
    except Exception as e:
        return {"status": "down", "detail": str(e)}


def check_all_sources() -> dict:
    """يرجع حالة كل مصدر بيانات على حدة + حالة عامة مجمّعة."""
    sources = {
        "mubasher": _check_mubasher(),
        "news": _check_news(),
        "yahoo_finance": _check_yahoo_finance(),
    }

    statuses = [s["status"] for s in sources.values()]
    if all(s == "ok" for s in statuses):
        overall = "ok"
    elif all(s == "down" for s in statuses):
        overall = "down"
    else:
        overall = "degraded"

    return {
        "overall_status": overall,
        "checked_at": datetime.now().isoformat(),
        "sources": sources,
    }
