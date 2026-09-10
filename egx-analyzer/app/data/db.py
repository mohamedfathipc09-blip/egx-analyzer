# -*- coding: utf-8 -*-
"""
سجل التوصيات وتتبع أدائها الفعلي - باستخدام SQLite (مكتبة قياسية، مفيش
اعتمادية جديدة). الفكرة: المستخدم يحفظ توصية بنفسه (مش تسجيل تلقائي لكل
تحليل)، والنظام بعد كده يتابعها ضد السعر الحي ويحدّث حالتها، وفي الآخر
نقدر نحسب أداء النظام الفعلي من نتائج حقيقية مسجّلة - مش توقعات.

حالات الصفقة (Status):
    OPEN → TARGET1_HIT → TARGET2_HIT → CLOSED_PROFIT (بعد الهدف الثالث)
    OPEN → CLOSED_LOSS (لو كسر وقف الخسارة قبل أي هدف)
    TARGET1_HIT/TARGET2_HIT → CLOSED_PROFIT (لو كسر الوقف المتحرك بعد تأمين ربح)
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path

from app.risk.position import suggest_trailing_stop

log = logging.getLogger("db")

DEFAULT_DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "egx_analyzer.db")

STATUS_TARGET_INDEX = {"OPEN": 0, "TARGET1_HIT": 1, "TARGET2_HIT": 2}
OPEN_STATUSES = tuple(STATUS_TARGET_INDEX.keys())


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """ينشئ الجدول لو مش موجود - آمن الاستدعاء أكتر من مرة."""
    conn = get_connection(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                created_at TEXT NOT NULL,
                recommendation TEXT,
                score REAL,
                entry REAL NOT NULL,
                stop_loss REAL NOT NULL,
                target1 REAL NOT NULL,
                target2 REAL,
                target3 REAL,
                risk_reward_ratio REAL,
                historical_win_rate REAL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                result_percent REAL,
                closed_at TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()


def save_recommendation(record: dict, db_path: str = DEFAULT_DB_PATH) -> int:
    """
    يحفظ توصية جديدة في السجل. المتوقع في record: symbol, recommendation,
    score, entry, stop_loss, target1, target2 (اختياري), target3 (اختياري),
    risk_reward_ratio, historical_win_rate (اختياري). يرجع الـ id بتاع
    السجل الجديد.
    """
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        cursor = conn.execute("""
            INSERT INTO recommendations
                (symbol, created_at, recommendation, score, entry, stop_loss,
                 target1, target2, target3, risk_reward_ratio, historical_win_rate, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
        """, (
            record["symbol"].upper(),
            datetime.now().isoformat(),
            record.get("recommendation"),
            record.get("score"),
            record["entry"],
            record["stop_loss"],
            record["target1"],
            record.get("target2"),
            record.get("target3"),
            record.get("risk_reward_ratio"),
            record.get("historical_win_rate"),
        ))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def list_recommendations(
    symbol: str = None, status: str = None, limit: int = 50, db_path: str = DEFAULT_DB_PATH
) -> list:
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        query = "SELECT * FROM recommendations WHERE 1=1"
        params = []
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol.upper())
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_recommendation(rec_id: int, db_path: str = DEFAULT_DB_PATH) -> dict:
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM recommendations WHERE id = ?", (rec_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _update_status(rec_id: int, new_status: str, result_percent: float, db_path: str) -> None:
    conn = get_connection(db_path)
    try:
        closed = new_status in ("CLOSED_PROFIT", "CLOSED_LOSS")
        conn.execute(
            "UPDATE recommendations SET status = ?, result_percent = ?, closed_at = ? WHERE id = ?",
            (new_status, result_percent, datetime.now().isoformat() if closed else None, rec_id),
        )
        conn.commit()
    finally:
        conn.close()


def refresh_recommendation(rec_id: int, current_price: float, db_path: str = DEFAULT_DB_PATH) -> dict:
    """
    يعيد تقييم توصية واحدة ضد السعر الحالي: هل تحقق هدف جديد؟ هل انكسر
    وقف الخسارة (العادي أو المتحرك بعد تأمين ربح)؟ يحدّث الحالة في القاعدة
    ويرجع السجل بعد التحديث (أو زي ما هو لو لسه OPEN بلا تغيير).
    """
    rec = get_recommendation(rec_id, db_path)
    if rec is None:
        raise ValueError(f"لا توجد توصية بالمعرف {rec_id}")

    if rec["status"] not in OPEN_STATUSES:
        return rec  # الصفقة مقفولة بالفعل - مفيش داعي لإعادة تقييم

    targets = [rec["target1"], rec["target2"], rec["target3"]]
    target_hit_count = STATUS_TARGET_INDEX[rec["status"]]
    effective_stop = suggest_trailing_stop(rec["entry"], target_hit_count, rec["stop_loss"], targets)

    entry = rec["entry"]

    if rec["target3"] and current_price >= rec["target3"]:
        result = (rec["target3"] - entry) / entry * 100
        _update_status(rec_id, "CLOSED_PROFIT", result, db_path)
    elif current_price <= effective_stop:
        result = (effective_stop - entry) / entry * 100
        new_status = "CLOSED_LOSS" if target_hit_count == 0 else "CLOSED_PROFIT"
        _update_status(rec_id, new_status, result, db_path)
    elif rec["target2"] and current_price >= rec["target2"] and target_hit_count < 2:
        _update_status(rec_id, "TARGET2_HIT", None, db_path)
    elif current_price >= rec["target1"] and target_hit_count < 1:
        _update_status(rec_id, "TARGET1_HIT", None, db_path)
    else:
        return rec  # مفيش تغيير

    return get_recommendation(rec_id, db_path)


def compute_performance_summary(db_path: str = DEFAULT_DB_PATH) -> dict:
    """
    يحسب أداء النظام من التوصيات المقفولة فعليًا بس (مش المفتوحة) - أرقام
    حقيقية مسجّلة، مش توقعات. لو مفيش توصيات مقفولة كفاية، بيوضح ده صراحة.
    """
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        closed = conn.execute(
            "SELECT * FROM recommendations WHERE status IN ('CLOSED_PROFIT', 'CLOSED_LOSS')"
        ).fetchall()
        total_open = conn.execute(
            f"SELECT COUNT(*) as c FROM recommendations WHERE status IN {OPEN_STATUSES}"
        ).fetchone()["c"]
    finally:
        conn.close()

    closed = [dict(r) for r in closed]
    if not closed:
        return {
            "total_closed": 0,
            "total_open": total_open,
            "note": "لا توجد توصيات مقفولة بعد لحساب أداء فعلي - احفظ توصيات وتابعها أولًا.",
        }

    results = [r["result_percent"] for r in closed if r["result_percent"] is not None]
    wins = [r for r in results if r > 0]
    losses = [r for r in results if r < 0]
    breakeven = [r for r in results if r == 0]
    gross_profit = sum(wins)
    gross_loss = -sum(losses)
    decisive_trades = len(wins) + len(losses)  # مستبعد منها صفقات التعادل عمدًا

    return {
        "total_closed": len(closed),
        "total_open": total_open,
        "winning": len(wins),
        "losing": len(losses),
        "breakeven": len(breakeven),
        # نسبة النجاح بتُحسب من الصفقات الحاسمة (ربح/خسارة) بس - صفقة
        # اتقفلت عند نقطة التعادل بالظبط مش "خسارة" ومينفعش تقلل النسبة
        "win_rate_percent": round(len(wins) / decisive_trades * 100, 1) if decisive_trades else None,
        "average_return_percent": round(sum(results) / len(results), 2) if results else None,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else None,
        "total_return_percent": round(sum(results), 2) if results else None,
    }
