# -*- coding: utf-8 -*-
"""صفحة التوصيات: التحليل الكمي الاحترافي"""

import sys
import os
import streamlit as st

# التأكد من مسار الاستيراد الصحيح زي الملف القديم بالظبط
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import inject_rtl_style, api_get, render_recommendation_badge

def show_quant_recommendations():
    # تفعيل الثيم الاحترافي
    inject_rtl_style(st)
    
    st.title("🎯 التحليل الكمّي وإدارة الصفقات (Quant Engine)")
    st.markdown("نظام تحليل احترافي يعتمد على Price Action, Volume, Momentum وإدارة مخاطر صارمة.")

    # إدخال رمز السهم
    symbol = st.text_input("اكتب رمز السهم (مثال: COMI, ISPH, MASR):", "COMI").strip().upper()

    if st.button("إجراء تحليل كمّي دقيق 📊", use_container_width=True):
        if not symbol:
            st.warning("يرجى إدخال رمز السهم.")
            return

        with st.spinner(f"جاري فحص جودة البيانات وتشغيل محرك الاستراتيجيات لسهم {symbol}..."):
            # استدعاء الـ API الجديد
            data, error = api_get(f"/recommendations/quant-analysis/{symbol}")

            if error:
                st.error(error)
                return

            # 1. حالة الـ Data Quality Warning
            if "error_msg" in data:
                st.error("⚠️ فشل في التحقق من جودة البيانات!")
                st.warning(data["error_msg"])
                st.markdown(render_recommendation_badge("NO TRADE"), unsafe_allow_html=True)
                return

            # 2. عرض البطاقة الرئيسية (Header)
            st.markdown(f"## {data['symbol']} | السعر الحالي: **{data['current_price']}**")
            st.markdown(render_recommendation_badge(data['signal']), unsafe_allow_html=True)
            st.markdown(f"**Market Regime:** `{data.get('regime', 'UNKNOWN')}`")
            st.write("---")

            # 3. بطاقة التقييم (Scores)
            st.markdown('<div class="egx-card">', unsafe_allow_html=True)
            st.markdown("### 🧮 التقييم الفني (Scoring & Confidence)")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Score (جودة الإشارة)", f"{data['score']}/100")
            with col2:
                st.metric("Confidence (التوافق)", f"{data['confidence']}/100")
            with col3:
                st.metric("Historical Win Rate", data.get("historical_win_rate", "N/A"))
            st.markdown('</div>', unsafe_allow_html=True)

            # 4. بطاقة إدارة الصفقة (Trade Management)
            st.markdown('<div class="egx-card">', unsafe_allow_html=True)
            st.markdown("### 🎯 إعدادات الصفقة (Trade Setup)")
            
            # إذا كانت الإشارة NO TRADE، لا داعي لعرض أهداف وهمية
            if data['signal'] == "NO TRADE":
                st.info("لا توجد فرصة تداول واضحة حالياً بناءً على معايير النظام. يرجى الانتظار.")
            else:
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("Entry Zone (منطقة الدخول)", data['entry_zone'])
                with c2:
                    st.metric("Stop Loss (وقف الخسارة)", data['stop_loss'], "- خطر")
                with c3:
                    st.metric("Take Profit 1", data['tp1'], "+ هدف أول")
                with c4:
                    st.metric("Risk / Reward", f"1 : {data['risk_reward']}")
                
                st.markdown(f"**أهداف ممتدة:** TP2 = `{data['tp2']}` | TP3 = `{data['tp3']}`")
            st.markdown('</div>', unsafe_allow_html=True)

            # 5. التفاصيل (Reasons & Risks)
            st.markdown('<div class="egx-card">', unsafe_allow_html=True)
            col_reasons, col_risks = st.columns(2)
            
            with col_reasons:
                st.markdown("#### ✅ أسباب الدخول والإيجابيات")
                if data.get('reasons'):
                    for r in data['reasons']:
                        st.markdown(f"<span style='color: var(--egx-green);'>{r}</span>", unsafe_allow_html=True)
                else:
                    st.write("لا توجد إيجابيات قوية.")

            with col_risks:
                st.markdown("#### ⚠️ المخاطر والسلبيات")
                if data.get('risks'):
                    for r in data['risks']:
                        st.markdown(f"<span style='color: var(--egx-yellow);'>{r}</span>", unsafe_allow_html=True)
                else:
                    st.write("لا توجد مخاطر واضحة.")
            st.markdown('</div>', unsafe_allow_html=True)

# استدعاء الدالة
show_quant_recommendations()