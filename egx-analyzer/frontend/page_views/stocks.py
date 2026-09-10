# -*- coding: utf-8 -*-
"""صفحة الأسهم: عرض الأسعار اللحظية وبيانات كل سهم."""

import sys
import os
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import inject_rtl_style, api_get, DEFAULT_SYMBOLS

inject_rtl_style(st)

st.title("📊 أسعار الأسهم")

symbols_input = st.text_input(
    "رموز الأسهم (مفصولة بفاصلة)", value=",".join(DEFAULT_SYMBOLS), key="prices_symbols"
)

col1, col2 = st.columns([1, 4])
with col1:
    refresh = st.button("🔄 تحديث الأسعار", use_container_width=True)

if refresh or "prices_data" not in st.session_state:
    data, err = api_get("/prices", params={"symbols": symbols_input})
    if err:
        st.error(err)
    else:
        st.session_state["prices_data"] = data

if "prices_data" in st.session_state:
    rows, errors = [], []
    for d in st.session_state["prices_data"]:
        if d.get("error"):
            errors.append((d["symbol"], d["error"]))
        else:
            rows.append({
                "الرمز": d["symbol"],
                "الاسم": d.get("name") or "—",
                "السعر": d.get("last_price"),
                "التغيير": d.get("change"),
                "%التغيير": d.get("change_percent"),
                "الفتح": d.get("open"),
                "الإغلاق السابق": d.get("prev_close"),
                "أعلى": d.get("high"),
                "أدنى": d.get("low"),
                "الكمية": d.get("volume"),
            })

    if rows:
        df = pd.DataFrame(rows)

        def _highlight_change(val):
            if isinstance(val, (int, float)):
                if val > 0:
                    return "color: #2ecc71; font-weight: 700"
                elif val < 0:
                    return "color: #e74c3c; font-weight: 700"
            return ""

        # Styler.format بيتحكم في شكل الرقم المعروض (فواصل آلاف + خانتين
        # عشريتين ثابتتين) مع إبقاء القيمة نفسها رقمية عشان الفرز والألوان
        # يفضلوا شغالين صح - ده الفرق بين جدول احترافي وأرقام خام
        styled = (
            df.style
            .format({
                "السعر": "{:,.2f}",
                "التغيير": "{:+,.2f}",
                "%التغيير": "{:+,.2f}%",
                "الفتح": "{:,.2f}",
                "الإغلاق السابق": "{:,.2f}",
                "أعلى": "{:,.2f}",
                "أدنى": "{:,.2f}",
                "الكمية": "{:,.0f}",
            }, na_rep="—")
            .map(_highlight_change, subset=["التغيير", "%التغيير"])
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)
        st.caption(f"📡 بيانات مباشر - {len(rows)} سهم")

    if errors:
        with st.expander(f"⚠️ تعذر جلب بيانات {len(errors)} سهم"):
            for symbol, error in errors:
                st.caption(f"**{symbol}**: {error}")
else:
    st.info("اضغط 'تحديث الأسعار' لعرض البيانات.")
