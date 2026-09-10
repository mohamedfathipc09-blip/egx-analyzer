# -*- coding: utf-8 -*-
"""اختبارات وحدة لطبقة Signal Engine (app/signals/interpreter.py)."""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from app.signals.interpreter import compute_impact, interpret_indicator, enrich_category_votes
from app.analysis import scoring


def test_compute_impact_zero_vote_is_zero():
    assert compute_impact(0, "momentum", 5) == 0.0


def test_compute_impact_matches_weight_and_count():
    # الزخم وزنه 30% ومفروض يبقى فيه 5 مؤشرات - أقصى تأثير لمؤشر واحد
    # = 100 * 0.30 / 5 = 6.0
    assert compute_impact(1, "momentum", 5) == 6.0
    assert compute_impact(-1, "momentum", 5) == -6.0


def test_compute_impact_handles_zero_indicators_safely():
    assert compute_impact(1, "momentum", 0) == 0.0


def test_interpret_indicator_missing_signal_shows_insufficient_data():
    result = interpret_indicator("test_indicator", 0, "trend", 4, signal_text="")
    assert result["interpretation"] == "بيانات غير كافية"
    assert result["status_icon"] == "⚪"


def test_interpret_indicator_status_icons():
    assert interpret_indicator("x", 1, "trend", 4)["status_icon"] == "🟢"
    assert interpret_indicator("x", -1, "trend", 4)["status_icon"] == "🔴"
    assert interpret_indicator("x", 0, "trend", 4)["status_icon"] == "⚪"


def test_enrich_category_votes_preserves_existing_fields():
    category_votes = {
        "trend": {
            "sma_cross": {"vote": 1, "signal": "صاعد"},
        }
    }
    enriched = enrich_category_votes(category_votes)
    info = enriched["trend"]["sma_cross"]
    # الحقول القديمة لازم تفضل موجودة (توافقية مع أي كود قديم بيقرأها)
    assert info["vote"] == 1
    assert info["signal"] == "صاعد"
    # والحقول الجديدة لازم تتضاف
    assert "status_icon" in info
    assert "impact" in info


def _make_df(n=250, direction="up"):
    close = pd.Series(np.linspace(100, 200, n) if direction == "up" else np.linspace(200, 100, n))
    high, low = close + 1, close - 1
    open_ = close.shift(1).fillna(close.iloc[0])
    vol = pd.Series(np.random.randint(1000, 5000, n))
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    return pd.DataFrame({"Open": open_.values, "High": high.values, "Low": low.values,
                          "Close": close.values, "Volume": vol.values}, index=idx)


@patch("app.analysis.scoring.fetch_history")
def test_sum_of_impacts_matches_overall_score(mock_fetch):
    """
    الخاصية الأهم: مجموع درجات تأثير كل المؤشرات النشطة لازم يساوي الـ Score
    النهائي تقريبًا (هامش تقريب صغير جدًا مقبول، أقل من 0.05).
    """
    np.random.seed(11)
    mock_fetch.return_value = _make_df(direction="up")
    result = scoring.analyze_stock("TEST")

    total_impact = sum(
        info["impact"] for cat in result["categories"].values() for info in cat.values()
    )
    assert abs(total_impact - result["score"]) < 0.05


@patch("app.analysis.scoring.fetch_history")
def test_every_indicator_has_signal_engine_fields(mock_fetch):
    """كل مؤشر في المخرجات النهائية لازم يكون معاه status_icon وimpact."""
    np.random.seed(12)
    mock_fetch.return_value = _make_df(direction="down")
    result = scoring.analyze_stock("TEST")

    for category, indicators in result["categories"].items():
        for name, info in indicators.items():
            assert "status_icon" in info, f"{category}.{name} ناقصه status_icon"
            assert "impact" in info, f"{category}.{name} ناقصه impact"
