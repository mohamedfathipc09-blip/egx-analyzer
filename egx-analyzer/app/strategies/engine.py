# -*- coding: utf-8 -*-
"""
Strategy Engine: يختبر كل استراتيجية مسجّلة في STRATEGY_REGISTRY على
تاريخ سهم معيّن فعليًا (باك-تيستنج حقيقي، مش تخمين)، ويرشّح "الأفضل"
بناءً على أداء فعلي - مش نسبة نجاح لوحدها.

قاعدة مهمة (زي ما نص عليها البرومت الأصلي): استراتيجية بنسبة نجاح 90%
من 12 صفقة بس مش بالضرورة أفضل من استراتيجية بنسبة 65% من 300 صفقة.
لذلك الترتيب هنا:
1. يستبعد أي استراتيجية بعدد صفقات أقل من MIN_TRADES_FOR_RANKING من
   الترتيب (بيتعرضوا لوحدهم مع توضيح السبب، مش بيتحذفوا خالص).
2. يرتب الباقي بـ Profit Factor أولًا، ثم نسبة النجاح كفاصل عند التقارب.
"""

import logging

from app.data.history_client import fetch_history, HistoryNotFoundError
from app.backtesting.engine import _summarize_trades
from app.strategies.registry import STRATEGY_REGISTRY

log = logging.getLogger("strategy_engine")

MIN_TRADES_FOR_RANKING = 20  # حد أدنى أعلى إحصائيًا - 10 صفقات مش كفاية للحكم بثقة
FULL_CONFIDENCE_TRADES = 50  # عدد الصفقات اللي عنده الثقة في العينة تبقى كاملة (100%)


def _future_returns(close, holding_days: int):
    return (close.shift(-holding_days) - close) / close * 100


def backtest_strategy(df, compute_fn, holding_days: int = 10, buy_threshold: float = 20.0) -> dict:
    """يختبر استراتيجية واحدة (دالتها) على بيانات سهم معين، ويرجع إحصائيات صفقات الشراء بتاعتها فقط."""
    close = df["Close"]
    scores = compute_fn(df)
    future_return = _future_returns(close, holding_days)
    buy_returns = future_return[scores >= buy_threshold].dropna()
    return _summarize_trades(buy_returns, is_short=False)


def find_best_strategy(
    symbol: str,
    period: str = "2y",
    holding_days: int = 10,
    buy_threshold: float = 20.0,
) -> dict:
    """
    يختبر كل الاستراتيجيات المسجّلة على نفس السهم، ويرجع ترتيبها بناءً على
    أداء فعلي، مع فصل الاستراتيجيات بعدد صفقات غير كافٍ عن الترتيب.
    """
    try:
        df = fetch_history(symbol, period=period)
    except HistoryNotFoundError as e:
        raise ValueError(str(e)) from e

    results = []
    for key, meta in STRATEGY_REGISTRY.items():
        try:
            stats = backtest_strategy(df, meta["compute"], holding_days=holding_days, buy_threshold=buy_threshold)
        except Exception as e:
            log.warning("فشل اختبار استراتيجية %s على %s: %s", key, symbol, e)
            continue
        results.append({
            "strategy_key": key,
            "strategy_label": meta["label"],
            **stats,
            "eligible_for_ranking": (stats.get("n_trades") or 0) >= MIN_TRADES_FOR_RANKING,
        })

    eligible = [r for r in results if r["eligible_for_ranking"]]
    insufficient = [r for r in results if not r["eligible_for_ranking"]]

    # الترتيب مش بس "profit_factor الخام" - بنخصم بيه حسب حجم العينة، عشان
    # استراتيجية بـ 20 صفقة وProfit Factor عالي متطلعش أفضل من استراتيجية
    # بـ 300 صفقة برقم أقل بس أوثق إحصائيًا. sample_confidence بين 0 و1،
    # بتوصل لـ 1 عند FULL_CONFIDENCE_TRADES صفقة أو أكتر.
    for r in eligible:
        n_trades = r.get("n_trades") or 0
        sample_confidence = round(min(1.0, n_trades / FULL_CONFIDENCE_TRADES), 2)
        raw_pf = r["profit_factor"] if r["profit_factor"] is not None else 0.0
        r["sample_confidence"] = sample_confidence
        r["confidence_adjusted_profit_factor"] = round(raw_pf * sample_confidence, 2)

    def _sort_key(r):
        wr = r["win_rate_percent"] if r["win_rate_percent"] is not None else 0.0
        return (r["confidence_adjusted_profit_factor"], wr)

    eligible.sort(key=_sort_key, reverse=True)
    best = eligible[0] if eligible else None

    return {
        "symbol": symbol.upper(),
        "period_tested": period,
        "holding_days": holding_days,
        "buy_threshold": buy_threshold,
        "best_strategy": best,
        "ranked_strategies": eligible,
        "insufficient_sample_strategies": insufficient,
        "min_trades_required": MIN_TRADES_FOR_RANKING,
        "note": (
            "الترتيب مبني على Profit Factor مخصوم منه حسب حجم العينة "
            "(confidence_adjusted_profit_factor) - مش الرقم الخام - عشان "
            "استراتيجية بعدد صفقات قليل نسبيًا لكن برقم مغري متطلعش أفضل من "
            "استراتيجية بعينة أكبر وأوثق إحصائيًا برقم أقل شوية. استراتيجية "
            f"بعدد صفقات أقل من {MIN_TRADES_FOR_RANKING} مستبعدة تمامًا من "
            "الترتيب ومعروضة لوحدها لعدم كفاية العينة."
        ),
    }
