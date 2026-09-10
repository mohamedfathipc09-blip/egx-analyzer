# -*- coding: utf-8 -*-
"""
محرك اختبار الأداء التاريخي (Backtesting) لنظام التصويت في scoring.py.

الفكرة: بدل الثقة في النظام نظريًا، نرجع بالتاريخ ونحسب - لو كل مرة كانت
فيها إشارة شراء افترضنا شراءً وبيعًا بعد N يوم، كانت النتيجة إيه فعليًا؟

تحذير منهجي: هذا اختبار على بيانات ماضية. الأداء الممتاز تاريخيًا لا يضمن
نفس الأداء مستقبلًا (احتمال Overfitting أو تغيّر ظروف السوق). كل ما اختبرت
على فترات وأسهم أكتر، كل ما الأرقام كانت أوثق.
"""

import logging

import numpy as np
import pandas as pd

from app.config import CATEGORY_WEIGHTS
from app.data.history_client import fetch_history, HistoryNotFoundError
from app.indicators import trend, momentum, volatility, volume

log = logging.getLogger("backtest_engine")


def compute_daily_scores(df: pd.DataFrame) -> pd.Series:
    """
    نسخة متجهة (vectorized) من نفس منطق التصويت في scoring.py، لكن بتحسب
    Score لكل يوم في التاريخ مرة واحدة (أسرع بكثير من التكرار يوم بيوم).

    ملحوظة: هذه الدالة عامة (مش داخلية) عشان app/backtesting/robustness.py
    يقدر يعيد استخدامها في اختبارات Walk-Forward وفصل العينات، من غير ما
    نكرر نفس منطق حساب المؤشرات مرة تانية.
    """
    close = df["Close"]

    # ------- فئة الاتجاه
    sma50, sma200 = trend.sma(close, 50), trend.sma(close, 200)
    trend_sma_vote = np.where(sma50 > sma200, 1, -1)
    trend_sma_vote = np.where(sma50.isna() | sma200.isna(), 0, trend_sma_vote)

    adx_df = trend.adx(df, 14)
    adx_vote = np.where(
        adx_df["adx"] < 20, 0,
        np.where(adx_df["plus_di"] > adx_df["minus_di"], 1, -1),
    )
    adx_vote = np.where(adx_df["adx"].isna(), 0, adx_vote)

    sar = trend.parabolic_sar(df)
    sar_vote = np.where(close > sar, 1, -1)

    trend_votes = np.vstack([trend_sma_vote, adx_vote, sar_vote])
    trend_score = trend_votes.mean(axis=0)

    # ------- فئة الزخم
    rsi_s = momentum.rsi(close, 14)
    rsi_vote = np.select([rsi_s < 30, rsi_s > 70], [1, -1], default=0)
    rsi_vote = np.where(rsi_s.isna(), 0, rsi_vote)

    macd_line, signal_line, hist = momentum.macd(close)
    hist_prev = hist.shift(1)
    macd_vote = np.where(
        (hist_prev <= 0) & (hist > 0), 1,
        np.where((hist_prev >= 0) & (hist < 0), -1, np.where(hist > 0, 1, -1)),
    )
    macd_vote = np.where(hist.isna() | hist_prev.isna(), 0, macd_vote)

    k, d = momentum.stochastic(df)
    stoch_vote = np.select([(k < 20) & (k > d), (k > 80) & (k < d)], [1, -1], default=0)
    stoch_vote = np.where(k.isna() | d.isna(), 0, stoch_vote)

    momentum_votes = np.vstack([rsi_vote, macd_vote, stoch_vote])
    momentum_score = momentum_votes.mean(axis=0)

    # ------- فئة التذبذب
    upper, mid, lower = volatility.bollinger_bands(close)
    bb_vote = np.select([close <= lower, close >= upper], [1, -1], default=0)
    bb_vote = np.where(upper.isna() | lower.isna(), 0, bb_vote)
    volatility_score = bb_vote  # مؤشر واحد فقط في النسخة المتجهة المبسطة

    # ------- فئة الحجم
    vol_avg, ratio = volume.volume_vs_average(df, 20)
    price_change = close.diff()
    vol_vote = np.where(ratio > 1.5, np.sign(price_change), 0)
    vol_vote = np.where(ratio.isna(), 0, vol_vote)
    volume_score = vol_vote

    total = (
        trend_score * CATEGORY_WEIGHTS["trend"]
        + momentum_score * CATEGORY_WEIGHTS["momentum"]
        + volatility_score * CATEGORY_WEIGHTS["volatility"]
        + volume_score * CATEGORY_WEIGHTS["volume"]
    ) * 100

    return pd.Series(total, index=close.index)


# اسم قديم محتفظ به للتوافق - أي كود قديم بيستدعي الدالة بالاسم الداخلي لسه هيشتغل
_compute_daily_scores = compute_daily_scores


def _summarize_trades(returns: pd.Series, is_short: bool = False) -> dict:
    if len(returns) == 0:
        return {
            "n_trades": 0, "win_rate_percent": None, "avg_return_percent": None,
            "best_trade_percent": None, "worst_trade_percent": None,
            "avg_profit_percent": None, "avg_loss_percent": None,
            "profit_factor": None, "expected_value_percent": None,
        }
    realized = -returns if is_short else returns
    wins_mask = realized > 0
    losses_mask = realized <= 0
    n = len(realized)

    gross_profit = realized[wins_mask].sum()
    gross_loss = -realized[losses_mask].sum()  # رقم موجب يمثل إجمالي الخسائر

    return {
        "n_trades": int(n),
        "win_rate_percent": round(wins_mask.sum() / n * 100, 1),
        "avg_return_percent": round(realized.mean(), 2),
        "best_trade_percent": round(realized.max(), 2),
        "worst_trade_percent": round(realized.min(), 2),
        "avg_profit_percent": round(realized[wins_mask].mean(), 2) if wins_mask.any() else None,
        "avg_loss_percent": round(realized[losses_mask].mean(), 2) if losses_mask.any() else None,
        # Profit Factor = إجمالي الأرباح / إجمالي الخسائر. None لو مفيش خسائر
        # في العينة (مش infinity عشان يفضل قابل للتخزين/العرض بسهولة)
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else None,
        # Expected Value = متوسط العائد لكل صفقة (نفس avg_return لكن اسمه
        # الشائع في أدبيات التداول - بيتضاف كحقل منفصل زي ما طلب البرومت)
        "expected_value_percent": round(realized.mean(), 2),
    }


def _max_drawdown(equity_curve: pd.Series) -> float:
    running_max = equity_curve.cummax()
    drawdown = (equity_curve - running_max) / running_max
    return round(drawdown.min() * 100, 2)


def _sharpe_ratio(returns_pct: pd.Series, risk_free_rate_annual: float = 0.0) -> float:
    """نسبة شارب مبسطة على عوائد الصفقات الفردية (وليست يومية)."""
    if len(returns_pct) < 2 or returns_pct.std() == 0:
        return None
    excess = returns_pct - (risk_free_rate_annual / 252 * 100)
    return round((excess.mean() / excess.std()) * np.sqrt(252), 2)


def backtest_symbol(
    symbol: str,
    period: str = "2y",
    buy_threshold: float = 20.0,
    sell_threshold: float = -20.0,
    holding_days: int = 10,
) -> dict:
    """
    يختبر أداء نظام التصويت تاريخيًا: كل يوم كان فيه score >= buy_threshold
    (إشارة شراء)، نفترض شراءً عند إغلاق نفس اليوم وبيعًا بعد holding_days.
    يرجع نسبة نجاح فعلية محسوبة من التاريخ + مقارنة بعائد Buy & Hold.
    """
    try:
        df = fetch_history(symbol, period=period)
    except HistoryNotFoundError as e:
        raise ValueError(str(e)) from e

    close = df["Close"]
    scores = compute_daily_scores(df)
    future_return = (close.shift(-holding_days) - close) / close * 100

    buy_mask = scores >= buy_threshold
    sell_mask = scores <= sell_threshold

    buy_returns = future_return[buy_mask].dropna()
    sell_returns = future_return[sell_mask].dropna()

    buy_hold_return = round((close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100, 2)

    # منحنى تراكمي مبسط لصفقات الشراء فقط، لحساب Max Drawdown و Sharpe.
    # تنبيه منهجي: هذا المنحنى يفترض تنفيذ الصفقات بالتتابع (صفقة بعد الأخرى)
    # للتبسيط، رغم أن إشارات الشراء المتقاربة زمنيًا قد تتداخل فعليًا (holding
    # period واحد يغطي عدة إشارات متتالية). لذلك Max Drawdown هنا مؤشر تقريبي
    # على حدة التقلب بين الصفقات، وليس محاكاة دقيقة لمحفظة حقيقية متزامنة.
    equity_curve = (1 + buy_returns.fillna(0) / 100).cumprod() if len(buy_returns) else pd.Series([1.0])

    return {
        "symbol": symbol.upper(),
        "period_tested": period,
        "holding_days": holding_days,
        "buy_signal_threshold": buy_threshold,
        "sell_signal_threshold": sell_threshold,
        "buy_signals_performance": _summarize_trades(buy_returns, is_short=False),
        "sell_signals_performance": _summarize_trades(sell_returns, is_short=True),
        "buy_and_hold_return_percent": buy_hold_return,
        "max_drawdown_percent_buy_signals": _max_drawdown(equity_curve),
        "sharpe_ratio_buy_signals": _sharpe_ratio(buy_returns),
        "note": (
            "win_rate_percent هنا محسوب فعليًا من التاريخ (وليس تقديرًا)، لكنه "
            "خاص بالفترة والسهم والإعدادات المحددة. جرّب فترات وإعدادات مختلفة "
            "لتتأكد من استقرار النتائج - إذا كانت متذبذبة بشدة، فالنظام قد يكون "
            "غير مستقر (overfitted) على ظرف سوقي معين."
        ),
    }


def backtest_multiple(symbols: list, **kwargs) -> list:
    results = []
    for s in symbols:
        try:
            results.append(backtest_symbol(s, **kwargs))
        except Exception as e:
            log.warning("فشل backtest لـ %s: %s", s, e)
            results.append({"symbol": s.upper(), "error": str(e)})
    return results
