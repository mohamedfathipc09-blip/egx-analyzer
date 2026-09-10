# -*- coding: utf-8 -*-
"""
Alert Engine: يقرر امتى نبعت تنبيه، بمعزل عن كيفية الإرسال نفسه (ده شغل
app/notifications/telegram.py). نوعين من التنبيهات:

1. Buy Setup: سهم في قايمة المتابعة (Watchlist) وصل لخطة تداول صالحة
   ومتحققش فيه شروط كافية (Score + توافق مؤشرات)، ومفيش توصية مفتوحة
   بالفعل عليه (عشان منبعتش تنبيه متكرر لنفس الفرصة كل ما نفحص).
2. Exit Alerts: توصية محفوظة اتغيرت حالتها (تحقق هدف / انكسر وقف) بعد
   إعادة التقييم ضد السعر الحي.
"""

import logging

from app.data.settings_store import get_settings
from app.data.db import list_recommendations, refresh_recommendation, OPEN_STATUSES
from app.data.mubasher_client import get_stock_data
from app.analysis.scoring import analyze_stock
from app.notifications.telegram import send_alert

log = logging.getLogger("alert_engine")

STATUS_ALERT_TEMPLATES = {
    "TARGET1_HIT": "🎯 {symbol}: تحقق الهدف الأول (السعر الحالي {price})",
    "TARGET2_HIT": "🎯 {symbol}: تحقق الهدف الثاني (السعر الحالي {price})",
    "CLOSED_PROFIT": "✅ {symbol}: الصفقة اتقفلت بربح {result}%",
    "CLOSED_LOSS": "🔴 {symbol}: تم كسر وقف الخسارة - الصفقة اتقفلت بخسارة {result}%",
}


def _is_symbol_already_tracked(symbol: str) -> bool:
    """هل السهم ده عليه توصية مفتوحة بالفعل في السجل؟"""
    for status in OPEN_STATUSES:
        if list_recommendations(symbol=symbol, status=status, limit=1):
            return True
    return False


def format_buy_setup_alert(symbol: str, analysis: dict, plan: dict) -> str:
    targets_text = " / ".join(str(t) for t in plan["targets"])
    return (
        f"🟢 فرصة شراء محتملة: {symbol}\n"
        f"السعر الحالي: {analysis['last_close']}\n"
        f"Score: {analysis['score']} | نسبة توافق المؤشرات: {analysis['agreement_percent']}%\n"
        f"الدخول: {plan['entry']} | الوقف: {plan['stop_loss']}\n"
        f"الأهداف: {targets_text}\n"
        f"R:R: 1:{plan['risk_reward_ratio']}\n\n"
        f"⚠️ إشارة فنية مبنية على مؤشرات تاريخية - ليست ضمانًا للربح."
    )


def check_watchlist_for_buy_alerts() -> dict:
    """
    يفحص قايمة المتابعة الشخصية ويبعت تنبيه شراء لأي سهم استوفى الشروط
    ومفيش عليه توصية متابَعة بالفعل.
    """
    settings = get_settings()
    if not settings.get("alerts_enabled"):
        return {"checked": 0, "alerts_sent": 0, "note": "التنبيهات معطّلة من الإعدادات"}

    watchlist = settings.get("watchlist", [])
    min_score = settings.get("min_score_alert", 20.0)
    min_agreement = settings.get("min_agreement_alert", 50.0)

    sent = 0
    for symbol in watchlist:
        if _is_symbol_already_tracked(symbol):
            continue
        try:
            analysis = analyze_stock(symbol)
        except Exception as e:
            log.warning("تعذر تحليل %s أثناء فحص التنبيهات: %s", symbol, e)
            continue

        plan = analysis.get("trade_plan", {})
        meets_conditions = (
            plan.get("status") == "valid_long_setup"
            and analysis["score"] >= min_score
            and analysis["agreement_percent"] >= min_agreement
        )
        if meets_conditions:
            message = format_buy_setup_alert(symbol, analysis, plan)
            result = send_alert(message)
            if result["sent"]:
                sent += 1

    return {"checked": len(watchlist), "alerts_sent": sent}


def check_open_positions_for_exit_alerts() -> dict:
    """
    يعيد تقييم كل التوصيات المفتوحة ضد السعر الحي، ويبعت تنبيه لأي توصية
    اتغيرت حالتها (تحقق هدف / انكسر وقف / اتقفلت).
    """
    settings = get_settings()
    if not settings.get("alerts_enabled"):
        return {"checked": 0, "alerts_sent": 0, "note": "التنبيهات معطّلة من الإعدادات"}

    checked, sent = 0, 0
    for status in OPEN_STATUSES:
        for rec in list_recommendations(status=status, limit=200):
            checked += 1
            price_data = get_stock_data(rec["symbol"], delay=0)
            current_price = price_data.get("last_price")
            if current_price is None:
                continue

            old_status = rec["status"]
            updated = refresh_recommendation(rec["id"], current_price)
            if updated["status"] != old_status and updated["status"] in STATUS_ALERT_TEMPLATES:
                message = STATUS_ALERT_TEMPLATES[updated["status"]].format(
                    symbol=rec["symbol"], price=current_price,
                    result=updated.get("result_percent"),
                )
                result = send_alert(message)
                if result["sent"]:
                    sent += 1

    return {"checked": checked, "alerts_sent": sent}
