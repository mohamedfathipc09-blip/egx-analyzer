# -*- coding: utf-8 -*-
"""
دوال تنسيق موحّدة للأرقام والنصوص - تُستخدم في كل صفحات الواجهة عشان
الأرقام تظهر بشكل احترافي متسق (فواصل آلاف، عدد خانات عشرية ثابت، إشارة
واضحة للنسب المئوية) بدل أرقام خام زي 116.28999999999999.
"""


def format_price(value, decimals: int = 2) -> str:
    """116.29 -> '116.29' | None -> '—'"""
    if value is None:
        return "—"
    try:
        return f"{float(value):,.{decimals}f}"
    except (ValueError, TypeError):
        return "—"


def format_currency(value, decimals: int = 2) -> str:
    """116.29 -> '116.29 ج.م'"""
    formatted = format_price(value, decimals)
    return f"{formatted} ج.م" if formatted != "—" else "—"


def format_percent(value, decimals: int = 1, show_sign: bool = True) -> str:
    """5.2 -> '+5.20%' | -3.1 -> '-3.10%' | None -> '—'"""
    if value is None:
        return "—"
    try:
        value = float(value)
    except (ValueError, TypeError):
        return "—"
    sign = "+" if (show_sign and value > 0) else ""
    return f"{sign}{value:,.{decimals}f}%"


def format_large_number(value) -> str:
    """1_500_000 -> '1.50 مليون' | 2_300 -> '2.3 ألف' | None -> '—'"""
    if value is None:
        return "—"
    try:
        value = float(value)
    except (ValueError, TypeError):
        return "—"
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        return f"{value / 1_000_000_000:,.2f} مليار"
    if abs_value >= 1_000_000:
        return f"{value / 1_000_000:,.2f} مليون"
    if abs_value >= 1_000:
        return f"{value / 1_000:,.1f} ألف"
    return f"{value:,.0f}"


def format_ratio(value, decimals: int = 2) -> str:
    """يستخدم لعرض R:R - بيرجع 1:X.XX جاهزة"""
    if value is None:
        return "—"
    try:
        return f"1:{float(value):,.{decimals}f}"
    except (ValueError, TypeError):
        return "—"


def color_for_value(value) -> str:
    """يرجع اسم لون CSS مناسب لرقم موجب/سالب/صفر - يُستخدم مع render_colored_number."""
    if value is None:
        return "var(--egx-muted)"
    try:
        value = float(value)
    except (ValueError, TypeError):
        return "var(--egx-muted)"
    if value > 0:
        return "var(--egx-green)"
    if value < 0:
        return "var(--egx-red)"
    return "var(--egx-muted)"


def render_colored_number(value, formatted_text: str) -> str:
    """يرجع HTML لرقم ملوّن (أخضر للموجب، أحمر للسالب) - استخدمه مع st.markdown(..., unsafe_allow_html=True)."""
    color = color_for_value(value)
    return f'<span style="color:{color}; font-weight:700;">{formatted_text}</span>'
