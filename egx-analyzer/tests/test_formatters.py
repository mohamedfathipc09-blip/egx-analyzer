# -*- coding: utf-8 -*-
"""اختبارات وحدة لدوال التنسيق والبادجات في الواجهة (frontend/formatters.py, frontend/api_client.py)."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend"))

from formatters import (
    format_price, format_percent, format_currency, format_large_number, format_ratio,
)
from api_client import recommendation_badge_kind, render_badge, render_recommendation_badge


# ------------------------------------------------------------------ formatters

def test_format_price_rounds_and_handles_none():
    assert format_price(116.28999999) == "116.29"
    assert format_price(None) == "—"


def test_format_price_adds_thousands_separator():
    assert format_price(1004828) == "1,004,828.00"


def test_format_percent_default_sign_and_decimals():
    assert format_percent(5.2) == "+5.2%"
    assert format_percent(-3.1) == "-3.1%"
    assert format_percent(0) == "0.0%"


def test_format_percent_custom_decimals():
    assert format_percent(5.234, decimals=2) == "+5.23%"


def test_format_percent_without_sign():
    assert format_percent(5.2, show_sign=False) == "5.2%"


def test_format_percent_none_returns_dash():
    assert format_percent(None) == "—"


def test_format_currency_appends_egp_suffix():
    assert format_currency(116.29) == "116.29 ج.م"
    assert format_currency(None) == "—"


def test_format_large_number_scales_correctly():
    assert format_large_number(1_500_000) == "1.50 مليون"
    assert format_large_number(2_300) == "2.3 ألف"
    assert format_large_number(3_200_000_000) == "3.20 مليار"
    assert format_large_number(500) == "500"
    assert format_large_number(None) == "—"


def test_format_ratio():
    assert format_ratio(1.567) == "1:1.57"
    assert format_ratio(None) == "—"


def test_formatters_never_raise_on_bad_input():
    """أي دالة تنسيق لازم ترجع '—' بدل ما ترمي استثناء لو استقبلت قيمة غير رقمية."""
    for fn in (format_price, format_percent, format_currency, format_large_number, format_ratio):
        assert fn("not a number") == "—"


# ------------------------------------------------------------------ badges

def test_recommendation_badge_kind_all_cases():
    assert recommendation_badge_kind("شراء قوي (Strong Buy)") == "strong-buy"
    assert recommendation_badge_kind("شراء (Buy)") == "buy"
    assert recommendation_badge_kind("محايد / انتظار (Hold)") == "hold"
    assert recommendation_badge_kind("بيع (Sell)") == "sell"
    assert recommendation_badge_kind("بيع قوي (Strong Sell)") == "strong-sell"


def test_recommendation_badge_kind_handles_empty_and_none():
    assert recommendation_badge_kind("") == "neutral"
    assert recommendation_badge_kind(None) == "neutral"


def test_render_badge_produces_expected_html_class():
    html = render_badge("شراء", "buy")
    assert 'class="egx-badge egx-badge-buy"' in html
    assert "شراء" in html


def test_render_recommendation_badge_shortcut():
    html = render_recommendation_badge("شراء قوي (Strong Buy)")
    assert 'egx-badge-strong-buy' in html
