# -*- coding: utf-8 -*-
"""اختبارات وحدة لسجل التوصيات (app/data/db.py) - بيستخدم قاعدة بيانات مؤقتة لكل اختبار."""

import os
import tempfile

import pytest

from app.data.db import (
    init_db, save_recommendation, get_recommendation, list_recommendations,
    refresh_recommendation, compute_performance_summary,
)


@pytest.fixture
def temp_db():
    path = tempfile.mktemp(suffix=".db")
    init_db(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


def _sample_recommendation(**overrides):
    base = {
        "symbol": "COMI", "recommendation": "شراء (Buy)", "score": 35.0,
        "entry": 100.0, "stop_loss": 90.0, "target1": 115.0, "target2": 125.0,
        "target3": 135.0, "risk_reward_ratio": 1.5,
    }
    base.update(overrides)
    return base


def test_save_and_retrieve_recommendation(temp_db):
    rec_id = save_recommendation(_sample_recommendation(), db_path=temp_db)
    rec = get_recommendation(rec_id, db_path=temp_db)
    assert rec["symbol"] == "COMI"
    assert rec["status"] == "OPEN"
    assert rec["entry"] == 100.0


def test_refresh_no_change_while_price_between_entry_and_target(temp_db):
    rec_id = save_recommendation(_sample_recommendation(), db_path=temp_db)
    updated = refresh_recommendation(rec_id, current_price=105.0, db_path=temp_db)
    assert updated["status"] == "OPEN"


def test_refresh_hits_target1(temp_db):
    rec_id = save_recommendation(_sample_recommendation(), db_path=temp_db)
    updated = refresh_recommendation(rec_id, current_price=116.0, db_path=temp_db)
    assert updated["status"] == "TARGET1_HIT"


def test_refresh_closes_at_breakeven_after_target1(temp_db):
    """
    اختبار انحدار (regression) لباگ حقيقي: بعد تحقق الهدف الأول، الوقف
    المتحرك بيتحرك لنقطة الدخول. لو السهم رجع لنقطة الدخول بالظبط، الصفقة
    تُقفل عند تعادل (0%) - مش خسارة.
    """
    rec_id = save_recommendation(_sample_recommendation(), db_path=temp_db)
    refresh_recommendation(rec_id, current_price=116.0, db_path=temp_db)  # target1
    updated = refresh_recommendation(rec_id, current_price=99.0, db_path=temp_db)  # ارتداد لتحت الدخول
    assert updated["status"] == "CLOSED_PROFIT"
    assert updated["result_percent"] == 0.0


def test_refresh_closes_at_loss_without_hitting_any_target(temp_db):
    rec_id = save_recommendation(_sample_recommendation(), db_path=temp_db)
    updated = refresh_recommendation(rec_id, current_price=89.0, db_path=temp_db)
    assert updated["status"] == "CLOSED_LOSS"
    assert updated["result_percent"] < 0


def test_refresh_already_closed_recommendation_is_noop(temp_db):
    rec_id = save_recommendation(_sample_recommendation(), db_path=temp_db)
    refresh_recommendation(rec_id, current_price=89.0, db_path=temp_db)  # يقفل بخسارة
    unchanged = refresh_recommendation(rec_id, current_price=200.0, db_path=temp_db)
    assert unchanged["status"] == "CLOSED_LOSS"  # ما اتغيرش رغم سعر خيالي عالي


def test_performance_summary_separates_breakeven_from_loss(temp_db):
    """
    اختبار انحدار: صفقة التعادل (نتيجة 0%) لازم تتحسب في breakeven، مش في
    losing - وإلا نسبة النجاح المعروضة هتبقى أقل من الواقع ظلمًا للنظام.
    """
    rec1 = save_recommendation(_sample_recommendation(symbol="COMI"), db_path=temp_db)
    refresh_recommendation(rec1, current_price=116.0, db_path=temp_db)
    refresh_recommendation(rec1, current_price=99.0, db_path=temp_db)  # breakeven

    rec2 = save_recommendation(_sample_recommendation(symbol="ETEL", entry=50, stop_loss=45,
                                                       target1=60, target2=65, target3=70), db_path=temp_db)
    refresh_recommendation(rec2, current_price=44.0, db_path=temp_db)  # خسارة فعلية

    perf = compute_performance_summary(db_path=temp_db)
    assert perf["breakeven"] == 1
    assert perf["losing"] == 1
    assert perf["winning"] == 0
    # نسبة النجاح من الصفقات الحاسمة بس (0 ربح من صفقة حاسمة واحدة) = 0%
    assert perf["win_rate_percent"] == 0.0


def test_performance_summary_with_no_closed_trades(temp_db):
    save_recommendation(_sample_recommendation(), db_path=temp_db)  # لسه OPEN
    perf = compute_performance_summary(db_path=temp_db)
    assert perf["total_closed"] == 0
    assert "note" in perf


def test_list_recommendations_filters_by_status(temp_db):
    save_recommendation(_sample_recommendation(symbol="COMI"), db_path=temp_db)
    rec2 = save_recommendation(_sample_recommendation(symbol="ETEL"), db_path=temp_db)
    refresh_recommendation(rec2, current_price=44.0, db_path=temp_db)  # يقفل بخسارة

    open_only = list_recommendations(status="OPEN", db_path=temp_db)
    closed_only = list_recommendations(status="CLOSED_LOSS", db_path=temp_db)
    assert len(open_only) == 1 and open_only[0]["symbol"] == "COMI"
    assert len(closed_only) == 1 and closed_only[0]["symbol"] == "ETEL"
