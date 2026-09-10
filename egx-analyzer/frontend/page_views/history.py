# -*- coding: utf-8 -*-
"""صفحة سجل التوصيات: التوصيات المحفوظة، حالتها، وأداء النظام الفعلي."""

import sys
import os
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import inject_rtl_style, api_get, api_post
from formatters import format_currency, format_percent, format_ratio

inject_rtl_style(st)

st.title("📜 سجل التوصيات وأداء النظام")

# ------------------------------------------------------------ أداء النظام
st.markdown("### 📈 أداء النظام الفعلي")
perf, err = api_get("/recommendations/performance")
if err:
    st.error(err)
elif perf and perf.get("total_closed", 0) == 0:
    st.info(perf.get("note", "لا توجد توصيات مقفولة بعد."))
elif perf:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("نسبة النجاح (من الصفقات الحاسمة)", format_percent(perf["win_rate_percent"], show_sign=False))
    c2.metric("Profit Factor", perf.get("profit_factor") or "—")
    c3.metric("إجمالي العائد", format_percent(perf["total_return_percent"]))
    c4.metric("توصيات مفتوحة حاليًا", perf["total_open"])
    st.caption(
        f"من إجمالي {perf['total_closed']} توصية مقفولة: "
        f"{perf['winning']} رابحة، {perf['losing']} خاسرة، {perf['breakeven']} تعادل."
    )

st.divider()

# ------------------------------------------------------------ تحديث جماعي
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("🔄 حدّث كل التوصيات المفتوحة", use_container_width=True):
        with st.spinner("جاري جلب الأسعار الحالية وإعادة التقييم..."):
            result, err = api_post("/recommendations/refresh-all")
        if err:
            st.error(err)
        else:
            st.success(f"تم تحديث {result['updated_count']} توصية")
            st.rerun()

# ------------------------------------------------------------ السجل
st.markdown("### 📋 كل التوصيات")
status_filter = st.selectbox(
    "فلترة بالحالة",
    ["الكل", "OPEN", "TARGET1_HIT", "TARGET2_HIT", "CLOSED_PROFIT", "CLOSED_LOSS"],
)

params = {} if status_filter == "الكل" else {"status": status_filter}
history, err = api_get("/recommendations", params=params)

if err:
    st.error(err)
elif not history:
    st.info("مفيش توصيات محفوظة بالفلتر ده. احفظ توصية من صفحة 🎯 التوصيات الأول.")
else:
    STATUS_LABELS = {
        "OPEN": "🟡 مفتوحة", "TARGET1_HIT": "🟢 تحقق الهدف الأول",
        "TARGET2_HIT": "🟢 تحقق الهدف الثاني", "CLOSED_PROFIT": "✅ مقفولة بربح",
        "CLOSED_LOSS": "🔴 مقفولة بخسارة",
    }
    rows = [{
        "#": r["id"],
        "الرمز": r["symbol"],
        "التاريخ": r["created_at"][:16].replace("T", " "),
        "الحالة": STATUS_LABELS.get(r["status"], r["status"]),
        "الدخول": r["entry"],
        "الوقف": r["stop_loss"],
        "الهدف 1": r["target1"],
        "R:R": format_ratio(r.get("risk_reward_ratio")),
        "النتيجة": format_percent(r.get("result_percent")),
    } for r in history]
    df = pd.DataFrame(rows)
    styled = df.style.format({
        "الدخول": "{:,.2f}",
        "الوقف": "{:,.2f}",
        "الهدف 1": "{:,.2f}",
    }, na_rep="—")
    st.dataframe(styled, use_container_width=True, hide_index=True)

    with st.expander("تحديث توصية واحدة بالمعرف"):
        rec_id = st.number_input("رقم التوصية (#)", min_value=1, step=1)
        if st.button("تحديث هذه التوصية"):
            updated, err = api_post(f"/recommendations/{int(rec_id)}/refresh")
            if err:
                st.error(err)
            else:
                st.success(f"الحالة الحالية: {STATUS_LABELS.get(updated['status'], updated['status'])}")
                st.rerun()
