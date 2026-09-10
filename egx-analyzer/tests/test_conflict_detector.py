# -*- coding: utf-8 -*-
"""اختبارات وحدة لكاشف تضارب المؤشرات (app/signals/conflict_detector.py)."""

from app.signals.conflict_detector import detect_conflict, MIN_ACTIVE_INDICATORS_FOR_CONFLICT


def test_equal_split_with_enough_indicators_is_conflicted():
    result = detect_conflict(5, 5)
    assert result["is_conflicted"] is True
    assert result["conflict_ratio"] == 1.0


def test_clear_majority_is_not_conflicted_even_with_many_indicators():
    result = detect_conflict(9, 1)
    assert result["is_conflicted"] is False


def test_close_split_with_too_few_indicators_is_not_conflicted():
    """سوق هادئ (عدد قليل جدًا من المؤشرات النشطة) - مش نفس حاجة التضارب الحقيقي."""
    result = detect_conflict(2, 2)
    assert result["is_conflicted"] is False


def test_boundary_ratio_exactly_at_threshold_is_conflicted():
    result = detect_conflict(5, 3)  # 3/5 = 0.6 بالظبط = العتبة
    assert result["is_conflicted"] is True


def test_just_below_threshold_is_not_conflicted():
    result = detect_conflict(6, 3)  # 3/6 = 0.5 < 0.6
    assert result["is_conflicted"] is False


def test_zero_indicators_is_not_conflicted():
    result = detect_conflict(0, 0)
    assert result["is_conflicted"] is False
    assert result["conflict_ratio"] == 0.0


def test_min_active_threshold_boundary():
    """بالظبط عند الحد الأدنى لعدد المؤشرات النشطة."""
    bullish, bearish = MIN_ACTIVE_INDICATORS_FOR_CONFLICT // 2, MIN_ACTIVE_INDICATORS_FOR_CONFLICT // 2
    result = detect_conflict(bullish, bearish)
    assert result["is_conflicted"] is True


def test_reason_mentions_both_counts_when_conflicted():
    result = detect_conflict(5, 5)
    assert "5" in result["reason"]
