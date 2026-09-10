# -*- coding: utf-8 -*-
"""اختبارات وحدة للجدولة التلقائية للتنبيهات (app/scheduler.py)."""

from unittest.mock import patch

import app.scheduler as sched


def teardown_function(_):
    """نتأكد إن كل اختبار بيبدأ من حالة نظيفة (مفيش scheduler من اختبار سابق)."""
    sched.stop_scheduler()


def test_start_scheduler_registers_both_jobs():
    scheduler = sched.start_scheduler()
    assert scheduler.running is True
    assert "watchlist_check" in scheduler.jobs
    assert "open_positions_check" in scheduler.jobs


def test_start_scheduler_uses_configured_interval():
    scheduler = sched.start_scheduler()
    assert scheduler.jobs["watchlist_check"]["minutes"] == sched.CHECK_INTERVAL_MINUTES
    assert scheduler.jobs["open_positions_check"]["minutes"] == sched.CHECK_INTERVAL_MINUTES


def test_start_scheduler_is_idempotent():
    """نداء start_scheduler أكتر من مرة لازم يرجع نفس الـ instance، مش يكرر الـ jobs."""
    first = sched.start_scheduler()
    second = sched.start_scheduler()
    assert first is second


def test_stop_scheduler_marks_not_running():
    sched.start_scheduler()
    sched.stop_scheduler()
    assert sched.is_running() is False


def test_is_running_reflects_actual_state():
    assert sched.is_running() is False
    sched.start_scheduler()
    assert sched.is_running() is True


def test_watchlist_check_failure_does_not_propagate():
    """فشل فحص واحد لازم يتلقط جوه الدالة نفسها - الجدولة تفضل شغالة للدورة الجاية."""
    with patch("app.scheduler.check_watchlist_for_buy_alerts") as m:
        m.side_effect = Exception("فشل مؤقت")
        sched._run_watchlist_check()  # ميرميش استثناء للخارج


def test_open_positions_check_failure_does_not_propagate():
    with patch("app.scheduler.check_open_positions_for_exit_alerts") as m:
        m.side_effect = Exception("فشل مؤقت")
        sched._run_open_positions_check()
