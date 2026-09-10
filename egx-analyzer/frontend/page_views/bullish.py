# -*- coding: utf-8 -*-
"""صفحة الفرص الصاعدة: فحص تلقائي للأسهم اللي استوفت شروط الصعود الفنية."""

import sys
import os
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import inject_rtl_style, api_get, DEFAULT_SYMBOLS, recommendation_badge_kind
from formatters import format_currency

inject_rtl_style(st)

st.title("🚀 أسهم استوفت شروط الصعود")
st.caption(
    "فحص تلقائي لكل سهم حسب نظام التصويت متعدد المؤشرات - بيعرض فقط الأسهم "
    "اللي حققت درجة ونسبة توافق أعلى من الحدود اللي تحددها تحت."
)

if "screener_symbols_text" not in st.session_state:
    st.session_state["screener_symbols_text"] = ",".join(DEFAULT_SYMBOLS)

col_load1, col_load2, col_load3 = st.columns(3)
with col_load1:
    if st.button("🛰️ رادار السوق كامل (~229 سهم)", use_container_width=True):
        with st.spinner("جاري جلب قائمة كل الأسهم المُدرجة..."):
            full_market, err = api_get("/symbols/full-market")
        if err:
            st.error(err)
        else:
            st.session_state["screener_symbols_text"] = ",".join(s["symbol"] for s in full_market["symbols"])
            st.caption(f"المصدر: {full_market['source']}")
            st.rerun()
with col_load2:
    if st.button("📋 حمّل القائمة الموسّعة (39 سهم)", use_container_width=True):
        all_symbols, err = api_get("/symbols")
        if err:
            st.error(err)
        else:
            st.session_state["screener_symbols_text"] = ",".join(s["symbol"] for s in all_symbols)
            st.rerun()
with col_load3:
    sectors, sect_err = api_get("/symbols/sectors")
    if not sect_err and sectors:
        chosen_sector = st.selectbox("...أو حمّل قطاع معين بس", ["-"] + sectors)
        if chosen_sector != "-":
            sector_symbols, err = api_get("/symbols", params={"sector": chosen_sector})
            if not err and sector_symbols:
                st.session_state["screener_symbols_text"] = ",".join(s["symbol"] for s in sector_symbols)

meta, _ = api_get("/symbols/metadata")
if meta:
    st.caption(f"ℹ️ القائمة المنسّقة يدويًا فيها {meta.get('total_symbols')} سهم (آخر مراجعة: {meta.get('last_reviewed')}) - {meta.get('note', '')}")

with st.form("screener_form"):
    symbols_input = st.text_area(
        "رموز الأسهم المراد فحصها (مفصولة بفاصلة)",
        value=st.session_state["screener_symbols_text"],
        height=70,
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        min_score = st.slider("أقل درجة (Score) مقبولة", 0, 100, 20, step=5)
    with col2:
        min_agreement = st.slider("أقل نسبة توافق مؤشرات", 0, 100, 50, step=5)
    with col3:
        timeframe = st.selectbox("الإطار الزمني", ["daily", "weekly"])
    submitted = st.form_submit_button("🔍 ابدأ الفحص", use_container_width=True)

if submitted:
    with st.spinner("جاري فحص الأسهم... قد يستغرق وقتًا حسب عدد الأسهم"):
        data, err = api_get("/screener/bullish", params={
            "symbols": symbols_input,
            "min_score": min_score,
            "min_agreement": min_agreement,
            "timeframe": timeframe,
        })
    if err:
        st.error(err)
    elif not data:
        st.warning("مفيش أي سهم استوفى الشروط دي حاليًا. جرب تقليل الحدود أو تغيير قايمة الأسهم.")
    else:
        st.success(f"✅ {len(data)} سهم استوفى شروط الصعود")

        def _plan_summary(r):
            plan = r.get("trade_plan", {})
            if plan.get("status") == "valid_long_setup":
                return (
                    f"دخول {format_currency(plan['entry'])} / "
                    f"وقف {format_currency(plan['stop_loss'])} / "
                    f"R:R 1:{plan['risk_reward_ratio']:.2f}"
                )
            return plan.get("status_label", "—")

        BADGE_EMOJI = {
            "strong-buy": "🟢🟢", "buy": "🟢", "hold": "🟡", "sell": "🔴", "strong-sell": "🔴🔴",
        }

        rows = [{
            "الرمز": r["symbol"],
            "السعر": r["last_close"],
            "التوصية": f"{BADGE_EMOJI.get(recommendation_badge_kind(r['recommendation']), '')} {r['recommendation']}",
            "الدرجة": r["score"],
            "نسبة التوافق": r["agreement_percent"],
            "مؤشرات صاعدة": r["indicators_bullish"],
            "مؤشرات هابطة": r["indicators_bearish"],
            "خطة التداول": _plan_summary(r),
        } for r in data]
        df = pd.DataFrame(rows)
        styled = df.style.format({
            "السعر": "{:,.2f}",
            "الدرجة": "{:+,.1f}",
            "نسبة التوافق": "{:,.1f}%",
        }, na_rep="—")
        st.dataframe(styled, use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("#### أنماط الشموع المكتشفة (إن وُجدت)")
        for r in data:
            if r.get("candlestick_patterns"):
                st.write(f"**{r['symbol']}**: " + "، ".join(r["candlestick_patterns"]))

        st.info(
            "💡 لتقرير تحليل كامل مع اختبار أداء تاريخي لأي سهم من دول، "
            "روح لصفحة **🎯 التوصيات** واكتب رمزه."
        )
        st.warning(data[0]["disclaimer"])
