# -*- coding: utf-8 -*-
"""Endpoints الخاصة بإعدادات التنبيهات وتشغيلها يدويًا."""

from fastapi import APIRouter, Body

from app.data.settings_store import get_settings, save_settings
from app.notifications.telegram import send_alert
from app.alerts.engine import check_watchlist_for_buy_alerts, check_open_positions_for_exit_alerts

router = APIRouter(tags=["الإعدادات والتنبيهات"])

_ALLOWED_SETTINGS_KEYS = {
    "alerts_enabled", "telegram_bot_token", "telegram_chat_id",
    "watchlist", "min_score_alert", "min_agreement_alert",
}


def _mask_token(settings: dict) -> dict:
    """يخفي التوكن جزئيًا في أي استجابة للمستخدم - آخر 4 خانات بس تظهر."""
    masked = dict(settings)
    token = masked.get("telegram_bot_token", "")
    if token:
        masked["telegram_bot_token"] = "•" * max(len(token) - 4, 0) + token[-4:]
    return masked


@router.get("/settings")
def read_settings():
    """يرجع الإعدادات الحالية (التوكن مخفي جزئيًا لأسباب أمان بسيطة)."""
    return _mask_token(get_settings())


@router.post("/settings")
def update_settings(payload: dict = Body(...)):
    """
    يحدّث الإعدادات - يقبل أي مجموعة فرعية من الحقول المسموحة فقط. لو عايز
    تسيب التوكن الحالي زي ما هو، متبعتش الحقل ده خالص في الطلب.
    """
    filtered = {k: v for k, v in payload.items() if k in _ALLOWED_SETTINGS_KEYS}
    updated = save_settings(filtered)
    return _mask_token(updated)


@router.post("/alerts/test")
def send_test_alert():
    """يبعت رسالة تجريبية للتأكد إن إعدادات تليجرام شغالة صح."""
    return send_alert("🔔 رسالة تجربة من EGX Analyzer - التنبيهات شغالة تمام!")


@router.post("/alerts/check-watchlist")
def run_watchlist_check():
    """يفحص قايمة المتابعة الشخصية ويبعت تنبيه شراء لأي سهم استوفى الشروط."""
    return check_watchlist_for_buy_alerts()


@router.post("/alerts/check-open-positions")
def run_open_positions_check():
    """يعيد تقييم كل التوصيات المفتوحة ضد السعر الحي ويبعت تنبيه لأي تغيير حالة."""
    return check_open_positions_for_exit_alerts()
