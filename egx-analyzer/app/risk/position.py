# -*- coding: utf-8 -*-
"""
Risk Management Engine: يحوّل الاتجاه الفني (Score إيجابي/سلبي) لخطة تنفيذ
ملموسة - نقطة دخول، وقف خسارة، أهداف متعددة، ونسبة المخاطرة للعائد (R:R) -
مبنية على مستويات دعم/مقاومة فعلية وATR (تذبذب طبيعي للسهم)، مش أرقام
عشوائية أو نسب ثابتة.

القاعدة الأهم (غير قابلة للتفاوض): لو R:R أقل من الحد الأدنى المقبول،
الفرصة تُرفض ولا تُعرض كخطة تنفيذ صالحة - حتى لو كان التحليل الفني نفسه
إيجابي. "لا توجد فرصة مناسبة" نتيجة صحيحة، مش قصور في النظام.
"""

import logging

import pandas as pd

from app.indicators.volatility import average_true_range

log = logging.getLogger("risk_engine")

MIN_ACCEPTABLE_RR = 1.5  # الحد الأدنى المقبول لنسبة العائد للمخاطرة
ATR_STOP_MULTIPLIER = 1.5  # مضاعف ATR لحساب وقف الخسارة البديل

# إعدادات خطة المضاربة القصيرة (نسب ثابتة بدل ATR/فيبوناتشي) - افتراضيًا
# هدف 5% مقابل وقف خسارة 1.5% (R:R ≈ 1:3.3)، حسب طلب المستخدم تحديدًا
SPECULATION_STOP_LOSS_PCT = 1.5
SPECULATION_TARGET_PCT = 5.0


def _round(x, decimals=2):
    return round(x, decimals) if x is not None else None


def _empty_plan(status: str, status_label: str) -> dict:
    return {
        "status": status,
        "status_label": status_label,
        "entry": None,
        "stop_loss": None,
        "targets": [],
        "risk": None,
        "reward": None,
        "risk_reward_ratio": None,
    }


def _fibonacci_support_resistance(fibonacci_levels: dict, entry: float) -> dict:
    """
    يرتب مستويات فيبوناتشي (0%, 23.6%, 38.2%, 50%, 61.8%, 100%) ويلاقي
    أقرب دعم (أعلى مستوى أقل من سعر الدخول) وأقرب مقاومة (أقل مستوى أعلى
    من سعر الدخول)، بالإضافة لكل المستويات الأعلى مرتبة (تستخدم كأهداف
    متعددة لو توفرت).
    """
    if not fibonacci_levels:
        return {"support": None, "resistance": None, "levels_above": []}

    values = sorted(set(fibonacci_levels.values()))
    below = [v for v in values if v < entry]
    above = [v for v in values if v > entry]

    return {
        "support": max(below) if below else None,
        "resistance": min(above) if above else None,
        "levels_above": sorted(above),  # تصاعديًا - أقرب مقاومة أولًا، تصلح كأهداف متتالية
    }


def build_trade_plan(
    df: pd.DataFrame,
    score: float,
    support_resistance: dict,
    fibonacci_levels: dict = None,
) -> dict:
    """
    يبني خطة تداول كاملة لو الشروط مواتية، أو يرجع سبب واضح لرفض الفرصة.

    المنطق:
    1. لو مفيش اتجاه صاعد كافٍ في التحليل الفني (score <= 0) → مفيش خطة شراء.
    2. لو مفيش بيانات كافية لحساب ATR → "بيانات غير كافية" صراحة.
    3. الدخول عند السعر الحالي. وقف الخسارة أسفل أقرب دعم (فيبوناتشي لو
       متوفر، وإلا الدعم البسيط من recent_support_resistance) بهامش أمان،
       أو عبر ATR أيهما أكثر منطقية.
    4. الأهداف: مستويات فيبوناتشي المتتالية فوق سعر الدخول لو متوفرة
       ومحققة حد أدنى معقول من R:R لكل هدف، وإلا يُحسب من مضاعفات
       المخاطرة مباشرة - فيبوناتشي مصدر أساسي مش الوحيد.
    5. لو R:R الناتج أقل من MIN_ACCEPTABLE_RR → رفض صريح مع توضيح السبب.
    """
    close = df["Close"]
    last_price = close.iloc[-1]

    atr_series = average_true_range(df, 14)
    last_atr = atr_series.iloc[-1] if len(atr_series) else None

    if last_atr is None or pd.isna(last_atr):
        return _empty_plan("insufficient_data", "⚪ بيانات غير كافية لحساب خطة التداول")

    if score <= 0:
        return _empty_plan(
            "no_bullish_setup",
            "⚪ لا توجد فرصة شراء حاليًا (التحليل الفني لا يظهر اتجاهًا صاعدًا كافيًا)",
        )

    entry = last_price
    fib = _fibonacci_support_resistance(fibonacci_levels or {}, entry)

    # الدعم: نفضّل الدعم الفعلي البسيط (أعلى/أدنى سعر أخيرًا) لو موجود
    # ومنطقي، وإلا ندّي الأولوية لأقرب مستوى فيبوناتشي تحت السعر - عشان
    # الدعم يفضل "أقرب نقطة واقعية" مش بعيد أوي عن سعر الدخول
    simple_support = support_resistance.get("support")
    candidate_supports = [
        s for s in [simple_support, fib["support"]] if s is not None and s < entry
    ]
    chosen_support = max(candidate_supports) if candidate_supports else None

    # وقف الخسارة: أسفل الدعم المختار بهامش أمان 0.5%، أو عبر ATR لو مفيش
    # دعم متاح أو منطقي
    atr_based_stop = entry - ATR_STOP_MULTIPLIER * last_atr
    support_based_stop = chosen_support * 0.995 if chosen_support else None
    stop_loss = support_based_stop if support_based_stop else atr_based_stop

    risk = entry - stop_loss
    if risk <= 0:
        return _empty_plan("insufficient_data", "⚪ تعذر حساب وقف خسارة منطقي بالبيانات المتاحة")

    # الأهداف: نجرّب مستويات فيبوناتشي فوق سعر الدخول أولًا (مرتبة تصاعديًا)
    # كل مستوى بيتقبل بس لو بيحقق حد أدنى معقول من R:R - وإلا نستخدم مضاعف
    # المخاطرة العادي بدله (نفس منطق الحماية من "هدف قريب مصطنع" زي قبل كده)
    min_reward = risk * MIN_ACCEPTABLE_RR
    fib_targets = [lvl for lvl in fib["levels_above"] if (lvl - entry) >= min_reward]

    fallback_targets = [
        entry + risk * MIN_ACCEPTABLE_RR,
        entry + risk * (MIN_ACCEPTABLE_RR + 1),
        entry + risk * (MIN_ACCEPTABLE_RR + 2),
    ]

    targets = []
    for i in range(3):
        if i < len(fib_targets):
            targets.append(fib_targets[i])
        else:
            targets.append(fallback_targets[i])
    targets = sorted(set(_round(t) for t in targets))  # إزالة أي تكرار بين فيبوناتشي والمضاعفات

    target1 = targets[0]
    reward = target1 - entry
    risk_reward_ratio = round(reward / risk, 2) if risk else None

    used_fibonacci = len(fib_targets) > 0 or (fib["support"] is not None and chosen_support == fib["support"])

    # نقارن بعد التقريب مباشرة - عشان الرقم المعروض للمستخدم يفضل متسق مع
    # قرار القبول/الرفض (لو قارنا بالقيمة الخام قبل التقريب، ممكن يظهر رفض
    # لفرصة الرقم المعروض بتاعها 1.5 بالظبط بسبب خطأ تقريب عائم بسيط)
    if not risk_reward_ratio or risk_reward_ratio < MIN_ACCEPTABLE_RR:
        return {
            "status": "rejected_low_rr",
            "status_label": (
                f"⚪ لا توجد فرصة مناسبة حاليًا "
                f"(R:R = 1:{risk_reward_ratio:.2f} أقل من الحد الأدنى 1:{MIN_ACCEPTABLE_RR})"
                if risk_reward_ratio else "⚪ لا توجد فرصة مناسبة حاليًا (تعذر حساب R:R)"
            ),
            "entry": _round(entry),
            "stop_loss": _round(stop_loss),
            "targets": [target1],
            "risk": _round(risk),
            "reward": _round(reward),
            "risk_reward_ratio": _round(risk_reward_ratio, 2),
            "based_on_fibonacci": used_fibonacci,
        }

    return {
        "status": "valid_long_setup",
        "status_label": "🟢 خطة تداول صالحة (شراء)",
        "entry": _round(entry),
        "stop_loss": _round(stop_loss),
        "targets": targets,
        "risk": _round(risk),
        "reward": _round(reward),
        "risk_reward_ratio": _round(risk_reward_ratio, 2),
        "based_on_fibonacci": used_fibonacci,
    }


def suggest_trailing_stop(entry: float, current_target_hit: int, stop_loss: float, targets: list) -> float:
    """
    يقترح تحريك وقف الخسارة بعد تحقق كل هدف - لتأمين الأرباح تدريجيًا بدل
    ترك الصفقة عرضة لارتداد كامل. current_target_hit: 0 = لسه مفيش هدف
    تحقق، 1 = الهدف الأول تحقق، وهكذا.
    """
    if current_target_hit <= 0:
        return stop_loss
    if current_target_hit == 1:
        return entry  # تأمين نقطة التعادل بعد الهدف الأول
    if current_target_hit >= 2 and len(targets) >= 1:
        return targets[0]  # تحريك الوقف لمستوى الهدف الأول بعد تحقق الثاني
    return stop_loss


def build_speculative_trade_plan(
    df: pd.DataFrame,
    score: float,
    stop_loss_pct: float = SPECULATION_STOP_LOSS_PCT,
    target_pct: float = SPECULATION_TARGET_PCT,
) -> dict:
    """
    خطة مضاربة قصيرة الأجل بنسب ثابتة (وقف خسارة % وهدف % محددين مسبقًا)
    بدل الاعتماد على ATR/الدعم/فيبوناتشي - مناسبة لأسلوب مضاربة سريع
    بنسبة مخاطرة/عائد ثابتة معروفة مقدمًا، بعكس build_trade_plan اللي
    بيدي نسب متغيرة حسب تذبذب السهم نفسه.

    الافتراضي: وقف 1.5% وهدف 5% (R:R ≈ 1:3.3) - القيم قابلة للتخصيص.
    نفس قاعدة الرفض: لو الناتج R:R < MIN_ACCEPTABLE_RR (نادر جدًا بالنسب
    الافتراضية) بيترفض بنفس المنطق.
    """
    close = df["Close"]
    last_price = close.iloc[-1]

    if score <= 0:
        plan = _empty_plan(
            "no_bullish_setup",
            "⚪ لا توجد فرصة شراء حاليًا (التحليل الفني لا يظهر اتجاهًا صاعدًا كافيًا)",
        )
        plan["mode"] = "speculation"
        return plan

    entry = last_price
    stop_loss = entry * (1 - stop_loss_pct / 100)
    target = entry * (1 + target_pct / 100)
    risk = entry - stop_loss
    reward = target - entry
    risk_reward_ratio = round(reward / risk, 2) if risk else None

    if not risk_reward_ratio or risk_reward_ratio < MIN_ACCEPTABLE_RR:
        return {
            "status": "rejected_low_rr",
            "status_label": (
                f"⚪ نسب المضاربة المدخلة بتدي R:R = 1:{risk_reward_ratio:.2f} "
                f"أقل من الحد الأدنى 1:{MIN_ACCEPTABLE_RR} - جرّب هدف أعلى أو وقف أضيق"
            ),
            "entry": _round(entry),
            "stop_loss": _round(stop_loss),
            "targets": [_round(target)],
            "risk": _round(risk),
            "reward": _round(reward),
            "risk_reward_ratio": _round(risk_reward_ratio, 2) if risk_reward_ratio else None,
            "mode": "speculation",
            "stop_loss_pct": stop_loss_pct,
            "target_pct": target_pct,
        }

    return {
        "status": "valid_long_setup",
        "status_label": f"🟢 خطة مضاربة قصيرة (هدف {target_pct}% / وقف {stop_loss_pct}%)",
        "entry": _round(entry),
        "stop_loss": _round(stop_loss),
        "targets": [_round(target)],
        "risk": _round(risk),
        "reward": _round(reward),
        "risk_reward_ratio": _round(risk_reward_ratio, 2),
        "mode": "speculation",
        "stop_loss_pct": stop_loss_pct,
        "target_pct": target_pct,
    }
