# -*- coding: utf-8 -*-
"""
نظام التصويت والتجميع (Confluence System): يجمع إشارات كل المؤشرات في
درجة موزونة واحدة (Score) ويحدد التوصية، مع حساب نسبة توافق المؤشرات
كمقياس منفصل تمامًا عن أي نسبة نجاح تاريخية (تلك تُحسب فقط في backtesting).
"""

import logging
from datetime import datetime

import pandas as pd

from app.config import CATEGORY_WEIGHTS, SCORE_THRESHOLDS, DISCLAIMER
from app.data.history_client import fetch_history, HistoryNotFoundError
from app.indicators import trend, momentum, volatility, volume, patterns
from app.signals.interpreter import enrich_category_votes
from app.signals.conflict_detector import detect_conflict
from app.risk.position import build_trade_plan, build_speculative_trade_plan
from app.data.quality import validate_data_quality

log = logging.getLogger("scoring")


def _safe_last(series: pd.Series):
    if series is None or len(series) == 0:
        return None
    val = series.iloc[-1]
    return None if pd.isna(val) else val


def _vote_trend(df: pd.DataFrame) -> dict:
    close = df["Close"]
    votes = {}

    sma50, sma200 = trend.sma(close, 50), trend.sma(close, 200)
    v = 0
    if len(close) >= 200 and _safe_last(sma50) is not None and _safe_last(sma200) is not None:
        v = 1 if sma50.iloc[-1] > sma200.iloc[-1] else -1
    votes["sma_cross"] = {
        "vote": v,
        "signal": "صاعد (Golden Cross)" if v == 1 else ("هابط (Death Cross)" if v == -1 else "بيانات غير كافية"),
        "sma50": round(_safe_last(sma50), 2) if _safe_last(sma50) is not None else None,
        "sma200": round(_safe_last(sma200), 2) if _safe_last(sma200) is not None else None,
    }

    adx_df = trend.adx(df, 14)
    last_adx = _safe_last(adx_df["adx"])
    last_plus_di = _safe_last(adx_df["plus_di"])
    last_minus_di = _safe_last(adx_df["minus_di"])
    if last_adx is None or last_plus_di is None or last_minus_di is None:
        v = 0
        sig = "بيانات غير كافية"
    elif last_adx < 20:
        v = 0
        sig = f"اتجاه ضعيف/عرضي (ADX={last_adx:.1f})"
    else:
        v = 1 if last_plus_di > last_minus_di else -1
        sig = f"اتجاه {'صاعد' if v == 1 else 'هابط'} قوي (ADX={last_adx:.1f})"
    votes["adx"] = {"vote": v, "signal": sig, "adx": round(last_adx, 2) if last_adx is not None else None}

    sar = trend.parabolic_sar(df)
    last_sar, last_close = _safe_last(sar), close.iloc[-1]
    if last_sar is None:
        v, sig = 0, "بيانات غير كافية"
    else:
        v = 1 if last_close > last_sar else -1
        sig = "السعر فوق SAR (صاعد)" if v == 1 else "السعر تحت SAR (هابط)"
    votes["parabolic_sar"] = {"vote": v, "signal": sig, "sar": round(last_sar, 2) if last_sar is not None else None}

    ichi = trend.ichimoku(df)
    last_a, last_b = _safe_last(ichi["senkou_span_a"]), _safe_last(ichi["senkou_span_b"])
    if last_a is None or last_b is None:
        v, sig = 0, "بيانات غير كافية"
    else:
        cloud_top, cloud_bottom = max(last_a, last_b), min(last_a, last_b)
        if last_close > cloud_top:
            v, sig = 1, "السعر فوق سحابة إيشيموكو (صاعد)"
        elif last_close < cloud_bottom:
            v, sig = -1, "السعر تحت سحابة إيشيموكو (هابط)"
        else:
            v, sig = 0, "السعر داخل السحابة (تذبذب/تردد)"
    votes["ichimoku"] = {"vote": v, "signal": sig}

    return votes


def _vote_momentum(df: pd.DataFrame) -> dict:
    close = df["Close"]
    votes = {}

    rsi_val = _safe_last(momentum.rsi(close, 14))
    if rsi_val is None:
        v, sig = 0, "بيانات غير كافية"
    elif rsi_val < 30:
        v, sig = 1, "تشبع بيعي (فرصة ارتداد محتملة)"
    elif rsi_val > 70:
        v, sig = -1, "تشبع شرائي (احتمال تصحيح)"
    else:
        v, sig = 0, "منطقة محايدة"
    votes["rsi"] = {"vote": v, "signal": sig, "value": round(rsi_val, 2) if rsi_val is not None else None}

    macd_line, signal_line, hist = momentum.macd(close)
    h_last, h_prev = _safe_last(hist), (hist.iloc[-2] if len(hist) > 1 and not pd.isna(hist.iloc[-2]) else None)
    if h_last is None or h_prev is None:
        v, sig = 0, "بيانات غير كافية"
    elif h_prev <= 0 < h_last:
        v, sig = 1, "تقاطع صاعد حديث"
    elif h_prev >= 0 > h_last:
        v, sig = -1, "تقاطع هابط حديث"
    else:
        v = 1 if h_last > 0 else -1
        sig = "زخم صاعد مستمر" if v == 1 else "زخم هابط مستمر"
    votes["macd"] = {"vote": v, "signal": sig}

    k, d = momentum.stochastic(df)
    k_last, d_last = _safe_last(k), _safe_last(d)
    if k_last is None or d_last is None:
        v, sig = 0, "بيانات غير كافية"
    elif k_last < 20 and k_last > d_last:
        v, sig = 1, "تشبع بيعي مع تقاطع صاعد"
    elif k_last > 80 and k_last < d_last:
        v, sig = -1, "تشبع شرائي مع تقاطع هابط"
    else:
        v, sig = 0, "منطقة محايدة"
    votes["stochastic"] = {"vote": v, "signal": sig}

    wr = _safe_last(momentum.williams_r(df, 14))
    if wr is None:
        v, sig = 0, "بيانات غير كافية"
    elif wr < -80:
        v, sig = 1, "تشبع بيعي (Williams %R)"
    elif wr > -20:
        v, sig = -1, "تشبع شرائي (Williams %R)"
    else:
        v, sig = 0, "منطقة محايدة"
    votes["williams_r"] = {"vote": v, "signal": sig, "value": round(wr, 2) if wr is not None else None}

    cci_val = _safe_last(momentum.cci(df, 20))
    if cci_val is None:
        v, sig = 0, "بيانات غير كافية"
    elif cci_val < -100:
        v, sig = 1, "تشبع بيعي (CCI)"
    elif cci_val > 100:
        v, sig = -1, "تشبع شرائي (CCI)"
    else:
        v, sig = 0, "منطقة محايدة"
    votes["cci"] = {"vote": v, "signal": sig, "value": round(cci_val, 2) if cci_val is not None else None}

    return votes


def _vote_volatility(df: pd.DataFrame) -> dict:
    close = df["Close"]
    last_close = close.iloc[-1]
    votes = {}

    upper, mid, lower = volatility.bollinger_bands(close)
    u, l = _safe_last(upper), _safe_last(lower)
    if u is None or l is None:
        v, sig = 0, "بيانات غير كافية"
    elif last_close <= l:
        v, sig = 1, "السعر عند/تحت النطاق السفلي (بيع مبالغ فيه)"
    elif last_close >= u:
        v, sig = -1, "السعر عند/فوق النطاق العلوي (شراء مبالغ فيه)"
    else:
        v, sig = 0, "داخل النطاق الطبيعي"
    votes["bollinger"] = {"vote": v, "signal": sig,
                           "upper": round(u, 2) if u is not None else None,
                           "lower": round(l, 2) if l is not None else None}

    k_upper, k_mid, k_lower = volatility.keltner_channels(df)
    ku, kl = _safe_last(k_upper), _safe_last(k_lower)
    if u is not None and ku is not None and u > ku:
        v, sig = 1, "بولينجر تخترق كيلتنر للأعلى (تمدد تذبذب حقيقي)"
    elif l is not None and kl is not None and l < kl:
        v, sig = -1, "بولينجر تخترق كيلتنر للأسفل (تمدد تذبذب حقيقي هابط)"
    else:
        v, sig = 0, "لا يوجد اختراق واضح بين القناتين"
    votes["keltner_vs_bollinger"] = {"vote": v, "signal": sig}

    return votes


def _vote_volume(df: pd.DataFrame) -> dict:
    votes = {}
    vol = df["Volume"]
    vol_avg, ratio = volume.volume_vs_average(df, 20)
    r_last = _safe_last(ratio)
    price_change = df["Close"].iloc[-1] - df["Close"].iloc[-2] if len(df) > 1 else 0

    if r_last is None:
        v, sig = 0, "بيانات غير كافية"
    elif r_last > 1.5:
        v = 1 if price_change > 0 else (-1 if price_change < 0 else 0)
        sig = "حجم تداول مرتفع يؤكد حركة السعر الأخيرة"
    else:
        v, sig = 0, "حجم تداول عادي"
    votes["volume_trend"] = {"vote": v, "signal": sig,
                              "ratio_to_avg20": round(r_last, 2) if r_last is not None else None}

    obv = volume.on_balance_volume(df)
    if len(obv) >= 20:
        obv_slope = obv.iloc[-1] - obv.iloc[-20]
        v = 1 if obv_slope > 0 else (-1 if obv_slope < 0 else 0)
        sig = "تدفق أموال إيجابي (OBV صاعد)" if v == 1 else "تدفق أموال سلبي (OBV هابط)"
    else:
        v, sig = 0, "بيانات غير كافية"
    votes["obv"] = {"vote": v, "signal": sig}

    return votes


def _aggregate(category_votes: dict) -> float:
    """كل فئة بتاخد متوسط أصوات مؤشراتها، وبعدين بيتحسب متوسط موزون بين الفئات."""
    weighted_sum = 0.0
    for category, indicators_dict in category_votes.items():
        weight = CATEGORY_WEIGHTS.get(category, 0)
        votes = [i["vote"] for i in indicators_dict.values()]
        category_avg = sum(votes) / len(votes) if votes else 0
        weighted_sum += category_avg * weight
    return round(weighted_sum * 100, 1)  # من -100 إلى +100


def _recommendation_from_score(score: float) -> str:
    t = SCORE_THRESHOLDS
    if score >= t["strong_buy"]:
        return "شراء قوي (Strong Buy)"
    if score >= t["buy"]:
        return "شراء (Buy)"
    if score <= t["strong_sell"]:
        return "بيع قوي (Strong Sell)"
    if score <= t["sell"]:
        return "بيع (Sell)"
    return "محايد / انتظار (Hold)"


def analyze_stock(
    symbol: str,
    timeframe: str = "daily",
    period: str = "1y",
    speculation_stop_loss_pct: float = None,
    speculation_target_pct: float = None,
) -> dict:
    """
    يحلل سهمًا واحدًا عبر كل فئات المؤشرات (اتجاه/زخم/تذبذب/حجم) بالإضافة
    إلى الدعم/المقاومة وأنماط الشموع، ويرجع توصية نهائية مبنية على توافق
    الإشارات. timeframe: "daily" أو "weekly".
    """
    interval = "1d" if timeframe == "daily" else "1wk"
    try:
        df = fetch_history(symbol, period=period, interval=interval)
    except HistoryNotFoundError as e:
        raise ValueError(str(e)) from e

    if len(df) < 15:
        raise ValueError(f"بيانات تاريخية غير كافية لتحليل {symbol} (متاح {len(df)} شمعة فقط)")

    data_quality = validate_data_quality(df)

    category_votes = {
        "trend": _vote_trend(df),
        "momentum": _vote_momentum(df),
        "volatility": _vote_volatility(df),
        "volume": _vote_volume(df),
    }
    category_votes = enrich_category_votes(category_votes)

    score = _aggregate(category_votes)

    # لو فيه مشكلة جوهرية في جودة البيانات (OHLC غير منطقي، شمعات مكررة...)،
    # نمنع "إشارة قوية" حتى لو المؤشرات نفسها بتقول كده - التوصية لازم
    # تفضل ضمن حدود معتدلة لحد ما البيانات تتأكد
    if data_quality["has_critical_issues"]:
        score = max(-49.0, min(49.0, score))

    recommendation = _recommendation_from_score(score)

    all_votes = [i["vote"] for cat in category_votes.values() for i in cat.values()]
    active_votes = [v for v in all_votes if v != 0]
    bullish = sum(1 for v in active_votes if v > 0)
    bearish = sum(1 for v in active_votes if v < 0)
    agreement_percent = round((max(bullish, bearish) / len(active_votes)) * 100, 1) if active_votes else 0.0

    support_resistance = patterns.recent_support_resistance(df)
    fib_levels = patterns.fibonacci_levels(df)
    pivots = patterns.pivot_points(df)
    candle_patterns = patterns.detect_candlestick_patterns(df)
    trade_plan = build_trade_plan(df, score, support_resistance, fibonacci_levels=fib_levels)

    # خطة مضاربة قصيرة بنسب ثابتة (افتراضيًا هدف 5% / وقف 1.5%) - إضافية
    # جنب الخطة الأساسية، مش بديلة عنها، عشان تقدر تقارن الاتنين
    spec_kwargs = {}
    if speculation_stop_loss_pct is not None:
        spec_kwargs["stop_loss_pct"] = speculation_stop_loss_pct
    if speculation_target_pct is not None:
        spec_kwargs["target_pct"] = speculation_target_pct
    speculative_trade_plan = build_speculative_trade_plan(df, score, **spec_kwargs)

    # كشف التضارب القوي بين المؤشرات - حالة مختلفة عن "محايد" العادي.
    # لو المؤشرات فعليًا بتتعارك مع بعض (مش مجرد سوق هادئ)، منجبرش النظام
    # يديّ توصية شراء/بيع حتى لو الـ Score التجميعي مال لجهة معينة بالصدفة.
    conflict = detect_conflict(bullish, bearish)
    if conflict["is_conflicted"]:
        recommendation = "⚪ لا تداول - إشارات متضاربة (NO TRADE)"
        conflict_label = (
            "⚪ لا تداول حاليًا - المؤشرات متضاربة بشدة رغم إشارة الشراء الظاهرية. "
            "الأفضل انتظار وضوح أكبر بدل الدخول وسط عدم يقين حقيقي."
        )
        if trade_plan["status"] == "valid_long_setup":
            trade_plan = {**trade_plan, "status": "no_trade_conflicting_signals", "status_label": conflict_label}
        if speculative_trade_plan["status"] == "valid_long_setup":
            speculative_trade_plan = {
                **speculative_trade_plan,
                "status": "no_trade_conflicting_signals",
                "status_label": conflict_label,
            }

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "analyzed_at": datetime.now().isoformat(),
        "last_close": round(df["Close"].iloc[-1], 2),
        "recommendation": recommendation,
        "score": score,  # -100 (بيع قوي) إلى +100 (شراء قوي) - القيمة الخام تفضل زي ما هي حتى لو النظام رفض التوصية بسبب تضارب
        "agreement_percent": agreement_percent,  # توافق المؤشرات اللحظي - وليس نسبة نجاح تاريخية
        "indicators_bullish": bullish,
        "indicators_bearish": bearish,
        "indicators_neutral": len(all_votes) - len(active_votes),
        "signal_conflict": conflict,
        "data_quality": data_quality,
        "categories": category_votes,
        "support_resistance": support_resistance,
        "fibonacci_levels": fib_levels,
        "pivot_points": pivots,
        "candlestick_patterns": candle_patterns,
        "trade_plan": trade_plan,
        "speculative_trade_plan": speculative_trade_plan,
        "disclaimer": DISCLAIMER,
        "note": (
            "agreement_percent يقيس توافق المؤشرات الآن فقط، وليس نسبة نجاح "
            "متوقعة. للحصول على نسبة نجاح فعلية محسوبة من التاريخ، استخدم "
            "/backtest/{symbol}."
        ),
    }


def analyze_multiple(symbols: list, timeframe: str = "daily", period: str = "1y") -> list:
    results = []
    for s in symbols:
        try:
            results.append(analyze_stock(s, timeframe=timeframe, period=period))
        except Exception as e:
            log.warning("فشل تحليل %s: %s", s, e)
            results.append({"symbol": s.upper(), "error": str(e)})
    return results
