# -*- coding: utf-8 -*-
"""
تقرير توصية شامل لسهم واحد: يجمع التحليل الفني + نتائج الباك-تيستنج +
البيانات الأساسية في استجابة واحدة، عشان صفحة "التوصيات" تقدر تعرض كل حاجة
مرة واحدة بدل ما تعمل 3 طلبات منفصلة.
"""

import logging
from datetime import datetime

from app.analysis.scoring import analyze_stock
from app.analysis.fundamentals import get_fundamentals
from app.backtesting.engine import backtest_symbol
from app.config import DISCLAIMER

log = logging.getLogger("report")


def generate_full_report(
    symbol: str,
    timeframe: str = "daily",
    analysis_period: str = "1y",
    backtest_period: str = "2y",
    holding_days: int = 10,
) -> dict:
    """يرجع تقريرًا كاملًا: التحليل الفني، الباك-تيستنج، والبيانات الأساسية."""
    symbol = symbol.upper()

    analysis = analyze_stock(symbol, timeframe=timeframe, period=analysis_period)

    try:
        backtest = backtest_symbol(symbol, period=backtest_period, holding_days=holding_days)
    except Exception as e:
        log.warning("تعذر عمل backtest لـ %s ضمن التقرير: %s", symbol, e)
        backtest = {"error": str(e)}

    fundamentals = get_fundamentals(symbol)

    return {
        "symbol": symbol,
        "generated_at": datetime.now().isoformat(),
        "analysis": analysis,
        "backtest": backtest,
        "fundamentals": fundamentals,
        "disclaimer": DISCLAIMER,
    }


def generate_reports_for_qualifying(qualifying_results: list, **kwargs) -> list:
    """يبني تقرير كامل لكل سهم في قائمة نتائج الفحص (screener)."""
    reports = []
    for r in qualifying_results:
        try:
            reports.append(generate_full_report(r["symbol"], **kwargs))
        except Exception as e:
            log.warning("تعذر بناء تقرير لـ %s: %s", r.get("symbol"), e)
    return reports
