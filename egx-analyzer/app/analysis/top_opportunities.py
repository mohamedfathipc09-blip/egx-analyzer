# -*- coding: utf-8 -*-
"""
فحص تلقائي كامل بدون أي تدخل من المستخدم: يحلل كل الأسهم في القائمة
المنسّقة (أو قائمة مخصصة) ويرجع أفضل N فرصة فعلية - مش بس أعلى Score.

معيار "الفرصة الفعلية" هنا أدق من الـ screener العادي: لازم يكون عندها
خطة تنفيذ صالحة (trade_plan.status == valid_long_setup، يعني R:R اتفحص
وقُبل فعلاً من Risk Engine) ومفيش تضارب إشارات (NO_TRADE) - عشان القايمة
النهائية تكون "جاهزة للتنفيذ" مش بس "شكلها كويس رقميًا".
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.data.symbols_repository import get_symbol_codes
from app.data.stockanalysis_client import get_full_symbol_list
from app.analysis.scoring import analyze_stock

log = logging.getLogger("top_opportunities")

MAX_PARALLEL_SCANS = 8  # عدد الفحوصات المتوازية - محدود عشان منضغطش على مصادر البيانات


def _get_default_symbols(use_full_market: bool) -> list:
    """
    لو use_full_market=True: يجيب كل أسهم البورصة المصرية (~229 سهم) من
    stockanalysis.com. لو فشل المصدر الحي، بيرجع تلقائيًا للقائمة المنسّقة
    الأساسية (39 سهم) بدل ما ينهار الفحص بالكامل.
    """
    if not use_full_market:
        return get_symbol_codes()
    full_list = get_full_symbol_list()
    return [s["symbol"] for s in full_list["symbols"]]


def get_top_opportunities(
    limit: int = 5,
    symbols: list = None,
    timeframe: str = "daily",
    period: str = "1y",
    use_full_market: bool = True,
) -> dict:
    """
    يفحص كل الأسهم (أو القايمة المحددة لو اتبعتت) بدون أي إعدادات مطلوبة
    من المستخدم، ويرجع أفضل `limit` فرصة فعلية: خطة تنفيذ صالحة + مفيش
    تضارب إشارات، مرتبة تنازليًا حسب Score.

    use_full_market=True (الافتراضي): يفحص كل سوق EGX (~229 سهم) بدل
    القائمة المنسّقة الصغيرة (39 سهم) - الفحص بيتم بالتوازي (حتى
    MAX_PARALLEL_SCANS في نفس الوقت) لتقليل الوقت الكلي.
    """
    symbols = symbols or _get_default_symbols(use_full_market)
    candidates = []
    failed = []

    def _analyze_one(symbol):
        return symbol, analyze_stock(symbol, timeframe=timeframe, period=period)

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_SCANS) as executor:
        futures = {executor.submit(_analyze_one, s): s for s in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                _, result = future.result()
            except Exception as e:
                failed.append({"symbol": symbol, "error": str(e)})
                log.warning("تعذر تحليل %s أثناء الفحص الشامل: %s", symbol, e)
                continue

            is_conflicted = result.get("signal_conflict", {}).get("is_conflicted", False)
            has_valid_plan = result.get("trade_plan", {}).get("status") == "valid_long_setup"

            if not is_conflicted and has_valid_plan:
                candidates.append(result)

    # ترتيب حسب Score أولًا، وبعدين نسبة توافق المؤشرات كفاصل عند التساوي
    candidates.sort(key=lambda r: (r["score"], r["agreement_percent"]), reverse=True)

    return {
        "scanned_count": len(symbols),
        "qualifying_count": len(candidates),
        "failed_count": len(failed),
        "top_opportunities": candidates[:limit],
        "failed_symbols": failed,
    }
