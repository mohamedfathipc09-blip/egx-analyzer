# -*- coding: utf-8 -*-
"""
اختبارات متانة إضافية فوق محرك الباك-تيستنج الأساسي (engine.py)، هدفها
كشف الـ Overfitting بدل مجرد الإبلاغ عن رقم نجاح واحد من فترة واحدة.

ملحوظة منهجية مهمة يجب توضيحها بصراحة: نظام التصويت في هذا المشروع قواعد
ثابتة (عتبات شراء/بيع محددة مسبقًا في config.py)، مش نظام بيتعلم أو بيتم
ضبط معاملاته تلقائيًا من البيانات. لذلك "Walk-Forward" هنا يعني بالتحديد:
هل نفس القواعد الثابتة حافظت على أداء مستقر عبر فترات زمنية متتالية؟ - وليس
إعادة تدريب/ضبط معاملات في كل نافذة زمنية (وهو المعنى الأدق لـ Walk-Forward
Optimization في الأدبيات). هذا الفرق مهم: أي نظام هنا مفيش فيه معاملات
بيتم "ضبطها" على الماضي أصلًا، فاحتمال Overfitting الكلاسيكي (ضبط مؤشرات
لتحقيق نتائج ممتازة على الماضي تحديدًا) أقل، لكن يبقى احتمال إن القواعد
الثابتة تصادف إنها تناسب فترة سوقية معينة بالذات - وهذا بالضبط ما تكشفه
الاختبارات هنا.
"""

import logging

import numpy as np
import pandas as pd

from app.data.history_client import fetch_history, HistoryNotFoundError
from app.backtesting.engine import compute_daily_scores, _summarize_trades

log = logging.getLogger("backtest_robustness")


def _future_returns(close: pd.Series, holding_days: int) -> pd.Series:
    return (close.shift(-holding_days) - close) / close * 100


def _trade_stats_for_slice(
    df_slice: pd.DataFrame,
    scores_slice: pd.Series,
    holding_days: int,
    buy_threshold: float,
    sell_threshold: float,
) -> dict:
    close = df_slice["Close"]
    future_return = _future_returns(close, holding_days)
    buy_returns = future_return[scores_slice >= buy_threshold].dropna()
    sell_returns = future_return[scores_slice <= sell_threshold].dropna()
    return {
        "buy_signals_performance": _summarize_trades(buy_returns, is_short=False),
        "sell_signals_performance": _summarize_trades(sell_returns, is_short=True),
        "buy_and_hold_return_percent": (
            round((close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100, 2) if len(close) > 1 else None
        ),
        "n_days": len(df_slice),
        "start_date": str(df_slice.index[0].date()) if len(df_slice) else None,
        "end_date": str(df_slice.index[-1].date()) if len(df_slice) else None,
    }


def train_test_split_backtest(
    symbol: str,
    period: str = "5y",
    split_ratio: float = 0.7,
    holding_days: int = 10,
    buy_threshold: float = 20.0,
    sell_threshold: float = -20.0,
) -> dict:
    """
    يقسّم الفترة التاريخية زمنيًا لجزئين منفصلين تمامًا: الجزء الأول
    (in_sample - "بيانات البناء") والجزء الثاني (out_of_sample - "بيانات
    الاختبار المستقلة"). المؤشرات نفسها بتتحسب على السلسلة الكاملة (عشان
    مؤشرات زي SMA200 محتاجة تاريخ طويل كافي للإحماء)، لكن تقييم الصفقات
    (هل الإشارة نجحت أو فشلت) بيتحسب لكل جزء بمعزل عن التاني تمامًا.

    القاعدة: لو نسبة نجاح الجزئين متقاربة، ده مؤشر إيجابي على استقرار
    النظام. لو الفرق كبير، ده تحذير من احتمال إن الأداء كان مرتبط بظرف
    سوقي معين في جزء واحد بالذات.
    """
    try:
        df = fetch_history(symbol, period=period)
    except HistoryNotFoundError as e:
        raise ValueError(str(e)) from e

    scores = compute_daily_scores(df)
    split_idx = int(len(df) * split_ratio)

    in_sample_stats = _trade_stats_for_slice(
        df.iloc[:split_idx], scores.iloc[:split_idx], holding_days, buy_threshold, sell_threshold
    )
    out_of_sample_stats = _trade_stats_for_slice(
        df.iloc[split_idx:], scores.iloc[split_idx:], holding_days, buy_threshold, sell_threshold
    )

    in_wr = in_sample_stats["buy_signals_performance"]["win_rate_percent"]
    out_wr = out_of_sample_stats["buy_signals_performance"]["win_rate_percent"]
    gap = abs(in_wr - out_wr) if (in_wr is not None and out_wr is not None) else None

    if gap is None:
        stability_note = "بيانات غير كافية للمقارنة (عدد صفقات قليل جدًا في أحد الجزئين أو كليهما)."
    elif gap <= 10:
        stability_note = f"مستقر نسبيًا: الفرق بين نسبة النجاح في الجزئين {gap:.1f} نقطة مئوية فقط."
    else:
        stability_note = (
            f"⚠️ تحذير: فرق كبير ({gap:.1f} نقطة مئوية) بين نسبة النجاح في جزئي البيانات - "
            "قد يكون الأداء مرتبطًا بظرف سوقي معين في فترة واحدة بالذات، مش نمط ثابت."
        )

    return {
        "symbol": symbol.upper(),
        "period_tested": period,
        "split_ratio": split_ratio,
        "in_sample": in_sample_stats,
        "out_of_sample": out_of_sample_stats,
        "stability_gap_percentage_points": round(gap, 1) if gap is not None else None,
        "stability_note": stability_note,
    }


def walk_forward_backtest(
    symbol: str,
    period: str = "5y",
    n_folds: int = 4,
    holding_days: int = 10,
    buy_threshold: float = 20.0,
    sell_threshold: float = -20.0,
) -> dict:
    """
    يقسّم الفترة التاريخية لعدة أجزاء زمنية متتالية غير متداخلة (folds)
    ويحسب أداء النظام في كل جزء بمعزل عن الباقي. الهدف: هل القواعد الثابتة
    حافظت على أداء متسق عبر فترات زمنية مختلفة، ولا كان الأداء العام مدفوع
    بفترة واحدة قوية بالصدفة؟
    """
    try:
        df = fetch_history(symbol, period=period)
    except HistoryNotFoundError as e:
        raise ValueError(str(e)) from e

    if len(df) < n_folds * 60:
        raise ValueError(
            f"بيانات غير كافية لتقسيمها إلى {n_folds} فترات مفيدة "
            f"(متاح {len(df)} يوم فقط - محتاج على الأقل {n_folds * 60})"
        )

    scores = compute_daily_scores(df)
    fold_size = len(df) // n_folds

    folds = []
    win_rates = []
    for i in range(n_folds):
        start = i * fold_size
        end = (i + 1) * fold_size if i < n_folds - 1 else len(df)
        fold_stats = _trade_stats_for_slice(
            df.iloc[start:end], scores.iloc[start:end], holding_days, buy_threshold, sell_threshold
        )
        fold_stats["fold_number"] = i + 1
        folds.append(fold_stats)
        wr = fold_stats["buy_signals_performance"]["win_rate_percent"]
        if wr is not None:
            win_rates.append(wr)

    if len(win_rates) >= 2:
        win_rate_std = round(float(np.std(win_rates)), 1)
        consistency_note = (
            f"الانحراف المعياري لنسبة النجاح عبر {len(win_rates)} فترات: {win_rate_std} نقطة مئوية. "
            + ("مستقر نسبيًا." if win_rate_std <= 12 else "⚠️ تذبذب كبير - النظام قد يكون غير مستقر عبر الزمن.")
        )
    else:
        win_rate_std = None
        consistency_note = "عدد صفقات غير كافٍ في أغلب الفترات للحكم على الاستقرار."

    return {
        "symbol": symbol.upper(),
        "period_tested": period,
        "n_folds": n_folds,
        "folds": folds,
        "win_rate_std_across_folds": win_rate_std,
        "consistency_note": consistency_note,
    }


def _classify_market_regime(close: pd.Series, lookback: int = 90, threshold_pct: float = 10.0) -> pd.Series:
    """
    تصنيف مبسّط لحالة السوق يوميًا: صاعد / هابط / عرضي، بناءً على نسبة
    التغير خلال آخر `lookback` يوم. هذا تصنيف heuristic بسيط، مش نموذج
    إحصائي متقدم لكشف الأنظمة (regime detection)، لكنه كافٍ لغرضنا هنا:
    التأكد إن أداء النظام مش مقتصر على موجة صعود عامة بالسوق.
    """
    pct_change = close.pct_change(lookback) * 100
    regime = pd.Series("sideways", index=close.index)
    regime[pct_change > threshold_pct] = "bull"
    regime[pct_change < -threshold_pct] = "bear"
    return regime


def backtest_by_market_regime(
    symbol: str,
    period: str = "5y",
    holding_days: int = 10,
    buy_threshold: float = 20.0,
    sell_threshold: float = -20.0,
) -> dict:
    """
    يحسب أداء إشارات الشراء منفصلًا لكل حالة سوق (صاعد/هابط/عرضي) بناءً
    على حالة السوق في يوم الإشارة نفسه. لو النظام بيدّي نتايج جيدة بس في
    السوق الصاعد ونتايج سيئة في الهابط/العرضي، ده مؤشر إن الأداء العام
    مدفوع بالاتجاه العام مش بجودة الإشارات نفسها.
    """
    try:
        df = fetch_history(symbol, period=period)
    except HistoryNotFoundError as e:
        raise ValueError(str(e)) from e

    close = df["Close"]
    scores = compute_daily_scores(df)
    regime = _classify_market_regime(close)
    future_return = _future_returns(close, holding_days)

    buy_mask = scores >= buy_threshold
    results = {}
    for regime_name in ["bull", "bear", "sideways"]:
        regime_buy_mask = buy_mask & (regime == regime_name)
        regime_returns = future_return[regime_buy_mask].dropna()
        results[regime_name] = _summarize_trades(regime_returns, is_short=False)

    regime_names_ar = {"bull": "سوق صاعد", "bear": "سوق هابط", "sideways": "سوق عرضي"}
    return {
        "symbol": symbol.upper(),
        "period_tested": period,
        "by_regime": {regime_names_ar[k]: v for k, v in results.items()},
        "note": (
            "أداء إشارات الشراء مقسّم حسب حالة السوق وقت صدور الإشارة. لو "
            "الأداء قوي بس في 'سوق صاعد' وضعيف في الباقي، فالنظام على الأرجح "
            "بيستفيد من الاتجاه العام للسوق مش من جودة الإشارات في حد ذاتها."
        ),
    }
