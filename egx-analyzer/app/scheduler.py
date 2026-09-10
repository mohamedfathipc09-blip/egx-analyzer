# -*- coding: utf-8 -*-
"""
جدولة تلقائية لفحص التنبيهات (Watchlist + الصفقات المفتوحة) بدون أي تدخل
يدوي - بتشتغل تلقائيًا طول ما الـ API شغال، وبتُبدأ مع تشغيل التطبيق
نفسه (app/api/main.py).

مهم: الجدولة نفسها بتشتغل دايمًا في الخلفية، لكن الفحص الفعلي جوه كل
job بيتأكد بنفسه (عبر get_settings() داخل alerts/engine.py) إن التنبيهات
مفعّلة قبل ما يبعت أي رسالة فعلية - فمفيش أي إرسال تلقائي بدون تفعيل
صريح من المستخدم، حتى لو الجدولة نفسها شغالة.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.alerts.engine import check_watchlist_for_buy_alerts, check_open_positions_for_exit_alerts

log = logging.getLogger("scheduler")

CHECK_INTERVAL_MINUTES = 15

_scheduler = None  # نسخة واحدة بس طول عمر العملية - آمن الاستدعاء المتكرر


def _run_watchlist_check():
    try:
        result = check_watchlist_for_buy_alerts()
        if result.get("alerts_sent"):
            log.info("تنبيهات شراء تلقائية اتبعتت: %s", result)
    except Exception as e:
        # فشل فحص واحد ميوقفش الجدولة نفسها - هيحاول تاني في الدورة الجاية
        log.warning("فشل فحص watchlist المجدول: %s", e)


def _run_open_positions_check():
    try:
        result = check_open_positions_for_exit_alerts()
        if result.get("alerts_sent"):
            log.info("تنبيهات صفقات مفتوحة تلقائية اتبعتت: %s", result)
    except Exception as e:
        log.warning("فشل فحص الصفقات المفتوحة المجدول: %s", e)


def start_scheduler():
    """يبدأ الجدولة مرة واحدة فقط - نداء تاني بيرجع نفس الـ instance من غير ما يكرر الـ jobs."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _run_watchlist_check, "interval",
        minutes=CHECK_INTERVAL_MINUTES, id="watchlist_check", replace_existing=True,
    )
    _scheduler.add_job(
        _run_open_positions_check, "interval",
        minutes=CHECK_INTERVAL_MINUTES, id="open_positions_check", replace_existing=True,
    )
    _scheduler.start()
    log.info("بدأت الجدولة التلقائية للتنبيهات - فحص كل %d دقيقة", CHECK_INTERVAL_MINUTES)
    return _scheduler


def stop_scheduler():
    """يوقف الجدولة - يُستخدم عند إغلاق التطبيق بشكل نظيف."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("تم إيقاف الجدولة التلقائية")


def is_running() -> bool:
    return _scheduler is not None
