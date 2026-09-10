# -*- coding: utf-8 -*-
"""
إرسال تنبيهات عبر Telegram Bot API - الخيار الأسهل والمجاني للاستخدام
الشخصي. لا يرسل أي حاجة إلا لو المستخدم فعّل التنبيهات صراحة وأدخل بيانات
بوت حقيقية من الإعدادات.
"""

import logging

import requests

from app.data.settings_store import get_settings

log = logging.getLogger("telegram_notifier")

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
REQUEST_TIMEOUT_SECONDS = 10


def send_alert(message: str) -> dict:
    """
    يرسل رسالة تنبيه. يرجع {"sent": bool, "reason": str|None} - لا يرمي
    استثناء أبدًا، عشان فشل إرسال تنبيه واحد ميوقفش باقي المنصة.
    """
    settings = get_settings()

    if not settings.get("alerts_enabled"):
        return {"sent": False, "reason": "التنبيهات معطّلة من الإعدادات"}

    token = settings.get("telegram_bot_token")
    chat_id = settings.get("telegram_chat_id")
    if not token or not chat_id:
        return {"sent": False, "reason": "لم يتم إدخال بيانات بوت تليجرام (Token/Chat ID) في الإعدادات"}

    try:
        resp = requests.post(
            TELEGRAM_API_URL.format(token=token),
            json={"chat_id": chat_id, "text": message},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return {"sent": True, "reason": None}
    except requests.RequestException as e:
        log.warning("فشل إرسال تنبيه تليجرام: %s", e)
        return {"sent": False, "reason": f"فشل الإرسال - تأكد من صحة الـ Token والـ Chat ID: {e}"}
