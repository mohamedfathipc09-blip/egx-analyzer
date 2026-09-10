# -*- coding: utf-8 -*-
"""اختبارات وحدة لطبقة Risk Management Engine (app/risk/position.py)."""

import numpy as np
import pandas as pd
import pytest

from app.risk.position import (
    build_trade_plan, suggest_trailing_stop, MIN_ACCEPTABLE_RR,
    _fibonacci_support_resistance, build_speculative_trade_plan,
)


def _make_df(n=250, direction="up", noise=1.0, seed=42):
    np.random.seed(seed)
    base = np.linspace(100, 150, n) if direction == "up" else np.linspace(150, 100, n)
    close = pd.Series(base + np.random.normal(0, noise, n))
    high = close + abs(np.random.normal(1, 0.3, n))
    low = close - abs(np.random.normal(1, 0.3, n))
    open_ = close.shift(1).fillna(close.iloc[0])
    vol = pd.Series(np.random.randint(1000, 5000, n))
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    return pd.DataFrame({"Open": open_.values, "High": high.values, "Low": low.values,
                          "Close": close.values, "Volume": vol.values}, index=idx)


def test_no_bullish_setup_when_score_not_positive():
    df = _make_df(direction="down")
    plan = build_trade_plan(df, score=-30, support_resistance={"support": 90, "resistance": 140})
    assert plan["status"] == "no_bullish_setup"
    assert plan["entry"] is None
    assert plan["stop_loss"] is None
    assert plan["targets"] == []


def test_insufficient_data_returns_explicit_status():
    short_df = pd.DataFrame({
        "Open": [10, 11], "High": [11, 12], "Low": [9, 10],
        "Close": [10.5, 11.5], "Volume": [1000, 1200],
    })
    plan = build_trade_plan(short_df, score=30, support_resistance={"support": 9, "resistance": 12})
    assert plan["status"] == "insufficient_data"


def test_valid_setup_has_consistent_fields():
    df = _make_df(direction="up", seed=33)
    support_resistance = {"support": df["Low"].tail(60).min(), "resistance": df["High"].tail(60).max()}
    plan = build_trade_plan(df, score=35, support_resistance=support_resistance)
    if plan["status"] == "valid_long_setup":
        assert plan["stop_loss"] < plan["entry"]
        assert plan["targets"][0] > plan["entry"]
        assert plan["risk_reward_ratio"] >= MIN_ACCEPTABLE_RR
        # الأهداف لازم تكون مرتبة تصاعديًا
        assert plan["targets"] == sorted(plan["targets"])


def test_rejected_plan_never_shows_rr_above_threshold():
    """
    اختبار انحدار (regression) لباگ حقيقي: كانت بعض الحالات بترفض الفرصة
    (rejected_low_rr) بينما الرقم المعروض للمستخدم R:R >= 1.5 بسبب خطأ
    تقريب عائم - وده تناقض مربك. نتأكد إنه ما بيتكررش عبر عينات كتير.
    """
    for seed in range(1, 40):
        df = _make_df(direction="up", seed=seed, noise=1.0)
        support_resistance = {"support": df["Low"].tail(60).min(), "resistance": df["High"].tail(60).max()}
        plan = build_trade_plan(df, score=30, support_resistance=support_resistance)
        if plan["status"] == "rejected_low_rr" and plan["risk_reward_ratio"] is not None:
            assert plan["risk_reward_ratio"] < MIN_ACCEPTABLE_RR, (
                f"seed={seed}: رُفضت الفرصة لكن R:R المعروض ({plan['risk_reward_ratio']}) "
                f"يساوي أو أعلى من الحد الأدنى - تناقض"
            )


def test_valid_setup_never_rejected_below_threshold():
    """العكس: أي خطة اتقبلت لازم فعلًا يكون R:R بتاعها >= الحد الأدنى."""
    for seed in range(1, 40):
        df = _make_df(direction="up", seed=seed, noise=1.0)
        support_resistance = {"support": df["Low"].tail(60).min(), "resistance": df["High"].tail(60).max()}
        plan = build_trade_plan(df, score=30, support_resistance=support_resistance)
        if plan["status"] == "valid_long_setup":
            assert plan["risk_reward_ratio"] >= MIN_ACCEPTABLE_RR


def test_suggest_trailing_stop_progression():
    entry, stop_loss = 100.0, 90.0
    targets = [110.0, 120.0, 130.0]

    assert suggest_trailing_stop(entry, 0, stop_loss, targets) == stop_loss
    assert suggest_trailing_stop(entry, 1, stop_loss, targets) == entry  # تعادل بعد الهدف الأول
    assert suggest_trailing_stop(entry, 2, stop_loss, targets) == targets[0]  # تأمين ربح بعد الهدف الثاني


# ------------------------------------------------------------------ فيبوناتشي

def test_fibonacci_support_resistance_finds_nearest_levels():
    fib = {"0.0%": 150, "23.6%": 138, "38.2%": 130, "50.0%": 125, "61.8%": 120, "100.0%": 100}
    result = _fibonacci_support_resistance(fib, entry=128)
    assert result["support"] == 125
    assert result["resistance"] == 130
    assert result["levels_above"] == [130, 138, 150]


def test_fibonacci_support_resistance_handles_empty_levels():
    result = _fibonacci_support_resistance({}, entry=100)
    assert result["support"] is None
    assert result["resistance"] is None
    assert result["levels_above"] == []


def test_fibonacci_support_resistance_entry_below_all_levels():
    fib = {"0.0%": 150, "100.0%": 100}
    result = _fibonacci_support_resistance(fib, entry=90)
    assert result["support"] is None  # مفيش مستوى تحت السعر
    assert result["resistance"] == 100


def test_fibonacci_support_resistance_entry_above_all_levels():
    fib = {"0.0%": 150, "100.0%": 100}
    result = _fibonacci_support_resistance(fib, entry=200)
    assert result["support"] == 150
    assert result["resistance"] is None  # مفيش مستوى فوق السعر - المفروض fallback لمضاعف المخاطرة


def test_build_trade_plan_uses_fibonacci_targets_when_available():
    df = _make_df(direction="up", seed=33)
    support_resistance = {"support": df["Low"].tail(60).min(), "resistance": df["High"].tail(60).max()}
    entry_price = df["Close"].iloc[-1]
    # نصنع مستويات فيبوناتشي فيها مقاومة قريبة قابلة للاستخدام كهدف
    fib_levels = {
        "0.0%": entry_price * 1.3, "23.6%": entry_price * 1.15,
        "50.0%": entry_price * 1.05, "100.0%": entry_price * 0.8,
    }
    plan = build_trade_plan(df, score=35, support_resistance=support_resistance, fibonacci_levels=fib_levels)
    if plan["status"] == "valid_long_setup":
        assert plan.get("based_on_fibonacci") is True


def test_build_trade_plan_falls_back_gracefully_without_fibonacci():
    """التوافقية القديمة: النداء من غير fibonacci_levels لازم يفضل شغال زي الأول."""
    df = _make_df(direction="up", seed=33)
    support_resistance = {"support": df["Low"].tail(60).min(), "resistance": df["High"].tail(60).max()}
    plan = build_trade_plan(df, score=35, support_resistance=support_resistance)
    assert "status" in plan
    assert plan.get("based_on_fibonacci") in (False, None)


def test_build_trade_plan_targets_always_sorted_with_fibonacci():
    for seed in range(1, 20):
        df = _make_df(direction="up", seed=seed, noise=1.0)
        support_resistance = {"support": df["Low"].tail(60).min(), "resistance": df["High"].tail(60).max()}
        entry_price = df["Close"].iloc[-1]
        fib_levels = {
            "0.0%": entry_price * 1.4, "38.2%": entry_price * 1.2,
            "61.8%": entry_price * 1.1, "100.0%": entry_price * 0.7,
        }
        plan = build_trade_plan(df, score=30, support_resistance=support_resistance, fibonacci_levels=fib_levels)
        if plan["status"] == "valid_long_setup":
            assert plan["targets"] == sorted(plan["targets"])
            assert len(plan["targets"]) == len(set(plan["targets"]))  # مفيش تكرار


# ------------------------------------------------------------ فيبوناتشي

def test_fibonacci_support_resistance_finds_nearest_levels():
    fib = {"0.0%": 150, "23.6%": 138, "38.2%": 130, "50.0%": 125, "61.8%": 120, "100.0%": 100}
    result = _fibonacci_support_resistance(fib, entry=128)
    assert result["support"] == 125
    assert result["resistance"] == 130
    assert result["levels_above"] == [130, 138, 150]


def test_fibonacci_support_resistance_handles_empty_levels():
    result = _fibonacci_support_resistance({}, entry=100)
    assert result["support"] is None
    assert result["resistance"] is None
    assert result["levels_above"] == []


def test_fibonacci_support_resistance_entry_above_all_levels():
    fib = {"0.0%": 150, "100.0%": 100}
    result = _fibonacci_support_resistance(fib, entry=200)
    assert result["support"] == 150
    assert result["resistance"] is None
    assert result["levels_above"] == []


def test_build_trade_plan_uses_fibonacci_targets_when_provided():
    df = _make_df(direction="up", seed=33)
    support_resistance = {"support": df["Low"].tail(60).min(), "resistance": df["High"].tail(60).max()}
    close = df["Close"]
    high, low = close.max(), close.min()
    diff = high - low
    fib_levels = {
        "0.0%": round(high, 2), "23.6%": round(high - 0.236 * diff, 2),
        "38.2%": round(high - 0.382 * diff, 2), "50.0%": round(high - 0.5 * diff, 2),
        "61.8%": round(high - 0.618 * diff, 2), "100.0%": round(low, 2),
    }
    plan = build_trade_plan(df, score=35, support_resistance=support_resistance, fibonacci_levels=fib_levels)
    if plan["status"] == "valid_long_setup":
        assert plan["stop_loss"] < plan["entry"]
        assert plan["targets"][0] > plan["entry"]
        assert plan["targets"] == sorted(plan["targets"])
        assert "based_on_fibonacci" in plan


def test_build_trade_plan_without_fibonacci_still_works():
    """توافقية: build_trade_plan من غير fibonacci_levels لازم يفضل شغال زي الأول بالظبط."""
    df = _make_df(direction="up", seed=10)
    support_resistance = {"support": df["Low"].tail(60).min(), "resistance": df["High"].tail(60).max()}
    plan = build_trade_plan(df, score=30, support_resistance=support_resistance)
    assert plan["status"] in ("valid_long_setup", "rejected_low_rr")


def test_build_trade_plan_targets_never_have_duplicates():
    """لو مستوى فيبوناتشي طابق مضاعف المخاطرة بالصدفة، الأهداف لازم تفضل فريدة."""
    df = _make_df(direction="up", seed=7)
    support_resistance = {"support": df["Low"].tail(60).min(), "resistance": df["High"].tail(60).max()}
    fib_levels = {"0.0%": 999999, "100.0%": 1}  # مستويات بعيدة جدًا - مش هتتقبل كأهداف
    plan = build_trade_plan(df, score=30, support_resistance=support_resistance, fibonacci_levels=fib_levels)
    if plan["status"] == "valid_long_setup":
        assert len(plan["targets"]) == len(set(plan["targets"]))


# ------------------------------------------------------------------ خطة المضاربة القصيرة (نسب ثابتة)

def test_speculative_plan_uses_exact_default_percentages():
    df = _make_df(direction="up", seed=1)
    entry_price = df["Close"].iloc[-1]
    plan = build_speculative_trade_plan(df, score=30)
    assert plan["status"] == "valid_long_setup"
    assert abs(plan["stop_loss"] - entry_price * 0.985) < 0.02
    assert abs(plan["targets"][0] - entry_price * 1.05) < 0.02
    assert plan["risk_reward_ratio"] == round(5.0 / 1.5, 2)
    assert plan["mode"] == "speculation"


def test_speculative_plan_rejects_when_no_bullish_direction():
    df = _make_df(direction="down", seed=1)
    plan = build_speculative_trade_plan(df, score=-20)
    assert plan["status"] == "no_bullish_setup"
    assert plan["entry"] is None


def test_speculative_plan_accepts_custom_percentages():
    df = _make_df(direction="up", seed=1)
    plan = build_speculative_trade_plan(df, score=30, stop_loss_pct=2.0, target_pct=6.0)
    assert plan["risk_reward_ratio"] == 3.0
    assert plan["stop_loss_pct"] == 2.0
    assert plan["target_pct"] == 6.0


def test_speculative_plan_rejects_bad_risk_reward_ratio():
    df = _make_df(direction="up", seed=1)
    plan = build_speculative_trade_plan(df, score=30, stop_loss_pct=5.0, target_pct=3.0)
    assert plan["status"] == "rejected_low_rr"


def test_speculative_plan_independent_of_atr_fibonacci_inputs():
    """خطة المضاربة القصيرة لازم تفضل ثابتة بالنسبة المئوية بغض النظر عن تذبذب السهم (عكس الخطة القياسية)."""
    low_vol_df = _make_df(direction="up", seed=1, noise=0.2)
    high_vol_df = _make_df(direction="up", seed=1, noise=5.0)
    plan_low = build_speculative_trade_plan(low_vol_df, score=30)
    plan_high = build_speculative_trade_plan(high_vol_df, score=30)
    # نسبة الوقف عن سعر الدخول لازم تكون 1.5% في الحالتين بالظبط، بغض النظر عن التذبذب
    ratio_low = (plan_low["entry"] - plan_low["stop_loss"]) / plan_low["entry"] * 100
    ratio_high = (plan_high["entry"] - plan_high["stop_loss"]) / plan_high["entry"] * 100
    assert abs(ratio_low - 1.5) < 0.05
    assert abs(ratio_high - 1.5) < 0.05
