# -*- coding: utf-8 -*-
"""صفحة الأخبار: آخر أخبار البورصة المصرية من RSS مباشر."""

import sys
import os
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import inject_rtl_style, api_get

inject_rtl_style(st)

st.title("📰 آخر أخبار البورصة المصرية")

col1, col2 = st.columns([3, 1])
with col1:
    limit = st.slider("عدد الأخبار", 5, 50, 20)
with col2:
    st.write("")
    st.write("")
    refresh = st.button("🔄 تحديث", use_container_width=True)

if refresh or "news_data" not in st.session_state:
    data, err = api_get("/news", params={"limit": limit})
    if err:
        st.error(err)
    else:
        st.session_state["news_data"] = data

if "news_data" in st.session_state:
    for item in st.session_state["news_data"]:
        with st.container(border=True):
            st.markdown(f"#### [{item['title']}]({item['link']})")
            st.caption(item.get("published", ""))
            if item.get("summary"):
                summary = item["summary"]
                st.write(summary[:300] + ("..." if len(summary) > 300 else ""))
else:
    st.info("اضغط 'تحديث' لعرض آخر الأخبار.")
