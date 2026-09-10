# -*- coding: utf-8 -*-
"""
نقطة الدخول الرئيسية للتطبيق. بتستخدم st.navigation عشان تحدد اسم كل صفحة
صراحة في الكود، بدل ما نسيب Streamlit يستنتجه من اسم الملف - لأن الاستنتاج
التلقائي بيتلخبط لما اسم الملف فيه إيموجي + نص عربي مع بعض.

التشغيل:
    streamlit run frontend/app.py
"""

import streamlit as st

st.set_page_config(page_title="EGX Analyzer", page_icon="📈", layout="wide")

pages = [
    st.Page("page_views/home.py", title="الرئيسية", icon="🏠", default=True),
    st.Page("page_views/stocks.py", title="الأسهم", icon="📊"),
    st.Page("page_views/bullish.py", title="فرص صاعدة", icon="🚀"),
    st.Page("page_views/news.py", title="الأخبار", icon="📰"),
    st.Page("page_views/recommendations.py", title="التوصيات", icon="🎯"),
    st.Page("page_views/history.py", title="سجل التوصيات", icon="📜"),
    st.Page("page_views/settings.py", title="الإعدادات", icon="⚙️"),
]

pg = st.navigation(pages)
pg.run()
