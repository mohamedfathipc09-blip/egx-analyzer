# -*- coding: utf-8 -*-
"""
فحص (Screener) لأسهم استوفت "شروط الصعود": درجة تحليل فني إيجابية بما فيه
الكفاية + نسبة توافق مؤشرات كافية. مبني فوق نظام التصويت في scoring.py.
"""

import logging

from app.config import DEFAULT_SYMBOLS
from app.analysis.scoring import analyze_stock

log = logging.getLogger("screener")


def screen_bullish_stocks(
    symbols: list = None,
    min_score: float = 20.0,
    min_agreement: float = 50.0,
    timeframe: str = "daily",
    period: str = "1y",
) -> list:
    """
    يفحص قائمة أسهم ويرجع بس اللي حققت "شروط الصعود":
    - score >= min_score (بشكل افتراضي 20 = توصية شراء على الأقل)
    - agreement_percent >= min_agreement (توافق كافٍ بين المؤشرات)
    النتيجة مرتبة تنازليًا حسب الـ score (الأقوى صعودًا أولًا).
    """
    symbols = symbols or DEFAULT_SYMBOLS
    qualifying = []

    for symbol in symbols:
        try:
            result = analyze_stock(symbol, timeframe=timeframe, period=period)
        except Exception as e:
            log.warning("تعذر فحص %s: %s", symbol, e)
            continue

        # لازم نستبعد أي سهم اتعلّم عليه NO_TRADE بسبب تضارب المؤشرات، حتى
        # لو الـ score بالصدفة عدّى الحد الأدنى - التضارب معناه عدم يقين
        # حقيقي، مش فرصة صاعدة فعلية
        is_conflicted = result.get("signal_conflict", {}).get("is_conflicted", False)
        meets_thresholds = (
            result.get("score", -999) >= min_score
            and result.get("agreement_percent", 0) >= min_agreement
        )
        if meets_thresholds and not is_conflicted:
            qualifying.append(result)

    qualifying.sort(key=lambda r: r["score"], reverse=True)
    return qualifying
