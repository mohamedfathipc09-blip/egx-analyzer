# -*- coding: utf-8 -*-
"""صفحة الإعدادات: تفعيل التنبيهات (اختياري)، بيانات بوت تليجرام، وقايمة المتابعة الشخصية."""

import sys
import os
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api_client import inject_rtl_style, api_get, api_post

inject_rtl_style(st)

st.title("⚙️ الإعدادات والتنبيهات")

st.info(
    "💡 التنبيهات ميزة **اختيارية ومعطّلة افتراضيًا**. مش هتشتغل إلا لو فعّلتها "
    "بنفسك من هنا وأدخلت بيانات بوت تليجرام حقيقية."
)

settings, err = api_get("/settings")
if err:
    st.error(err)
    st.stop()

with st.form("settings_form"):
    st.markdown("### 🔔 تفعيل التنبيهات")
    alerts_enabled = st.toggle("فعّل التنبيهات عبر تليجرام", value=settings.get("alerts_enabled", False))

    st.markdown("### 🤖 بيانات بوت تليجرام")
    st.caption(
        "اعمل بوت جديد عبر [@BotFather](https://t.me/BotFather) على تليجرام واحصل على الـ Token، "
        "وابعت أي رسالة للبوت واحصل على الـ Chat ID بتاعك عبر [@userinfobot](https://t.me/userinfobot)."
    )
    current_token_masked = settings.get("telegram_bot_token", "")
    new_token = st.text_input(
        "Bot Token (سيبه فاضي لو عايز تسيب القيمة الحالية زي ما هي)",
        value="", type="password",
        placeholder=current_token_masked if current_token_masked else "لسه معملتش بوت",
    )
    chat_id = st.text_input("Chat ID", value=settings.get("telegram_chat_id", ""))

    st.markdown("### 👁️ قايمة المتابعة الشخصية (Watchlist)")
    watchlist_text = st.text_area(
        "رموز الأسهم اللي عايز تتابعها للتنبيهات (مفصولة بفاصلة)",
        value=",".join(settings.get("watchlist", [])),
    )

    st.markdown("### 🎯 حدود التنبيه")
    col1, col2 = st.columns(2)
    with col1:
        min_score = st.slider("أقل درجة (Score) لإرسال تنبيه شراء", 0, 100,
                               int(settings.get("min_score_alert", 20)), step=5)
    with col2:
        min_agreement = st.slider("أقل نسبة توافق مؤشرات لإرسال التنبيه", 0, 100,
                                   int(settings.get("min_agreement_alert", 50)), step=5)

    submitted = st.form_submit_button("💾 احفظ الإعدادات", use_container_width=True)

if submitted:
    payload = {
        "alerts_enabled": alerts_enabled,
        "telegram_chat_id": chat_id,
        "watchlist": [s.strip().upper() for s in watchlist_text.split(",") if s.strip()],
        "min_score_alert": min_score,
        "min_agreement_alert": min_agreement,
    }
    if new_token:  # ميتبعتش التوكن إلا لو المستخدم كتب قيمة جديدة فعليًا
        payload["telegram_bot_token"] = new_token

    result, err = api_post("/settings", json_body=payload)
    if err:
        st.error(err)
    else:
        st.success("✅ اتحفظت الإعدادات")
        st.rerun()

st.divider()

st.markdown("### 🧪 اختبار وتشغيل يدوي")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("📨 ابعت رسالة تجربة", use_container_width=True):
        result, err = api_post("/alerts/test")
        if err:
            st.error(err)
        elif result["sent"]:
            st.success("✅ اتبعتت! افتح تليجرام وشوف")
        else:
            st.warning(result["reason"])

with col2:
    if st.button("🔍 افحص قايمة المتابعة دلوقتي", use_container_width=True):
        result, err = api_post("/alerts/check-watchlist")
        if err:
            st.error(err)
        else:
            st.info(f"تم فحص {result.get('checked', 0)} سهم - اتبعت {result.get('alerts_sent', 0)} تنبيه")

with col3:
    if st.button("📊 افحص الصفقات المفتوحة دلوقتي", use_container_width=True):
        result, err = api_post("/alerts/check-open-positions")
        if err:
            st.error(err)
        else:
            st.info(f"تم فحص {result.get('checked', 0)} صفقة - اتبعت {result.get('alerts_sent', 0)} تنبيه")

scheduler_status, _ = api_get("/scheduler/status")
if scheduler_status and scheduler_status.get("is_running"):
    st.success(
        f"🟢 الفحص التلقائي شغال في الخلفية - بيفحص كل "
        f"{scheduler_status['check_interval_minutes']} دقيقة من غير أي تدخل يدوي "
        "(طول ما التنبيهات مفعّلة والـ API شغال). الأزرار فوق للفحص الفوري بس لو عايز تتأكد دلوقتي."
    )
else:
    st.warning("⚪ تعذر التأكد من حالة الفحص التلقائي - جرب تتأكد إن الـ API شغال.")

st.caption(
    "ملحوظة: الفحص التلقائي بيشتغل طول ما الـ API (uvicorn) شغال على جهازك - "
    "لو قفلت السيرفر، الفحص التلقائي بيقف معاه."
)
